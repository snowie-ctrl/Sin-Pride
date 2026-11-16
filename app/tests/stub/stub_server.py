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
STUB_SEED=1            the stub reader starts with Upper/Lower adopted (dumbbell and bench, 4 days a week, goal muscle,
                       intro done) and one Upper workout on the Monday of the week holding STUB_TODAY.
STUB_INTRO=1           the stub reader's intro is "pending", so the app opens it.
STUB_TODAY=<date>      YYYY-MM-DD: the day STUB_SEED's workout is placed by, instead of the real today.

Milestone 2's routes are kept per reader in memory. Checks, rules and starters are server/'s own modules, imported
here, so the stub can never disagree with the server on them.
"""
import copy
import functools
import json
import os
import re
import sys
import threading
import time
from datetime import date, timedelta
from pathlib import Path

from flask import Flask, jsonify, request, send_file

API = "/api/pride"
TOKEN = "stub"
UID = 7
PORT = 5089
PUBLIC = {"/ping", "/auth", "/device/identify"}
HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent
sys.path.insert(0, str(REPO / "server"))
import prideCatalog as words, prideChecks as checks, prideRules as rules, prideStarters as starters  # noqa: E402
PICTURE = re.compile(r"[0-9a-f]{20}\.jpg")
DEVICE = re.compile(r"[0-9a-f]{16}")
THIS_DEVICE, OTHER_DEVICE = "f00dfeedf00dfeed", "0a1b2c3d4e5f6071"

app = Flask(__name__)
lock = threading.Lock()
state = {}


def catalogFolder():
    folder = Path(os.environ.get("STUB_SNAPSHOT") or HERE / "snapshot")
    return folder if (folder / "catalog.json").is_file() else HERE / "fixture"


def newPerson(introState):
    return {"profile": {"units": "lb", "goal": "general", "daysPerWeek": 3, "upperIncrement": 5.0,
                        "lowerIncrement": 10.0, "weekStart": "mon", "introState": introState},
            "equipment": [], "programs": {}, "nextId": 1000, "own": {}, "workouts": []}


def reset():
    folder = catalogFolder()
    state.clear()
    state.update({
        "folder": folder,
        "catalog": json.loads((folder / "catalog.json").read_text(encoding="utf-8")),
        "readers": {UID: {"username": "stub", "password": "stub-password"}},
        "tokens": {TOKEN: UID},
        "people": {UID: newPerson("pending" if os.environ.get("STUB_INTRO") else "done")},
        "deviceUid": None if os.environ.get("STUB_NEW_DEVICE") else UID,
        "otherDevice": True,
        "nextUid": 100,
    })
    if os.environ.get("STUB_SEED"):
        seed(state["people"][UID])


def seed(who):
    who["profile"].update(goal="muscle", daysPerWeek=4)
    who["equipment"] = ["dumbbell", "bench", "bodyweight"]
    program = adopt(who, "upperLower")
    day = date.fromisoformat(os.environ.get("STUB_TODAY") or date.today().isoformat())
    who["workouts"].append({"performedOn": rules.weekStartDate(day, "mon"), "programId": program["id"],
                            "routineId": program["routines"][0]["id"], "createdAt": 1})


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
            state["people"][rid] = newPerson("pending")
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


# ---- Milestone 2: what a person owns, kept per reader, answering as server/prideUserRoutes.py does ----

def refuse(refusal):
    return jsonify({"status": "error", "field": refusal.field, "message": refusal.message}), 400


def notFound():
    return fail("error", 404, "not found")


def overLimit(field, message):
    return jsonify({"status": "limit", "field": field, "message": message}), 409


def unavailable():
    return fail("unavailable", 409, "none of this starter's exercises are in the catalog")


def person():
    return state["people"][uid()]


def stamp():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def newId(who):
    who["nextId"] += 1
    return who["nextId"]


def locked(route):
    @functools.wraps(route)
    def wrapper(*args, **kwargs):
        with lock:
            return route(*args, **kwargs)
    return wrapper


def lookup(who, exerciseId):
    """The catalog's or the caller's own exercise, hidden or not (a routine keeps naming one that left; plan
    decision 19)."""
    return next((e for e in state["catalog"]["exercises"] if e["id"] == exerciseId), None) or who["own"].get(exerciseId)


def visible(who, exerciseId):
    """The catalog's or the caller's own exercise, not hidden (plan decision 19); None when there is none."""
    found = lookup(who, exerciseId)
    return None if found is None or found["removed"] else found


def findRoutine(who, routineId):
    return next(((p, r) for p in who["programs"].values() for r in p["routines"] if r["id"] == routineId), (None, None))


def findItem(who, itemId):
    return next(((p, r, i) for p in who["programs"].values() for r in p["routines"] for i in r["items"]
                 if i["id"] == itemId), (None, None, None))


def answer(program):
    return ok(copy.deepcopy(program))


def rows(who):
    return [{"id": p["id"], "title": p["title"], "active": p["active"], "starterKey": p["starterKey"],
             "days": p["days"], "routineCount": len(p["routines"]), "updatedAt": p["updatedAt"]}
            for p in who["programs"].values()]


def addProgram(who, title, starterKey=None, days=(), routines=()):
    """`routines` are (title, items) pairs. A person's first program is the one they follow (plan decision 13)."""
    programId = newId(who)
    who["programs"][programId] = {"id": programId, "title": title, "active": not who["programs"],
                                  "starterKey": starterKey, "days": list(days), "updatedAt": stamp(),
                                  "routines": [{"id": newId(who), "title": t, "items": i} for t, i in routines]}
    return who["programs"][programId]


def programLimit(who):
    if len(who["programs"]) >= checks.LIMITS["programs"]:
        return overLimit("program", f"at most {checks.LIMITS['programs']} programs")
    return None


# Profile

def profileJson(who):
    return {**who["profile"], "equipment": [w for w in words.EQUIPMENT if w in who["equipment"]]}


@app.route(API + "/profile", methods=["GET"])
def getProfile():
    return ok(profileJson(person()))


@app.route(API + "/profile", methods=["PUT"])
@locked
def putProfile():
    who = person()
    try:
        changes = checks.profileChanges(body(), who["profile"]["units"])
    except checks.Refusal as refusal:
        return refuse(refusal)
    who["equipment"] = changes.pop("equipment", who["equipment"])
    who["profile"].update(changes)
    return ok(profileJson(who))


# Own exercises

def ownJson(exerciseId, key, clean):
    return {"id": exerciseId, "key": key, "source": words.OWN_SOURCE, "licence": None, "name": clean["name"],
            "category": None, "level": None, "measure": clean["measure"], "region": clean["region"], "removed": False,
            "primary": clean["primary"], "secondary": clean["secondary"], "equipment": clean["equipment"],
            "steps": clean["steps"], "pictures": []}


@app.route(API + "/exercises", methods=["GET"])
def ownExercises():
    return ok(sorted(copy.deepcopy(list(person()["own"].values())), key=lambda e: (e["name"], e["id"])))


@app.route(API + "/exercises", methods=["POST"])
@locked
def addOwnExercise():
    who = person()
    try:
        clean = checks.ownExercise(body())
    except checks.Refusal as refusal:
        return refuse(refusal)
    if len(who["own"]) >= checks.LIMITS["own"]:
        return overLimit("exercise", f"at most {checks.LIMITS['own']} exercises of your own")
    exerciseId = newId(who)
    who["own"][exerciseId] = ownJson(exerciseId, f"own-{exerciseId}", clean)
    return ok(copy.deepcopy(who["own"][exerciseId]))


@app.route(API + "/exercises/<int:exerciseId>", methods=["PUT"])
@locked
def editOwnExercise(exerciseId):
    who = person()
    try:
        clean = checks.ownExercise(body())
    except checks.Refusal as refusal:
        return refuse(refusal)
    old = who["own"].get(exerciseId)
    if old is None:
        return notFound()
    used = any(i["exerciseId"] == exerciseId for p in who["programs"].values() for r in p["routines"] for i in r["items"])
    if clean["measure"] != old["measure"] and used:
        return refuse(checks.Refusal("measure", "the measure can't change once a routine or workout uses it"))
    who["own"][exerciseId] = ownJson(exerciseId, old["key"], clean)
    return ok(copy.deepcopy(who["own"][exerciseId]))


@app.route(API + "/exercises/<int:exerciseId>", methods=["DELETE"])
@locked
def deleteOwnExercise(exerciseId):
    who = person()
    if exerciseId not in who["own"]:
        return notFound()
    touched = 0
    for program in who["programs"].values():
        for routine in program["routines"]:
            kept = [i for i in routine["items"] if i["exerciseId"] != exerciseId]
            if len(kept) != len(routine["items"]):
                touched += 1
                routine["items"] = kept
                program["updatedAt"] = stamp()
    # The stub logs no workout that names an own exercise, so one is never hidden, only deleted.
    del who["own"][exerciseId]
    return ok({"routinesTouched": touched, "hidden": False})


# Starters

def filled(who, starter):
    found = {e["key"]: {"id": e["id"], "name": e["name"], "measure": e["measure"]}
             for e in state["catalog"]["exercises"] if e["source"] == starters.SOURCE and not e["removed"]}
    p = who["profile"]
    return starters.fill(starter, who["equipment"], p["goal"], p["daysPerWeek"], found)


def adopt(who, key):
    """Copies the starter, filled for this person, into a new active program; None when none of it is in the catalog."""
    plan = filled(who, next(s for s in starters.load() if s["key"] == key))
    if not any(r["items"] for r in plan["routines"]):
        return None
    routines = []
    for routine in plan["routines"]:
        items = []
        for item in routine["items"]:
            targets = dict.fromkeys(checks.TARGET_FIELDS)
            targets.update({k: item[k] for k in ("sets", "repsMin", "repsMax", "targetSeconds", "restSeconds")})
            items.append({"id": newId(who), "exerciseId": item["exerciseId"], **targets})
        routines.append((routine["title"], items))
    for program in who["programs"].values():
        program["active"] = False
    program = addProgram(who, plan["title"], key, plan["days"], routines)
    program["active"] = True
    return program


@app.route(API + "/starters", methods=["GET"])
def listStarters():
    return ok([filled(person(), s) for s in starters.load()])


@app.route(API + "/starters/<key>/adopt", methods=["POST"])
@locked
def adoptStarter(key):
    who = person()
    if programLimit(who):
        return programLimit(who)
    if key not in {s["key"] for s in starters.load()}:
        return notFound()
    program = adopt(who, key)
    return unavailable() if program is None else answer(program)


# Programs

@app.route(API + "/programs", methods=["GET"])
def listPrograms():
    return ok(rows(person()))


@app.route(API + "/programs", methods=["POST"])
@locked
def createProgram():
    who = person()
    try:
        name = checks.title(body().get("title"))
    except checks.Refusal as refusal:
        return refuse(refusal)
    return programLimit(who) or answer(addProgram(who, name))


@app.route(API + "/programs/<int:programId>", methods=["GET"])
def getProgram(programId):
    program = person()["programs"].get(programId)
    return notFound() if program is None else answer(program)


@app.route(API + "/programs/<int:programId>", methods=["PUT"])
@locked
def renameProgram(programId):
    try:
        name = checks.title(body().get("title"))
    except checks.Refusal as refusal:
        return refuse(refusal)
    program = person()["programs"].get(programId)
    if program is None:
        return notFound()
    program.update(title=name, updatedAt=stamp())
    return answer(program)


@app.route(API + "/programs/<int:programId>/duplicate", methods=["POST"])
@locked
def duplicateProgram(programId):
    who = person()
    if programLimit(who):
        return programLimit(who)
    source = who["programs"].get(programId)
    if source is None:
        return notFound()
    # Plan decision 14: "<title> copy", cut to the title's 60 characters; not active.
    name = source["title"][:checks.LIMITS["title"] - len(" copy")] + " copy"
    copied = addProgram(who, name, source["starterKey"], source["days"],
                        [(r["title"], [{**i, "id": newId(who)} for i in r["items"]]) for r in source["routines"]])
    copied["active"] = False
    return answer(copied)


@app.route(API + "/programs/<int:programId>", methods=["DELETE"])
@locked
def deleteProgram(programId):
    who = person()
    if who["programs"].pop(programId, None) is None:
        return notFound()
    return ok(rows(who))


@app.route(API + "/programs/<int:programId>/activate", methods=["POST"])
@locked
def activateProgram(programId):
    who = person()
    if programId not in who["programs"]:
        return notFound()
    for program in who["programs"].values():
        program["active"] = program["id"] == programId
    who["programs"][programId]["updatedAt"] = stamp()
    return ok(rows(who))


@app.route(API + "/programs/<int:programId>/days", methods=["PUT"])
@locked
def setProgramDays(programId):
    program = person()["programs"].get(programId)
    if program is None:
        return notFound()
    try:
        days = checks.weekdays(body().get("days"))
    except checks.Refusal as refusal:
        return refuse(refusal)
    program.update(days=days, updatedAt=stamp())
    return answer(program)


# Routines and items

def reorder(rowsOf, order):
    if sorted(order) != sorted(r["id"] for r in rowsOf):
        raise checks.Refusal("order", "order must list every one of them, each once")
    rowsOf.sort(key=lambda r: order.index(r["id"]))


@app.route(API + "/routines", methods=["POST"])
@locked
def addRoutine():
    who, data = person(), body()
    try:
        programId = checks.idOf(data.get("programId"), "programId")
        name = checks.title(data.get("title"))
    except checks.Refusal as refusal:
        return refuse(refusal)
    program = who["programs"].get(programId)
    if program is None:
        return notFound()
    if len(program["routines"]) >= checks.LIMITS["routines"]:
        return overLimit("routine", f"at most {checks.LIMITS['routines']} routines in a program")
    program["routines"].append({"id": newId(who), "title": name, "items": []})
    program["updatedAt"] = stamp()
    return answer(program)


@app.route(API + "/routines/<int:routineId>", methods=["PUT"])
@locked
def renameRoutine(routineId):
    try:
        name = checks.title(body().get("title"))
    except checks.Refusal as refusal:
        return refuse(refusal)
    program, routine = findRoutine(person(), routineId)
    if routine is None:
        return notFound()
    routine["title"] = name
    program["updatedAt"] = stamp()
    return answer(program)


@app.route(API + "/routines/<int:routineId>", methods=["DELETE"])
@locked
def deleteRoutine(routineId):
    program, routine = findRoutine(person(), routineId)
    if routine is None:
        return notFound()
    program["routines"].remove(routine)
    program["updatedAt"] = stamp()
    return answer(program)


@app.route(API + "/routines/reorder", methods=["POST"])
@locked
def reorderRoutines():
    data = body()
    try:
        programId = checks.idOf(data.get("programId"), "programId")
        order = checks.idList(data.get("order"))
    except checks.Refusal as refusal:
        return refuse(refusal)
    program = person()["programs"].get(programId)
    if program is None:
        return notFound()
    try:
        reorder(program["routines"], order)
    except checks.Refusal as refusal:
        return refuse(refusal)
    program["updatedAt"] = stamp()
    return answer(program)


@app.route(API + "/routine-items", methods=["POST"])
@locked
def addItem():
    who, data = person(), body()
    try:
        routineId = checks.idOf(data.get("routineId"), "routineId")
        exerciseId = checks.idOf(data.get("exerciseId"), "exerciseId")
    except checks.Refusal as refusal:
        return refuse(refusal)
    program, routine = findRoutine(who, routineId)
    if routine is None:
        return notFound()
    exercise = visible(who, exerciseId)
    if exercise is None:
        return refuse(checks.Refusal("exerciseId", "no such exercise in the catalog or yours"))
    if len(routine["items"]) >= checks.LIMITS["items"]:
        return overLimit("item", f"at most {checks.LIMITS['items']} exercises in a routine")
    given = {k: data[k] for k in checks.TARGET_FIELDS if k in data}
    defaults = checks.itemDefaults(exercise["measure"], who["profile"]["goal"], who["profile"]["units"])
    try:
        targets = checks.itemTargets(exercise["measure"], {**defaults, **given})
    except checks.Refusal as refusal:
        return refuse(refusal)
    routine["items"].append({"id": newId(who), "exerciseId": exerciseId, **targets})
    program["updatedAt"] = stamp()
    return answer(program)


@app.route(API + "/routine-items/<int:itemId>", methods=["PUT"])
@locked
def editItem(itemId):
    who = person()
    program, routine, item = findItem(who, itemId)
    if item is None:
        return notFound()
    try:
        targets = checks.itemTargets(lookup(who, item["exerciseId"])["measure"], body())
    except checks.Refusal as refusal:
        return refuse(refusal)
    item.update(targets)
    program["updatedAt"] = stamp()
    return answer(program)


@app.route(API + "/routine-items/<int:itemId>", methods=["DELETE"])
@locked
def deleteItem(itemId):
    program, routine, item = findItem(person(), itemId)
    if item is None:
        return notFound()
    routine["items"].remove(item)
    program["updatedAt"] = stamp()
    return answer(program)


@app.route(API + "/routine-items/reorder", methods=["POST"])
@locked
def reorderItems():
    data = body()
    try:
        routineId = checks.idOf(data.get("routineId"), "routineId")
        order = checks.idList(data.get("order"))
    except checks.Refusal as refusal:
        return refuse(refusal)
    program, routine = findRoutine(person(), routineId)
    if routine is None:
        return notFound()
    try:
        reorder(routine["items"], order)
    except checks.Refusal as refusal:
        return refuse(refusal)
    program["updatedAt"] = stamp()
    return answer(program)


# Today

@app.route(API + "/today", methods=["GET"])
def today():
    who = person()
    try:
        day = checks.isoDate(request.args.get("date"))
    except checks.Refusal as refusal:
        return refuse(refusal)
    weekStart = who["profile"]["weekStart"]
    first = rules.weekStartDate(day, weekStart)
    done = {w["performedOn"] for w in who["workouts"] if first <= w["performedOn"] <= first + timedelta(days=6)}
    program = next((p for p in who["programs"].values() if p["active"]), None)
    if program is None:
        return ok({"program": None, "nextUp": None, "plannedDay": None,
                   "week": rules.week(day, weekStart, set(), done)})
    routines = program["routines"]
    latest = max((w for w in who["workouts"] if w["programId"] == program["id"]),
                 key=lambda w: (w["performedOn"], w["createdAt"]), default=None)
    nextId = rules.nextUp([r["id"] for r in routines], latest["routineId"] if latest else None)
    nextUp = None
    if nextId is not None:
        routine = next(r for r in routines if r["id"] == nextId)
        nextUp = {"routineId": nextId, "title": routine["title"], "items": copy.deepcopy(routine["items"])}
    weekdays = set(program["days"]) if routines else set()
    planned = rules.plannedDay(day, weekdays, day in done) if routines else None
    return ok({"program": {"id": program["id"], "title": program["title"]}, "nextUp": nextUp,
               "plannedDay": planned.isoformat() if planned else None,
               "week": rules.week(day, weekStart, weekdays, done)})


reset()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=PORT, threaded=True)
