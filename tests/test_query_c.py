"""
Test Query C — Mom's birthday (durable memory across two runs)
Issue: sujitojha1/AgentiAI#12

Expected flow:
  Run 1: classify statement as fact, create reminder files in state/
  Run 2: retrieve fact from memory, answer without a web tool call
  Verify state/memory.json persists the fact between runs

Run:
    uv run python tests/test_query_c.py
    uv run python tests/test_query_c.py --no-clean   # keep existing state
"""

import argparse
import asyncio
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

QUERY_RUN1 = (
    "My mom's birthday is 15 May 2026. Remember that and give me a "
    "calendar reminder for two weeks before and on the day."
)
QUERY_RUN2 = "When is mom's birthday?"

STATE_DIR  = ROOT / "state"
MEMORY_FILE = STATE_DIR / "memory.json"

# Keywords that must appear in the final answer of Run 2
RUN2_REQUIRED = ["birthday", "may", "2026"]

# At least one date signal: "15" or "may" already covered above, but also check
DATE_SIGNALS = ["15", "1 may", "may 1", "may 15", "15 may"]


def clean_state() -> None:
    if STATE_DIR.exists():
        shutil.rmtree(STATE_DIR)
        print(f"[test] cleared {STATE_DIR}")
    STATE_DIR.mkdir(parents=True)


# ── memory.json validation ────────────────────────────────────────────────────

def _load_memory() -> list[dict]:
    if not MEMORY_FILE.exists():
        return []
    return json.loads(MEMORY_FILE.read_text())


def check_memory_fact() -> tuple[bool, list[str]]:
    """Verify memory.json contains a 'fact' item about mom's birthday."""
    items = _load_memory()
    failures: list[str] = []

    if not items:
        failures.append("state/memory.json is empty or missing")
        return False, failures

    fact_items = [m for m in items if m.get("kind") == "fact"]
    if not fact_items:
        failures.append(
            f"no 'fact' items in memory (found kinds: "
            f"{list({m.get('kind') for m in items})})"
        )
        return False, failures

    birthday_facts = [
        m for m in fact_items
        if any(kw in ["mom", "birthday", "may"] for kw in m.get("keywords", []))
    ]
    if not birthday_facts:
        all_kws = [kw for m in fact_items for kw in m.get("keywords", [])]
        failures.append(
            f"no fact item with mom/birthday/may keywords "
            f"(found keywords: {all_kws[:12]})"
        )
        return False, failures

    # Confirm value contains a date hint
    item = birthday_facts[0]
    raw_value = json.dumps(item.get("value", {})).lower()
    if "2026" not in raw_value and "may" not in raw_value:
        failures.append(
            f"fact value does not mention the date "
            f"(value: {item.get('value')})"
        )

    return len(failures) == 0, failures


# ── answer validation ─────────────────────────────────────────────────────────

def check_run1_answer(answer: str) -> tuple[bool, list[str]]:
    low = answer.lower()
    failures: list[str] = []
    if "reminder" not in low and "remind" not in low and "calendar" not in low:
        failures.append("Run 1 answer does not mention a reminder or calendar")
    if "2026" not in low and "may" not in low:
        failures.append("Run 1 answer does not reference the date (May 2026)")
    return len(failures) == 0, failures


def check_run2_answer(answer: str) -> tuple[bool, list[str]]:
    low = answer.lower()
    failures: list[str] = []
    for kw in RUN2_REQUIRED:
        if kw not in low:
            failures.append(f"Run 2 answer missing keyword: '{kw}'")
    if not any(sig in low for sig in DATE_SIGNALS):
        failures.append(
            f"Run 2 answer does not include a specific date signal "
            f"(checked: {DATE_SIGNALS})"
        )
    return len(failures) == 0, failures


# ── main ──────────────────────────────────────────────────────────────────────

async def main(clean: bool) -> int:
    if clean:
        clean_state()

    from agent6 import run  # noqa: PLC0415 (local import after path setup)

    overall_pass = True

    # ── Run 1 ─────────────────────────────────────────────────────────────────
    print("=" * 78)
    print("TEST QUERY C — Run 1: store mom's birthday + create reminders")
    print("=" * 78)

    answer1 = await run(QUERY_RUN1)

    print("\n" + "=" * 78)
    print("VALIDATION — Run 1")
    print("=" * 78)

    r1_pass, r1_failures = check_run1_answer(answer1)
    mem_pass, mem_failures = check_memory_fact()

    low1 = answer1.lower()
    print(f"  answer references reminder/calendar : {'✓' if 'remind' in low1 or 'calendar' in low1 else '✗'}")
    print(f"  answer references May / 2026        : {'✓' if 'may' in low1 or '2026' in low1 else '✗'}")
    print(f"  state/memory.json has birthday fact : {'✓' if mem_pass else '✗'}")

    memory_items = _load_memory()
    fact_count   = sum(1 for m in memory_items if m.get("kind") == "fact")
    print(f"  total memory items                  : {len(memory_items)}  (facts: {fact_count})")

    if r1_failures or mem_failures:
        print("\n  FAILURES:")
        for f in r1_failures + mem_failures:
            print(f"    ✗ {f}")
        overall_pass = False

    print(f"\n  RUN 1 RESULT: {'PASS ✓' if r1_pass and mem_pass else 'FAIL ✗'}")

    # ── Run 2 ─────────────────────────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("TEST QUERY C — Run 2: retrieve mom's birthday from memory")
    print("=" * 78)

    answer2 = await run(QUERY_RUN2)

    print("\n" + "=" * 78)
    print("VALIDATION — Run 2")
    print("=" * 78)

    r2_pass, r2_failures = check_run2_answer(answer2)

    low2 = answer2.lower()
    date_found = [s for s in DATE_SIGNALS if s in low2]
    print(f"  answer mentions 'birthday'          : {'✓' if 'birthday' in low2 else '✗'}")
    print(f"  answer mentions 'may'               : {'✓' if 'may' in low2 else '✗'}")
    print(f"  answer mentions '2026'              : {'✓' if '2026' in low2 else '✗'}")
    print(f"  answer includes specific date       : {'✓' if date_found else '✗'}"
          + (f"  ({', '.join(date_found)})" if date_found else ""))

    # Memory should have grown with at least one more read hit recorded
    memory_items_after = _load_memory()
    print(f"  memory items after run 2            : {len(memory_items_after)}")

    if r2_failures:
        print("\n  FAILURES:")
        for f in r2_failures:
            print(f"    ✗ {f}")
        overall_pass = False

    print(f"\n  RUN 2 RESULT: {'PASS ✓' if r2_pass else 'FAIL ✗'}")

    print("\n" + "=" * 78)
    print(f"  OVERALL RESULT: {'PASS ✓' if overall_pass else 'FAIL ✗'}")
    print("=" * 78)
    return 0 if overall_pass else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-clean", dest="clean", action="store_false",
                    help="Skip clearing state/ before Run 1")
    args = ap.parse_args()
    sys.exit(asyncio.run(main(clean=args.clean)))
