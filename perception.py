"""Perception role — orchestrator and goal tracker, pinned to Gemini."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from schemas import Goal, MemoryItem, Observation

sys.path.insert(0, str(Path(__file__).resolve().parent / "llm_gatewayV3"))
from client import LLM  # type: ignore[import]  # noqa: E402

# ── System prompt ─────────────────────────────────────────────────────────────
# Designed to satisfy all PoP criteria: explicit step-by-step reasoning,
# structured output, conversation-loop awareness, self-checks, and fallbacks.

_SYSTEM_PROMPT = """\
You are the Perception module of an agentic AI system.
Your sole responsibility: maintain a structured Goal list that drives the agent loop.

━━━ FIRST CALL (Current goals = none) ━━━
Decompose the user query into 1–5 clear, actionable Goals.
• Assign each goal a unique kebab-case id (e.g. "fetch-weather", "summarise-article").
• Set done=false and attach_artifact_id=null for every goal.
• Each goal must be specific enough for the Decision module to act on independently.

━━━ SUBSEQUENT CALLS (Current goals provided) ━━━
Do EXACTLY ONE of the following — never both in the same response:

  (A) Update done flags
      Read conversation history oldest→newest. For each goal, check whether any
      history entry clearly and fully satisfies it. Set done=true only on explicit
      evidence. Preserve all goal ids, texts, and order. Do not add new goals.

  (B) Set attach_artifact_id on the first unfinished goal
      If the first unfinished goal needs content from a prior tool result, set its
      attach_artifact_id to the integer shown in an [artifact:N] tag in the history.
      Leave done=false.

━━━ STEP-BY-STEP REASONING (work through this before writing JSON) ━━━
1. Is this the first call (no prior goals) or a subsequent call?
2. For each existing goal, find the history entry — if any — that satisfies it.
3. Does the first unfinished goal need artifact bytes to proceed?
   Yes → action B.  No → action A.
4. Self-check: am I marking any goal done without explicit history evidence?
   If yes, keep it false. When in doubt, keep done=false.

━━━ OUTPUT ━━━
Return a single JSON object — no markdown, no prose, no extra keys:
{"goals": [{"id": "...", "text": "...", "done": true|false, "attach_artifact_id": null|<integer>}]}
"""

# JSON Schema for response_format (matches schemas.Goal / schemas.Observation)
_OBSERVATION_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "goals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id":                {"type": "string"},
                    "text":              {"type": "string"},
                    "done":              {"type": "boolean"},
                    "attach_artifact_id": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
                },
                "required": ["id", "text", "done", "attach_artifact_id"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["goals"],
    "additionalProperties": False,
}


class Perception:
    def __init__(self) -> None:
        self._llm = LLM()

    # ── formatting helpers ────────────────────────────────────────────────────

    def _fmt_hits(self, hits: list[MemoryItem]) -> str:
        if not hits:
            return "(none)"
        lines = []
        for m in hits:
            art = f" [artifact:{m.artifact_id}]" if m.artifact_id is not None else ""
            lines.append(f"- [{m.kind}] {m.descriptor}{art}")
        return "\n".join(lines)

    def _fmt_history(self, history: list[dict]) -> str:
        if not history:
            return "(empty)"
        lines = []
        for entry in history:
            kind = entry.get("kind", "?")
            it = entry.get("iter", "?")
            goal_id = entry.get("goal_id", "")
            if kind == "answer":
                text = (entry.get("text") or "")[:300]
                lines.append(f"[iter {it}] ANSWER ({goal_id}): {text}")
            elif kind == "action":
                tool = entry.get("tool", "?")
                desc = (entry.get("result_descriptor") or "")[:200]
                art = entry.get("artifact_id")
                suffix = f" [artifact:{art}]" if art is not None else ""
                lines.append(f"[iter {it}] ACTION ({goal_id}): {tool} → {desc}{suffix}")
            else:
                lines.append(f"[iter {it}] {kind}: {str(entry)[:200]}")
        return "\n".join(lines)

    def _fmt_goals(self, goals: list[Goal]) -> str:
        if not goals:
            return "(none — first iteration, decompose the query)"
        return json.dumps([g.model_dump() for g in goals], indent=2)

    # ── public API ────────────────────────────────────────────────────────────

    def observe(
        self,
        query: str,
        hits: list[MemoryItem],
        history: list[dict],
        prior_goals: list[Goal],
        run_id: str,
    ) -> Observation:
        """One LLM call (pinned Gemini) → Observation with updated Goal list."""
        user_msg = (
            f"## Run\n{run_id}\n\n"
            f"## Query\n{query}\n\n"
            f"## Memory hits\n{self._fmt_hits(hits)}\n\n"
            f"## Conversation history\n{self._fmt_history(history)}\n\n"
            f"## Current goals\n{self._fmt_goals(prior_goals)}"
        )
        resp = self._llm.chat(
            messages=[{"role": "user", "content": user_msg}],
            system=_SYSTEM_PROMPT,
            provider="gemini",
            auto_route="perception",
            temperature=1.0,
            max_tokens=1024,
            response_format={
                "type": "json_schema",
                "schema": _OBSERVATION_SCHEMA,
                "name": "observation",
                "strict": True,
            },
        )

        parsed: dict = resp.get("parsed") or {}
        if not parsed:
            text = resp.get("text", "")
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                try:
                    parsed = json.loads(m.group())
                except Exception:
                    parsed = {}

        return Observation.model_validate(parsed)


# module-level singleton
perception = Perception()
