"""
Test Query B — Tokyo activities with weather (multi-goal + memory carryover)
Issue: sujitojha1/AgentiAI#11

Expected flow:
  ~3 goals: find activities, check Saturday weather, synthesise recommendation
  Decision: web_search for activities, web_search/fetch_url for weather forecast
  Final answer: references the weather and recommends indoor/outdoor accordingly
  ~6 iterations

Run:
    uv run python tests/test_query_b.py
    uv run python tests/test_query_b.py --no-clean   # keep existing state
"""

import argparse
import asyncio
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

QUERY = (
    "Find 3 family-friendly things to do in Tokyo this weekend. "
    "Check Saturday's weather forecast there and tell me which one "
    "is most appropriate."
)

STATE_DIR = ROOT / "state"

# Keywords that must appear somewhere in the final answer
REQUIRED_KEYWORDS = [
    "tokyo",        # answer is about Tokyo
    "weather",      # weather was checked and referenced
]

# At least one weather-condition word must appear
WEATHER_WORDS = [
    "rain", "sunny", "cloud", "clear", "humid", "hot", "warm",
    "indoor", "outdoor", "forecast",
]

# Answer must mention at least 2 distinct activities
ACTIVITY_SIGNALS = [
    "museum", "park", "shrine", "temple", "disneyland", "aquarium",
    "teamlab", "odaiba", "ueno", "shinjuku", "asakusa", "zoo",
    "skytree", "garden", "market", "tower",
]


def clean_state() -> None:
    if STATE_DIR.exists():
        shutil.rmtree(STATE_DIR)
        print(f"[test] cleared {STATE_DIR}")
    STATE_DIR.mkdir(parents=True)


def check_answer(answer: str) -> tuple[bool, list[str]]:
    low = answer.lower()
    failures = []

    for kw in REQUIRED_KEYWORDS:
        if kw not in low:
            failures.append(f"missing keyword: '{kw}'")

    if not any(w in low for w in WEATHER_WORDS):
        failures.append(f"no weather condition referenced (checked: {WEATHER_WORDS[:5]}...)")

    activities_found = [a for a in ACTIVITY_SIGNALS if a in low]
    if len(activities_found) < 2:
        failures.append(
            f"fewer than 2 recognisable activities found (found: {activities_found})"
        )

    return len(failures) == 0, failures


async def main(clean: bool) -> int:
    if clean:
        clean_state()

    from agent6 import run

    print("=" * 78)
    print("TEST QUERY B — Tokyo Activities + Weather (multi-goal + memory carryover)")
    print("=" * 78)

    answer = await run(QUERY)

    print("\n" + "=" * 78)
    print("VALIDATION")
    print("=" * 78)

    passed, failures = check_answer(answer)
    low = answer.lower()

    activities_found = [a for a in ACTIVITY_SIGNALS if a in low]
    weather_found    = [w for w in WEATHER_WORDS if w in low]

    print(f"  answer mentions 'tokyo'           : {'✓' if 'tokyo' in low else '✗'}")
    print(f"  answer references weather         : {'✓' if weather_found else '✗'}"
          + (f"  ({', '.join(weather_found[:3])})" if weather_found else ""))
    print(f"  ≥2 activities identified          : {'✓' if len(activities_found) >= 2 else '✗'}"
          + f"  ({', '.join(activities_found[:4])})")
    print(f"  answer recommends one activity    : {'✓' if 'recommend' in low or 'best' in low or 'ideal' in low or 'suggest' in low else '✗'}")

    if failures:
        print(f"\n  FAILURES:")
        for f in failures:
            print(f"    ✗ {f}")

    print(f"\n  RESULT: {'PASS ✓' if passed else 'FAIL ✗'}")
    return 0 if passed else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-clean", dest="clean", action="store_false",
                    help="Skip clearing state/ before the run")
    args = ap.parse_args()
    sys.exit(asyncio.run(main(clean=args.clean)))
