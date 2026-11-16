"""
Pride's rules (spec §5), run on the server so the desktop and iOS always agree. Plain functions over plain values, no
Flask and no database, each table-tested in tests/test_rules.py. Milestone 2 has the planning rules (next up, the next
planned day, the week strip); milestone 3 adds records, crowns, chart series and suggestions, over flat rows of
logged sets. The stub imports this file too.
Weekdays are 0 = Monday … 6 = Sunday, as date.weekday() and ProgramDays have them.
"""
import math
from datetime import timedelta


def nextUp(routineIds, latestRoutineId):
    """The routine after the latest workout's (by rotation order, wrapping round); the first with no workouts yet
    or when that routine is gone; None when the program has no routines."""
    if not routineIds:
        return None
    if latestRoutineId in routineIds:
        return routineIds[(routineIds.index(latestRoutineId) + 1) % len(routineIds)]
    return routineIds[0]


def plannedDay(today, weekdays, loggedToday):
    """The first planned weekday from today; today counts unless a workout is already logged today. None with no
    planned days. A missed day is never looked at."""
    for offset in range(1 if loggedToday else 0, 8):
        day = today + timedelta(days=offset)
        if day.weekday() in weekdays:
            return day
    return None


def weekStartDate(today, weekStart):
    back = today.weekday() if weekStart == "mon" else (today.weekday() + 1) % 7
    return today - timedelta(days=back)


def week(today, weekStart, weekdays, doneDates):
    """The 7 days of the week holding today (plan decision 22): done from any workout that day; planned only today
    and later, and never on a done day, so a past planned day with no workout shows nothing."""
    first = weekStartDate(today, weekStart)
    days = []
    for n in range(7):
        day = first + timedelta(days=n)
        done = day in doneDates
        days.append({"date": day.isoformat(), "weekday": day.weekday(), "done": done,
                     "planned": not done and day >= today and day.weekday() in weekdays})
    return days


# ---- Units (spec §5: comparisons convert to kg internally; shown as entered) ----

LB_IN_KG = 0.45359237
KM_IN = {"km": 1.0, "mi": 1.609344, "m": 0.001}


def toKg(weight, unit):
    return None if weight is None else float(weight) * (LB_IN_KG if unit == "lb" else 1.0)


def fromKg(kg, unit):
    return kg / LB_IN_KG if unit == "lb" else kg


def toKm(distance, unit):
    return None if distance is None else float(distance) * KM_IN[unit]


def epley(weight, reps):
    """The estimated one-rep max (spec §5: Epley, w × (1 + r/30), for sets of 12 reps or fewer); None otherwise."""
    if not weight or not reps or reps > 12:
        return None
    return weight * (1 + reps / 30)


def _round(value, places=1):
    return None if value is None else round(value, places)


# ---- Rows: one logged set each, with its workout's place in time ----

def when(row):
    """A row's place in time: by date, then by when it was saved, then by id (spec §5's "latest")."""
    return (row["performedOn"], row["createdAt"], row["workoutId"])


def _iso(day):
    return day.isoformat() if hasattr(day, "isoformat") else day


def _inOrder(rows):
    return sorted(rows, key=lambda r: (when(r), r["order"], r["setNo"]))


def setJson(row):
    return {"warmup": bool(row["warmup"]), "weight": row["weight"], "weightUnit": row["weightUnit"],
            "reps": row["reps"], "seconds": row["seconds"], "distance": row["distance"],
            "distanceUnit": row["distanceUnit"]}


def _byWorkout(rows):
    """The rows grouped by workout, oldest first; each group's sets in order."""
    groups = {}
    for r in _inOrder(rows):
        groups.setdefault(r["workoutId"], []).append(r)
    return list(groups.values())


# ---- Records and crowns (plan decisions 10-12) ----

RECORD_KINDS = {"weight_reps": ("heaviest", "e1rm"), "reps": ("reps", "heaviest"), "time": ("time",),
                "distance_time": ("distance", "pace")}


def setValue(kind, row):
    """A working set's value for one kind of record, comparable across units (bigger is better); None when the set
    has none. Pace is minus the seconds a km, so the fastest is the biggest."""
    if row["warmup"]:
        return None
    if kind == "heaviest":
        return toKg(row["weight"], row["weightUnit"]) if row["weight"] else None
    if kind == "e1rm":
        return epley(toKg(row["weight"], row["weightUnit"]), row["reps"])
    if kind == "reps":
        return row["reps"] or None
    if kind == "time":
        return row["seconds"] or None
    if kind == "distance":
        return toKm(row["distance"], row["distanceUnit"]) if row["distance"] else None
    if kind == "pace":
        km = toKm(row["distance"], row["distanceUnit"]) if row["distance"] else None
        return -row["seconds"] / km if km and row["seconds"] else None
    raise ValueError(kind)


def _best(rows, kind):
    """(value, row) of the best set for one kind, or None; on a tie the earlier set keeps it (plan decision 11)."""
    top = None
    for r in _inOrder(rows):
        value = setValue(kind, r)
        if value is not None and (top is None or value > top[0] + 1e-9):
            top = (value, r)
    return top


def _recordJson(kind, row, units):
    out = {"kind": kind, "workoutId": row["workoutId"], "performedOn": _iso(row["performedOn"]), **setJson(row),
           "estimate": None, "estimateUnit": None}
    del out["warmup"]
    if kind == "e1rm":
        out["estimate"] = _round(fromKg(epley(toKg(row["weight"], row["weightUnit"]), row["reps"]), units))
        out["estimateUnit"] = units
    return out


def records(rows, measure, units):
    """One exercise's records (spec §5), in RECORD_KINDS order, each shown as its set was entered."""
    found = []
    for kind in RECORD_KINDS[measure]:
        top = _best(rows, kind)
        if top is not None:
            found.append(_recordJson(kind, top[1], units))
    return found


def crownsOf(workoutId, rows, measures, units):
    """The New crowns a workout earned (plan decision 12): for each exercise it logged and each kind of record, its
    best set beats every set logged before it. Before means an earlier place in time, so an edit of an old workout
    is judged against what came before it, never after. An exercise's first workout has nothing to beat."""
    mine = [r for r in rows if r["workoutId"] == workoutId]
    if not mine:
        return []
    place = when(mine[0])
    crowns = []
    for exerciseId in dict.fromkeys(r["exerciseId"] for r in sorted(mine, key=lambda r: (r["order"], r["setNo"]))):
        here = [r for r in mine if r["exerciseId"] == exerciseId]
        before = [r for r in rows if r["exerciseId"] == exerciseId and when(r) < place]
        if not before:
            continue
        for kind in RECORD_KINDS[measures[exerciseId]]:
            top, prior = _best(here, kind), _best(before, kind)
            if top is not None and prior is not None and top[0] > prior[0] + 1e-9:
                crowns.append({"exerciseId": exerciseId, **_recordJson(kind, top[1], units)})
    return crowns


def latestCrowns(rows, measures, units, limit=3):
    """Today's crowns row (spec §6): the latest crowns, newest workout first."""
    found = []
    for group in reversed(_byWorkout(rows)):
        found += crownsOf(group[0]["workoutId"], rows, measures, units)
        if len(found) >= limit:
            break
    return found[:limit]


def recordsByExercise(rows, measures, units):
    """Every logged exercise's records (GET /records), the most recently logged first."""
    last = {}
    for r in rows:
        if r["exerciseId"] not in last or when(r) > last[r["exerciseId"]]:
            last[r["exerciseId"]] = when(r)
    order = sorted(last, key=lambda e: (last[e], e), reverse=True)
    return [{"exerciseId": e, "measure": measures[e], "lastOn": _iso(last[e][0]),
             "records": records([r for r in rows if r["exerciseId"] == e], measures[e], units)} for e in order]


# ---- Charts (plan decision 13) ----

BEST_KIND = {"weight_reps": "heaviest", "reps": "reps", "time": "time", "distance_time": "distance"}


def _chartValue(measure, row, units):
    """The best set's value on the chart, in the person's units: a weight, reps, seconds, or km (mi with lb)."""
    if measure == "weight_reps":
        return _round(fromKg(toKg(row["weight"], row["weightUnit"]), units))
    if measure == "reps":
        return row["reps"]
    if measure == "time":
        return row["seconds"]
    km = toKm(row["distance"], row["distanceUnit"])
    return _round(km / KM_IN["mi"] if units == "lb" else km, 2)


def series(rows, measure, units):
    """One exercise's chart points, a point a workout, oldest first (spec §4: best set, estimated one-rep max,
    volume), each naming the records it set."""
    points = []
    for group in _byWorkout(rows):
        workoutId = group[0]["workoutId"]
        working = [r for r in group if not r["warmup"]]
        top = _best(group, BEST_KIND[measure])
        estimates = [e for e in (epley(toKg(r["weight"], r["weightUnit"]), r["reps"]) for r in working) if e]
        weighed = [r for r in working if r["weight"] and r["reps"]]
        volume = sum(fromKg(toKg(r["weight"], r["weightUnit"]), units) * r["reps"] for r in weighed)
        crowned = crownsOf(workoutId, rows, {group[0]["exerciseId"]: measure}, units)
        points.append({"workoutId": workoutId, "performedOn": _iso(group[0]["performedOn"]),
                       "value": _chartValue(measure, top[1], units) if top else None,
                       "best": setJson(top[1]) if top else None,
                       "estimate": _round(fromKg(max(estimates), units)) if estimates else None,
                       "volume": _round(volume) if weighed and measure in ("weight_reps", "reps") else None,
                       "crowns": [c["kind"] for c in crowned]})
    return points


# ---- Last time (spec §6: rows filled from last time; plan decision 8) ----

def _logging(rows, latest):
    """The sets of the one logging (workout and place in it) that `latest` belongs to."""
    return [setJson(r) for r in sorted(rows, key=lambda r: r["setNo"])
            if r["workoutId"] == latest["workoutId"] and r["order"] == latest["order"]]


def lastFor(itemId, exerciseId, rows):
    """The latest logging of this routine item or, failing that, of this exercise."""
    pick = [r for r in rows if itemId is not None and r["itemId"] == itemId] or \
           [r for r in rows if r["exerciseId"] == exerciseId]
    if not pick:
        return None
    latest = max(pick, key=lambda r: (when(r), r["order"]))
    return {"workoutId": latest["workoutId"], "performedOn": _iso(latest["performedOn"]),
            "sets": _logging(pick, latest)}


def recent(rows, limit=5):
    """One exercise's latest loggings, newest first (the Exercise page's history)."""
    found = []
    for group in reversed(_byWorkout(rows)):
        latest = max(group, key=lambda r: r["order"])
        found.append({"workoutId": latest["workoutId"], "performedOn": _iso(latest["performedOn"]),
                      "sets": _logging(group, latest)})
        if len(found) == limit:
            break
    return found


# ---- Suggestions (spec §5; plan decisions 14-18) ----

STEP = {"lb": 5.0, "kg": 2.5}
MAX_WEIGHT = 2000
PROPOSAL_FIELDS = ("weight", "unit", "repsMin", "repsMax", "seconds")


def roundToStep(value, unit):
    """To the nearest loadable step (spec §5: 5 lb or 2.5 kg); a half step goes up."""
    step = STEP[unit]
    return math.floor(value / step + 0.5) * step


def increase(item, sets, profile):
    """The step-up the item's latest workout earned (spec §5), as the proposed targets, or None. `sets` are that
    workout's rows for the item."""
    working = [s for s in sets if not s["warmup"]]
    if len(working) < item["sets"]:
        return None                                   # plan decision 14: a full session
    measure = item["measure"]
    if measure == "time":
        target = item["targetSeconds"]
        if target and all((s["seconds"] or 0) >= target for s in working):
            return {"seconds": min(target + 10, 36000)}
        return None
    if measure not in ("weight_reps", "reps"):
        return None                                   # distance and time: none in part 1
    top = item["repsMax"]
    if top is None or not all((s["reps"] or 0) >= top for s in working):
        return None
    weighted = measure == "weight_reps" or item["targetWeight"] is not None or all(s["weight"] for s in working)
    if not weighted:
        low, high = min(item["repsMin"] + 2, 100), min(top + 2, 100)
        return None if high == top else {"repsMin": low, "repsMax": high}
    if any(s["weight"] is None for s in working):
        return None
    if item["targetWeight"] is not None:
        base, unit = float(item["targetWeight"]), item["targetUnit"]
        if not all(toKg(s["weight"], s["weightUnit"]) >= toKg(base, unit) - 1e-6 for s in working):
            return None
    else:
        lightest = min(working, key=lambda s: toKg(s["weight"], s["weightUnit"]))
        base, unit = float(lightest["weight"]), lightest["weightUnit"]
    step = profile["upperIncrement"] if item["region"] in ("upper", "full") else profile["lowerIncrement"]
    if profile["units"] != unit:
        step = fromKg(toKg(step, profile["units"]), unit)
    proposed = roundToStep(base + step, unit)
    if proposed <= base + 1e-9:
        # Plan decision 15: always at least one step above the base, however small the increment.
        proposed = (math.floor(base / STEP[unit] + 1e-9) + 1) * STEP[unit]
    return None if proposed > MAX_WEIGHT else {"weight": float(proposed), "unit": unit}


def bestValue(measure, sets):
    """A workout's best for the stall rule (plan decision 18): the estimated one-rep max (the heaviest set when no
    set has 12 reps or fewer), reps, or seconds; None for distance and time, or when nothing counts."""
    working = [s for s in sets if not s["warmup"]]
    if measure == "weight_reps":
        estimates = [e for e in (epley(toKg(s["weight"], s["weightUnit"]), s["reps"]) for s in working) if e]
        heaviest = [toKg(s["weight"], s["weightUnit"]) for s in working if s["weight"]]
        return max(estimates) if estimates else (max(heaviest) if heaviest else None)
    if measure in ("reps", "time"):
        values = [v for v in (s["reps" if measure == "reps" else "seconds"] for s in working) if v]
        return max(values) if values else None
    return None


def stalled(values):
    """The last three workouts brought nothing above the best before them (spec §5); needs one before them."""
    if len(values) < 4:
        return False
    prior = [v for v in values[:-3] if v is not None]
    if not prior:
        return False
    recent = [v for v in values[-3:] if v is not None]
    return not recent or max(recent) <= max(prior) + 1e-9


def lastImprovement(values):
    """The index of the latest workout that beat everything before it (the first measured one counts); -1 for
    none."""
    found, best = -1, None
    for index, value in enumerate(values):
        if value is not None and (best is None or value > best + 1e-9):
            found, best = index, value
    return found


def _same(existing, wanted):
    if existing["kind"] != wanted["kind"] or existing["basedOn"] != wanted["basedOn"]:
        return False
    for key in PROPOSAL_FIELDS:
        a, b = existing.get(key), wanted.get(key)
        if (a is None) != (b is None):
            return False
        if a is not None and a != b and (isinstance(a, str) or abs(float(a) - float(b)) > 1e-6):
            return False
    return True


def suggestionFor(item, rows, profile, existing):
    """What the item's suggestions become after its history changed (spec §5's lifecycle, plan decisions 17-18):
    (the ids of open suggestions to withdraw, the suggestion to add or None). `rows` are the item's logged sets,
    `existing` its suggestions in every state."""
    workouts = _byWorkout(rows)
    wanted = None
    if workouts:
        ids = [group[0]["workoutId"] for group in workouts]
        latestId = ids[-1]
        step = increase(item, workouts[-1], profile)
        if step is not None:
            settled = any(s["kind"] == "increase" and s["basedOn"] == latestId
                          and s["state"] in ("dismissed", "accepted") for s in existing)
            if not settled:
                wanted = {"kind": "increase", "basedOn": latestId, **dict.fromkeys(PROPOSAL_FIELDS), **step}
        else:
            values = [bestValue(item["measure"], group) for group in workouts]
            if stalled(values):
                since = lastImprovement(values)
                raised = [s for s in existing if s["kind"] == "stall" and s["state"] != "withdrawn"
                          and s["basedOn"] in ids and ids.index(s["basedOn"]) > since]
                kept = next((s for s in raised if s["state"] == "open"), None)
                if kept is not None:
                    wanted = {"kind": "stall", "basedOn": kept["basedOn"], **dict.fromkeys(PROPOSAL_FIELDS)}
                elif not raised:
                    wanted = {"kind": "stall", "basedOn": latestId, **dict.fromkeys(PROPOSAL_FIELDS)}
    openOnes = [s for s in existing if s["state"] == "open"]
    keep = next((s for s in openOnes if wanted is not None and _same(s, wanted)), None)
    withdraw = [s["id"] for s in openOnes if s is not keep]
    return withdraw, (None if keep is not None or wanted is None else wanted)
