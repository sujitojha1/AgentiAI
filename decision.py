"""Decision role — single LLM call returning answer or tool_call."""
from __future__ import annotations

import sys
from pathlib import Path

from schemas import DecisionOutput, Goal, MemoryItem, ToolCall

sys.path.insert(0, str(Path(__file__).resolve().parent / "llm_gatewayV3"))
from client import LLM  # type: ignore[import]  # noqa: E402

# ── System prompt ─────────────────────────────────────────────────────────────
# Reviewed against PoP criteria: explicit step-by-step reasoning, structured
# output (one-of rule), tool/answer separation, self-checks, fallbacks.

_SYSTEM_PROMPT = """\
You are the Decision module of an agentic AI system.
For the current Goal, emit exactly ONE of: a plain-text answer OR a single tool call.

━━━ RULES ━━━

RULE 1 — Answer directly when any of these apply:
  • The attached artifact already contains what the goal needs (extract, list, summarise, compare).
  • Memory hits or conversation history already fully cover the goal.
  • The goal asks for synthesis, analysis, or comparison of information already in context.

  EXTRACTION RULE: When the goal says "extract from fetched content" and an artifact is
  attached, your answer MUST come from the artifact text — not from your own knowledge.
  Scan the artifact for specific paper titles, years, theorem names, and technical terms,
  and include them verbatim. Never replace them with vague descriptions like "he founded
  X" when the artifact contains the specific name of the paper or theorem.

RULE 2 — Call a tool when:
  • The goal needs real-time data not present in context (search, time, currency).
  • A specific URL must be fetched that has not yet been retrieved.
  • No existing context can satisfy the goal.

RULE 3 — art: handles and artifacts
  • Artifact content is provided in the ## Attached artifact section — read it there.
  • Never call read_file or fetch_url to access an artifact. read_file is for sandbox
    files you previously created; artifacts are not sandbox files.
  • If you must pass an artifact to a tool argument, use "art:<integer_id>" — the
    Action module resolves it to real bytes before dispatch.
  • If the ## Attached artifact section contains enough information to answer, do so
    directly (Rule 1) — do not make an additional tool call to re-read it.

RULE 4 — One output, never both
  • Produce ONE tool call OR ONE plain-text answer. Never both. Never an empty answer.
  • When the goal is extraction / listing / comparison, always answer directly (Rule 1).

RULE 5 — web_search snippets are NOT fetched content; track remaining URLs in history
  • web_search returns only titles, URLs, and brief snippets — NOT the full page.
  • Snippets are never a substitute for fetched content.
  • To fulfil a "fetch top N results" goal:
    1. Find the ACTION entry with tool=web_search in history. Its result_descriptor
       lists all URLs: "web_search → URLs: url1 | url2 | url3".
    2. Find which of those URLs already appear as fetch_url arguments in later
       history entries (look for ACTION entries with tool=fetch_url).
    3. Call fetch_url for the NEXT unfetched URL — one call per iteration.
    4. NEVER call web_search again to re-find URLs that are already in history.

━━━ STEP-BY-STEP REASONING (work through this before responding) ━━━
1. Read the Goal text. What type of task is it?
   Classify: [fetch] [search] [extract] [summarise] [compare] [calculate] [other]
2. Check the attached artifact and conversation history.
   Can the goal be fully answered from existing context? → YES: write the answer (Rule 1).
3. If NO: identify the single best tool call. Emit it (Rule 2).
4. Self-check before output:
   • Am I producing exactly one of answer or tool_call?
   • If the goal is extraction/summarisation, am I answering directly instead of re-fetching?
   • Is my answer substantive and specific, not a hedge or deferral?
5. If [extract] from an artifact: scan the artifact text for specific named items —
   paper titles with years (e.g. "A Mathematical Theory of Communication, 1948"),
   theorem names (e.g. "Noisy-Channel Coding Theorem", "channel capacity"),
   coined terms (e.g. "bit"). Include these exact phrases. Do NOT substitute
   vague descriptions ("he founded the field") for named concepts in the text.

━━━ OUTPUT ━━━
Answering: write complete, specific prose — no JSON wrapping, no markdown fences.
Tool call: the gateway captures tool calls natively from your response.
"""


class Decision:
    def __init__(self) -> None:
        self._llm = LLM()

    # ── helpers ───────────────────────────────────────────────────────────────

    def _to_gateway_tools(self, mcp_tools: list) -> list[dict]:
        """Normalise MCP Tool objects or plain dicts to gateway ToolDef format."""
        result = []
        for t in mcp_tools:
            if hasattr(t, "inputSchema"):
                schema = t.inputSchema
                result.append({
                    "name": t.name,
                    "description": getattr(t, "description", "") or "",
                    "input_schema": schema if isinstance(schema, dict) else {},
                })
            elif isinstance(t, dict):
                result.append(t)
            elif hasattr(t, "model_dump"):
                result.append(t.model_dump())
        return result

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
                desc = (entry.get("result_descriptor") or "")[:400]
                art = entry.get("artifact_id")
                suffix = f" [artifact:{art}]" if art is not None else ""
                lines.append(f"[iter {it}] ACTION ({goal_id}): {tool} → {desc}{suffix}")
            else:
                lines.append(f"[iter {it}] {kind}: {str(entry)[:200]}")
        return "\n".join(lines)

    # ── public API ────────────────────────────────────────────────────────────

    def next_step(
        self,
        goal: Goal,
        hits: list[MemoryItem],
        attached: list[tuple[int, bytes]],
        history: list[dict],
        mcp_tools: list,
    ) -> DecisionOutput:
        """One LLM call (auto_route=decision) → DecisionOutput(answer|tool_call)."""
        # Budget 30 KB across all artifacts to stay in LARGE gateway tier.
        # Divide evenly so each source gets a fair share.
        _BUDGET = 30_000
        if attached:
            per_art = _BUDGET // len(attached)
            sections = []
            for art_id, blob in attached:
                text = blob[:per_art].decode("utf-8", errors="replace")
                truncation_note = (
                    f" [first {per_art:,} of {len(blob):,} bytes shown]"
                    if len(blob) > per_art else ""
                )
                sections.append(
                    f"## Attached artifact (artifact:{art_id}){truncation_note}\n{text}"
                )
            attached_section = "\n\n".join(sections)
        else:
            attached_section = "## Attached artifact\n(none)"
        user_msg = (
            f"## Goal\nid: {goal.id}\ntext: {goal.text}\n\n"
            f"## Memory hits\n{self._fmt_hits(hits)}\n\n"
            f"{attached_section}\n\n"
            f"## Conversation history\n{self._fmt_history(history)}"
        )

        gateway_tools = self._to_gateway_tools(mcp_tools)
        resp = self._llm.chat(
            messages=[{"role": "user", "content": user_msg}],
            system=_SYSTEM_PROMPT,
            auto_route="decision",
            tools=gateway_tools if gateway_tools else None,
            tool_choice="auto" if gateway_tools else None,
            temperature=0.7,
            max_tokens=2048,
        )

        # Tool call response
        tool_calls = resp.get("tool_calls") or []
        if tool_calls:
            tc = tool_calls[0]
            return DecisionOutput(
                answer=None,
                tool_call=ToolCall(
                    name=tc.get("name") or tc.get("function", {}).get("name", ""),
                    arguments=tc.get("arguments") or tc.get("function", {}).get("arguments", {}),
                ),
            )

        # Text answer response
        return DecisionOutput(answer=resp.get("text", ""), tool_call=None)


# module-level singleton
decision = Decision()
