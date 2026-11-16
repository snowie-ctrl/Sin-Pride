"""Workouts against docs/api.md and plan decisions 1-7: save, resend, edit, delete, the history, the draft."""
from datetime import date

from conftest import UID
from logSamples import (ACTIVE, CID, ITEM, LOCK, PROFILE, ROUTINES, TOP, answered, loggedRow, setRow,
                        suggestionRow, workoutRow)

A = "/api/pride"


def body(**changes):
    data = {"clientId": CID, "performedOn": "2026-11-16", "routineId": 50, "note": None,
            "exercises": [{"exerciseId": 12, "itemId": 500,
                           "sets": [{"weight": 135, "weightUnit": "lb", "reps": 12}] * 3}]}
    data.update(changes)
    return data


MEASURES = [{"ExerciseID": 12, "Measure": "weight_reps"}]


def test_theyNeedASession(anonUserClient):
    assert anonUserClient.get(f"{A}/workouts").status_code == 401
    assert anonUserClient.post(f"{A}/workouts", json=body()).status_code == 401
    assert anonUserClient.get(f"{A}/routines").status_code == 401


def test_savingAWorkoutWritesItAndAnswersTheResultCard(userClient, useDb):
    one, all_ = answered(raised=[suggestionRow()])
    conn = useDb(fetchone=[LOCK, None, {"RoutineID": 50, "ProgramID": 5}, PROFILE] + one,
                 fetchall=[MEASURES, [{"ItemID": 500, "ExerciseID": 12}], [ITEM], TOP, []] + all_,
                 lastrowids={"Workouts": [70], "WorkoutExercises": [700]})
    answer = userClient.post(f"{A}/workouts", json=body())
    assert answer.status_code == 200
    assert conn.cur.statements("INSERT INTO Workouts")[0][1] == (UID, CID, date(2026, 11, 16), 5, 50, None)
    assert conn.cur.statements("INSERT INTO WorkoutExercises")[0][1] == (70, 12, 0, 500, None)
    assert [p[:4] for _, p in conn.cur.statements("INSERT INTO WorkoutSets")] == [
        (700, 1, 0, 135.0), (700, 2, 0, 135.0), (700, 3, 0, 135.0)]
    # Every set at the top of the range at the target: the rules made a step-up based on this workout.
    assert conn.cur.statements("INSERT INTO Suggestions")[0][1] == (UID, 500, "increase", 140.0, "lb", None, None,
                                                                   None, 70)
    data = answer.get_json()["data"]
    assert data["workout"]["id"] == 70 and data["workout"]["title"] == "Upper"
    assert data["workout"]["exercises"][0]["measure"] == "weight_reps"
    assert data["workout"]["exercises"][0]["sets"][0] == {"warmup": False, "weight": 135.0, "weightUnit": "lb",
                                                          "reps": 12, "seconds": None, "distance": None,
                                                          "distanceUnit": None}
    assert data["suggestions"][0]["weight"] == 140.0 and data["suggestions"][0]["basedOn"] == 70
    assert data["crowns"] == []                    # its first workout: nothing to beat
    assert data["nextUp"] == {"routineId": 51, "title": "Lower"}
    assert conn.commits == 1


def test_aResultCardNamesTheCrownsTheWorkoutEarned(userClient, useDb):
    earlier = [loggedRow(69, n, weight=130, day=date(2026, 11, 12)) for n in (1, 2, 3)]
    one, all_ = answered(logged=earlier + TOP)
    useDb(fetchone=[LOCK, {"WorkoutID": 70, "UserID": UID}] + one, fetchall=all_)
    crowns = userClient.post(f"{A}/workouts", json=body()).get_json()["data"]["crowns"]
    assert [(c["kind"], c["exerciseId"], c["weight"]) for c in crowns] == [("heaviest", 12, 135.0), ("e1rm", 12, 135.0)]


def test_aResentClientIdIsStoredOnce(userClient, useDb):
    one, all_ = answered()
    conn = useDb(fetchone=[LOCK, {"WorkoutID": 70, "UserID": UID}] + one, fetchall=all_)
    answer = userClient.post(f"{A}/workouts", json=body())
    assert answer.status_code == 200 and answer.get_json()["data"]["workout"]["id"] == 70
    assert not conn.cur.statements("INSERT")


def test_someoneElsesClientIdIsRefused(userClient, useDb):
    useDb(fetchone=[LOCK, {"WorkoutID": 70, "UserID": 99}])
    answer = userClient.post(f"{A}/workouts", json=body())
    assert answer.status_code == 400 and answer.get_json()["field"] == "clientId"


def test_aRefusedWorkoutWritesNothing(userClient, useDb):
    conn = useDb(fetchone=[LOCK, None])
    answer = userClient.post(f"{A}/workouts", json=body(exercises=[]))
    assert answer.status_code == 400 and answer.get_json()["field"] == "exercises"
    assert not conn.cur.statements("INSERT") and conn.commits == 0


def test_anExerciseThePersonMayNotLogIsRefused(userClient, useDb):
    useDb(fetchone=[LOCK, None], fetchall=[[]])
    answer = userClient.post(f"{A}/workouts", json=body())
    assert answer.status_code == 400 and answer.get_json()["field"] == "exerciseId"


def test_afterTomorrowIsRefused(userClient, useDb, logRoutes, monkeypatch):
    monkeypatch.setattr(logRoutes, "latestDay", lambda: date(2026, 11, 15))
    useDb(fetchone=[LOCK, None], fetchall=[MEASURES])
    answer = userClient.post(f"{A}/workouts", json=body())
    assert answer.status_code == 400 and answer.get_json()["field"] == "performedOn"


def test_aRoutineGoneMeanwhileSavesAFreeWorkout(userClient, useDb):
    # Review focus 5 (plan decision 5): the routine and the item were deleted on another device while logging.
    one, all_ = answered()
    conn = useDb(fetchone=[LOCK, None, None] + one, fetchall=[MEASURES, []] + all_,
                 lastrowids={"Workouts": [70], "WorkoutExercises": [700]})
    assert userClient.post(f"{A}/workouts", json=body()).status_code == 200
    assert conn.cur.statements("INSERT INTO Workouts")[0][1][3:5] == (None, None)
    assert conn.cur.statements("INSERT INTO WorkoutExercises")[0][1][3] is None
    assert not conn.cur.statements("INSERT INTO Suggestions")


def test_anItemOfAnotherExerciseIsDropped(userClient, useDb):
    one, all_ = answered()
    conn = useDb(fetchone=[LOCK, None, {"RoutineID": 50, "ProgramID": 5}] + one,
                 fetchall=[MEASURES, [{"ItemID": 500, "ExerciseID": 13}]] + all_,
                 lastrowids={"Workouts": [70], "WorkoutExercises": [700]})
    userClient.post(f"{A}/workouts", json=body())
    assert conn.cur.statements("INSERT INTO WorkoutExercises")[0][1][3] is None


def test_editingReplacesTheExercisesAndRecalculatesOldAndNewItems(userClient, useDb):
    one, all_ = answered()
    conn = useDb(fetchone=[LOCK, {"WorkoutID": 70}, PROFILE] + one,
                 fetchall=[[{"ItemID": 501}], MEASURES, [{"ItemID": 500, "ExerciseID": 12}], [ITEM], TOP, []] + all_,
                 lastrowids={"WorkoutExercises": [700]})
    edited = body(clientId=None, performedOn="2026-11-15", routineId=51, note="felt strong")
    assert userClient.put(f"{A}/workouts/70", json=edited).status_code == 200
    assert conn.cur.statements("DELETE FROM WorkoutExercises")[0][1] == (70,)
    # The date and note change; the routine stays as logged (plan decision 7).
    assert conn.cur.statements("UPDATE Workouts")[0][1] == (date(2026, 11, 15), "felt strong", 70)
    recalc = next((sql, p) for sql, p in conn.cur.executed if "e.Region" in sql and "p.UserID" in sql)
    assert recalc[1] == (UID, 500, 501)
    assert not conn.cur.statements("INSERT INTO Workouts")


def test_editingSomeoneElsesWorkoutIsNotFound(userClient, useDb):
    useDb(fetchone=[LOCK, None])
    assert userClient.put(f"{A}/workouts/70", json=body(clientId=None)).status_code == 404


def test_deletingTheWorkoutBehindAStepUpWithdrawsIt(userClient, useDb):
    # Review focus 4. The real database sets BasedOnWorkoutID to NULL on delete; nothing is logged for the item now.
    conn = useDb(fetchone=[LOCK, {"WorkoutID": 70}, PROFILE, ACTIVE, None],
                 fetchall=[[{"ItemID": 500}], [ITEM], [], [suggestionRow(basedOn=None)], ROUTINES])
    answer = userClient.delete(f"{A}/workouts/70")
    assert answer.status_code == 200
    assert conn.cur.statements("DELETE FROM Workouts")[0][1] == (70, UID)
    assert conn.cur.statements("UPDATE Suggestions SET State = 'withdrawn'")[0][1] == (9,)
    assert answer.get_json()["data"] == {"deleted": 70, "nextUp": {"routineId": 50, "title": "Upper"}}
    assert conn.commits == 1


def test_deletingSomeoneElsesWorkoutIsNotFound(userClient, useDb):
    useDb(fetchone=[LOCK, None])
    assert userClient.delete(f"{A}/workouts/70").status_code == 404


def test_aWorkoutOpens(userClient, useDb):
    useDb(fetchone=[workoutRow(routineId=None, title=None)], fetchall=[[setRow(1), setRow(2, weight=None, reps=5)]])
    data = userClient.get(f"{A}/workouts/70").get_json()["data"]
    assert data["id"] == 70 and data["title"] is None and data["routineId"] is None and data["programId"] is None
    assert data["performedOn"] == "2026-11-16" and data["createdAt"] == "2026-11-16T18:00:00Z"
    assert len(data["exercises"]) == 1 and [s["reps"] for s in data["exercises"][0]["sets"]] == [12, 5]
    useDb(fetchone=[None])
    assert userClient.get(f"{A}/workouts/71").status_code == 404


def test_theHistoryIsNewestFirst(userClient, useDb):
    conn = useDb(fetchall=[[{"WorkoutID": 70, "PerformedOn": date(2026, 11, 16), "RoutineID": 50, "Title": "Upper",
                             "Note": None, "UpdatedAt": workoutRow()["UpdatedAt"], "ExerciseCount": 4,
                             "SetCount": 12}]])
    data = userClient.get(f"{A}/workouts").get_json()["data"]
    assert data == [{"id": 70, "performedOn": "2026-11-16", "routineId": 50, "title": "Upper", "note": None,
                     "exerciseCount": 4, "setCount": 12, "updatedAt": "2026-11-16T18:00:00Z"}]
    assert conn.cur.executed[0][0].endswith("ORDER BY w.PerformedOn DESC, w.CreatedAt DESC, w.WorkoutID DESC")


def test_theRoutinesMenuPutsTheActiveProgramFirst(userClient, useDb):
    conn = useDb(fetchall=[[{"RoutineID": 50, "Title": "Upper", "ProgramID": 5, "ProgramTitle": "Upper/Lower",
                             "IsActive": 1}]])
    assert userClient.get(f"{A}/routines").get_json()["data"] == [
        {"id": 50, "title": "Upper", "programId": 5, "programTitle": "Upper/Lower", "active": True}]
    assert "ORDER BY p.IsActive DESC" in conn.cur.executed[0][0]


def test_theDraftFillsFromLastTimeAndTheOpenSuggestion(userClient, useDb):
    useDb(fetchone=[{"RoutineID": 50, "Title": "Upper", "ProgramID": 5}],
          fetchall=[[ITEM], [suggestionRow()], [loggedRow(69, n) for n in (1, 2, 3)]])
    data = userClient.get(f"{A}/workouts/draft?routineId=50").get_json()["data"]
    assert data["routineId"] == 50 and data["title"] == "Upper" and data["programId"] == 5
    item = data["items"][0]
    assert item["id"] == 500 and item["measure"] == "weight_reps" and item["last"]["workoutId"] == 69
    assert item["suggestion"]["id"] == 9


def test_theDraftNeedsTheRoutineAndOnlyTheirs(userClient, useDb):
    answer = userClient.get(f"{A}/workouts/draft")
    assert answer.status_code == 400 and answer.get_json()["field"] == "routineId"
    useDb(fetchone=[None])
    assert userClient.get(f"{A}/workouts/draft?routineId=50").status_code == 404
