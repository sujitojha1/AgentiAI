"""
agent6.py — Session 6 agentic loop.

Wires four cognitive roles into a single iterative loop:
    Memory     (memory.py)     — persist and retrieve episodic facts
    Perception (perception.py) — orchestrator: goal decomposition and tracking
    Decision   (decision.py)   — single LLM call: answer or tool_call
    Action     (action.py)     — pure MCP dispatch + ArtifactStore

  agent5.py (Session 5)                agent6.py (Session 6)
  ─────────────────────────────────    ────────────────────────────────────
  single-role math agent           →   four-role cognitive architecture
  flat message history             →   structured per-iter history dicts
  LLM decides tool vs answer       →   Perception decomposes goals; Decision
                                        picks answer vs tool per goal
  no artifact handling             →   ArtifactStore for payloads > 4 KB
  no durable memory                →   state/memory.json persists across runs
  hardcoded task                   →   open-ended natural language query
  gateway V2 (port 8100)           →   gateway V3 (port 8101, auto_route)
"""

import asyncio
import sys
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from action import store as artifacts
from action import action
from decision import decision
from memory import memory
from perception import perception
from schemas import Goal

GATEWAY_URL = "http://localhost:8101"
MAX_ITERATIONS = 12


# ── Gateway health check ──────────────────────────────────────────────────────

def ensure_gateway() -> None:
    try:
        r = httpx.get(f"{GATEWAY_URL}/v1/capabilities", timeout=5)
        r.raise_for_status()
    except Exception as exc:
        raise RuntimeError(
            f"LLM Gateway V3 not reachable at {GATEWAY_URL}. "
            f"Start it with: cd llm_gatewayV3 && uvicorn main:app --port 8101\n({exc})"
        ) from exc


# ── MCP helpers ───────────────────────────────────────────────────────────────

@asynccontextmanager
async def mcp_session():
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(Path(__file__).resolve().parent / "mcp_server.py")],
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def load_tools(session: ClientSession) -> list:
    return (await session.list_tools()).tools


def mcp_tools_for_decision(mcp_tools: list) -> list[dict]:
    """Convert MCP Tool objects to the gateway ToolDef dict format."""
    return [
        {
            "name": t.name,
            "description": getattr(t, "description", "") or "",
            "input_schema": t.inputSchema if isinstance(t.inputSchema, dict) else {},
        }
        for t in mcp_tools
    ]


# ── History helper ────────────────────────────────────────────────────────────

def final_answer_from(history: list[dict]) -> str:
    """Return the last non-empty answer text from the history."""
    for entry in reversed(history):
        if entry.get("kind") == "answer":
            text = (entry.get("text") or "").strip()
            if text:
                return text
    return "(no answer produced)"


# ── Main loop ─────────────────────────────────────────────────────────────────

async def run(query: str) -> str:
    ensure_gateway()

    run_id = uuid.uuid4().hex[:8]
    print("═" * 78)
    print(f"agent6.py — Session 6  |  run_id={run_id}")
    print(f"query: {query}")
    print("═" * 78)

    history: list[dict] = []
    prior_goals: list[Goal] = []

    # Persist the user query so facts/preferences survive into future runs
    memory.remember(query, source="user_query", run_id=run_id)

    t0 = time.time()

    async with mcp_session() as session:
        mcp_tools = await load_tools(session)
        tools = mcp_tools_for_decision(mcp_tools)
        print(f"[mcp] {len(mcp_tools)} tools: {[t.name for t in mcp_tools]}\n")

        for it in range(1, MAX_ITERATIONS + 1):
            print(f"{'─' * 60}")
            print(f"[iter {it}]")

            # ── Memory read ───────────────────────────────────────────────
            hits = memory.read(query, history)
            print(f"  [memory]     {len(hits)} hit(s)")

            # ── Perception ────────────────────────────────────────────────
            obs = perception.observe(query, hits, history, prior_goals, run_id)
            prior_goals = obs.goals
            done_count = sum(1 for g in obs.goals if g.done)
            print(f"  [perception] {len(obs.goals)} goal(s), {done_count} done")
            for g in obs.goals:
                marker = "✓" if g.done else "○"
                art = f"  [artifact:{g.attach_artifact_id}]" if g.attach_artifact_id else ""
                print(f"    {marker} {g.id}: {g.text}{art}")

            # ── Loop termination ──────────────────────────────────────────
            if obs.all_done:
                print("  [loop]       all goals done — terminating\n")
                break

            # ── Pick first unfinished goal ────────────────────────────────
            goal = obs.next_unfinished()

            # ── Resolve artifact attachment ───────────────────────────────
            attached: list[tuple[int, bytes]] = []
            if goal.attach_artifact_id and artifacts.exists(goal.attach_artifact_id):
                blob = artifacts.get_bytes(goal.attach_artifact_id)
                attached.append((goal.attach_artifact_id, blob))
                print(f"  [artifact]   loaded artifact:{goal.attach_artifact_id} "
                      f"({len(blob):,} bytes)")

            # ── Decision ──────────────────────────────────────────────────
            out = decision.next_step(goal, hits, attached, history, tools)

            if out.is_answer:
                print(f"  [decision]   answer: {out.answer[:120]!r}")
                history.append({"iter": it, "kind": "answer",
                                "goal_id": goal.id, "text": out.answer})
                continue

            # ── Action (MCP dispatch) ─────────────────────────────────────
            tc = out.tool_call
            print(f"  [decision]   tool_call: {tc.name}({tc.arguments})")

            result_text, art_id = await action.execute(session, tc)
            result_preview = result_text[:120] if art_id is None else f"→ artifact:{art_id}"
            print(f"  [action]     {result_preview!r}")

            # ── Memory record ─────────────────────────────────────────────
            memory.record_outcome(
                tool_call=tc,
                result_text=result_text,
                artifact_id=art_id,
                run_id=run_id,
                goal_id=goal.id,
            )

            # ── Append action outcome to history ──────────────────────────
            history.append({"iter": it, "kind": "action",
                            "goal_id": goal.id, "tool": tc.name,
                            "arguments": tc.arguments,
                            "result_descriptor": result_text[:300],
                            "artifact_id": art_id})

        else:
            print(f"\n[loop] reached MAX_ITERATIONS={MAX_ITERATIONS} without completion")

    elapsed = round(time.time() - t0, 2)
    answer = final_answer_from(history)
    print(f"\n{'═' * 78}")
    print(f"FINAL ANSWER  ({elapsed}s, {it} iteration(s)):")
    print(answer)
    print("═" * 78)
    return answer


# ── Entrypoint ────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="AgentiAI Session 6 agent loop")
    ap.add_argument("query", nargs="?",
                    default="What is today's date and time in Tokyo?")
    args = ap.parse_args()
    asyncio.run(run(args.query))


if __name__ == "__main__":
    main()
