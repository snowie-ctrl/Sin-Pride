"""
Every check on what a person sends (spec §3, §4) and the defaults for what they leave out, in one pure module so the
routes (prideUserRoutes.py), the stub (app/tests/stub) and the tests all use the same rules. app/qml/logic/forms.mjs
mirrors these limits. A check returns the cleaned value or raises Refusal naming the field, which the route answers as
400 {status:"error", field, message}.
"""
import math
import re
from datetime import date

try:
    from . import prideCatalog as catalog
except ImportError:  # the stub loads server/ as plain modules
    import prideCatalog as catalog

LIMITS = {"programs": 20, "routines": 14, "items": 30, "own": 200, "title": 60, "note": 1000, "name": 120,
          "steps": 50, "step": 1000, "sets": 20, "reps": 100, "weight": 2000, "seconds": 36000, "distance": 1000,
          "rest": 3600, "increment": 100}
UNITS = ("lb", "kg")
DISTANCE_UNITS = ("km", "mi", "m")
GOALS = ("strength", "muscle", "general")
WEEK_STARTS = ("mon", "sun")
INTRO_STATES = ("pending", "done", "skipped")
# Spec §6: the starter's rep ranges by goal, at 3 sets; new routine items use them too (plan decision 16).
REPS_BY_GOAL = {"strength": (5, 8), "muscle": (8, 12), "general": (10, 15)}
# Spec §3: the increments' defaults in each unit; a switch of units resets them (plan decision 4).
INCREMENT_DEFAULTS = {"lb": (5.0, 10.0), "kg": (2.5, 5.0)}
TARGET_FIELDS = ("sets", "repsMin", "repsMax", "targetWeight", "targetUnit", "targetSeconds", "targetDistance",
                 "distanceUnit", "restSeconds", "note")
PROFILE_FIELDS = ("units", "goal", "daysPerWeek", "upperIncrement", "lowerIncrement", "weekStart", "introState",
                  "equipment")
# Which target fields each measure takes beyond sets, rest and note (spec §4: each measure only its own fields).
MEASURE_FIELDS = {
    "weight_reps": {"repsMin", "repsMax", "targetWeight", "targetUnit"},
    "reps": {"repsMin", "repsMax", "targetWeight", "targetUnit"},
    "time": {"targetSeconds"},
    "distance_time": {"targetDistance", "distanceUnit", "targetSeconds"},
}


class Refusal(Exception):
    def __init__(self, field, message):
        super().__init__(f"{field}: {message}")
        self.field = field
        self.message = message


def _isInt(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _isNumber(value):
    return (_isInt(value) or isinstance(value, float)) and math.isfinite(value)


def _intIn(value, field, low, high):
    if not _isInt(value) or not low <= value <= high:
        raise Refusal(field, f"{field} must be a whole number from {low} to {high}")
    return value


def title(value, field="title"):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > LIMITS["title"]:
        raise Refusal(field, f"{field} must be 1 to {LIMITS['title']} characters")
    return value.strip()


def note(value, field="note"):
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > LIMITS["note"]:
        raise Refusal(field, f"{field} must be up to {LIMITS['note']} characters")
    return value.strip() or None


def weekdays(value, field="days"):
    if not isinstance(value, list) or not all(_isInt(d) and 0 <= d <= 6 for d in value) or len(set(value)) != len(value):
        raise Refusal(field, f"{field} must list distinct weekdays from 0 (Monday) to 6 (Sunday)")
    return sorted(value)


def idOf(value, field):
    if not _isInt(value) or value <= 0:
        raise Refusal(field, f"{field} must be an id")
    return value


def idList(value, field="order"):
    if not isinstance(value, list) or not all(_isInt(v) and v > 0 for v in value) or len(set(value)) != len(value):
        raise Refusal(field, f"{field} must list ids, each once")
    return value


def isoDate(value, field="date"):
    try:
        # date.fromisoformat also reads week dates such as 2026-W46-1 (Python 3.11+); only YYYY-MM-DD is the contract.
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError
        return date.fromisoformat(value)
    except ValueError:
        raise Refusal(field, f"{field} must be a date written YYYY-MM-DD") from None


def _increment(value, field):
    if not _isNumber(value) or not 0 < value <= LIMITS["increment"] or abs(value * 4 - round(value * 4)) > 1e-9:
        raise Refusal(field, f"{field} must be from 0.25 to {LIMITS['increment']} in steps of 0.25")
    return float(value)


def profileChanges(body, currentUnits):
    """The profile columns a PUT /profile changes, by their API names. Switching units without sending increments
    resets both to that unit's defaults (plan decision 4)."""
    if not isinstance(body, dict) or not body:
        raise Refusal("profile", "send at least one profile field")
    for key in body:
        if key not in PROFILE_FIELDS:
            raise Refusal(key, f"{key} is not a profile field")
    changes = {}
    for key, allowed in (("units", UNITS), ("goal", GOALS), ("weekStart", WEEK_STARTS), ("introState", INTRO_STATES)):
        if key in body:
            if body[key] not in allowed:
                raise Refusal(key, f"{key} must be one of {', '.join(allowed)}")
            changes[key] = body[key]
    if "daysPerWeek" in body:
        changes["daysPerWeek"] = _intIn(body["daysPerWeek"], "daysPerWeek", 2, 6)
    for key in ("upperIncrement", "lowerIncrement"):
        if key in body:
            changes[key] = _increment(body[key], key)
    if "equipment" in body:
        given = body["equipment"]
        if (not isinstance(given, list) or not all(w in catalog.EQUIPMENT for w in given)
                or len(set(given)) != len(given)):
            raise Refusal("equipment", "equipment must list known equipment, each once")
        changes["equipment"] = [w for w in catalog.EQUIPMENT if w in given]
    if changes.get("units", currentUnits) != currentUnits:
        upper, lower = INCREMENT_DEFAULTS[changes["units"]]
        changes.setdefault("upperIncrement", upper)
        changes.setdefault("lowerIncrement", lower)
    return changes


def itemDefaults(measure, goal, units):
    """A new routine item's targets (plan decision 16): the goal's rep range at 3 sets, 3 × 30 s for time, one set
    with nothing set for distance and time. No target weight: the person finds their own."""
    values = dict.fromkeys(TARGET_FIELDS)
    if measure in ("weight_reps", "reps"):
        low, high = REPS_BY_GOAL.get(goal, REPS_BY_GOAL["general"])
        values.update(sets=3, repsMin=low, repsMax=high)
    elif measure == "time":
        values.update(sets=3, targetSeconds=30)
    else:
        values.update(sets=1)
    return values


def itemTargets(measure, values):
    """Every target field of a routine item, checked for its exercise's measure; absent ones are None. A field the
    measure doesn't take must be absent or null (spec §4)."""
    if measure not in MEASURE_FIELDS:
        raise Refusal("measure", "the exercise's measure is not one Pride knows")
    own = MEASURE_FIELDS[measure]
    get = {k: values.get(k) for k in TARGET_FIELDS}
    for key in TARGET_FIELDS:
        if key not in own and key not in ("sets", "restSeconds", "note") and get[key] is not None:
            raise Refusal(key, f"{key} is not a target for this exercise")
    clean = dict.fromkeys(TARGET_FIELDS)
    clean["sets"] = _intIn(get["sets"], "sets", 1, LIMITS["sets"])
    if get["restSeconds"] is not None:
        clean["restSeconds"] = _intIn(get["restSeconds"], "restSeconds", 0, LIMITS["rest"])
    clean["note"] = note(get["note"])
    if "repsMin" in own:
        clean["repsMin"] = _intIn(get["repsMin"], "repsMin", 1, LIMITS["reps"])
        clean["repsMax"] = _intIn(get["repsMax"], "repsMax", 1, LIMITS["reps"])
        if clean["repsMin"] > clean["repsMax"]:
            raise Refusal("repsMax", "repsMax must be at least repsMin")
    if "targetWeight" in own:
        weight, unit = get["targetWeight"], get["targetUnit"]
        if weight is not None and (not _isNumber(weight) or not 0 <= weight <= LIMITS["weight"]):
            raise Refusal("targetWeight", f"targetWeight must be from 0 to {LIMITS['weight']}")
        if unit is not None and unit not in UNITS:
            raise Refusal("targetUnit", "targetUnit must be lb or kg")
        if weight is not None and unit is None:
            raise Refusal("targetUnit", "a target weight needs its unit")
        if unit is not None and weight is None:
            raise Refusal("targetWeight", "a unit needs a target weight")
        clean["targetWeight"] = None if weight is None else round(float(weight), 2)
        clean["targetUnit"] = unit
    if measure == "time":
        clean["targetSeconds"] = _intIn(get["targetSeconds"], "targetSeconds", 1, LIMITS["seconds"])
    if measure == "distance_time":
        distance, unit = get["targetDistance"], get["distanceUnit"]
        if distance is not None and (not _isNumber(distance) or not 0 < distance <= LIMITS["distance"]):
            raise Refusal("targetDistance", f"targetDistance must be above 0 and up to {LIMITS['distance']}")
        if unit is not None and unit not in DISTANCE_UNITS:
            raise Refusal("distanceUnit", "distanceUnit must be km, mi or m")
        if distance is not None and unit is None:
            raise Refusal("distanceUnit", "a target distance needs its unit")
        if unit is not None and distance is None:
            raise Refusal("targetDistance", "a unit needs a target distance")
        clean["targetDistance"] = None if distance is None else round(float(distance), 2)
        clean["distanceUnit"] = unit
        if get["targetSeconds"] is not None:
            clean["targetSeconds"] = _intIn(get["targetSeconds"], "targetSeconds", 1, LIMITS["seconds"])
    return clean


def _known(value, allowed):
    return isinstance(value, list) and all(isinstance(v, str) and v in allowed for v in value) and len(set(value)) == len(value)


def ownExercise(body):
    """A person's own exercise (spec §6: name, equipment, muscles, measure, optional steps), with its region."""
    if not isinstance(body, dict):
        raise Refusal("exercise", "send the exercise as an object")
    name = body.get("name")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > LIMITS["name"]:
        raise Refusal("name", f"name must be 1 to {LIMITS['name']} characters")
    if body.get("measure") not in catalog.MEASURES:
        raise Refusal("measure", f"measure must be one of {', '.join(catalog.MEASURES)}")
    primary = body.get("primary")
    if not _known(primary, catalog.MUSCLES) or not primary:
        raise Refusal("primary", "primary must list known muscles, at least one, each once")
    secondary = body.get("secondary") or []
    if not _known(secondary, catalog.MUSCLES) or set(primary) & set(secondary):
        raise Refusal("secondary", "secondary must list known muscles, each once, none already primary")
    equipment = body.get("equipment")
    if not _known(equipment, catalog.EQUIPMENT) or not equipment:
        raise Refusal("equipment", "equipment must list known equipment, at least one, each once")
    steps = body.get("steps") or []
    if (not isinstance(steps, list) or len(steps) > LIMITS["steps"]
            or not all(isinstance(s, str) and s.strip() and len(s) <= LIMITS["step"] for s in steps)):
        raise Refusal("steps", f"steps must be up to {LIMITS['steps']} texts of 1 to {LIMITS['step']} characters")
    return {"name": name.strip(), "measure": body["measure"], "primary": primary, "secondary": secondary,
            "equipment": [w for w in catalog.EQUIPMENT if w in equipment], "steps": [s.strip() for s in steps],
            "region": catalog.regionOf(primary)}
