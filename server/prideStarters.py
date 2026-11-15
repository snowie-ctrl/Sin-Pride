"""
The starter programs (spec §6): readable JSON in server/starters/, one file a starter, each with three variants (gym,
dumbbell, bodyweight) naming the equipment they need. This module chooses the variant for a person's equipment, the
planned weekdays for their days a week, and the rep ranges for their goal (plan decisions 10–12). Pure: the route
looks the exercise keys up in the catalog and hands them in, so the stub uses this file unchanged.
"""
import json
from pathlib import Path

try:
    from . import prideCatalog as catalog, prideChecks as checks
except ImportError:  # the stub and tools/checkStarters.py load server/ as plain modules
    import prideCatalog as catalog
    import prideChecks as checks

STARTER_DIR = Path(__file__).resolve().parent / "starters"
# Every starter names free-exercise-db's keys: its beginner exercises are what the intro offers (spec §2).
SOURCE = "free-exercise-db"
VARIANTS = ("gym", "dumbbell", "bodyweight")
TIMED_SECONDS = 30


def load(folder=STARTER_DIR):
    return sorted((json.loads(p.read_text(encoding="utf-8")) for p in Path(folder).glob("*.json")),
                  key=lambda s: s["order"])


def keysOf(starters):
    return {item["exercise"] for s in starters for v in s["variants"] for r in v["routines"] for item in r["items"]}


def variantFor(starter, equipment):
    """The first variant whose needs the person has; bodyweight always counts, and the last variant needs nothing."""
    have = set(equipment) | {"bodyweight"}
    for variant in starter["variants"]:
        if set(variant["needs"]) <= have:
            return variant
    return starter["variants"][-1]


def daysFor(starter, daysPerWeek):
    """Spec §6's planned weekdays for this many days a week; a count the starter isn't for takes its nearest."""
    table = starter["days"]
    if str(daysPerWeek) in table:
        return table[str(daysPerWeek)]
    counts = sorted(int(k) for k in table)
    return table[str(counts[-1] if daysPerWeek > counts[-1] else counts[0])]


def fill(starter, equipment, goal, daysPerWeek, found):
    """The starter as GET /starters shows it to this person. `found` maps a key to the visible catalog exercise
    ({"id", "name", "measure"}); a key not in it is left out and listed in "missing" (plan decision 12)."""
    variant = variantFor(starter, equipment)
    low, high = checks.REPS_BY_GOAL.get(goal, checks.REPS_BY_GOAL["general"])
    routines, missing = [], set()
    for routine in variant["routines"]:
        items = []
        for entry in routine["items"]:
            exercise = found.get(entry["exercise"])
            if exercise is None:
                missing.add(entry["exercise"])
                continue
            measure = exercise["measure"]
            item = {"exerciseId": exercise["id"], "name": exercise["name"], "measure": measure, "sets": 3,
                    "repsMin": None, "repsMax": None, "targetSeconds": None,
                    "restSeconds": 90 if measure == "weight_reps" else 60}
            if measure in ("weight_reps", "reps"):
                item.update(repsMin=low, repsMax=high)
            elif measure == "time":
                item["targetSeconds"] = entry.get("seconds", TIMED_SECONDS)
            else:
                item["sets"] = 1
            items.append(item)
        routines.append({"title": routine["title"], "items": items})
    return {"key": starter["key"], "title": starter["title"], "blurb": variant.get("blurb", starter["blurb"]),
            "suggested": daysPerWeek in starter["forDays"], "variant": variant["name"],
            "days": daysFor(starter, daysPerWeek), "routines": routines, "missing": sorted(missing)}


def problems(starter):
    """What is wrong with a starter file's shape; [] when nothing is."""
    found = []
    for field in ("key", "title", "blurb"):
        if not isinstance(starter.get(field), str) or not starter[field].strip():
            found.append(f"{field} must be text")
    if len(starter.get("title", "")) > checks.LIMITS["title"]:
        found.append("title is longer than a program title may be")
    if [v.get("name") for v in starter.get("variants", [])] != list(VARIANTS):
        found.append(f"variants must be {', '.join(VARIANTS)}, in that order")
    for count in starter.get("forDays", []):
        days = starter.get("days", {}).get(str(count))
        if not isinstance(days, list) or len(days) != count or sorted(set(days)) != days or not all(0 <= d <= 6 for d in days):
            found.append(f"days for {count} must be {count} distinct weekdays in order")
    for variant in starter.get("variants", []):
        if not all(w in catalog.EQUIPMENT for w in variant.get("needs", [])):
            found.append(f"{variant.get('name')}: needs lists unknown equipment")
        routines = variant.get("routines", [])
        if not routines or len(routines) > checks.LIMITS["routines"]:
            found.append(f"{variant.get('name')}: 1 to {checks.LIMITS['routines']} routines")
        for routine in routines:
            items = routine.get("items", [])
            if not items or len(items) > checks.LIMITS["items"]:
                found.append(f"{variant.get('name')} {routine.get('title')}: 1 to {checks.LIMITS['items']} items")
            for item in items:
                seconds = item.get("seconds", TIMED_SECONDS)
                if not isinstance(item.get("exercise"), str) or not isinstance(seconds, int) or not 1 <= seconds <= 36000:
                    found.append(f"{variant.get('name')} {routine.get('title')}: a bad item {item}")
    return found
