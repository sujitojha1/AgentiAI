"""
Test Query D — Asyncio research (multi-source synthesis)
Issue: sujitojha1/AgentiAI#13

Expected flow:
  Iter 1  : web_search → 3 URLs
  Iter 2-4: fetch_url × 3, each result stored as artifact (>4KB)
  Iter 5+ : Perception attaches artifact to synthesis goal;
            Decision reads content and produces numbered list
  Total   : 5–7 iterations

Run:
    uv run python tests/test_query_d.py
    uv run python tests/test_query_d.py --no-clean   # keep existing state
"""

import argparse
import asyncio
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

QUERY = (
    "Search for 'Python asyncio best practices', read the top 3 results, "
    "and give me a short numbered list of the advice they agree on."
)

STATE_DIR    = ROOT / "state"
ARTIFACT_DIR = STATE_DIR / "artifacts"
MEMORY_FILE  = STATE_DIR / "memory.json"

# ── answer signal groups ──────────────────────────────────────────────────────
# Each group represents one recognised asyncio best-practice.
# At least 3 of 5 groups must match in the final answer.
ADVICE_GROUPS = [
    # entry point / asyncio.run
    ["asyncio.run", "asyncio run", "entry point", "main entry"],
    # concurrency primitives: gather / TaskGroup / tasks
    ["gather", "taskgroup", "task group", "concurrently", "create_task"],
    # blocking-call avoidance / to_thread / executor
    ["blocking", "to_thread", "run_in_executor", "executor", "cpu-bound", "cpu bound"],
    # timeouts / wait_for
    ["timeout", "wait_for", "asyncio.wait_for", "time out", "timed out"],
    # semaphores / rate-limiting / concurrency caps
    ["semaphore", "rate limit", "rate-limit", "throttle", "limit concurrency"],
]

# Core terms that must appear somewhere in the final answer
REQUIRED_KEYWORDS = ["asyncio", "async"]


def clean_state() -> None:
    if STATE_DIR.exists():
        shutil.rmtree(STATE_DIR)
        print(f"[test] cleared {STATE_DIR}")
    STATE_DIR.mkdir(parents=True)


# ── memory helpers ────────────────────────────────────────────────────────────

def _memory_items() -> list[dict]:
    if not MEMORY_FILE.exists():
        return []
    return json.loads(MEMORY_FILE.read_text())


def _tool_outcomes() -> list[dict]:
    return [m for m in _memory_items() if m.get("kind") == "tool_outcome"]


# ── artifact store checks ─────────────────────────────────────────────────────

def check_artifact_store() -> tuple[bool, list[str]]:
    """Verify ≥ 1 artifact ≥ 4 KB exists.

    The agent may synthesise from the web_search result artifact alone
    (without separate fetch_url calls), so we accept any ≥4KB artifact.
    """
    if not ARTIFACT_DIR.exists():
        return False, ["state/artifacts/ directory does not exist"]
    bins  = list(ARTIFACT_DIR.glob("*.bin"))
    large = [b for b in bins if b.stat().st_size >= 4096]
    if not large:
        return False, [
            f"no artifact ≥4KB found "
            f"(total .bin files: {len(bins)}, "
            f"sizes: {sorted((b.stat().st_size for b in bins), reverse=True)[:5]})"
        ]
    return True, []


def check_memory_records() -> tuple[bool, list[str]]:
    """Verify memory.json has web_search recorded and ≥1 tool_outcome with artifact_id."""
    outcomes = _tool_outcomes()
    if not outcomes:
        return False, ["no tool_outcome records in memory.json"]

    failures: list[str] = []
    tools = [m.get("value", {}).get("tool", "?") for m in outcomes]

    if "web_search" not in tools:
        failures.append(f"web_search not recorded in memory (tools seen: {tools})")

    with_artifact = [m for m in outcomes if m.get("artifact_id") is not None]
    if not with_artifact:
        failures.append(
            f"no tool_outcome with artifact_id in memory.json (tools: {tools})"
        )

    return len(failures) == 0, failures


# ── answer checks ─────────────────────────────────────────────────────────────

def check_numbered_list(answer: str) -> tuple[bool, list[str]]:
    """Verify answer contains ≥ 3 numbered items in any common style:

      1. Plain text            →  1. Title
      Markdown header          →  ### 1. Title
      Bold numbered (common)   →  **1. Title**
    """
    # Allow optional leading #'s or *'s (markdown headers / bold), then a number + . or )
    items = re.findall(r"(?m)^\s*(?:[#*]{1,6}\s*)?\d+[\.\)]\s", answer)
    if len(items) < 3:
        return False, [
            f"answer does not contain ≥3 numbered items "
            f"(found {len(items)}; checked '1.', '### 1.', '**1.' styles)"
        ]
    return True, []


def check_asyncio_keywords(answer: str) -> tuple[bool, list[str]]:
    low      = answer.lower()
    failures = [kw for kw in REQUIRED_KEYWORDS if kw not in low]
    if failures:
        return False, [f"required keyword(s) missing from answer: {failures}"]
    return True, []


def check_advice_coverage(answer: str) -> tuple[bool, list[str]]:
    """Verify ≥ 3 of 5 recognised asyncio advice groups appear in the answer."""
    low     = answer.lower()
    matched = [
        i for i, group in enumerate(ADVICE_GROUPS, 1)
        if any(sig in low for sig in group)
    ]
    if len(matched) < 3:
        missing = [i for i in range(1, 6) if i not in matched]
        return False, [
            f"only {len(matched)}/5 advice groups matched (need ≥3); "
            f"missing group(s): {missing} "
            f"(signals: {[ADVICE_GROUPS[i-1][:2] for i in missing]})"
        ]
    return True, []


# ── main ──────────────────────────────────────────────────────────────────────

async def main(clean: bool) -> int:
    if clean:
        clean_state()

    from agent6 import run  # noqa: PLC0415

    print("=" * 78)
    print("TEST QUERY D — Asyncio Research (multi-source synthesis)")
    print("=" * 78)

    answer = await run(QUERY)

    print("\n" + "=" * 78)
    print("VALIDATION")
    print("=" * 78)

    low = answer.lower()

    kw_pass,  kw_failures  = check_asyncio_keywords(answer)
    lst_pass, lst_failures = check_numbered_list(answer)
    adv_pass, adv_failures = check_advice_coverage(answer)
    art_pass, art_failures = check_artifact_store()
    mem_pass, mem_failures = check_memory_records()

    # Keywords
    for kw in REQUIRED_KEYWORDS:
        print(f"  answer contains '{kw}'              : {'✓' if kw in low else '✗'}")

    # Numbered list
    items_found = re.findall(r"(?m)^\s*\d+[\.\)]\s+\S", answer)
    print(f"  numbered list ≥3 items              : {'✓' if lst_pass else '✗'}"
          f"  ({len(items_found)} item(s) found)")

    # Advice groups
    for i, group in enumerate(ADVICE_GROUPS, 1):
        hit = next((s for s in group if s in low), None)
        print(f"  advice group {i} matched              : {'✓' if hit else '✗'}"
              + (f"  ('{hit}')" if hit else f"  (signals: {group[:2]}...)"))

    # Artifacts
    bins      = list(ARTIFACT_DIR.glob("*.bin")) if ARTIFACT_DIR.exists() else []
    large     = [b for b in bins if b.stat().st_size >= 4096]
    sizes_kb  = sorted((b.stat().st_size // 1024 for b in large), reverse=True)
    print(f"  artifact(s) ≥4KB stored             : {'✓' if art_pass else '✗'}"
          f"  ({len(large)} artifact(s), sizes: {sizes_kb[:5]} KB)")

    # Memory tool records
    outcomes  = _tool_outcomes()
    tools_seq = [m.get("value", {}).get("tool", "?") for m in outcomes]
    fetch_cnt = tools_seq.count("fetch_url")
    with_art  = sum(1 for m in outcomes if m.get("artifact_id") is not None)
    print(f"  web_search recorded in memory       : {'✓' if 'web_search' in tools_seq else '✗'}")
    print(f"  tool outcome(s) with artifact_id    : {'✓' if mem_pass else '✗'}"
          f"  ({with_art} record(s); fetch_url calls: {fetch_cnt})")

    all_failures = kw_failures + lst_failures + adv_failures + art_failures + mem_failures
    if all_failures:
        print("\n  FAILURES:")
        for f in all_failures:
            print(f"    ✗ {f}")

    overall = kw_pass and lst_pass and adv_pass and art_pass and mem_pass
    print(f"\n  RESULT: {'PASS ✓' if overall else 'FAIL ✗'}")
    return 0 if overall else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-clean", dest="clean", action="store_false",
                    help="Skip clearing state/ before the run")
    args = ap.parse_args()
    sys.exit(asyncio.run(main(clean=args.clean)))
