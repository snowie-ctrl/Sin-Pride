"""
Checks every starter exercise (server/starters/*.json) against the real catalog as the importer's last dry run left
it, in app/tests/stub/snapshot/catalog.json (snapshot.py makes it; git-ignored, so this runs only on a machine that has
one). Every key must be there, shown, and a beginner exercise (spec §2); an item with seconds must be measured by
time, and a timed exercise must have seconds. Prints "clean" or each problem, and exits 1 on any.
    server/.venv/Scripts/python.exe tools/checkStarters.py [catalog.json]
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "server"))

import prideStarters  # noqa: E402

SNAPSHOT = REPO / "app" / "tests" / "stub" / "snapshot" / "catalog.json"


def check(starters, exercises):
    byKey = {e["key"]: e for e in exercises}
    found = []
    for starter in starters:
        seen = set()
        for variant in starter["variants"]:
            for routine in variant["routines"]:
                for item in routine["items"]:
                    key = item["exercise"]
                    if key in seen:
                        continue
                    seen.add(key)
                    e = byKey.get(key)
                    if e is None or e.get("removed"):
                        found.append(f"{starter['key']}: {key} is not in the catalog")
                    elif e["level"] != "beginner":
                        found.append(f"{starter['key']}: {key} is {e['level']}, not beginner")
                    elif "seconds" in item and e["measure"] != "time":
                        found.append(f"{starter['key']}: {key} has seconds but is measured {e['measure']}")
                    elif "seconds" not in item and e["measure"] == "time":
                        found.append(f"{starter['key']}: {key} is timed but has no seconds")
    return found


def main(argv):
    path = Path(argv[1]) if len(argv) > 1 else SNAPSHOT
    if not path.is_file():
        print(f"no catalog at {path}: run the importer's dry run, then app/tests/stub/snapshot.py")
        return 2
    exercises = json.loads(path.read_text(encoding="utf-8"))["exercises"]
    problems = check(prideStarters.load(), exercises)
    for problem in problems:
        print(problem)
    print("clean" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
