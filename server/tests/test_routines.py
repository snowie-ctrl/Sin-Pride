"""Routines and routine items against docs/api.md and plan decisions 15, 16, 18 and 19."""
from conftest import UID
from programSamples import PROGRAM, whole

A = "/api/pride"
ROUTINE = {"RoutineID": 50, "ProgramID": 5}
ITEM = {"ItemID": 500, "RoutineID": 50, "ProgramID": 5, "Measure": "weight_reps"}
PROFILE = {"Units": "kg", "Goal": "strength", "DaysPerWeek": 4, "UpperIncrement": 2.5, "LowerIncrement": 5,
           "WeekStart": "mon", "IntroState": "done"}
FULL = {"sets": 4, "repsMin": 6, "repsMax": 10, "targetWeight": 60, "targetUnit": "kg", "targetSeconds": None,
        "targetDistance": None, "distanceUnit": None, "restSeconds": 120, "note": "pause at the bottom"}


def test_theyNeedASession(anonUserClient):
    assert anonUserClient.post(f"{A}/routines", json={}).status_code == 401
    assert anonUserClient.post(f"{A}/routine-items", json={}).status_code == 401


def test_aNewRoutineGoesLast(userClient, useDb):
    conn = useDb(fetchone=[PROGRAM, {"n": 2, "top": 1}, PROGRAM], fetchall=whole())
    assert userClient.post(f"{A}/routines", json={"programId": 5, "title": "Arms"}).status_code == 200
    assert conn.cur.statements("INSERT INTO Routines")[0][1] == (5, "Arms", 2)
    assert conn.cur.statements("UPDATE Programs SET UpdatedAt")[0][1] == (5,)


def test_the15thRoutineIsRefused(userClient, useDb):
    useDb(fetchone=[PROGRAM, {"n": 14, "top": 13}])
    assert userClient.post(f"{A}/routines", json={"programId": 5, "title": "More"}).status_code == 409


def test_aRoutineNeedsItsProgramsId(userClient):
    answer = userClient.post(f"{A}/routines", json={"programId": "5", "title": "Arms"})
    assert answer.status_code == 400 and answer.get_json()["field"] == "programId"


def test_someoneElsesProgramGetsNoRoutine(userClient, useDb):
    useDb(fetchone=[None])
    assert userClient.post(f"{A}/routines", json={"programId": 5, "title": "Arms"}).status_code == 404


def test_renamingAndDeletingARoutine(userClient, useDb):
    conn = useDb(fetchone=[ROUTINE, PROGRAM], fetchall=whole())
    userClient.put(f"{A}/routines/50", json={"title": "Upper A"})
    assert conn.cur.statements("UPDATE Routines SET Title")[0][1] == ("Upper A", 50)
    conn = useDb(fetchone=[ROUTINE, PROGRAM], fetchall=whole())
    userClient.delete(f"{A}/routines/50")
    assert conn.cur.statements("DELETE FROM Routines")[0][1] == (50,)


def test_reorderingRoutinesTakesTheWholeOrder(userClient, useDb):
    conn = useDb(fetchone=[PROGRAM, PROGRAM], fetchall=[[{"RoutineID": 50}, {"RoutineID": 51}], *whole()])
    userClient.post(f"{A}/routines/reorder", json={"programId": 5, "order": [51, 50]})
    assert [p for _, p in conn.cur.statements("UPDATE Routines SET OrderIndex")] == [(0, 51), (1, 50)]


def test_aPartialOrderIsRefused(userClient, useDb):
    conn = useDb(fetchone=[PROGRAM], fetchall=[[{"RoutineID": 50}, {"RoutineID": 51}]])
    answer = userClient.post(f"{A}/routines/reorder", json={"programId": 5, "order": [51]})
    assert answer.status_code == 400 and answer.get_json()["field"] == "order"
    assert not conn.cur.statements("UPDATE")


def test_aNewItemTakesTheGoalsDefaults(userClient, useDb):
    conn = useDb(fetchone=[ROUTINE, {"ExerciseID": 12, "Measure": "weight_reps"}, {"n": 1, "top": 0}, PROFILE, PROGRAM],
                 fetchall=whole())
    userClient.post(f"{A}/routine-items", json={"routineId": 50, "exerciseId": 12})
    assert conn.cur.statements("INSERT INTO RoutineItems")[0][1] == (
        50, 12, 1, 3, 5, 8, None, None, None, None, None, None, None)


def test_givenTargetsOverrideTheDefaults(userClient, useDb):
    conn = useDb(fetchone=[ROUTINE, {"ExerciseID": 12, "Measure": "weight_reps"}, {"n": 0, "top": None}, PROFILE,
                           PROGRAM], fetchall=whole())
    userClient.post(f"{A}/routine-items", json={"routineId": 50, "exerciseId": 12, "sets": 5,
                                               "targetWeight": 60, "targetUnit": "kg"})
    params = conn.cur.statements("INSERT INTO RoutineItems")[0][1]
    assert params[2:4] == (0, 5) and params[6:8] == (60.0, "kg")


def test_aRemovedOrUnknownExerciseCannotBeAdded(userClient, useDb):
    useDb(fetchone=[ROUTINE, None])
    answer = userClient.post(f"{A}/routine-items", json={"routineId": 50, "exerciseId": 9})
    assert answer.status_code == 400 and answer.get_json()["field"] == "exerciseId"


def test_the31stItemIsRefused(userClient, useDb):
    useDb(fetchone=[ROUTINE, {"ExerciseID": 12, "Measure": "weight_reps"}, {"n": 30, "top": 29}])
    assert userClient.post(f"{A}/routine-items", json={"routineId": 50, "exerciseId": 12}).status_code == 409


def test_editingAnItemReplacesEveryTarget(userClient, useDb):
    conn = useDb(fetchone=[ITEM, PROGRAM], fetchall=whole())
    assert userClient.put(f"{A}/routine-items/500", json=FULL).status_code == 200
    sql, params = conn.cur.statements("UPDATE RoutineItems")[0]
    assert sql.startswith("UPDATE RoutineItems SET Sets = %s, RepsMin = %s")
    assert params == (4, 6, 10, 60.0, "kg", None, None, None, 120, "pause at the bottom", 500)


def test_anEditMissingARequiredTargetIsRefused(userClient, useDb):
    conn = useDb(fetchone=[ITEM])
    answer = userClient.put(f"{A}/routine-items/500", json={**FULL, "repsMin": None})
    assert answer.status_code == 400 and answer.get_json()["field"] == "repsMin"
    assert not conn.cur.statements("UPDATE")


def test_aTimedItemTakesNoReps(userClient, useDb):
    useDb(fetchone=[{**ITEM, "Measure": "time"}])
    answer = userClient.put(f"{A}/routine-items/500", json={"sets": 3, "targetSeconds": 30, "repsMax": 5})
    assert answer.status_code == 400 and answer.get_json()["field"] == "repsMax"


def test_deletingAndReorderingItems(userClient, useDb):
    conn = useDb(fetchone=[ITEM, PROGRAM], fetchall=whole())
    userClient.delete(f"{A}/routine-items/500")
    assert conn.cur.statements("DELETE FROM RoutineItems")[0][1] == (500,)
    conn = useDb(fetchone=[ROUTINE, PROGRAM], fetchall=[[{"ItemID": 500}, {"ItemID": 501}], *whole()])
    userClient.post(f"{A}/routine-items/reorder", json={"routineId": 50, "order": [501, 500]})
    assert [p for _, p in conn.cur.statements("UPDATE RoutineItems SET OrderIndex")] == [(0, 501), (1, 500)]


def test_aRemovedExerciseStaysInItsRoutine(userClient, useDb, userRoutes):
    """Plan decision 19 (Review Focus 2): reading a program never filters exercises, so a hidden one stays named."""
    assert "RemovedAt" not in userRoutes.ITEMS_OF_PROGRAM and "Exercises" not in userRoutes.ITEMS_OF_PROGRAM
    useDb(fetchone=[PROGRAM], fetchall=whole())
    items = userClient.get(f"{A}/programs/5").get_json()["data"]["routines"][0]["items"]
    assert [i["exerciseId"] for i in items] == [12]
