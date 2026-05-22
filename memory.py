"""Memory service — typed read/write/persist backed by state/memory.json."""
from __future__ import annotations

import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from schemas import MemoryItem, ToolCall

sys.path.insert(0, str(Path(__file__).resolve().parent / "llm_gatewayV3"))
from client import LLM  # type: ignore[import]  # noqa: E402

_STATE_FILE = Path(__file__).resolve().parent / "state" / "memory.json"

_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "it", "its", "this", "that",
    "these", "those", "i", "you", "he", "she", "we", "they", "me", "him",
    "her", "us", "them",
})


class Memory:
    def __init__(self) -> None:
        self._items: list[MemoryItem] | None = None
        self._llm = LLM()

    # ── persistence ───────────────────────────────────────────────────────────

    def _load(self) -> None:
        if self._items is not None:
            return
        if _STATE_FILE.exists():
            raw = json.loads(_STATE_FILE.read_text())
            self._items = [MemoryItem.model_validate(r) for r in raw]
        else:
            self._items = []

    def _save(self) -> None:
        _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _STATE_FILE.write_text(
            json.dumps(
                [m.model_dump(mode="json") for m in self._items],
                indent=2,
                default=str,
            )
        )

    # ── helpers ───────────────────────────────────────────────────────────────

    def _tokenize(self, text: str) -> set[str]:
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        return {t for t in tokens if t not in _STOPWORDS and len(t) > 1}

    def _score(self, item: MemoryItem, query_tokens: set[str]) -> int:
        item_tokens = set(item.keywords) | self._tokenize(item.descriptor)
        return len(query_tokens & item_tokens)

    # ── public API ────────────────────────────────────────────────────────────

    def read(
        self,
        query: str,
        history: list[dict],
        kinds: Optional[list[str]] = None,
        top_k: int = 8,
    ) -> list[MemoryItem]:
        """Keyword-overlap retrieval — pure Python, no LLM."""
        self._load()
        query_tokens = self._tokenize(query)
        for msg in history[-4:]:
            content = msg.get("content", "")
            if isinstance(content, str):
                query_tokens |= self._tokenize(content)

        candidates = self._items if not kinds else [m for m in self._items if m.kind in kinds]
        scored = sorted(candidates, key=lambda m: self._score(m, query_tokens), reverse=True)
        return scored[:top_k]

    def filter(
        self,
        kinds: Optional[list[str]] = None,
        goal_id: Optional[str] = None,
        recent: Optional[int] = None,
    ) -> list[MemoryItem]:
        """Structured filter — no scoring, no LLM."""
        self._load()
        items: list[MemoryItem] = self._items
        if kinds:
            items = [m for m in items if m.kind in kinds]
        if goal_id is not None:
            items = [m for m in items if m.goal_id == goal_id]
        items = sorted(items, key=lambda m: m.created_at, reverse=True)
        if recent is not None:
            items = items[:recent]
        return items

    def relevant(
        self,
        query: str,
        kinds: Optional[list[str]] = None,
        top_k: int = 5,
    ) -> list[MemoryItem]:
        """LLM-scored relevance via gateway with auto_route='memory'."""
        self._load()
        candidates = self._items if not kinds else [m for m in self._items if m.kind in kinds]
        if not candidates:
            return []

        index_lines = "\n".join(
            f"- {m.id}: {m.descriptor} [{', '.join(m.keywords[:5])}]"
            for m in candidates
        )
        prompt = (
            f"Query: {query}\n\n"
            f"Memory items (id: descriptor [keywords]):\n{index_lines}\n\n"
            f"Return a JSON array of the {top_k} most relevant item IDs, "
            f"most relevant first. Output only the JSON array, nothing else."
        )
        resp = self._llm.chat(prompt, auto_route="memory", temperature=0.0, max_tokens=256)
        text = resp.get("text", "").strip()

        try:
            m = re.search(r"\[.*?\]", text, re.DOTALL)
            ids: list[str] = json.loads(m.group()) if m else []
        except Exception:
            ids = []

        id_map = {item.id: item for item in candidates}
        ordered = [id_map[i] for i in ids if i in id_map]
        seen = set(i for i in ids if i in id_map)
        for item in candidates:
            if len(ordered) >= top_k:
                break
            if item.id not in seen:
                ordered.append(item)
                seen.add(item.id)
        return ordered[:top_k]

    def remember(
        self,
        raw_text: str,
        source: str,
        run_id: str,
        goal_id: Optional[str] = None,
    ) -> MemoryItem:
        """Classify raw_text into a MemoryItem via LLM (pinned Gemini)."""
        self._load()
        prompt = (
            "Classify the following text into a structured memory item.\n\n"
            f"Text: {raw_text}\n\n"
            "Return a JSON object with exactly these fields:\n"
            '  "kind": one of "fact", "preference", "tool_outcome", "scratchpad"\n'
            '  "keywords": list of 3-8 lowercase single-word keywords\n'
            '  "descriptor": one short human-readable sentence (≤15 words)\n'
            '  "value": a dict with 1-3 relevant key-value pairs extracted from the text\n'
            '  "confidence": float between 0.0 and 1.0\n\n'
            "Output only the JSON object, nothing else."
        )
        resp = self._llm.chat(
            prompt,
            provider="gemini",
            temperature=0.2,
            max_tokens=512,
            response_format={"type": "json_object"},
        )
        parsed: dict = resp.get("parsed") or {}
        if not parsed:
            raw = resp.get("text", "")
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if m:
                try:
                    parsed = json.loads(m.group())
                except Exception:
                    parsed = {}

        item = MemoryItem(
            id=str(uuid.uuid4()),
            kind=parsed.get("kind", "scratchpad"),
            keywords=[k.lower() for k in parsed.get("keywords", [])[:8]],
            descriptor=parsed.get("descriptor", raw_text[:80]),
            value=parsed.get("value", {"raw": raw_text}),
            artifact_id=None,
            source=source,
            run_id=run_id,
            goal_id=goal_id,
            confidence=float(parsed.get("confidence", 0.5)),
            created_at=datetime.now(timezone.utc),
        )
        self._items.append(item)
        self._save()
        return item

    def record_outcome(
        self,
        tool_call: ToolCall,
        result_text: str,
        artifact_id: Optional[int] = None,
        run_id: str = "",
        goal_id: Optional[str] = None,
        source: str = "agent",
    ) -> MemoryItem:
        """Record a tool call result — no LLM, kind=tool_outcome."""
        self._load()
        keywords = [tool_call.name.lower()] + [k.lower() for k in list(tool_call.arguments.keys())[:4]]
        item = MemoryItem(
            id=str(uuid.uuid4()),
            kind="tool_outcome",
            keywords=keywords,
            descriptor=f"{tool_call.name} → {result_text[:60]}",
            value={
                "tool": tool_call.name,
                "arguments": tool_call.arguments,
                "result": result_text,
            },
            artifact_id=artifact_id,
            source=source,
            run_id=run_id,
            goal_id=goal_id,
            confidence=1.0,
            created_at=datetime.now(timezone.utc),
        )
        self._items.append(item)
        self._save()
        return item


# module-level singleton
memory = Memory()
