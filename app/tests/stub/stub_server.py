"""
Stand-in for Pride's app API (docs/api.md), for screenshot runs and for trying the app without plutus or anyone's
account. It listens on 127.0.0.1:5089 (Gluttony's stub has 5079, so both can run); tests/stub/grab.ps1 starts it.

It serves snapshot/catalog.json and snapshot/pictures/ (made by snapshot.py from the importer's last dry run; never
committed, only because it is large) or, without them, fixture/ (11 free-exercise-db exercises, public domain, with
made-up pictures; makeFixture.py).

Sign in as stub / stub-password (UID 7, token "stub"). Sign up with the key "stub-key" (any other key is 403
invalid_key); the username "taken" is 409. Signing out makes /device/identify say "new" until the next /auth.

STUB_NEW_DEVICE=1      /device/identify says "new", so the sign-in form shows.
STUB_CATALOG_DOWN=1    /catalog answers 503, to see the Catalog page's own failure.
STUB_PICTURES_FAIL=1   every picture is 404, to see the placeholders.
STUB_SLOW=<ms>         pictures answer that late, to see them loading.
STUB_SNAPSHOT=<dir>    serve that folder instead of snapshot/.
"""
import json
import os
import re
import threading
import time
from pathlib import Path

from flask import Flask, jsonify, request, send_file

API = "/api/pride"
TOKEN = "stub"
UID = 7
PORT = 5089
PUBLIC = {"/ping", "/auth", "/device/identify"}
HERE = Path(__file__).resolve().parent
PICTURE = re.compile(r"[0-9a-f]{20}\.jpg")
DEVICE = re.compile(r"[0-9a-f]{16}")
THIS_DEVICE, OTHER_DEVICE = "f00dfeedf00dfeed", "0a1b2c3d4e5f6071"

app = Flask(__name__)
lock = threading.Lock()
state = {}


def catalogFolder():
    folder = Path(os.environ.get("STUB_SNAPSHOT") or HERE / "snapshot")
    return folder if (folder / "catalog.json").is_file() else HERE / "fixture"


def reset():
    folder = catalogFolder()
    state.clear()
    state.update({
        "folder": folder,
        "catalog": json.loads((folder / "catalog.json").read_text(encoding="utf-8")),
        "readers": {UID: {"username": "stub", "password": "stub-password"}},
        "tokens": {TOKEN: UID},
        "deviceUid": None if os.environ.get("STUB_NEW_DEVICE") else UID,
        "otherDevice": True,
        "nextUid": 100,
    })


def ok(data=None, status="ok", **extra):
    answer = {"status": status}
    if data is not None:
        answer["data"] = data
    answer.update(extra)
    return jsonify(answer), 200


def fail(status, http, message=None):
    return jsonify({"status": status, "message": message or status}), http


def uid():
    return state["tokens"].get(request.headers.get("X-Session-Token") or "")


def body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


@app.before_request
def guard():
    # Only /api/pride/... is the API: a neighbour such as /api/pride-admin is not served here, as on the real host.
    route = request.path[len(API):] if request.path.startswith(API + "/") else None
    if route is not None and route not in PUBLIC and uid() is None:
        return fail("error", 401, "not signed in")
    return None


# ---- Account ----

@app.route(API + "/ping")
def ping():
    return ok()


def signedIn(rid):
    token = TOKEN if rid == UID else f"stub-{rid}"
    state["tokens"][token] = rid
    state["deviceUid"] = rid
    return ok(UID=rid, username=state["readers"][rid]["username"], token=token)


@app.route(API + "/device/identify", methods=["POST"])
def identify():
    if not body().get("fingerprint"):
        return fail("error", 400, "missing fingerprint")
    with lock:
        rid = state["deviceUid"]
        return signedIn(rid) if rid else ok(status="new")


@app.route(API + "/auth", methods=["POST"])
def auth():
    data = body()
    username = str(data.get("username") or "").strip()
    password = str(data.get("password") or "")
    key = str(data.get("key") or "").strip()
    if not username or not password or not data.get("fingerprint"):
        return fail("error", 400, "missing credentials")
    with lock:
        if key:
            if not 3 <= len(username) <= 32:
                return fail("error", 400, "a username is 3 to 32 characters")
            if not 8 <= len(password) <= 256:
                return fail("error", 400, "a password is 8 to 256 characters")
            if key != "stub-key":
                return fail("invalid_key", 403)
            if username == "taken" or any(r["username"] == username for r in state["readers"].values()):
                return fail("username_taken", 409)
            rid = state["nextUid"]
            state["nextUid"] += 1
            state["readers"][rid] = {"username": username, "password": password}
            return signedIn(rid)
        for rid, reader in state["readers"].items():
            if reader["username"] == username and reader["password"] == password:
                return signedIn(rid)
    return fail("invalid_credentials", 401)


@app.route(API + "/signout", methods=["POST"])
def signOut():
    with lock:
        state["deviceUid"] = None
        state["tokens"].pop(request.headers.get("X-Session-Token") or "", None)
    return ok()


@app.route(API + "/devices")
def devices():
    rows = [{"id": THIS_DEVICE, "label": THIS_DEVICE[:8], "current": True, "lastSignIn": "2026-11-05T08:00:00Z"}]
    if state["otherDevice"]:
        rows.append({"id": OTHER_DEVICE, "label": OTHER_DEVICE[:8], "current": False, "lastSignIn": None})
    return ok(rows)


@app.route(API + "/devices/<wanted>", methods=["DELETE"])
def removeDevice(wanted):
    if not DEVICE.fullmatch(wanted):
        return fail("error", 404, "no such device")
    if wanted == THIS_DEVICE:
        return fail("error", 400, "this is the device you are using: sign out instead")
    if wanted == OTHER_DEVICE:
        state["otherDevice"] = False
    return ok()


# ---- The catalog ----

@app.route(API + "/catalog")
def catalog():
    if os.environ.get("STUB_CATALOG_DOWN"):
        return fail("error", 503, "the catalog is down")
    data = state["catalog"]
    if request.args.get("version") == data["version"]:
        return ok({"version": data["version"], "unchanged": True})
    return ok(data)


@app.route(API + "/pictures/<name>")
def picture(name):
    if os.environ.get("STUB_SLOW"):
        time.sleep(int(os.environ["STUB_SLOW"]) / 1000)
    target = state["folder"] / "pictures" / name
    if os.environ.get("STUB_PICTURES_FAIL") or not PICTURE.fullmatch(name) or not target.is_file():
        return fail("error", 404, "no picture")
    return send_file(target, mimetype="image/jpeg")


reset()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=PORT, threaded=True)
