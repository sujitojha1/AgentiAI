"""
Test Query A — Shannon Wikipedia (artifact attach path)
Issue: sujitojha1/AgentiAI#10

Expected flow:
  Iter 1: Decision calls fetch_url → result >4KB → stored as artifact
  Iter 2: Perception sets attach_artifact_id on extraction goal
          Decision receives attached bytes → answers with birth/death/contributions
  Iter 3: All goals done

Run:
    uv run python tests/test_query_a.py
    uv run python tests/test_query_a.py --no-clean   # keep existing state
"""

import argparse
import asyncio
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

QUERY = (
    "Fetch https://en.wikipedia.org/wiki/Claude_Shannon and tell me his "
    "birth date, death date, and three key contributions to information theory."
)

REQUIRED_FACTS = [
    "1916",           # birth year
    "2001",           # death year
    "information theory",
]

STATE_DIR = ROOT / "state"


def clean_state() -> None:
    if STATE_DIR.exists():
        shutil.rmtree(STATE_DIR)
        print(f"[test] cleared {STATE_DIR}")
    STATE_DIR.mkdir(parents=True)


def check_answer(answer: str) -> tuple[bool, list[str]]:
    missing = [f for f in REQUIRED_FACTS if f.lower() not in answer.lower()]
    return len(missing) == 0, missing


async def main(clean: bool) -> int:
    if clean:
        clean_state()

    from agent6 import run

    print("=" * 78)
    print("TEST QUERY A — Claude Shannon Wikipedia")
    print("=" * 78)

    answer = await run(QUERY)

    print("\n" + "=" * 78)
    print("VALIDATION")
    print("=" * 78)

    passed, missing = check_answer(answer)

    # Check artifact was created
    artifact_dir = STATE_DIR / "artifacts"
    artifact_count = len(list(artifact_dir.glob("*.bin"))) if artifact_dir.exists() else 0
    artifact_ok = artifact_count >= 1

    print(f"  answer contains birth year (1916) : {'✓' if '1916' in answer else '✗'}")
    print(f"  answer contains death year (2001) : {'✓' if '2001' in answer else '✗'}")
    print(f"  answer mentions info theory       : {'✓' if 'information' in answer.lower() else '✗'}")
    print(f"  artifact stored (>4KB result)     : {'✓' if artifact_ok else '✗'} ({artifact_count} artifact(s))")

    if missing:
        print(f"\n  MISSING in answer: {missing}")

    overall = passed and artifact_ok
    print(f"\n  RESULT: {'PASS ✓' if overall else 'FAIL ✗'}")
    return 0 if overall else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-clean", dest="clean", action="store_false",
                    help="Skip clearing state/ before the run")
    args = ap.parse_args()
    sys.exit(asyncio.run(main(clean=args.clean)))
