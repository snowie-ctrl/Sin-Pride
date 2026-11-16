"""
Logging and progress, at /api/pride beside prideRoutes.py and prideUserRoutes.py (spec §4; plan decisions 21-22):
the routines a workout can follow, a routine's draft, workouts (enter, edit, delete, the history) with the result
card, progress and records, and taking or dismissing suggestions. It installs the same session check. Checks are
prideChecks', rules prideRules', the shared SQL prideHistory's; this file only reads and writes. Refusals follow
prideUserRoutes: 400 naming the field, 404 for someone else's id. docs/api.md is the contract.
"""
from datetime import date, timedelta

from flask import Blueprint, jsonify, request

from . import (prideChecks as checks, prideHistory as history, prideRules as rules, prideSession as session,
               prideUserRoutes as user)

prideLogBP = Blueprint("prideLog", __name__)
session.install(prideLogBP)
database = session.database
ok, refuse, notFound, body, lockPerson = user.ok, user.refuse, user.notFound, user.body, user.lockPerson


def latestDay():
    """Spec §4: PerformedOn is not later than tomorrow, by the server's own date, so a person whose day is ahead of
    the server's can still log their today."""
    return date.today() + timedelta(days=1)


def _marks(ids):
    return ", ".join(["%s"] * len(ids))


def _decimal(value):
    return None if value is None else float(value)


# ---- The routines menu and a routine's draft (plan decisions 8, 22) ----

@prideLogBP.route("/routines", methods=["GET"])
def listRoutines():
    uid = session.requestUID()
    with database() as (conn, cur):
        cur.execute("SELECT r.RoutineID, r.Title, p.ProgramID, p.Title AS ProgramTitle, p.IsActive FROM Routines r "
                    "JOIN Programs p ON p.ProgramID = r.ProgramID WHERE p.UserID = %s "
                    "ORDER BY p.IsActive DESC, p.CreatedAt, p.ProgramID, r.OrderIndex, r.RoutineID", (uid,))
        return ok([{"id": r["RoutineID"], "title": r["Title"], "programId": r["ProgramID"],
                    "programTitle": r["ProgramTitle"], "active": bool(r["IsActive"])} for r in cur.fetchall()])


@prideLogBP.route("/workouts/draft", methods=["GET"])
def draft():
    uid = session.requestUID()
    try:
        routineId = checks.idOf(request.args.get("routineId", type=int), "routineId")
    except checks.Refusal as refusal:
        return refuse(refusal)
    with database() as (conn, cur):
        cur.execute("SELECT r.RoutineID, r.Title, r.ProgramID FROM Routines r JOIN Programs p ON p.ProgramID = r.ProgramID "
                    "WHERE r.RoutineID = %s AND p.UserID = %s", (routineId, uid))
        routine = cur.fetchone()
        if routine is None:
            return notFound()
        return ok({"routineId": routineId, "title": routine["Title"], "programId": routine["ProgramID"],
                   "items": history.draftItems(cur, uid, routineId)})


# ---- Workouts (spec §6 Log a workout; plan decisions 1-7) ----

WORKOUT_ROW = ("SELECT w.WorkoutID, w.ClientID, w.PerformedOn, w.StartedAt, w.EndedAt, w.ProgramID, w.RoutineID, "
               "r.Title, w.Note, w.CreatedAt, w.UpdatedAt FROM Workouts w LEFT JOIN Routines r ON r.RoutineID = w.RoutineID "
               "WHERE w.WorkoutID = %s AND w.UserID = %s")
WORKOUT_SETS = ("SELECT we.WorkoutExerciseID, we.ExerciseID, we.ItemID, we.Note, e.Measure, s.SetNo, s.IsWarmup, "
                "s.Weight, s.WeightUnit, s.Reps, s.Seconds, s.Distance, s.DistanceUnit FROM WorkoutExercises we "
                "JOIN Exercises e ON e.ExerciseID = we.ExerciseID "
                "JOIN WorkoutSets s ON s.WorkoutExerciseID = we.WorkoutExerciseID "
                "WHERE we.WorkoutID = %s ORDER BY we.OrderIndex, we.WorkoutExerciseID, s.SetNo")


def readWorkout(cur, uid, workoutId):
    """The workout as stored, with its exercises and sets in order; None when it is not the person's."""
    cur.execute(WORKOUT_ROW, (workoutId, uid))
    w = cur.fetchone()
    if w is None:
        return None
    cur.execute(WORKOUT_SETS, (workoutId,))
    exercises = {}
    for r in cur.fetchall():
        e = exercises.setdefault(r["WorkoutExerciseID"], {"exerciseId": r["ExerciseID"], "itemId": r["ItemID"],
                                                         "measure": r["Measure"], "note": r["Note"], "sets": []})
        e["sets"].append({"warmup": bool(r["IsWarmup"]), "weight": _decimal(r["Weight"]), "weightUnit": r["WeightUnit"],
                          "reps": r["Reps"], "seconds": r["Seconds"], "distance": _decimal(r["Distance"]),
                          "distanceUnit": r["DistanceUnit"]})
    return {"id": w["WorkoutID"], "clientId": w["ClientID"], "performedOn": w["PerformedOn"].isoformat(),
            "startedAt": user.isoUtc(w["StartedAt"]), "endedAt": user.isoUtc(w["EndedAt"]),
            "programId": w["ProgramID"], "routineId": w["RoutineID"], "title": w["Title"], "note": w["Note"],
            "createdAt": user.isoUtc(w["CreatedAt"]), "updatedAt": user.isoUtc(w["UpdatedAt"]),
            "exercises": list(exercises.values())}


def answerSaved(conn, cur, uid, workoutId):
    """The result card (spec §6): the workout as stored, the crowns it earned (plan decision 12), the suggestions it
    raised, and next up after it. All worked out again on a resend, so a resend answers the same."""
    workout = readWorkout(cur, uid, workoutId)
    logged = history.rows(cur, uid, exerciseIds=[e["exerciseId"] for e in workout["exercises"]])
    units = history.unitsOf(cur, uid)
    measures = {e["exerciseId"]: e["measure"] for e in workout["exercises"]}
    crowns = rules.crownsOf(workoutId, logged, measures, units)
    cur.execute(history.SUGGESTION_QUERY + " WHERE UserID = %s AND BasedOnWorkoutID = %s AND State = 'open' "
                "ORDER BY SuggestionID", (uid, workoutId))
    raised = [history.suggestionJson(r) for r in cur.fetchall()]
    nextUp = history.nextUpJson(*history.rotation(cur, uid))
    conn.commit()
    return ok({"workout": workout, "crowns": crowns, "suggestions": raised, "nextUp": nextUp})


def askedExercises(data):
    """The exercise ids a body names, before it is checked, so their measures can be read in one query."""
    exercises = data.get("exercises")
    if not isinstance(exercises, list):
        return []
    return [e["exerciseId"] for e in exercises if isinstance(e, dict) and isinstance(e.get("exerciseId"), int)
            and not isinstance(e.get("exerciseId"), bool) and e["exerciseId"] > 0]


def routineOf(cur, uid, routineId):
    """The routine with its program when it is the person's; None otherwise (plan decision 5: a free workout)."""
    if routineId is None:
        return None
    cur.execute("SELECT r.RoutineID, r.ProgramID FROM Routines r JOIN Programs p ON p.ProgramID = r.ProgramID "
                "WHERE r.RoutineID = %s AND p.UserID = %s", (routineId, uid))
    return cur.fetchone()


def itemsOfPerson(cur, uid, itemIds):
    """{itemId: exerciseId} for the named routine items that are the person's."""
    ids = sorted({i for i in itemIds if i is not None})
    if not ids:
        return {}
    cur.execute("SELECT i.ItemID, i.ExerciseID FROM RoutineItems i JOIN Routines r ON r.RoutineID = i.RoutineID "
                f"JOIN Programs p ON p.ProgramID = r.ProgramID WHERE p.UserID = %s AND i.ItemID IN ({_marks(ids)})",
                (uid, *ids))
    return {r["ItemID"]: r["ExerciseID"] for r in cur.fetchall()}


def loggedItems(cur, workoutId):
    cur.execute("SELECT ItemID FROM WorkoutExercises WHERE WorkoutID = %s AND ItemID IS NOT NULL", (workoutId,))
    return [r["ItemID"] for r in cur.fetchall()]


def writeExercises(cur, workoutId, exercises, items):
    """Inserts the exercises and their sets in the order sent. An item that is not the person's, or names another
    exercise, is dropped to a plain exercise (plan decision 5). Returns the item ids that stayed."""
    kept = []
    for order, e in enumerate(exercises):
        itemId = e["itemId"] if e["itemId"] is not None and items.get(e["itemId"]) == e["exerciseId"] else None
        cur.execute("INSERT INTO WorkoutExercises (WorkoutID, ExerciseID, OrderIndex, ItemID, Note) "
                    "VALUES (%s, %s, %s, %s, %s)", (workoutId, e["exerciseId"], order, itemId, e["note"]))
        exerciseRow = cur.lastrowid
        for number, s in enumerate(e["sets"], start=1):
            cur.execute("INSERT INTO WorkoutSets (WorkoutExerciseID, SetNo, IsWarmup, Weight, WeightUnit, Reps, Seconds, "
                        "Distance, DistanceUnit) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (exerciseRow, number, int(s["warmup"]), s["weight"], s["weightUnit"], s["reps"], s["seconds"],
                         s["distance"], s["distanceUnit"]))
        if itemId is not None:
            kept.append(itemId)
    return kept


def ownedWorkout(cur, uid, workoutId):
    cur.execute("SELECT WorkoutID FROM Workouts WHERE WorkoutID = %s AND UserID = %s FOR UPDATE", (workoutId, uid))
    return cur.fetchone()


@prideLogBP.route("/workouts", methods=["GET"])
def listWorkouts():
    uid = session.requestUID()
    with database() as (conn, cur):
        cur.execute("SELECT w.WorkoutID, w.PerformedOn, w.RoutineID, r.Title, w.Note, w.UpdatedAt, "
                    "COUNT(DISTINCT we.WorkoutExerciseID) AS ExerciseCount, COUNT(s.SetNo) AS SetCount "
                    "FROM Workouts w LEFT JOIN Routines r ON r.RoutineID = w.RoutineID "
                    "LEFT JOIN WorkoutExercises we ON we.WorkoutID = w.WorkoutID "
                    "LEFT JOIN WorkoutSets s ON s.WorkoutExerciseID = we.WorkoutExerciseID WHERE w.UserID = %s "
                    "GROUP BY w.WorkoutID, w.PerformedOn, w.RoutineID, r.Title, w.Note, w.UpdatedAt, w.CreatedAt "
                    "ORDER BY w.PerformedOn DESC, w.CreatedAt DESC, w.WorkoutID DESC", (uid,))
        return ok([{"id": r["WorkoutID"], "performedOn": r["PerformedOn"].isoformat(), "routineId": r["RoutineID"],
                    "title": r["Title"], "note": r["Note"], "exerciseCount": r["ExerciseCount"],
                    "setCount": r["SetCount"], "updatedAt": user.isoUtc(r["UpdatedAt"])} for r in cur.fetchall()])


@prideLogBP.route("/workouts/<int:workoutId>", methods=["GET"])
def getWorkout(workoutId):
    uid = session.requestUID()
    with database() as (conn, cur):
        workout = readWorkout(cur, uid, workoutId)
        return notFound() if workout is None else ok(workout)


@prideLogBP.route("/workouts", methods=["POST"])
def addWorkout():
    uid = session.requestUID()
    data = body()
    with database() as (conn, cur):
        lockPerson(cur, uid)
        given = data.get("clientId")
        if isinstance(given, str) and checks.CLIENT_ID.fullmatch(given):
            cur.execute("SELECT WorkoutID, UserID FROM Workouts WHERE ClientID = %s", (given.lower(),))
            stored = cur.fetchone()
            if stored is not None:
                if stored["UserID"] != uid:
                    return refuse(checks.Refusal("clientId", "that clientId is already used"))
                return answerSaved(conn, cur, uid, stored["WorkoutID"])     # plan decision 4: stored once
        measures = history.measuresFor(cur, uid, askedExercises(data))
        try:
            clean = checks.workout(data, latestDay(), measures.get)
        except checks.Refusal as refusal:
            return refuse(refusal)
        routine = routineOf(cur, uid, clean["routineId"])
        items = itemsOfPerson(cur, uid, [e["itemId"] for e in clean["exercises"]])
        cur.execute("INSERT INTO Workouts (UserID, ClientID, PerformedOn, ProgramID, RoutineID, Note) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (uid, clean["clientId"], clean["performedOn"], routine["ProgramID"] if routine else None,
                     routine["RoutineID"] if routine else None, clean["note"]))
        workoutId = cur.lastrowid
        kept = writeExercises(cur, workoutId, clean["exercises"], items)
        history.recalculate(cur, uid, kept)
        return answerSaved(conn, cur, uid, workoutId)


@prideLogBP.route("/workouts/<int:workoutId>", methods=["PUT"])
def editWorkout(workoutId):
    """Replaces the date, note, exercises and sets; the routine stays as logged (plan decision 7). The suggestions
    of every item it logged before or logs now are settled again (spec §5)."""
    uid = session.requestUID()
    data = body()
    with database() as (conn, cur):
        lockPerson(cur, uid)
        if ownedWorkout(cur, uid, workoutId) is None:
            return notFound()
        before = loggedItems(cur, workoutId)
        measures = history.measuresFor(cur, uid, askedExercises(data), workoutId)
        try:
            clean = checks.workout(data, latestDay(), measures.get, needClientId=False)
        except checks.Refusal as refusal:
            return refuse(refusal)
        items = itemsOfPerson(cur, uid, [e["itemId"] for e in clean["exercises"]])
        # Its sets go with the exercises (ON DELETE CASCADE); its suggestions stay, still naming this workout.
        cur.execute("DELETE FROM WorkoutExercises WHERE WorkoutID = %s", (workoutId,))
        cur.execute("UPDATE Workouts SET PerformedOn = %s, Note = %s, UpdatedAt = CURRENT_TIMESTAMP WHERE WorkoutID = %s",
                    (clean["performedOn"], clean["note"], workoutId))
        kept = writeExercises(cur, workoutId, clean["exercises"], items)
        history.recalculate(cur, uid, before + kept)
        return answerSaved(conn, cur, uid, workoutId)


@prideLogBP.route("/workouts/<int:workoutId>", methods=["DELETE"])
def deleteWorkout(workoutId):
    """Its exercises and sets go with it; a suggestion based on it loses its workout (ON DELETE SET NULL) and is
    settled again, so one that no longer holds is withdrawn (spec §5)."""
    uid = session.requestUID()
    with database() as (conn, cur):
        lockPerson(cur, uid)
        if ownedWorkout(cur, uid, workoutId) is None:
            return notFound()
        before = loggedItems(cur, workoutId)
        cur.execute("DELETE FROM Workouts WHERE WorkoutID = %s AND UserID = %s", (workoutId, uid))
        history.recalculate(cur, uid, before)
        nextUp = history.nextUpJson(*history.rotation(cur, uid))
        conn.commit()
        return ok({"deleted": workoutId, "nextUp": nextUp})


# ---- Progress and records (spec §6 Progress; plan decisions 10-13) ----

@prideLogBP.route("/progress/<int:exerciseId>", methods=["GET"])
def progress(exerciseId):
    """One exercise's chart points, records and latest workouts. A hidden exercise still has its history."""
    uid = session.requestUID()
    with database() as (conn, cur):
        cur.execute("SELECT ExerciseID, Measure FROM Exercises WHERE ExerciseID = %s "
                    "AND (OwnerUserID IS NULL OR OwnerUserID = %s)", (exerciseId, uid))
        exercise = cur.fetchone()
        if exercise is None:
            return notFound()
        units = history.unitsOf(cur, uid)
        logged = history.rows(cur, uid, exerciseIds=[exerciseId])
        measure = exercise["Measure"]
        return ok({"exerciseId": exerciseId, "measure": measure, "units": units,
                   "points": rules.series(logged, measure, units), "records": rules.records(logged, measure, units),
                   "recent": rules.recent(logged)})


@prideLogBP.route("/records", methods=["GET"])
def allRecords():
    uid = session.requestUID()
    with database() as (conn, cur):
        units = history.unitsOf(cur, uid)
        logged = history.rows(cur, uid)
        measures = history.measuresOf(cur, [r["exerciseId"] for r in logged])
        return ok(rules.recordsByExercise(logged, measures, units))


# ---- Suggestions (spec §5, §6 Today: Take it / Not yet; plan decision 19) ----

def closed():
    return jsonify({"status": "closed", "message": "that suggestion is no longer open"}), 409


def ownedSuggestion(cur, uid, suggestionId):
    cur.execute("SELECT s.SuggestionID, s.ItemID, s.Kind, s.ProposedWeight, s.ProposedUnit, s.ProposedRepsMin, "
                "s.ProposedRepsMax, s.ProposedSeconds, s.BasedOnWorkoutID, s.State, r.ProgramID FROM Suggestions s "
                "JOIN RoutineItems i ON i.ItemID = s.ItemID JOIN Routines r ON r.RoutineID = i.RoutineID "
                "WHERE s.SuggestionID = %s AND s.UserID = %s FOR UPDATE", (suggestionId, uid))
    return cur.fetchone()


@prideLogBP.route("/suggestions/<int:suggestionId>/accept", methods=["POST"])
def acceptSuggestion(suggestionId):
    """Writes the proposed target onto the routine item (spec §4) and touches the program, so a device that has it
    open sees the change (spec §8)."""
    uid = session.requestUID()
    with database() as (conn, cur):
        found = ownedSuggestion(cur, uid, suggestionId)
        if found is None:
            return notFound()
        if found["State"] != "open":
            return closed()
        if found["Kind"] != "increase":
            return refuse(checks.Refusal("kind", "a stall is noted, not taken"))
        if found["ProposedWeight"] is not None:
            cur.execute("UPDATE RoutineItems SET TargetWeight = %s, TargetUnit = %s WHERE ItemID = %s",
                        (float(found["ProposedWeight"]), found["ProposedUnit"], found["ItemID"]))
        elif found["ProposedRepsMin"] is not None:
            cur.execute("UPDATE RoutineItems SET RepsMin = %s, RepsMax = %s WHERE ItemID = %s",
                        (found["ProposedRepsMin"], found["ProposedRepsMax"], found["ItemID"]))
        else:
            cur.execute("UPDATE RoutineItems SET TargetSeconds = %s WHERE ItemID = %s",
                        (found["ProposedSeconds"], found["ItemID"]))
        cur.execute("UPDATE Suggestions SET State = 'accepted' WHERE SuggestionID = %s", (suggestionId,))
        user.touch(cur, found["ProgramID"])
        conn.commit()
    return ok({"suggestion": {**history.suggestionJson(found), "state": "accepted"}, "programId": found["ProgramID"]})


@prideLogBP.route("/suggestions/<int:suggestionId>/dismiss", methods=["POST"])
def dismissSuggestion(suggestionId):
    """Not yet (a step-up) or Noted (a stall): the routine is left alone, and the item gets nothing more until
    another qualifying workout (spec §5)."""
    uid = session.requestUID()
    with database() as (conn, cur):
        found = ownedSuggestion(cur, uid, suggestionId)
        if found is None:
            return notFound()
        if found["State"] != "open":
            return closed()
        cur.execute("UPDATE Suggestions SET State = 'dismissed' WHERE SuggestionID = %s", (suggestionId,))
        conn.commit()
    return ok({"suggestion": {**history.suggestionJson(found), "state": "dismissed"}})
