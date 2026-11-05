# Copied in part from Gluttony server/gluttonyAdminRoutes.py at c1ed705; changes: Pride's routes (state, pictures,
# import); only the token check, body() and database() come from there.
"""
Pride's admin routes on plutus, at /api/pride-admin: what the catalog importer (importer/) reads and sends. LAN only:
the tunnel's nginx never routes this prefix. Every request needs X-Admin-Token, the token in prideAdminConfig.json
beside this file (never committed). Pictures go first (GET /pictures says which the server has, PUT stores one),
then the whole source as one batch (POST /import), so no exercise ever names a picture the server lacks.
"""
import hashlib
import hmac
import json
import os
from contextlib import contextmanager
from pathlib import Path

from flask import Blueprint, jsonify, request

from . import DBUtils, prideCatalog as catalog

prideAdminBP = Blueprint("prideAdmin", __name__)

CONFIG_FILE = Path(__file__).resolve().parent / "prideAdminConfig.json"
DB_NAME = "pride"
MAX_PICTURE_BYTES = 2 * 1024 * 1024
CHILD_TABLES = ("ExerciseMuscles", "ExerciseEquipment", "ExerciseSteps", "ExercisePictures")
_tokenCache = {"mtime": None, "token": None}


def adminToken():
    """The token from prideAdminConfig.json, read again whenever the file changes."""
    try:
        mtime = CONFIG_FILE.stat().st_mtime
    except (OSError, AttributeError, TypeError):
        return None
    if _tokenCache["mtime"] != mtime:
        try:
            _tokenCache["token"] = json.loads(CONFIG_FILE.read_text(encoding="utf-8")).get("token") or None
        except (OSError, ValueError):
            _tokenCache["token"] = None
        _tokenCache["mtime"] = mtime
    return _tokenCache["token"]


@prideAdminBP.before_request
def requireAdminToken():
    expected = adminToken()
    given = request.headers.get("X-Admin-Token", "")
    if not expected or not hmac.compare_digest(given.encode(), expected.encode()):
        return jsonify({"status": "error", "message": "unauthorized"}), 401


def error(message, code=400):
    return jsonify({"status": "error", "message": message}), code


def body():
    """The JSON body as a dict, or {} (never Flask 3's automatic 415)."""
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


@contextmanager
def database():
    conn = DBUtils.initConnection(DB_NAME)
    conn.autocommit = False
    cur = conn.cursor(dictionary=True)
    try:
        yield conn, cur
    finally:
        conn.rollback()             # nothing after a commit; anything half-done otherwise
        cur.close()
        conn.close()


def pictureFolder():
    return catalog.MEDIA_ROOT / catalog.PICTURE_DIR


# ---- What the server holds ----

@prideAdminBP.route("/state", methods=["GET"])
def state():
    with database() as (conn, cur):
        cur.execute("SELECT Version FROM CatalogVersion WHERE Id = 1")
        row = cur.fetchone()
        cur.execute("SELECT Source, SourceKey, Name, ContentHash, RemovedAt FROM Exercises "
                    "WHERE OwnerUserID IS NULL ORDER BY Source, SourceKey")
        rows = cur.fetchall()
    return jsonify({"status": "ok", "version": row["Version"] if row else None,
                    "exercises": [{"source": r["Source"], "key": r["SourceKey"], "name": r["Name"],
                                   "hash": r["ContentHash"], "removed": r["RemovedAt"] is not None} for r in rows]})


@prideAdminBP.route("/pictures", methods=["GET"])
def pictures():
    folder = pictureFolder()
    names = sorted(p.name for p in folder.iterdir() if catalog.PICTURE_NAME.fullmatch(p.name)) if folder.is_dir() else []
    return jsonify({"status": "ok", "pictures": names})


@prideAdminBP.route("/pictures/<name>", methods=["PUT"])
def putPicture(name):
    """One picture, stored under its own name. The name must be the bytes' hash and the bytes a JPEG, so a picture
    can never be stored under another's name, and a captive portal's page is never kept as one."""
    if not catalog.PICTURE_NAME.fullmatch(name):
        return error("a picture is named by its content: 20 hex and .jpg")
    if (request.content_length or 0) > MAX_PICTURE_BYTES:
        return error("a picture is at most 2 MB", 413)
    data = request.get_data(cache=False)
    if len(data) > MAX_PICTURE_BYTES:
        return error("a picture is at most 2 MB", 413)
    if not data.startswith(b"\xff\xd8\xff"):
        return error("not a JPEG")
    if hashlib.sha1(data).hexdigest()[:20] != name[:20]:
        return error("the name does not match the picture's content")
    folder = pictureFolder()
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / name
    if not target.is_file():
        # Written aside and moved into place, so a picture is never seen half-written.
        partial = folder / (name + ".part")
        partial.write_bytes(data)
        os.replace(partial, target)
    return jsonify({"status": "ok", "stored": name})


# ---- The import ----

def insertRows(cur, table, columns, rows):
    """One INSERT for all of an exercise's rows in a child table: a whole import is a few thousand statements, not
    tens of thousands."""
    if not rows:
        return
    marks = "(" + ", ".join(["%s"] * len(columns)) + ")"
    cur.execute(f"INSERT INTO {table} ({', '.join(columns)}) VALUES {', '.join([marks] * len(rows))}",
                [value for row in rows for value in row])


def storeChildren(cur, exerciseId, e):
    insertRows(cur, "ExerciseMuscles", ("ExerciseID", "Muscle", "Role"),
               [(exerciseId, m, "primary") for m in e["primary"]] + [(exerciseId, m, "secondary") for m in e["secondary"]])
    insertRows(cur, "ExerciseEquipment", ("ExerciseID", "Equipment"), [(exerciseId, q) for q in e["equipment"]])
    insertRows(cur, "ExerciseSteps", ("ExerciseID", "StepNo", "Text"),
               [(exerciseId, n, text) for n, text in enumerate(e["steps"], start=1)])
    insertRows(cur, "ExercisePictures", ("ExerciseID", "Idx", "Path"),
               [(exerciseId, n, path) for n, path in enumerate(e["pictures"])])


@prideAdminBP.route("/import", methods=["POST"])
def importBatch():
    """The whole of one source, in one transaction: new keys are added, changed ones replaced (children and all),
    missing ones hidden, and hidden ones that came back shown again. Nothing is written on any refusal."""
    data = body()
    problem = catalog.batchProblem(data)
    if problem:
        return error(problem)
    folder = pictureFolder()
    for e in data["exercises"]:
        for name in e["pictures"]:
            if not (folder / name).is_file():
                return error(f"exercise {e['key']}: picture {name} is not on the server; send pictures first")
    source, exercises = data["source"], data["exercises"]
    sent = {e["key"] for e in exercises}

    with database() as (conn, cur):
        # Locked, so two imports never interleave their hiding and adding.
        cur.execute("SELECT ExerciseID, SourceKey, ContentHash, RemovedAt FROM Exercises "
                    "WHERE Source = %s AND OwnerUserID IS NULL FOR UPDATE", (source,))
        stored = {r["SourceKey"]: r for r in cur.fetchall()}
        visible = [k for k, r in stored.items() if r["RemovedAt"] is None]
        toHide = [k for k in visible if k not in sent]
        if visible and len(toHide) > catalog.HIDE_GUARD * len(visible):
            return error(f"the import would hide {len(toHide)} of {len(visible)} exercises (more than "
                         f"{round(catalog.HIDE_GUARD * 100)}%); nothing was changed", 409)

        added = changed = unchanged = 0
        for e in exercises:
            row = stored.get(e["key"])
            if row and row["ContentHash"] == e["hash"] and row["RemovedAt"] is None:
                unchanged += 1
                continue
            columns = (e["licence"], e["name"].strip(), e["category"], e["level"], e["measure"], e["region"], e["hash"])
            if row:
                exerciseId = row["ExerciseID"]
                cur.execute("UPDATE Exercises SET Licence = %s, Name = %s, Category = %s, Level = %s, Measure = %s, "
                            "Region = %s, ContentHash = %s, RemovedAt = NULL WHERE ExerciseID = %s",
                            (*columns, exerciseId))
                for table in CHILD_TABLES:
                    cur.execute(f"DELETE FROM {table} WHERE ExerciseID = %s", (exerciseId,))
                changed += 1
            else:
                cur.execute("INSERT INTO Exercises (Source, SourceKey, Licence, Name, Category, Level, Measure, Region, "
                            "ContentHash) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)", (source, e["key"], *columns))
                exerciseId = cur.lastrowid
                added += 1
            storeChildren(cur, exerciseId, e)

        if toHide:
            ids = [stored[k]["ExerciseID"] for k in toHide]
            cur.execute(f"UPDATE Exercises SET RemovedAt = NOW() WHERE ExerciseID IN ({', '.join(['%s'] * len(ids))})",
                        ids)
        cur.execute("SELECT Source, SourceKey, ContentHash, RemovedAt FROM Exercises WHERE OwnerUserID IS NULL")
        version = catalog.versionOf(cur.fetchall())
        cur.execute("INSERT INTO CatalogVersion (Id, Version) VALUES (1, %s) "
                    "ON DUPLICATE KEY UPDATE Version = VALUES(Version), UpdatedAt = NOW()", (version,))
        conn.commit()
    return jsonify({"status": "ok", "added": added, "changed": changed, "unchanged": unchanged,
                    "hidden": len(toHide), "version": version})
