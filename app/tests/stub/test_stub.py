"""Checks that the stub serves what docs/api.md promises, so the app is built against the real shapes."""
import json
import uuid
from pathlib import Path

import pytest

import stub_server as stub

API = stub.API
AUTH = {"X-Session-Token": stub.TOKEN}
SHAPE = {"id", "key", "source", "licence", "name", "category", "level", "measure", "region", "removed", "primary",
         "secondary", "equipment", "steps", "pictures"}


@pytest.fixture
def client(monkeypatch):
    for name in ("STUB_NEW_DEVICE", "STUB_CATALOG_DOWN", "STUB_PICTURES_FAIL", "STUB_SLOW", "STUB_SEED", "STUB_INTRO",
                 "STUB_TODAY"):
        monkeypatch.delenv(name, raising=False)
    # The fixture, even once a real snapshot sits in snapshot/, so these checks never depend on it.
    monkeypatch.setenv("STUB_SNAPSHOT", str(stub.HERE / "fixture"))
    stub.reset()
    stub.app.config["TESTING"] = True
    return stub.app.test_client()


def test_routesNeedTheTokenButPingDoesNot(client):
    assert client.get(API + "/catalog").status_code == 401
    assert client.get(API + "/ping").get_json() == {"status": "ok"}


def test_aKnownDeviceSignsInAndANewOneDoesNot(client, monkeypatch):
    answer = client.post(API + "/device/identify", json={"fingerprint": "x"}).get_json()
    assert answer == {"status": "ok", "UID": 7, "username": "stub", "token": "stub"}
    monkeypatch.setenv("STUB_NEW_DEVICE", "1")
    stub.reset()
    assert client.post(API + "/device/identify", json={"fingerprint": "x"}).get_json() == {"status": "new"}


def test_signInSignUpAndTheirRefusals(client):
    assert client.post(API + "/auth", json={"username": "stub", "password": "nope", "fingerprint": "x"}).status_code == 401
    made = client.post(API + "/auth", json={"username": "newbie", "password": "long-enough", "fingerprint": "x",
                                            "key": "stub-key"}).get_json()
    assert made["status"] == "ok" and made["UID"] >= 100
    wrongKey = client.post(API + "/auth", json={"username": "other", "password": "long-enough", "fingerprint": "x",
                                                "key": "nope"})
    assert wrongKey.status_code == 403 and wrongKey.get_json()["status"] == "invalid_key"
    taken = client.post(API + "/auth", json={"username": "taken", "password": "long-enough", "fingerprint": "x",
                                             "key": "stub-key"})
    assert taken.status_code == 409 and taken.get_json()["status"] == "username_taken"
    short = client.post(API + "/auth", json={"username": "ab", "password": "long-enough", "fingerprint": "x",
                                             "key": "stub-key"})
    assert short.status_code == 400


def test_signingOutForgetsTheDevice(client):
    assert client.post(API + "/signout", json={"fingerprint": "x"}, headers=AUTH).get_json() == {"status": "ok"}
    assert client.post(API + "/device/identify", json={"fingerprint": "x"}).get_json() == {"status": "new"}
    assert client.get(API + "/catalog", headers=AUTH).status_code == 401


def test_devicesAreListedAndAnotherIsRemoved(client):
    rows = client.get(API + "/devices", headers=AUTH).get_json()["data"]
    assert [r["current"] for r in rows] == [True, False]
    assert client.delete(API + f"/devices/{stub.THIS_DEVICE}", headers=AUTH).status_code == 400
    assert client.delete(API + f"/devices/{stub.OTHER_DEVICE}", headers=AUTH).get_json() == {"status": "ok"}
    assert len(client.get(API + "/devices", headers=AUTH).get_json()["data"]) == 1
    assert client.delete(API + "/devices/nope", headers=AUTH).status_code == 404


def test_theCatalogIsWholeOrUnchanged(client):
    data = client.get(API + "/catalog", headers=AUTH).get_json()["data"]
    assert data["version"] == "fixture-1" and len(data["exercises"]) == 11
    assert all(set(e) == SHAPE for e in data["exercises"])
    names = [e["name"] for e in data["exercises"]]
    assert names == sorted(names, key=str.casefold) and [e["id"] for e in data["exercises"]] == list(range(1, 12))
    same = client.get(API + "/catalog?version=fixture-1", headers=AUTH).get_json()["data"]
    assert same == {"version": "fixture-1", "unchanged": True}


def test_everyPictureTheCatalogNamesIsServed(client):
    data = client.get(API + "/catalog", headers=AUTH).get_json()["data"]
    names = [p for e in data["exercises"] for p in e["pictures"]]
    assert len(names) == 20
    for name in names:
        answer = client.get(API + f"/pictures/{name}", headers=AUTH)
        assert answer.status_code == 200 and answer.data[:3] == b"\xff\xd8\xff", name
    halo = next(e for e in data["exercises"] if e["key"] == "Kettlebell_Halo")
    assert halo["pictures"] == []


def test_aBadOrMissingPictureIs404(client):
    assert client.get(API + "/pictures/..%2Fcatalog.json", headers=AUTH).status_code == 404
    assert client.get(API + f"/pictures/{'0' * 20}.jpg", headers=AUTH).status_code == 404


def test_theSwitchesBreakWhatTheySay(client, monkeypatch):
    monkeypatch.setenv("STUB_CATALOG_DOWN", "1")
    assert client.get(API + "/catalog", headers=AUTH).status_code == 503
    monkeypatch.setenv("STUB_PICTURES_FAIL", "1")
    name = json.loads((stub.HERE / "fixture" / "catalog.json").read_text(encoding="utf-8"))["exercises"][0]["pictures"][0]
    assert client.get(API + f"/pictures/{name}", headers=AUTH).status_code == 404


def get(client, path):
    return client.get(API + path, headers=AUTH)


def send(client, method, path, body=None):
    return getattr(client, method)(API + path, headers=AUTH, json=body if body is not None else {})


def test_theProfileIsReadAndChanged(client):
    profile = get(client, "/profile").get_json()["data"]
    assert profile["units"] == "lb" and profile["introState"] == "done"
    changed = send(client, "put", "/profile", {"units": "kg", "equipment": ["bench", "dumbbell"]}).get_json()["data"]
    assert (changed["upperIncrement"], changed["equipment"]) == (2.5, ["dumbbell", "bench"])
    refused = send(client, "put", "/profile", {"daysPerWeek": 9})
    assert refused.status_code == 400 and refused.get_json()["field"] == "daysPerWeek"


def test_aSignUpStartsWithTheIntroPending(client):
    token = client.post(API + "/auth", json={"username": "newbie", "password": "long-enough", "fingerprint": "x",
                                             "key": "stub-key"}).get_json()["token"]
    profile = client.get(API + "/profile", headers={"X-Session-Token": token}).get_json()["data"]
    assert profile["introState"] == "pending"


def test_programsRoutinesAndItemsAnswerTheWholeProgram(client):
    program = send(client, "post", "/programs", {"title": "Mine"}).get_json()["data"]
    assert program["active"] is True and program["routines"] == []
    program = send(client, "post", "/routines", {"programId": program["id"], "title": "A"}).get_json()["data"]
    program = send(client, "post", "/routines", {"programId": program["id"], "title": "B"}).get_json()["data"]
    a, b = (r["id"] for r in program["routines"])
    program = send(client, "post", "/routine-items", {"routineId": a, "exerciseId": 1}).get_json()["data"]
    item = program["routines"][0]["items"][0]
    assert (item["sets"], item["repsMin"], item["repsMax"]) == (3, 10, 15)
    program = send(client, "post", "/routines/reorder", {"programId": program["id"], "order": [b, a]}).get_json()["data"]
    assert [r["title"] for r in program["routines"]] == ["B", "A"]
    program = send(client, "put", f"/programs/{program['id']}/days", {"days": [4, 0]}).get_json()["data"]
    assert program["days"] == [0, 4]
    bad = send(client, "put", f"/routine-items/{item['id']}", {**item, "repsMin": 20})
    assert bad.status_code == 400 and bad.get_json()["field"] == "repsMax"
    assert send(client, "get", "/programs/999").status_code == 404


def test_adoptingAStarterAgainstTheFixtureLeavesTheMissingOut(client):
    starters = get(client, "/starters").get_json()["data"]
    assert [s["key"] for s in starters] == ["foundations", "upperLower", "pushPullLegs"]
    assert "Barbell_Squat" not in starters[0]["missing"] and starters[0]["missing"]
    program = send(client, "post", "/starters/foundations/adopt").get_json()["data"]
    assert program["active"] is True and program["starterKey"] == "foundations"
    assert all(i["exerciseId"] for r in program["routines"] for i in r["items"])


def test_ownExercisesAreAddedAndDeleted(client):
    own = send(client, "post", "/exercises", {"name": "Sandbag Carry", "measure": "distance_time",
                                              "primary": ["forearms"], "equipment": ["other"]}).get_json()["data"]
    assert own["source"] == "own" and own["region"] == "upper"
    assert [e["name"] for e in get(client, "/exercises").get_json()["data"]] == ["Sandbag Carry"]
    gone = send(client, "delete", f"/exercises/{own['id']}").get_json()["data"]
    assert gone == {"routinesTouched": 0, "hidden": False}
    assert get(client, "/exercises").get_json()["data"] == []


def test_todayWithASeededProgram(client, monkeypatch):
    monkeypatch.setenv("STUB_SEED", "1")
    monkeypatch.setenv("STUB_TODAY", "2026-11-18")
    stub.reset()
    data = get(client, "/today?date=2026-11-18").get_json()["data"]
    assert data["program"]["title"] == "Upper/Lower"
    assert data["nextUp"]["title"] == "Lower"          # the seeded workout was Upper
    assert data["week"][0]["done"] is True
    assert get(client, "/today").status_code == 400


def test_theIntroSwitchLeavesTheStubReadersIntroPending(client, monkeypatch):
    monkeypatch.setenv("STUB_INTRO", "1")
    stub.reset()
    assert get(client, "/profile").get_json()["data"]["introState"] == "pending"


def test_anItemOfARemovedCatalogExerciseCanStillBeEdited(client):
    program = send(client, "post", "/programs", {"title": "Mine"}).get_json()["data"]
    program = send(client, "post", "/routines", {"programId": program["id"], "title": "A"}).get_json()["data"]
    program = send(client, "post", "/routine-items", {"routineId": program["routines"][0]["id"],
                                                      "exerciseId": 1}).get_json()["data"]
    item = program["routines"][0]["items"][0]
    # The catalog drops the exercise after the routine took it; the routine keeps naming it (plan decision 19).
    next(e for e in stub.state["catalog"]["exercises"] if e["id"] == 1)["removed"] = True
    answer = send(client, "put", f"/routine-items/{item['id']}", {**item, "sets": 4})
    assert answer.status_code == 200 and answer.get_json()["data"]["routines"][0]["items"][0]["sets"] == 4


def test_deletingAnOwnExerciseStampsTheProgramsItChanged(client, monkeypatch):
    monkeypatch.setattr(stub, "stamp", lambda: "T-new")
    own = send(client, "post", "/exercises", {"name": "Sandbag Carry", "measure": "distance_time",
                                              "primary": ["forearms"], "equipment": ["other"]}).get_json()["data"]
    program = send(client, "post", "/programs", {"title": "Mine"}).get_json()["data"]
    program = send(client, "post", "/routines", {"programId": program["id"], "title": "A"}).get_json()["data"]
    send(client, "post", "/routine-items", {"routineId": program["routines"][0]["id"], "exerciseId": own["id"]})
    monkeypatch.setattr(stub, "stamp", lambda: "T-deleted")
    send(client, "delete", f"/exercises/{own['id']}")
    assert get(client, f"/programs/{program['id']}").get_json()["data"]["updatedAt"] == "T-deleted"


# ---- Milestone 3: workouts, progress, suggestions, end to end through server/'s own rules ----

CURL = {"sets": 3, "repsMin": 8, "repsMax": 12, "targetWeight": 135, "targetUnit": "lb"}


def routineWith(client, exerciseId=1, **targets):
    """A new program (the person's first, so the active one) with one routine holding one item."""
    program = client.post(API + "/programs", json={"title": "Mine"}, headers=AUTH).get_json()["data"]
    program = client.post(API + "/routines", json={"programId": program["id"], "title": "Arms"},
                          headers=AUTH).get_json()["data"]
    routineId = program["routines"][0]["id"]
    program = client.post(API + "/routine-items", json={"routineId": routineId, "exerciseId": exerciseId, **targets},
                          headers=AUTH).get_json()["data"]
    return program, program["routines"][0]


def workoutBody(routine, reps, weight=135, day="2026-11-16", clientId=None, note=None):
    item = routine["items"][0]
    return {"clientId": clientId or str(uuid.uuid4()), "performedOn": day, "routineId": routine["id"], "note": note,
            "exercises": [{"exerciseId": item["exerciseId"], "itemId": item["id"],
                           "sets": [{"weight": weight, "weightUnit": "lb", "reps": r} for r in reps]}]}


def log(client, routine, reps, **more):
    return client.post(API + "/workouts", json=workoutBody(routine, reps, **more), headers=AUTH)


def getData(client, route):
    return client.get(API + route, headers=AUTH).get_json()["data"]


def test_aWorkoutLogsAndItsResultCardFollowsTheRules(client):
    program, routine = routineWith(client, **CURL)
    first = log(client, routine, [12, 11, 10], day="2026-11-12").get_json()["data"]
    assert first["crowns"] == [] and first["suggestions"] == []
    assert first["nextUp"] == {"routineId": routine["id"], "title": "Arms"}
    assert first["workout"]["title"] == "Arms" and first["workout"]["exercises"][0]["measure"] == "weight_reps"
    second = log(client, routine, [12, 12, 12], day="2026-11-16").get_json()["data"]
    assert [(s["kind"], s["weight"], s["unit"]) for s in second["suggestions"]] == [("increase", 140.0, "lb")]
    third = log(client, routine, [8, 8, 8], weight=150, day="2026-11-17").get_json()["data"]
    assert [c["kind"] for c in third["crowns"]] == ["heaviest", "e1rm"]
    assert third["suggestions"] == []              # the step-up no longer holds: withdrawn


def test_aResentClientIdIsStoredOnce(client):
    program, routine = routineWith(client, **CURL)
    cid = str(uuid.uuid4())
    one = log(client, routine, [10, 10, 10], clientId=cid).get_json()["data"]
    two = log(client, routine, [10, 10, 10], clientId=cid).get_json()["data"]
    assert one["workout"]["id"] == two["workout"]["id"] and len(getData(client, "/workouts")) == 1


def test_aSetOfAnotherMeasureIsRefusedNamingTheField(client):
    program, routine = routineWith(client, **CURL)
    body = workoutBody(routine, [10])
    body["exercises"][0]["sets"] = [{"seconds": 30}]
    answer = client.post(API + "/workouts", json=body, headers=AUTH)
    assert answer.status_code == 400 and answer.get_json()["field"] == "seconds"


def test_takingAStepUpChangesTheTargetAndDismissingLeavesItAlone(client):
    program, routine = routineWith(client, **CURL)
    step = log(client, routine, [12, 12, 12]).get_json()["data"]["suggestions"][0]
    taken = client.post(f"{API}/suggestions/{step['id']}/accept", headers=AUTH)
    assert taken.status_code == 200 and taken.get_json()["data"]["programId"] == program["id"]
    item = getData(client, "/today?date=2026-11-17")["nextUp"]["items"][0]
    assert item["targetWeight"] == 140.0 and item["suggestion"] is None
    again = client.post(f"{API}/suggestions/{step['id']}/accept", headers=AUTH)
    assert again.status_code == 409 and again.get_json()["status"] == "closed"
    nextStep = log(client, routine, [12, 12, 12], weight=140, day="2026-11-17").get_json()["data"]["suggestions"][0]
    assert nextStep["weight"] == 145.0
    assert client.post(f"{API}/suggestions/{nextStep['id']}/dismiss", headers=AUTH).status_code == 200
    item = getData(client, "/today?date=2026-11-17")["nextUp"]["items"][0]
    assert item["targetWeight"] == 140.0 and item["suggestion"] is None


def test_editingTheWorkoutBehindATakenStepUpChangesNothing(client):
    # Review focus 1.
    program, routine = routineWith(client, **CURL)
    saved = log(client, routine, [12, 12, 12]).get_json()["data"]
    client.post(f"{API}/suggestions/{saved['suggestions'][0]['id']}/accept", headers=AUTH)
    body = workoutBody(routine, [12, 12, 12], note="felt strong")
    del body["clientId"]
    edited = client.put(f"{API}/workouts/{saved['workout']['id']}", json=body, headers=AUTH).get_json()["data"]
    assert edited["suggestions"] == [] and edited["workout"]["note"] == "felt strong"
    assert getData(client, "/today?date=2026-11-17")["nextUp"]["items"][0]["targetWeight"] == 140.0


def test_deletingTheLatestWorkoutStepsNextUpBackAndWithdraws(client):
    # Review focus 4: next up steps back, the done mark goes, the step-up based on it is withdrawn, its crowns go.
    program, routine = routineWith(client, **CURL)
    client.post(API + "/routines", json={"programId": program["id"], "title": "Legs"}, headers=AUTH)
    saved = log(client, routine, [12, 12, 12]).get_json()["data"]
    assert saved["nextUp"]["title"] == "Legs"
    answer = client.delete(f"{API}/workouts/{saved['workout']['id']}", headers=AUTH).get_json()["data"]
    assert answer == {"deleted": saved["workout"]["id"], "nextUp": {"routineId": routine["id"], "title": "Arms"}}
    today = getData(client, "/today?date=2026-11-17")
    assert today["nextUp"]["items"][0]["suggestion"] is None and today["week"][0]["done"] is False
    assert today["crowns"] == [] and getData(client, "/records") == []
    assert client.get(f"{API}/workouts/{saved['workout']['id']}", headers=AUTH).status_code == 404


def test_progressRecordsHistoryAndTodaysCrowns(client):
    program, routine = routineWith(client, **CURL)
    exerciseId = routine["items"][0]["exerciseId"]
    log(client, routine, [10, 10, 10], day="2026-11-12")
    log(client, routine, [10, 10, 10], weight=145, day="2026-11-16")
    data = getData(client, f"/progress/{exerciseId}")
    assert [p["value"] for p in data["points"]] == [135.0, 145.0] and data["points"][1]["crowns"] == ["heaviest", "e1rm"]
    assert [r["kind"] for r in data["records"]] == ["heaviest", "e1rm"] and len(data["recent"]) == 2
    assert [e["exerciseId"] for e in getData(client, "/records")] == [exerciseId]
    assert [c["kind"] for c in getData(client, "/today?date=2026-11-17")["crowns"]] == ["heaviest", "e1rm"]
    assert [w["performedOn"] for w in getData(client, "/workouts")] == ["2026-11-16", "2026-11-12"]
    assert client.get(API + "/progress/99999", headers=AUTH).status_code == 404


def test_theRoutinesMenuAndTheDraft(client):
    program, routine = routineWith(client, **CURL)
    log(client, routine, [10, 9, 8], day="2026-11-12")
    menu = getData(client, "/routines")
    assert menu == [{"id": routine["id"], "title": "Arms", "programId": program["id"], "programTitle": "Mine",
                     "active": True}]
    draft = getData(client, f"/workouts/draft?routineId={routine['id']}")
    assert draft["title"] == "Arms" and [s["reps"] for s in draft["items"][0]["last"]["sets"]] == [10, 9, 8]
    assert draft["items"][0]["measure"] == "weight_reps"
    assert client.get(API + "/workouts/draft?routineId=99999", headers=AUTH).status_code == 404


def test_anOwnExerciseALoggedWorkoutNamesIsHiddenNotDeleted(client):
    own = client.post(API + "/exercises", json={"name": "Sandbag Carry", "measure": "time", "primary": ["forearms"],
                                                "equipment": ["other"]}, headers=AUTH).get_json()["data"]
    client.post(API + "/workouts", headers=AUTH, json={
        "clientId": str(uuid.uuid4()), "performedOn": "2026-11-16", "routineId": None, "note": None,
        "exercises": [{"exerciseId": own["id"], "sets": [{"seconds": 60}]}]})
    answer = client.delete(f"{API}/exercises/{own['id']}", headers=AUTH).get_json()["data"]
    assert answer["hidden"] is True
    assert getData(client, "/workouts")[0]["title"] is None
    assert getData(client, f"/progress/{own['id']}")["records"][0]["seconds"] == 60


def test_theSeedHasHistoryStepUpsAndStalls(client, monkeypatch):
    monkeypatch.setenv("STUB_SEED", "1")
    monkeypatch.setenv("STUB_TODAY", "2026-11-17")
    stub.reset()
    workouts = getData(client, "/workouts")
    assert len(workouts) == 9 and workouts[0]["performedOn"] == "2026-11-16"
    today = getData(client, "/today?date=2026-11-17")
    assert today["nextUp"]["title"] == "Lower" and today["week"][0]["done"] is True and today["crowns"]
    drafts = [getData(client, f"/workouts/draft?routineId={r['id']}")["items"] for r in getData(client, "/routines")]
    kinds = {i["suggestion"]["kind"] for items in drafts for i in items if i["suggestion"]}
    assert "increase" in kinds
    if any(len(items) >= 2 for items in drafts):
        assert "stall" in kinds
