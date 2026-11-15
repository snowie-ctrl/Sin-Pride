"""
Everything a person owns, at /api/pride beside prideRoutes.py (spec §1, §4): the profile, their own exercises, the
starter programs, programs with their routines and items, and Today. It installs the same session check
(prideSession.py), so every route needs a session. Checks are prideChecks.py's and rules prideRules.py's; this file
only reads and writes. Every refusal names the field: 400 {status:"error", field, message}; an id that is not the
person's is 404; a limit is 409 {status:"limit", field, message} (plan decision 17). docs/api.md is the contract.
"""
import secrets

from flask import Blueprint, jsonify, request

from . import prideCatalog as catalog, prideChecks as checks, prideSession as session

prideUserBP = Blueprint("prideUser", __name__)
session.install(prideUserBP)
database = session.database
fail = session.fail


def ok(data):
    return jsonify({"status": "ok", "data": data}), 200


def refuse(refusal):
    return jsonify({"status": "error", "field": refusal.field, "message": refusal.message}), 400


def notFound():
    return fail("not found", 404)


def overLimit(field, message):
    return jsonify({"status": "limit", "field": field, "message": message}), 409


def body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def lockPerson(cur, uid):
    """Holds this person's row for the transaction, so two requests that change which programs exist (or which is
    active) run one after the other: two first programs can never both become active."""
    cur.execute("SELECT UserID FROM Users WHERE UserID = %s FOR UPDATE", (uid,))
    cur.fetchone()


# ---- Profile ----

PROFILE_COLUMNS = {"units": "Units", "goal": "Goal", "daysPerWeek": "DaysPerWeek", "upperIncrement": "UpperIncrement",
                   "lowerIncrement": "LowerIncrement", "weekStart": "WeekStart", "introState": "IntroState"}
PROFILE_QUERY = ("SELECT Units, Goal, DaysPerWeek, UpperIncrement, LowerIncrement, WeekStart, IntroState "
                 "FROM Profiles WHERE UserID = %s")


def profileJson(row, equipment):
    return {"units": row["Units"], "goal": row["Goal"], "daysPerWeek": row["DaysPerWeek"],
            "upperIncrement": float(row["UpperIncrement"]), "lowerIncrement": float(row["LowerIncrement"]),
            "weekStart": row["WeekStart"], "introState": row["IntroState"],
            "equipment": [w for w in catalog.EQUIPMENT if w in equipment]}


def profileRow(cur, uid, lock=False):
    """The person's profile row. Sign-up makes it (prideRoutes.auth); one missing all the same is made here with the
    columns' defaults rather than leaving the person with no profile."""
    cur.execute(PROFILE_QUERY + (" FOR UPDATE" if lock else ""), (uid,))
    row = cur.fetchone()
    if row is None:
        cur.execute("INSERT IGNORE INTO Profiles (UserID) VALUES (%s)", (uid,))
        cur.execute(PROFILE_QUERY + (" FOR UPDATE" if lock else ""), (uid,))
        row = cur.fetchone()
    return row


def equipmentOf(cur, uid):
    cur.execute("SELECT Equipment FROM UserEquipment WHERE UserID = %s", (uid,))
    return [r["Equipment"] for r in cur.fetchall()]


def profileOf(cur, uid):
    return profileJson(profileRow(cur, uid), equipmentOf(cur, uid))


@prideUserBP.route("/profile", methods=["GET"])
def getProfile():
    uid = session.requestUID()
    with database() as (conn, cur):
        row = profileRow(cur, uid)
        equipment = equipmentOf(cur, uid)
        conn.commit()
    return ok(profileJson(row, equipment))


@prideUserBP.route("/profile", methods=["PUT"])
def putProfile():
    uid = session.requestUID()
    with database() as (conn, cur):
        row = profileRow(cur, uid, lock=True)
        try:
            changes = checks.profileChanges(body(), row["Units"])
        except checks.Refusal as refusal:
            return refuse(refusal)
        columns = [(PROFILE_COLUMNS[k], v) for k, v in changes.items() if k in PROFILE_COLUMNS]
        if columns:
            # The column names come from PROFILE_COLUMNS, whose keys prideChecks.PROFILE_FIELDS alone lets through,
            # never from the request, so the f-string carries no caller text; every value is a parameter.
            cur.execute(f"UPDATE Profiles SET {', '.join(f'{c} = %s' for c, _ in columns)} WHERE UserID = %s",
                        (*[v for _, v in columns], uid))
        if "equipment" in changes:
            cur.execute("DELETE FROM UserEquipment WHERE UserID = %s", (uid,))
            for word in changes["equipment"]:
                cur.execute("INSERT INTO UserEquipment (UserID, Equipment) VALUES (%s, %s)", (uid, word))
            equipment = changes["equipment"]
        else:
            equipment = equipmentOf(cur, uid)
        conn.commit()
    merged = dict(row)
    merged.update({PROFILE_COLUMNS[k]: v for k, v in changes.items() if k in PROFILE_COLUMNS})
    return ok(profileJson(merged, equipment))


# ---- Own exercises (spec §6 Catalog: name, equipment, muscles, measure, optional steps) ----

def ownJson(exerciseId, key, clean, removed=False):
    return {"id": exerciseId, "key": key, "source": catalog.OWN_SOURCE, "licence": None, "name": clean["name"],
            "category": None, "level": None, "measure": clean["measure"], "region": clean["region"],
            "removed": removed, "primary": clean["primary"], "secondary": clean["secondary"],
            "equipment": clean["equipment"], "steps": clean["steps"], "pictures": []}


def writeChildren(cur, exerciseId, clean):
    for role in ("primary", "secondary"):
        for muscle in clean[role]:
            cur.execute("INSERT INTO ExerciseMuscles (ExerciseID, Muscle, Role) VALUES (%s, %s, %s)",
                        (exerciseId, muscle, role))
    for word in clean["equipment"]:
        cur.execute("INSERT INTO ExerciseEquipment (ExerciseID, Equipment) VALUES (%s, %s)", (exerciseId, word))
    for n, text in enumerate(clean["steps"], start=1):
        cur.execute("INSERT INTO ExerciseSteps (ExerciseID, StepNo, Text) VALUES (%s, %s, %s)", (exerciseId, n, text))


def ownedExercise(cur, uid, exerciseId):
    cur.execute("SELECT SourceKey, Measure FROM Exercises WHERE ExerciseID = %s AND OwnerUserID = %s "
                "AND RemovedAt IS NULL FOR UPDATE", (exerciseId, uid))
    return cur.fetchone()


def visibleExercise(cur, uid, exerciseId):
    """An exercise the person may put in a routine: the catalog's or their own, and not hidden (plan decision 19)."""
    cur.execute("SELECT ExerciseID, Measure FROM Exercises WHERE ExerciseID = %s AND RemovedAt IS NULL "
                "AND (OwnerUserID IS NULL OR OwnerUserID = %s)", (exerciseId, uid))
    return cur.fetchone()


@prideUserBP.route("/exercises", methods=["GET"])
def ownExercises():
    uid = session.requestUID()
    with database() as (conn, cur):
        cur.execute(catalog.OWN_EXERCISES_QUERY, (uid,))
        rows = cur.fetchall()
        children = {}
        for name, sql in catalog.OWN_CHILD_QUERIES:
            cur.execute(sql, (uid,))
            children[name] = cur.fetchall()
    return ok(catalog.exercisesJson(rows, children))


@prideUserBP.route("/exercises", methods=["POST"])
def addOwnExercise():
    uid = session.requestUID()
    try:
        clean = checks.ownExercise(body())
    except checks.Refusal as refusal:
        return refuse(refusal)
    with database() as (conn, cur):
        lockPerson(cur, uid)
        cur.execute("SELECT COUNT(*) AS n FROM Exercises WHERE OwnerUserID = %s AND RemovedAt IS NULL", (uid,))
        if cur.fetchone()["n"] >= checks.LIMITS["own"]:
            return overLimit("exercise", f"at most {checks.LIMITS['own']} exercises of your own")
        # The key only has to be unique among own exercises (Exercises' (Source, SourceKey) key); 64 random bits is.
        key = "own-" + secrets.token_hex(8)
        cur.execute("INSERT INTO Exercises (Source, SourceKey, Name, Measure, Region, OwnerUserID) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (catalog.OWN_SOURCE, key, clean["name"], clean["measure"], clean["region"], uid))
        exerciseId = cur.lastrowid
        writeChildren(cur, exerciseId, clean)
        conn.commit()
    return ok(ownJson(exerciseId, key, clean))


@prideUserBP.route("/exercises/<int:exerciseId>", methods=["PUT"])
def editOwnExercise(exerciseId):
    uid = session.requestUID()
    try:
        clean = checks.ownExercise(body())
    except checks.Refusal as refusal:
        return refuse(refusal)
    with database() as (conn, cur):
        row = ownedExercise(cur, uid, exerciseId)
        if row is None:
            return notFound()
        if clean["measure"] != row["Measure"]:
            # Targets and logged sets are shaped by the measure, so it is fixed once anything uses the exercise.
            cur.execute("SELECT 1 AS used FROM RoutineItems WHERE ExerciseID = %s UNION ALL "
                        "SELECT 1 FROM WorkoutExercises WHERE ExerciseID = %s LIMIT 1", (exerciseId, exerciseId))
            if cur.fetchone():
                return refuse(checks.Refusal("measure", "the measure can't change once a routine or workout uses it"))
        cur.execute("UPDATE Exercises SET Name = %s, Measure = %s, Region = %s WHERE ExerciseID = %s "
                    "AND OwnerUserID = %s", (clean["name"], clean["measure"], clean["region"], exerciseId, uid))
        for table in ("ExerciseMuscles", "ExerciseEquipment", "ExerciseSteps"):
            cur.execute(f"DELETE FROM {table} WHERE ExerciseID = %s", (exerciseId,))
        writeChildren(cur, exerciseId, clean)
        conn.commit()
    return ok(ownJson(exerciseId, row["SourceKey"], clean))


@prideUserBP.route("/exercises/<int:exerciseId>", methods=["DELETE"])
def deleteOwnExercise(exerciseId):
    """Plan decision 3: out of every routine first, then deleted, or hidden when a workout names it, so history keeps
    it (spec §8). One transaction."""
    uid = session.requestUID()
    with database() as (conn, cur):
        if ownedExercise(cur, uid, exerciseId) is None:
            return notFound()
        cur.execute("SELECT COUNT(DISTINCT ri.RoutineID) AS n FROM RoutineItems ri "
                    "JOIN Routines r ON r.RoutineID = ri.RoutineID JOIN Programs p ON p.ProgramID = r.ProgramID "
                    "WHERE ri.ExerciseID = %s AND p.UserID = %s", (exerciseId, uid))
        touched = cur.fetchone()["n"]
        cur.execute("DELETE ri FROM RoutineItems ri JOIN Routines r ON r.RoutineID = ri.RoutineID "
                    "JOIN Programs p ON p.ProgramID = r.ProgramID WHERE ri.ExerciseID = %s AND p.UserID = %s",
                    (exerciseId, uid))
        cur.execute("SELECT 1 AS one FROM WorkoutExercises WHERE ExerciseID = %s LIMIT 1", (exerciseId,))
        hidden = cur.fetchone() is not None
        if hidden:
            cur.execute("UPDATE Exercises SET RemovedAt = NOW() WHERE ExerciseID = %s AND OwnerUserID = %s",
                        (exerciseId, uid))
        else:
            cur.execute("DELETE FROM Exercises WHERE ExerciseID = %s AND OwnerUserID = %s", (exerciseId, uid))
        conn.commit()
    return ok({"routinesTouched": touched, "hidden": hidden})


# ---- Programs (spec §6 Programs; plan decisions 13–15). Every write to a program answers with the whole program,
# so the app replaces its copy instead of patching it; activate and delete answer with the list. ----

ITEM_COLUMNS = {"sets": "Sets", "repsMin": "RepsMin", "repsMax": "RepsMax", "targetWeight": "TargetWeight",
                "targetUnit": "TargetUnit", "targetSeconds": "TargetSeconds", "targetDistance": "TargetDistance",
                "distanceUnit": "DistanceUnit", "restSeconds": "RestSeconds", "note": "Note"}
PROGRAM_ROW = "SELECT ProgramID, Title, IsActive, StarterKey, UpdatedAt FROM Programs WHERE ProgramID = %s AND UserID = %s"
ITEMS_OF_PROGRAM = ("SELECT i.ItemID, i.RoutineID, i.ExerciseID, i.Sets, i.RepsMin, i.RepsMax, i.TargetWeight, "
                    "i.TargetUnit, i.TargetSeconds, i.TargetDistance, i.DistanceUnit, i.RestSeconds, i.Note "
                    "FROM RoutineItems i JOIN Routines r ON r.RoutineID = i.RoutineID WHERE r.ProgramID = %s "
                    "ORDER BY r.OrderIndex, r.RoutineID, i.OrderIndex, i.ItemID")


def isoUtc(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ") if moment else None


def decimalOrNone(value):
    return None if value is None else float(value)


def itemJson(row):
    return {"id": row["ItemID"], "exerciseId": row["ExerciseID"], "sets": row["Sets"], "repsMin": row["RepsMin"],
            "repsMax": row["RepsMax"], "targetWeight": decimalOrNone(row["TargetWeight"]),
            "targetUnit": row["TargetUnit"], "targetSeconds": row["TargetSeconds"],
            "targetDistance": decimalOrNone(row["TargetDistance"]), "distanceUnit": row["DistanceUnit"],
            "restSeconds": row["RestSeconds"], "note": row["Note"]}


def ownedProgram(cur, uid, programId, lock=False):
    cur.execute(PROGRAM_ROW + (" FOR UPDATE" if lock else ""), (programId, uid))
    return cur.fetchone()


def programJson(cur, row):
    programId = row["ProgramID"]
    cur.execute("SELECT Weekday FROM ProgramDays WHERE ProgramID = %s ORDER BY Weekday", (programId,))
    days = [r["Weekday"] for r in cur.fetchall()]
    cur.execute("SELECT RoutineID, Title FROM Routines WHERE ProgramID = %s ORDER BY OrderIndex, RoutineID",
                (programId,))
    routines = [{"id": r["RoutineID"], "title": r["Title"], "items": []} for r in cur.fetchall()]
    cur.execute(ITEMS_OF_PROGRAM, (programId,))
    byRoutine = {r["id"]: r for r in routines}
    for item in cur.fetchall():
        if item["RoutineID"] in byRoutine:
            byRoutine[item["RoutineID"]]["items"].append(itemJson(item))
    return {"id": programId, "title": row["Title"], "active": bool(row["IsActive"]), "starterKey": row["StarterKey"],
            "days": days, "updatedAt": isoUtc(row["UpdatedAt"]), "routines": routines}


def answerProgram(conn, cur, uid, programId):
    """Reads the program as this transaction left it, commits, and answers it whole."""
    row = ownedProgram(cur, uid, programId)
    data = programJson(cur, row)
    conn.commit()
    return ok(data)


def touch(cur, programId):
    # UpdatedAt moves only when a column of the row changes, and a routine or item write changes none of them, so
    # it is set by hand: the app compares it to warn about a change made on another device (spec §8).
    cur.execute("UPDATE Programs SET UpdatedAt = CURRENT_TIMESTAMP WHERE ProgramID = %s", (programId,))


def programRows(cur, uid):
    cur.execute("SELECT p.ProgramID, p.Title, p.IsActive, p.StarterKey, p.UpdatedAt, "
                "(SELECT COUNT(*) FROM Routines r WHERE r.ProgramID = p.ProgramID) AS RoutineCount "
                "FROM Programs p WHERE p.UserID = %s ORDER BY p.CreatedAt, p.ProgramID", (uid,))
    rows = cur.fetchall()
    cur.execute("SELECT d.ProgramID, d.Weekday FROM ProgramDays d JOIN Programs p ON p.ProgramID = d.ProgramID "
                "WHERE p.UserID = %s ORDER BY d.ProgramID, d.Weekday", (uid,))
    days = {}
    for d in cur.fetchall():
        days.setdefault(d["ProgramID"], []).append(d["Weekday"])
    return [{"id": r["ProgramID"], "title": r["Title"], "active": bool(r["IsActive"]), "starterKey": r["StarterKey"],
             "days": days.get(r["ProgramID"], []), "routineCount": r["RoutineCount"], "updatedAt": isoUtc(r["UpdatedAt"])}
            for r in rows]


def answerRows(conn, cur, uid):
    rows = programRows(cur, uid)
    conn.commit()
    return ok(rows)


def countPrograms(cur, uid):
    cur.execute("SELECT COUNT(*) AS n FROM Programs WHERE UserID = %s", (uid,))
    return cur.fetchone()["n"]


@prideUserBP.route("/programs", methods=["GET"])
def listPrograms():
    uid = session.requestUID()
    with database() as (conn, cur):
        return ok(programRows(cur, uid))


@prideUserBP.route("/programs", methods=["POST"])
def createProgram():
    uid = session.requestUID()
    try:
        name = checks.title(body().get("title"))
    except checks.Refusal as refusal:
        return refuse(refusal)
    with database() as (conn, cur):
        lockPerson(cur, uid)
        count = countPrograms(cur, uid)
        if count >= checks.LIMITS["programs"]:
            return overLimit("program", f"at most {checks.LIMITS['programs']} programs")
        # A person's first program is the one they follow (plan decision 13).
        cur.execute("INSERT INTO Programs (UserID, Title, IsActive) VALUES (%s, %s, %s)", (uid, name, int(count == 0)))
        return answerProgram(conn, cur, uid, cur.lastrowid)


@prideUserBP.route("/programs/<int:programId>", methods=["GET"])
def getProgram(programId):
    uid = session.requestUID()
    with database() as (conn, cur):
        row = ownedProgram(cur, uid, programId)
        if row is None:
            return notFound()
        return ok(programJson(cur, row))


@prideUserBP.route("/programs/<int:programId>", methods=["PUT"])
def renameProgram(programId):
    uid = session.requestUID()
    try:
        name = checks.title(body().get("title"))
    except checks.Refusal as refusal:
        return refuse(refusal)
    with database() as (conn, cur):
        if ownedProgram(cur, uid, programId, lock=True) is None:
            return notFound()
        cur.execute("UPDATE Programs SET Title = %s WHERE ProgramID = %s AND UserID = %s", (name, programId, uid))
        return answerProgram(conn, cur, uid, programId)


@prideUserBP.route("/programs/<int:programId>/duplicate", methods=["POST"])
def duplicateProgram(programId):
    uid = session.requestUID()
    with database() as (conn, cur):
        lockPerson(cur, uid)
        if countPrograms(cur, uid) >= checks.LIMITS["programs"]:
            return overLimit("program", f"at most {checks.LIMITS['programs']} programs")
        source = ownedProgram(cur, uid, programId)
        if source is None:
            return notFound()
        # Plan decision 14: "<title> copy", cut so the whole stays within the title's 60 characters; not active.
        name = source["Title"][:checks.LIMITS["title"] - len(" copy")] + " copy"
        cur.execute("INSERT INTO Programs (UserID, Title, IsActive, StarterKey) VALUES (%s, %s, %s, %s)",
                    (uid, name, 0, source["StarterKey"]))
        copyId = cur.lastrowid
        cur.execute("INSERT INTO ProgramDays (ProgramID, Weekday) SELECT %s, Weekday FROM ProgramDays "
                    "WHERE ProgramID = %s", (copyId, programId))
        cur.execute("SELECT RoutineID, Title FROM Routines WHERE ProgramID = %s ORDER BY OrderIndex, RoutineID",
                    (programId,))
        for index, routine in enumerate(cur.fetchall()):
            cur.execute("INSERT INTO Routines (ProgramID, Title, OrderIndex) VALUES (%s, %s, %s)",
                        (copyId, routine["Title"], index))
            cur.execute("INSERT INTO RoutineItems (RoutineID, ExerciseID, OrderIndex, Sets, RepsMin, RepsMax, "
                        "TargetWeight, TargetUnit, TargetSeconds, TargetDistance, DistanceUnit, RestSeconds, Note) "
                        "SELECT %s, ExerciseID, OrderIndex, Sets, RepsMin, RepsMax, TargetWeight, TargetUnit, "
                        "TargetSeconds, TargetDistance, DistanceUnit, RestSeconds, Note FROM RoutineItems "
                        "WHERE RoutineID = %s", (cur.lastrowid, routine["RoutineID"]))
        return answerProgram(conn, cur, uid, copyId)


@prideUserBP.route("/programs/<int:programId>", methods=["DELETE"])
def deleteProgram(programId):
    """Days, routines and items go with it; past workouts keep their exercises (ON DELETE SET NULL, spec §8)."""
    uid = session.requestUID()
    with database() as (conn, cur):
        lockPerson(cur, uid)
        if ownedProgram(cur, uid, programId) is None:
            return notFound()
        cur.execute("DELETE FROM Programs WHERE ProgramID = %s AND UserID = %s", (programId, uid))
        return answerRows(conn, cur, uid)


@prideUserBP.route("/programs/<int:programId>/activate", methods=["POST"])
def activateProgram(programId):
    uid = session.requestUID()
    with database() as (conn, cur):
        lockPerson(cur, uid)
        if ownedProgram(cur, uid, programId) is None:
            return notFound()
        # One statement sets every program of the person, so at most one is ever active (spec §3).
        cur.execute("UPDATE Programs SET IsActive = (ProgramID = %s) WHERE UserID = %s", (programId, uid))
        return answerRows(conn, cur, uid)


@prideUserBP.route("/programs/<int:programId>/days", methods=["PUT"])
def setProgramDays(programId):
    uid = session.requestUID()
    with database() as (conn, cur):
        if ownedProgram(cur, uid, programId, lock=True) is None:
            return notFound()
        try:
            days = checks.weekdays(body().get("days"))
        except checks.Refusal as refusal:
            return refuse(refusal)
        cur.execute("DELETE FROM ProgramDays WHERE ProgramID = %s", (programId,))
        for day in days:
            cur.execute("INSERT INTO ProgramDays (ProgramID, Weekday) VALUES (%s, %s)", (programId, day))
        touch(cur, programId)
        return answerProgram(conn, cur, uid, programId)
