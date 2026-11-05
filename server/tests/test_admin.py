"""The importer's admin routes against docs/api.md, and the checks and version they rest on."""
import hashlib

import pytest

import samples

B = "/api/pride-admin"
SOURCE = "free-exercise-db"


def stored(key, exerciseId, hash="a" * 40, removed=None):
    return {"ExerciseID": exerciseId, "SourceKey": key, "ContentHash": hash, "RemovedAt": removed}


def versionRows(*keys):
    return [{"Source": SOURCE, "SourceKey": k, "ContentHash": "a" * 40, "RemovedAt": None} for k in keys]


def put(client, name, data):
    return client.put(f"{B}/pictures/{name}", data=data, content_type="image/jpeg")


# ---- the token ----

def test_everyRouteNeedsTheToken(anonAdminClient):
    assert anonAdminClient.get(f"{B}/state").status_code == 401
    assert anonAdminClient.get(f"{B}/pictures").status_code == 401
    assert anonAdminClient.post(f"{B}/import", json=samples.batch()).status_code == 401
    assert put(anonAdminClient, samples.PICTURE, samples.JPEG).status_code == 401


def test_aWrongTokenIsRefused(anonAdminClient):
    anonAdminClient.environ_base["HTTP_X_ADMIN_TOKEN"] = "nope"
    assert anonAdminClient.get(f"{B}/state").status_code == 401


def test_aRequestThroughTheTunnelIsRefusedEvenWithTheToken(adminClient, useDb):
    conn = useDb(fetchone=[{"Version": "b" * 40}], fetchall=[[]])
    adminClient.environ_base["HTTP_CF_CONNECTING_IP"] = "203.0.113.9"
    assert adminClient.get(f"{B}/state").status_code == 404
    assert adminClient.post(f"{B}/import", json=samples.batch()).status_code == 404
    assert conn.cur.executed == []


# ---- state and pictures ----

def test_stateListsEveryCatalogRow(adminClient, useDb):
    from datetime import datetime
    useDb(fetchone=[{"Version": "b" * 40}],
          fetchall=[[{"Source": SOURCE, "SourceKey": "Plank", "Name": "Plank", "ContentHash": "c" * 40,
                      "RemovedAt": datetime(2026, 11, 1)}]])
    answer = adminClient.get(f"{B}/state").get_json()
    assert answer == {"status": "ok", "version": "b" * 40,
                      "exercises": [{"source": SOURCE, "key": "Plank", "name": "Plank", "hash": "c" * 40,
                                     "removed": True}]}


def test_picturesListsWhatTheServerHas(adminClient, media):
    (media / samples.PICTURE).write_bytes(samples.JPEG)
    (media / "notes.txt").write_text("not a picture")
    assert adminClient.get(f"{B}/pictures").get_json() == {"status": "ok", "pictures": [samples.PICTURE]}


def test_aPictureIsStoredUnderItsName(adminClient, media):
    answer = put(adminClient, samples.PICTURE, samples.JPEG)
    assert answer.get_json() == {"status": "ok", "stored": samples.PICTURE}
    assert (media / samples.PICTURE).read_bytes() == samples.JPEG
    assert not list(media.glob("*.part"))
    # Sending it again is fine.
    assert put(adminClient, samples.PICTURE, samples.JPEG).status_code == 200


def test_aPictureWhoseBytesDoNotMatchItsNameIsRefused(adminClient, media):
    other = "f" * 20 + ".jpg"
    assert put(adminClient, other, samples.JPEG).status_code == 400
    assert not (media / other).exists()


def test_somethingThatIsNotAJpegIsRefused(adminClient, media):
    data = b"<html>a captive portal</html>"
    name = hashlib.sha1(data).hexdigest()[:20] + ".jpg"
    assert put(adminClient, name, data).status_code == 400


def test_aPictureOverTwoMegabytesIsRefused(adminClient):
    data = b"\xff\xd8\xff" + b"x" * (2 * 1024 * 1024)
    name = hashlib.sha1(data).hexdigest()[:20] + ".jpg"
    assert put(adminClient, name, data).status_code == 413


@pytest.mark.parametrize("name", ["picture.jpg", "0123456789abcdef0123.png", "..%2F..%2Fx.jpg"])
def test_aNameThatIsNotOneIsRefused(adminClient, name):
    assert put(adminClient, name, samples.JPEG).status_code in (400, 404)


# ---- the checks ----

@pytest.mark.parametrize("changes, words", [
    ({"key": ""}, "key"), ({"name": " "}, "name"), ({"category": "yoga"}, "category"), ({"level": "pro"}, "level"),
    ({"measure": "laps"}, "measure"), ({"region": "core"}, "region"), ({"licence": ""}, "licence"),
    ({"primary": []}, "primary"), ({"primary": ["wings"]}, "primary"), ({"secondary": ["biceps"]}, "secondary"),
    ({"equipment": []}, "equipment"), ({"equipment": ["rope"]}, "equipment"), ({"steps": ["", "x"]}, "steps"),
    ({"steps": ["x" * 1001]}, "steps"), ({"pictures": ["x.jpg"]}, "pictures"), ({"hash": "abc"}, "hash"),
    ({"primary": ["biceps", "biceps"]}, "primary"),
])
def test_exerciseProblemNamesTheField(catalog, changes, words):
    problem = catalog.exerciseProblem(samples.exercise(**changes))
    assert problem and words in problem


def test_aValidExerciseHasNoProblem(catalog):
    assert catalog.exerciseProblem(samples.exercise()) is None
    assert catalog.exerciseProblem(samples.exercise(pictures=[], steps=[], secondary=[])) is None


@pytest.mark.parametrize("data", [{}, {"source": "own", "exercises": [samples.exercise()]},
                                  {"source": "Free DB", "exercises": [samples.exercise()]},
                                  {"source": SOURCE, "exercises": []},
                                  {"source": SOURCE, "exercises": [samples.exercise(), samples.exercise()]}])
def test_batchProblemRefusesABadBatch(catalog, data):
    assert catalog.batchProblem(data)


def test_theVersionDependsOnTheRowsNotTheirOrder(catalog):
    rows = versionRows("A", "B")
    assert catalog.versionOf(rows) == catalog.versionOf(list(reversed(rows)))
    assert len(catalog.versionOf(rows)) == 40
    hidden = [dict(rows[0], RemovedAt="2026-11-01"), rows[1]]
    assert catalog.versionOf(hidden) != catalog.versionOf(rows)


# ---- the import ----

def test_aNewExerciseIsInsertedWithItsChildren(adminClient, useDb, media, catalog):
    (media / samples.PICTURE).write_bytes(samples.JPEG)
    conn = useDb(fetchall=[[], versionRows("Barbell_Curl")], lastrowids={"Exercises": [41]})
    answer = adminClient.post(f"{B}/import", json=samples.batch())
    assert answer.status_code == 200, answer.get_json()
    result = answer.get_json()
    assert (result["added"], result["changed"], result["unchanged"], result["hidden"]) == (1, 0, 0, 0)
    assert result["version"] == catalog.versionOf(versionRows("Barbell_Curl"))
    assert conn.cur.executed[0][0].endswith("WHERE Source = %s AND OwnerUserID IS NULL FOR UPDATE")
    insert = conn.cur.statements("INSERT INTO Exercises")[0]
    assert insert[1] == (SOURCE, "Barbell_Curl", "Unlicense", "Barbell Curl", "strength", "beginner", "weight_reps",
                         "upper", "a" * 40)
    assert conn.cur.statements("INSERT INTO ExerciseMuscles")[0][1] == [41, "biceps", "primary", 41, "forearms", "secondary"]
    assert conn.cur.statements("INSERT INTO ExerciseEquipment")[0][1] == [41, "barbell"]
    assert conn.cur.statements("INSERT INTO ExerciseSteps")[0][1] == [41, 1, "Stand up straight.", 41, 2, "Curl the bar."]
    assert conn.cur.statements("INSERT INTO ExercisePictures")[0][1] == [41, 0, samples.PICTURE]
    assert conn.cur.statements("INSERT INTO CatalogVersion")[0][1] == (result["version"],)
    # The version hashes every catalog row, hidden ones included: no filter on RemovedAt or Source.
    versionSelect = conn.cur.statements("SELECT Source, SourceKey, ContentHash, RemovedAt FROM Exercises")[0][0]
    assert versionSelect.endswith("WHERE OwnerUserID IS NULL")
    assert conn.commits == 1


def test_anUnchangedExerciseIsLeftAlone(adminClient, useDb, media):
    (media / samples.PICTURE).write_bytes(samples.JPEG)
    conn = useDb(fetchall=[[stored("Barbell_Curl", 41)], versionRows("Barbell_Curl")])
    result = adminClient.post(f"{B}/import", json=samples.batch()).get_json()
    assert (result["added"], result["changed"], result["unchanged"]) == (0, 0, 1)
    assert not conn.cur.statements("INSERT INTO Exercises") and not conn.cur.statements("UPDATE Exercises")
    assert not conn.cur.statements("DELETE")


def test_aChangedExerciseIsUpdatedAndItsChildrenReplaced(adminClient, useDb, media):
    (media / samples.PICTURE).write_bytes(samples.JPEG)
    conn = useDb(fetchall=[[stored("Barbell_Curl", 41, hash="0" * 40)], versionRows("Barbell_Curl")])
    result = adminClient.post(f"{B}/import", json=samples.batch()).get_json()
    assert result["changed"] == 1
    assert not conn.cur.statements("INSERT INTO Exercises"), "a changed exercise keeps its ExerciseID"
    update = conn.cur.statements("UPDATE Exercises SET Licence")[0]
    assert "RemovedAt = NULL" in update[0] and update[1][-1] == 41
    sqls = [sql for sql, _ in conn.cur.executed]
    for table in ("ExerciseMuscles", "ExerciseEquipment", "ExerciseSteps", "ExercisePictures"):
        delete = sqls.index(f"DELETE FROM {table} WHERE ExerciseID = %s")
        assert all(delete < n for n, sql in enumerate(sqls) if sql.startswith(f"INSERT INTO {table} "))


def test_aHiddenExerciseThatReturnsIsShownAgain(adminClient, useDb, media):
    (media / samples.PICTURE).write_bytes(samples.JPEG)
    conn = useDb(fetchall=[[stored("Barbell_Curl", 41, removed="2026-11-01")], versionRows("Barbell_Curl")])
    assert adminClient.post(f"{B}/import", json=samples.batch()).get_json()["changed"] == 1
    assert not conn.cur.statements("INSERT INTO Exercises"), "a returning exercise keeps its ExerciseID"
    assert "RemovedAt = NULL" in conn.cur.statements("UPDATE Exercises SET Licence")[0][0]


def test_oneMissingOfTenIsHidden(adminClient, useDb, media):
    (media / samples.PICTURE).write_bytes(samples.JPEG)
    keys = [f"E{n}" for n in range(10)]
    conn = useDb(fetchall=[[stored(k, 100 + n) for n, k in enumerate(keys)], versionRows(*keys)], rowcounts=[1])
    sent = samples.batch(*[samples.exercise(k) for k in keys[:9]])
    result = adminClient.post(f"{B}/import", json=sent).get_json()
    assert result["hidden"] == 1 and result["unchanged"] == 9
    hide = conn.cur.statements("UPDATE Exercises SET RemovedAt = NOW()")[0]
    assert hide[1] == [109]
    assert conn.commits == 1


def test_hidingMoreThanATenthIsRefusedAndNothingIsWritten(adminClient, useDb, media):
    (media / samples.PICTURE).write_bytes(samples.JPEG)
    keys = [f"E{n}" for n in range(10)]
    conn = useDb(fetchall=[[stored(k, 100 + n) for n, k in enumerate(keys)]])
    sent = samples.batch(*[samples.exercise(k) for k in keys[:8]])
    answer = adminClient.post(f"{B}/import", json=sent)
    assert answer.status_code == 409 and "2 of 10" in answer.get_json()["message"]
    assert conn.commits == 0
    assert not [sql for sql, _ in conn.cur.executed if not sql.startswith("SELECT")]


def test_aBadExerciseIsRefusedNamingItsKeyBeforeAnyQuery(adminClient, media):
    (media / samples.PICTURE).write_bytes(samples.JPEG)
    answer = adminClient.post(f"{B}/import", json=samples.batch(samples.exercise("Bad_One", primary=["wings"])))
    assert answer.status_code == 400 and "Bad_One" in answer.get_json()["message"]


def test_aPictureTheServerLacksIsRefusedBeforeAnyQuery(adminClient):
    answer = adminClient.post(f"{B}/import", json=samples.batch())
    assert answer.status_code == 400 and samples.PICTURE in answer.get_json()["message"]


def test_aDatabaseFailureCommitsNothing(adminClient, useDb, media):
    (media / samples.PICTURE).write_bytes(samples.JPEG)
    conn = useDb(fetchall=[[]], lastrowids={"Exercises": [41]}, failOn="INSERT INTO ExerciseSteps")
    assert adminClient.post(f"{B}/import", json=samples.batch()).status_code == 500
    assert conn.commits == 0 and conn.rollbacks >= 1
