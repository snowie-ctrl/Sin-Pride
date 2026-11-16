"""A person's own exercises against docs/api.md and plan decision 3: deleting takes it out of routines, then deletes
it, or hides it once a workout names it."""
from conftest import UID

A = "/api/pride"
ROW = {"ExerciseID": 900, "Source": "own", "SourceKey": "own-0123456789abcdef", "Licence": None,
       "Name": "Sandbag Carry", "Category": None, "Level": None, "Measure": "distance_time", "Region": "upper",
       "RemovedAt": None}
NEW = {"name": "Sandbag Carry", "measure": "distance_time", "primary": ["forearms"], "secondary": ["traps"],
       "equipment": ["other"], "steps": ["Pick it up.", "Walk."]}


def test_ownExercisesNeedASession(anonUserClient):
    assert anonUserClient.get(f"{A}/exercises").status_code == 401


def test_onlyThePersonsOwnAreListed(userClient, useDb):
    conn = useDb(fetchall=[[ROW], [{"ExerciseID": 900, "Muscle": "forearms", "Role": "primary"}],
                           [{"ExerciseID": 900, "Equipment": "other"}], [{"ExerciseID": 900, "Text": "Walk."}], []])
    data = userClient.get(f"{A}/exercises").get_json()["data"]
    assert data[0]["source"] == "own" and data[0]["primary"] == ["forearms"] and data[0]["pictures"] == []
    assert all(params == (UID,) for _, params in conn.cur.executed)
    assert all("OwnerUserID = %s" in sql for sql, _ in conn.cur.executed)


def test_addingOneStoresItWithItsChildrenAndRegion(userClient, useDb):
    conn = useDb(fetchone=[{"UserID": UID}, {"n": 3}], lastrowids={"Exercises": [900]})
    data = userClient.post(f"{A}/exercises", json=NEW).get_json()["data"]
    assert data["id"] == 900 and data["region"] == "upper" and data["key"].startswith("own-")
    assert len(data["key"]) == 20 and data["licence"] is None and data["removed"] is False
    insert = conn.cur.statements("INSERT INTO Exercises")[0][1]
    assert insert[0] == "own" and insert[2:] == ("Sandbag Carry", "distance_time", "upper", UID)
    assert [p for _, p in conn.cur.statements("INSERT INTO ExerciseMuscles")] == [(900, "forearms", "primary"),
                                                                                 (900, "traps", "secondary")]
    assert [p for _, p in conn.cur.statements("INSERT INTO ExerciseSteps")] == [(900, 1, "Pick it up."), (900, 2, "Walk.")]
    assert conn.commits == 1


def test_the201stIsRefused(userClient, useDb):
    conn = useDb(fetchone=[{"UserID": UID}, {"n": 200}])
    answer = userClient.post(f"{A}/exercises", json=NEW)
    assert answer.status_code == 409 and answer.get_json()["status"] == "limit"
    assert not conn.cur.statements("INSERT")


def test_aBadOneIsRefusedNamingTheField(userClient, useDb):
    useDb()
    answer = userClient.post(f"{A}/exercises", json={**NEW, "primary": []})
    assert answer.status_code == 400 and answer.get_json()["field"] == "primary"


def test_editingReplacesItsChildren(userClient, useDb):
    conn = useDb(fetchone=[{"SourceKey": "own-0123456789abcdef", "Measure": "distance_time"}])
    data = userClient.put(f"{A}/exercises/900", json={**NEW, "name": "Sandbag Walk"}).get_json()["data"]
    assert data["name"] == "Sandbag Walk" and data["key"] == "own-0123456789abcdef"
    assert conn.cur.statements("DELETE FROM ExerciseMuscles")[0][1] == (900,)
    assert conn.cur.statements("UPDATE Exercises")[0][1] == ("Sandbag Walk", "distance_time", "upper", 900, UID)


def test_theMeasureCannotChangeOnceItIsUsed(userClient, useDb):
    conn = useDb(fetchone=[{"SourceKey": "own-0123456789abcdef", "Measure": "distance_time"}, {"used": 1}])
    answer = userClient.put(f"{A}/exercises/900", json={**NEW, "measure": "time"})
    assert answer.status_code == 400 and answer.get_json()["field"] == "measure"
    assert not conn.cur.statements("UPDATE")


def test_someoneElsesOrAHiddenOneIs404(userClient, useDb):
    useDb(fetchone=[None])
    assert userClient.put(f"{A}/exercises/900", json=NEW).status_code == 404
    useDb(fetchone=[None])
    assert userClient.delete(f"{A}/exercises/900").status_code == 404


def test_deletingAnUnloggedOneTakesItOutOfRoutinesThenDeletesIt(userClient, useDb):
    conn = useDb(fetchone=[{"SourceKey": "own-0123456789abcdef", "Measure": "distance_time"}, {"n": 2}, None],
                 fetchall=[[{"ProgramID": 5}, {"ProgramID": 6}]])
    assert userClient.delete(f"{A}/exercises/900").get_json()["data"] == {"routinesTouched": 2, "hidden": False}
    sqls = [sql for sql, _ in conn.cur.executed]
    takenOut = next(i for i, s in enumerate(sqls) if s.startswith("DELETE ri FROM RoutineItems"))
    deleted = next(i for i, s in enumerate(sqls) if s.startswith("DELETE FROM Exercises"))
    assert takenOut < deleted and conn.commits == 1
    # Each program whose routines changed is stamped, so another device's open copy is seen to be old.
    assert [p for _, p in conn.cur.statements("UPDATE Programs SET UpdatedAt")] == [(5,), (6,)]


def test_deletingALoggedOneHidesIt(userClient, useDb):
    conn = useDb(fetchone=[{"SourceKey": "own-0123456789abcdef", "Measure": "distance_time"}, {"n": 0}, {"one": 1}])
    assert userClient.delete(f"{A}/exercises/900").get_json()["data"] == {"routinesTouched": 0, "hidden": True}
    assert conn.cur.statements("UPDATE Exercises SET RemovedAt = NOW()")
    assert not conn.cur.statements("DELETE FROM Exercises")
