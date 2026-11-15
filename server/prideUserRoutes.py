"""
Everything a person owns, at /api/pride beside prideRoutes.py (spec §1, §4): the profile, their own exercises, the
starter programs, programs with their routines and items, and Today. It installs the same session check
(prideSession.py), so every route needs a session. Checks are prideChecks.py's and rules prideRules.py's; this file
only reads and writes. Every refusal names the field: 400 {status:"error", field, message}; an id that is not the
person's is 404; a limit is 409 {status:"limit", field, message} (plan decision 17). docs/api.md is the contract.
"""
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
