"""
Pride's app routes at /api/pride: the reachability check, accounts (sign-in, sign-up with a login key, a device that
signs itself in, sign-out, devices) and the exercise catalog with its pictures. docs/api.md is the contract for the
desktop app and the iOS app. Every route needs a session (prideSession.py) unless PUBLIC_ROUTES names it, so a route
added later cannot forget the check. What a person owns (profile, programs, workouts) arrives in prideUserRoutes.py in
milestone 2.
"""
import hashlib
import re
import secrets
from datetime import timedelta

from flask import Blueprint, jsonify, request, send_file
from werkzeug.security import check_password_hash, generate_password_hash

from . import prideCatalog as catalog, prideSession as session

prideBP = Blueprint("pride", __name__)
session.install(prideBP)
database = session.database
fail = session.fail


def ok(data=None, status="ok", **extra):
    answer = {"status": status}
    if data is not None:
        answer["data"] = data
    answer.update(extra)
    return jsonify(answer), 200


def body():
    """The JSON body, or {} when there is none or it isn't an object, so validation can say what is missing."""
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


@prideBP.route("/ping", methods=["GET"])
def ping():
    return ok()


# ---- Accounts. Copied from Gluttony server/gluttonyUserRoutes.py at c1ed705; changes: Pride's routes (/signout,
# DELETE /devices/<id>), a sign-up makes the person's profile row instead of a Cravings list, and no username or
# password change (not in Pride's routes). Users sign up with a login key the owner inserts by hand, and a device that
# signed in once signs in by itself (/device/identify) until it signs out. ----

USERNAME_MIN, USERNAME_MAX = 3, 32
PASSWORD_MIN, PASSWORD_MAX = 8, 256
DEVICE_ID = re.compile(r"[0-9a-f]{16}")


def isoUtc(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ") if moment else None


def usernameProblem(username):
    if not USERNAME_MIN <= len(username) <= USERNAME_MAX:
        return f"a username is {USERNAME_MIN} to {USERNAME_MAX} characters"
    return None


def passwordProblem(password):
    if not PASSWORD_MIN <= len(password) <= PASSWORD_MAX:
        return f"a password is {PASSWORD_MIN} to {PASSWORD_MAX} characters"
    return None


def createSession(cur, uid, fingerprint):
    """A new session token for this device. The user's ended sessions are cleared on the way, since nothing else
    ever removes them."""
    cur.execute("DELETE FROM Sessions WHERE UserID = %s AND ExpiresAt <= NOW()", (uid,))
    token = secrets.token_hex(32)
    cur.execute("INSERT INTO Sessions (Token, UserID, DeviceFingerprint, ExpiresAt) "
                "VALUES (%s, %s, %s, NOW() + INTERVAL %s DAY)", (token, uid, fingerprint, session.SESSION_DAYS))
    return token


def deviceId(fingerprint):
    """What a client may know of a device: the first 16 hex of its fingerprint's SHA-256. The fingerprint itself
    would sign the device in, so it never leaves the server."""
    return hashlib.sha256(fingerprint.encode()).hexdigest()[:16]


def currentFingerprint(cur, uid):
    cur.execute("SELECT DeviceFingerprint FROM Sessions WHERE Token = %s AND UserID = %s", (session.sessionToken(), uid))
    return (cur.fetchone() or {}).get("DeviceFingerprint")


@prideBP.route("/device/identify", methods=["POST"])
@session.rateLimited(10)
def identifyDevice():
    fingerprint = str(body().get("fingerprint") or "")[:255]
    if not fingerprint:
        return fail("missing fingerprint", 400)
    with database() as (conn, cur):
        cur.execute("SELECT UserID FROM Devices WHERE Fingerprint = %s", (fingerprint,))
        device = cur.fetchone()
        if not device:
            return ok(status="new")
        uid = device["UserID"]
        cur.execute("SELECT Username FROM Users WHERE UserID = %s", (uid,))
        account = cur.fetchone() or {}
        token = createSession(cur, uid, fingerprint)
        conn.commit()
    return ok(UID=uid, username=account.get("Username"), token=token)


@prideBP.route("/auth", methods=["POST"])
@session.rateLimited(5)
def auth():
    data = body()
    username = str(data.get("username") or "").strip()
    password = str(data.get("password") or "")
    fingerprint = str(data.get("fingerprint") or "")[:255]
    key = str(data.get("key") or "").strip()
    if not username or not password or not fingerprint:
        return fail("missing credentials", 400)
    if key:
        problem = usernameProblem(username) or passwordProblem(password)
        if problem:
            return fail(problem, 400)
    elif len(username) > USERNAME_MAX:
        return fail("invalid_credentials", 401, status="invalid_credentials")

    with database() as (conn, cur):
        if key:
            # The key's row is locked, so two sign-ups racing on one key cannot both use it.
            cur.execute("SELECT KeyValue, Used FROM LoginKeys WHERE KeyValue = %s FOR UPDATE", (key[:64],))
            found = cur.fetchone()
            if not found or found["Used"]:
                return fail("invalid_key", 403, status="invalid_key")
            cur.execute("SELECT UserID FROM Users WHERE Username = %s", (username,))
            if cur.fetchone():
                return fail("username_taken", 409, status="username_taken")
            cur.execute("INSERT INTO Users (Username, PasswordHash) VALUES (%s, %s)",
                        (username, generate_password_hash(password)))
            uid = cur.lastrowid
            cur.execute("UPDATE LoginKeys SET Used = 1, UsedBy = %s WHERE KeyValue = %s", (uid, found["KeyValue"]))
            # In the same transaction as the account, so no account ever exists without its profile. The columns'
            # defaults are the spec's (lb, general, 3 days, 5 lb and 10 lb, Monday), and the intro is pending.
            cur.execute("INSERT INTO Profiles (UserID) VALUES (%s)", (uid,))
        else:
            cur.execute("SELECT UserID, Username, PasswordHash FROM Users WHERE Username = %s", (username,))
            user = cur.fetchone()
            if not user or not check_password_hash(user["PasswordHash"], password):
                return fail("invalid_credentials", 401, status="invalid_credentials")
            uid, username = user["UserID"], user["Username"]
        # Remember the device either way, so it signs itself in next time.
        cur.execute("INSERT INTO Devices (Fingerprint, UserID) VALUES (%s, %s) "
                    "ON DUPLICATE KEY UPDATE UserID = VALUES(UserID)", (fingerprint, uid))
        token = createSession(cur, uid, fingerprint)
        conn.commit()
    return ok(UID=uid, username=username, token=token)


@prideBP.route("/signout", methods=["POST"])
def signOut():
    """Sign out, and make this device forget the account; without dropping the Devices row the next start would
    sign straight back in. Only this device is forgotten."""
    fingerprint = str(body().get("fingerprint") or request.headers.get("X-Device-Fingerprint") or "")[:255]
    if not fingerprint:
        return fail("missing fingerprint", 400)
    uid = session.requestUID()
    with database() as (conn, cur):
        cur.execute("DELETE FROM Devices WHERE Fingerprint = %s AND UserID = %s", (fingerprint, uid))
        cur.execute("DELETE FROM Sessions WHERE DeviceFingerprint = %s AND UserID = %s", (fingerprint, uid))
        conn.commit()
    return ok()


@prideBP.route("/devices", methods=["GET"])
def devices():
    uid = session.requestUID()
    with database() as (conn, cur):
        here = currentFingerprint(cur, uid)
        cur.execute("SELECT d.Fingerprint, MAX(s.ExpiresAt) AS LastExpiry FROM Devices d "
                    "LEFT JOIN Sessions s ON s.DeviceFingerprint = d.Fingerprint AND s.UserID = d.UserID "
                    "WHERE d.UserID = %s GROUP BY d.Fingerprint "
                    "ORDER BY MAX(s.ExpiresAt) IS NULL, MAX(s.ExpiresAt) DESC, d.Fingerprint", (uid,))
        rows = cur.fetchall()
    return ok([{"id": deviceId(r["Fingerprint"]), "label": deviceId(r["Fingerprint"])[:8],
                "current": r["Fingerprint"] == here,
                "lastSignIn": isoUtc(r["LastExpiry"] - timedelta(days=session.SESSION_DAYS)) if r["LastExpiry"] else None}
               for r in rows])


@prideBP.route("/devices/<wanted>", methods=["DELETE"])
def removeDevice(wanted):
    """Sign another of this person's devices out and forget it. The device asking is refused: signing out is how
    it leaves. Only this person's own devices can be named; an id that matches none is nothing to remove."""
    if not DEVICE_ID.fullmatch(wanted):
        return fail("no such device", 404)
    uid = session.requestUID()
    with database() as (conn, cur):
        here = currentFingerprint(cur, uid)
        if here is not None and wanted == deviceId(here):
            return fail("this is the device you are using: sign out instead", 400)
        cur.execute("SELECT Fingerprint FROM Devices WHERE UserID = %s", (uid,))
        fingerprint = next((r["Fingerprint"] for r in cur.fetchall() if deviceId(r["Fingerprint"]) == wanted), None)
        if fingerprint is None:
            return ok()
        cur.execute("DELETE FROM Sessions WHERE UserID = %s AND DeviceFingerprint = %s", (uid, fingerprint))
        cur.execute("DELETE FROM Devices WHERE UserID = %s AND Fingerprint = %s", (uid, fingerprint))
        conn.commit()
    return ok()


# ---- The catalog ----

@prideBP.route("/catalog", methods=["GET"])
def wholeCatalog():
    """The whole catalog, or "unchanged" when the app already holds this version. It is read in one transaction
    (InnoDB's consistent read), so the version and the rows always agree even while an import runs."""
    asked = (request.args.get("version") or "")[:64]
    with database() as (conn, cur):
        cur.execute("SELECT Version FROM CatalogVersion WHERE Id = 1")
        row = cur.fetchone()
        version = row["Version"] if row else None
        if version is not None and asked == version:
            return ok({"version": version, "unchanged": True})
        cur.execute(catalog.EXERCISES_QUERY)
        rows = cur.fetchall()
        children = {}
        for name, sql in catalog.CHILD_QUERIES:
            cur.execute(sql)
            children[name] = cur.fetchall()
    return ok({"version": version, "exercises": catalog.exercisesJson(rows, children)})


@prideBP.route("/pictures/<name>", methods=["GET"])
def picture(name):
    """An exercise's picture. It is named by its content, so the name alone says which file, and the pattern keeps
    the name inside the folder; no database is needed."""
    if not catalog.PICTURE_NAME.fullmatch(name):
        return fail("no picture", 404)
    target = catalog.MEDIA_ROOT / catalog.PICTURE_DIR / name
    if not target.is_file():
        return fail("no picture", 404)
    response = send_file(target, mimetype="image/jpeg", conditional=True, max_age=86400)
    response.headers["Cache-Control"] = "private, max-age=86400"
    return response
