"""
The SQL milestone 3's routes share (prideLogRoutes.py, and /today in prideUserRoutes.py): a person's logged sets as
flat rows for prideRules, a routine's items with last time and their open suggestion, the active program's rotation,
and recalculating items' suggestions after a workout that logged them changed (spec §5). It reads and writes only;
every rule is prideRules'. No Flask here. The f-strings only ever hold placeholders ("%s, %s"), never caller text.
"""
from . import prideRules as rules

ROW_QUERY = ("SELECT w.WorkoutID, w.PerformedOn, w.CreatedAt, we.ExerciseID, we.ItemID, we.OrderIndex, s.SetNo, "
             "s.IsWarmup, s.Weight, s.WeightUnit, s.Reps, s.Seconds, s.Distance, s.DistanceUnit "
             "FROM Workouts w JOIN WorkoutExercises we ON we.WorkoutID = w.WorkoutID "
             "JOIN WorkoutSets s ON s.WorkoutExerciseID = we.WorkoutExerciseID WHERE w.UserID = %s")
ITEM_QUERY = ("SELECT i.ItemID, i.RoutineID, i.ExerciseID, i.Sets, i.RepsMin, i.RepsMax, i.TargetWeight, "
              "i.TargetUnit, i.TargetSeconds, i.TargetDistance, i.DistanceUnit, i.RestSeconds, i.Note, e.Measure, "
              "e.Region FROM RoutineItems i JOIN Exercises e ON e.ExerciseID = i.ExerciseID")
SUGGESTION_QUERY = ("SELECT SuggestionID, ItemID, Kind, ProposedWeight, ProposedUnit, ProposedRepsMin, "
                    "ProposedRepsMax, ProposedSeconds, BasedOnWorkoutID, State FROM Suggestions")
PROFILE_DEFAULTS = {"Units": "lb", "UpperIncrement": 5, "LowerIncrement": 10}


def _decimal(value):
    return None if value is None else float(value)


def _marks(ids):
    return ", ".join(["%s"] * len(ids))


def itemJson(row):
    """A routine item as the API shows it (docs/api.md Programs); absent targets are null."""
    return {"id": row["ItemID"], "exerciseId": row["ExerciseID"], "sets": row["Sets"], "repsMin": row["RepsMin"],
            "repsMax": row["RepsMax"], "targetWeight": _decimal(row["TargetWeight"]),
            "targetUnit": row["TargetUnit"], "targetSeconds": row["TargetSeconds"],
            "targetDistance": _decimal(row["TargetDistance"]), "distanceUnit": row["DistanceUnit"],
            "restSeconds": row["RestSeconds"], "note": row["Note"]}


def suggestionJson(row):
    return {"id": row["SuggestionID"], "itemId": row["ItemID"], "kind": row["Kind"],
            "weight": _decimal(row["ProposedWeight"]), "unit": row["ProposedUnit"],
            "repsMin": row["ProposedRepsMin"], "repsMax": row["ProposedRepsMax"], "seconds": row["ProposedSeconds"],
            "basedOn": row["BasedOnWorkoutID"], "state": row["State"]}


def rowOf(r):
    return {"workoutId": r["WorkoutID"], "performedOn": r["PerformedOn"], "createdAt": r["CreatedAt"],
            "exerciseId": r["ExerciseID"], "itemId": r["ItemID"], "order": r["OrderIndex"], "setNo": r["SetNo"],
            "warmup": bool(r["IsWarmup"]), "weight": _decimal(r["Weight"]), "weightUnit": r["WeightUnit"],
            "reps": r["Reps"], "seconds": r["Seconds"], "distance": _decimal(r["Distance"]),
            "distanceUnit": r["DistanceUnit"]}


def rows(cur, uid, exerciseIds=None, itemIds=None):
    """The person's logged sets as prideRules' rows, in time order; narrowed to some exercises or routine items."""
    sql, params = ROW_QUERY, [uid]
    for column, ids in (("we.ExerciseID", exerciseIds), ("we.ItemID", itemIds)):
        if ids is not None:
            ids = sorted({i for i in ids if i is not None})
            if not ids:
                return []
            sql += f" AND {column} IN ({_marks(ids)})"
            params += ids
    cur.execute(sql + " ORDER BY w.PerformedOn, w.CreatedAt, w.WorkoutID, we.OrderIndex, s.SetNo", tuple(params))
    return [rowOf(r) for r in cur.fetchall()]


def measuresFor(cur, uid, exerciseIds, workoutId=None):
    """The measures of the exercises a workout may log (plan decision 6): the catalog's and the person's own, not
    hidden, or (editing) already in that workout."""
    ids = sorted(set(exerciseIds))
    if not ids:
        return {}
    shown = "RemovedAt IS NULL" if workoutId is None else \
        "(RemovedAt IS NULL OR ExerciseID IN (SELECT ExerciseID FROM WorkoutExercises WHERE WorkoutID = %s))"
    cur.execute(f"SELECT ExerciseID, Measure FROM Exercises WHERE ExerciseID IN ({_marks(ids)}) "
                f"AND (OwnerUserID IS NULL OR OwnerUserID = %s) AND {shown}",
                (*ids, uid) + (() if workoutId is None else (workoutId,)))
    return {r["ExerciseID"]: r["Measure"] for r in cur.fetchall()}


def measuresOf(cur, exerciseIds):
    """The measures of exercises already logged; history keeps an exercise however hidden it is now (spec §8)."""
    ids = sorted(set(exerciseIds))
    if not ids:
        return {}
    cur.execute(f"SELECT ExerciseID, Measure FROM Exercises WHERE ExerciseID IN ({_marks(ids)})", tuple(ids))
    return {r["ExerciseID"]: r["Measure"] for r in cur.fetchall()}


def itemsOf(cur, routineId):
    cur.execute(ITEM_QUERY + " WHERE i.RoutineID = %s ORDER BY i.OrderIndex, i.ItemID", (routineId,))
    return cur.fetchall()


def openSuggestions(cur, uid, itemIds):
    ids = sorted({i for i in itemIds if i is not None})
    if not ids:
        return {}
    cur.execute(SUGGESTION_QUERY + f" WHERE UserID = %s AND State = 'open' AND ItemID IN ({_marks(ids)}) "
                "ORDER BY SuggestionID", (uid, *ids))
    return {r["ItemID"]: suggestionJson(r) for r in cur.fetchall()}


def draftItem(row, logged, suggestions):
    """An item as Today and the draft show it: its targets, measure, last time (plan decision 8) and open
    suggestion."""
    return {**itemJson(row), "measure": row["Measure"],
            "last": rules.lastFor(row["ItemID"], row["ExerciseID"], logged),
            "suggestion": suggestions.get(row["ItemID"])}


def draftItems(cur, uid, routineId):
    items = itemsOf(cur, routineId)
    if not items:
        return []
    suggestions = openSuggestions(cur, uid, [i["ItemID"] for i in items])
    logged = rows(cur, uid, exerciseIds=[i["ExerciseID"] for i in items])
    return [draftItem(i, logged, suggestions) for i in items]


def rotation(cur, uid):
    """The active program, its routines in rotation order and the routine next up (spec §5); (None, [], None)
    with no active program."""
    cur.execute("SELECT ProgramID, Title FROM Programs WHERE UserID = %s AND IsActive = 1 LIMIT 1", (uid,))
    program = cur.fetchone()
    if program is None:
        return None, [], None
    cur.execute("SELECT RoutineID, Title FROM Routines WHERE ProgramID = %s ORDER BY OrderIndex, RoutineID",
                (program["ProgramID"],))
    routines = cur.fetchall()
    cur.execute("SELECT RoutineID FROM Workouts WHERE UserID = %s AND ProgramID = %s "
                "ORDER BY PerformedOn DESC, CreatedAt DESC, WorkoutID DESC LIMIT 1", (uid, program["ProgramID"]))
    latest = (cur.fetchone() or {}).get("RoutineID")
    return program, routines, rules.nextUp([r["RoutineID"] for r in routines], latest)


def nextUpJson(program, routines, nextId):
    if nextId is None:
        return None
    return {"routineId": nextId, "title": next(r["Title"] for r in routines if r["RoutineID"] == nextId)}


def unitsOf(cur, uid):
    cur.execute("SELECT Units FROM Profiles WHERE UserID = %s", (uid,))
    return (cur.fetchone() or PROFILE_DEFAULTS)["Units"]


def _ruleItem(row):
    return {"id": row["ItemID"], "measure": row["Measure"], "region": row["Region"], "sets": row["Sets"],
            "repsMin": row["RepsMin"], "repsMax": row["RepsMax"], "targetWeight": _decimal(row["TargetWeight"]),
            "targetUnit": row["TargetUnit"], "targetSeconds": row["TargetSeconds"]}


def recalculate(cur, uid, itemIds):
    """Settles the suggestions of these routine items after a workout that logged them was saved, edited or deleted
    (spec §5): each item's targets, the profile's increments, the item's logged sets and its suggestions go to
    prideRules.suggestionFor, and what it says is written. An item that is gone, or not the person's, is left
    alone. The suggestion rows are locked, so two saves for one item settle one after the other."""
    ids = sorted({i for i in itemIds if i})
    if not ids:
        return
    cur.execute(ITEM_QUERY + " JOIN Routines r ON r.RoutineID = i.RoutineID JOIN Programs p ON p.ProgramID = r.ProgramID "
                f"WHERE p.UserID = %s AND i.ItemID IN ({_marks(ids)})", (uid, *ids))
    items = cur.fetchall()
    if not items:
        return
    found = [i["ItemID"] for i in items]
    cur.execute("SELECT Units, UpperIncrement, LowerIncrement FROM Profiles WHERE UserID = %s", (uid,))
    p = cur.fetchone() or PROFILE_DEFAULTS
    profile = {"units": p["Units"], "upperIncrement": float(p["UpperIncrement"]),
               "lowerIncrement": float(p["LowerIncrement"])}
    logged = rows(cur, uid, itemIds=found)
    cur.execute(SUGGESTION_QUERY + f" WHERE UserID = %s AND ItemID IN ({_marks(found)}) FOR UPDATE", (uid, *found))
    existing = [suggestionJson(r) for r in cur.fetchall()]
    for item in items:
        withdraw, create = rules.suggestionFor(_ruleItem(item), [r for r in logged if r["itemId"] == item["ItemID"]],
                                               profile, [s for s in existing if s["itemId"] == item["ItemID"]])
        for suggestionId in withdraw:
            cur.execute("UPDATE Suggestions SET State = 'withdrawn' WHERE SuggestionID = %s", (suggestionId,))
        if create is not None:
            cur.execute("INSERT INTO Suggestions (UserID, ItemID, Kind, ProposedWeight, ProposedUnit, ProposedRepsMin, "
                        "ProposedRepsMax, ProposedSeconds, BasedOnWorkoutID) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (uid, item["ItemID"], create["kind"], create["weight"], create["unit"], create["repsMin"],
                         create["repsMax"], create["seconds"], create["basedOn"]))
