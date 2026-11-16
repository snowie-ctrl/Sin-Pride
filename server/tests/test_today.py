"""GET /today against spec §5/§6 and plan decisions 21-23 (milestone 2) and 8, 12, 25 (milestone 3)."""
from datetime import date

from conftest import UID
from logSamples import ITEM, TOP, loggedRow, suggestionRow

A = "/api/pride"
WED = "2026-11-18"
PROFILE = {"WeekStart": "mon", "Units": "lb"}
ACTIVE = {"ProgramID": 5, "Title": "Upper/Lower"}
ROUTINES = [{"RoutineID": 50, "Title": "Upper"}, {"RoutineID": 51, "Title": "Lower"}]
LOWER_ITEM = {**ITEM, "RoutineID": 51}
DONE_MONDAY = [{"PerformedOn": date(2026, 11, 16)}]
MWF = [{"Weekday": 0}, {"Weekday": 2}, {"Weekday": 4}]


def test_todayNeedsASession(anonUserClient):
    assert anonUserClient.get(f"{A}/today?date={WED}").status_code == 401


def test_todayNeedsADate(userClient):
    answer = userClient.get(f"{A}/today")
    assert answer.status_code == 400 and answer.get_json()["field"] == "date"
    assert userClient.get(f"{A}/today?date=18-11-2026").status_code == 400


def test_withNoProgramThereIsOnlyTheWeek(userClient, useDb):
    useDb(fetchone=[PROFILE, None], fetchall=[DONE_MONDAY, []])
    data = userClient.get(f"{A}/today?date={WED}").get_json()["data"]
    assert data["program"] is None and data["nextUp"] is None and data["plannedDay"] is None
    assert [d["date"] for d in data["week"]][0] == "2026-11-16" and data["week"][0]["done"] is True
    assert not any(d["planned"] for d in data["week"]) and data["crowns"] == []


def test_nextUpFollowsTheLatestWorkoutInTheProgram(userClient, useDb):
    conn = useDb(fetchone=[PROFILE, ACTIVE, {"RoutineID": 50}],
                 fetchall=[ROUTINES, DONE_MONDAY, [], MWF, [LOWER_ITEM], []])
    data = userClient.get(f"{A}/today?date={WED}").get_json()["data"]
    assert data["program"] == {"id": 5, "title": "Upper/Lower"}
    assert data["nextUp"]["routineId"] == 51 and data["nextUp"]["title"] == "Lower"
    assert [i["id"] for i in data["nextUp"]["items"]] == [500]
    assert data["plannedDay"] == WED
    assert [d["planned"] for d in data["week"]] == [False, False, True, False, True, False, False]
    latest = next(sql for sql, _ in conn.cur.executed if "ORDER BY PerformedOn DESC" in sql)
    assert "WHERE UserID = %s AND ProgramID = %s" in latest and latest.endswith("CreatedAt DESC, WorkoutID DESC LIMIT 1")
    weekParams = next(p for sql, p in conn.cur.executed if sql.startswith("SELECT DISTINCT PerformedOn"))
    assert weekParams == (UID, date(2026, 11, 16), date(2026, 11, 22))


def test_aWorkoutLoggedTodayMovesThePlannedDayOn(userClient, useDb):
    useDb(fetchone=[PROFILE, ACTIVE, {"RoutineID": 51}],
          fetchall=[ROUTINES, [{"PerformedOn": date(2026, 11, 18)}], [], [{"Weekday": 2}, {"Weekday": 4}], [ITEM], []])
    data = userClient.get(f"{A}/today?date={WED}").get_json()["data"]
    assert data["plannedDay"] == "2026-11-20" and data["nextUp"]["routineId"] == 50
    assert data["week"][2]["done"] is True and data["week"][2]["planned"] is False


def test_aProgramWithNoRoutinesHasNothingNextUp(userClient, useDb):
    conn = useDb(fetchone=[PROFILE, ACTIVE, None], fetchall=[[], [], [], []])
    data = userClient.get(f"{A}/today?date={WED}").get_json()["data"]
    assert data["nextUp"] is None and data["plannedDay"] is None
    assert not any("FROM RoutineItems" in sql for sql, _ in conn.cur.executed)


def test_eachItemCarriesLastTimeAndItsOpenSuggestion(userClient, useDb):
    logged = [loggedRow(69, n, itemId=500) for n in (1, 2, 3)]
    useDb(fetchone=[PROFILE, ACTIVE, {"RoutineID": 50}],
          fetchall=[ROUTINES, DONE_MONDAY, logged, [{"ExerciseID": 12, "Measure": "weight_reps"}], MWF,
                    [LOWER_ITEM], [suggestionRow(basedOn=69)]])
    item = userClient.get(f"{A}/today?date={WED}").get_json()["data"]["nextUp"]["items"][0]
    assert item["measure"] == "weight_reps"
    assert item["last"]["workoutId"] == 69 and [s["reps"] for s in item["last"]["sets"]] == [12, 12, 12]
    assert item["suggestion"]["weight"] == 140.0


def test_theCrownsAreTheLatestThree(userClient, useDb):
    earlier = [loggedRow(69, n, weight=130, day=date(2026, 11, 12)) for n in (1, 2, 3)]
    useDb(fetchone=[PROFILE, None], fetchall=[DONE_MONDAY, earlier + TOP, [{"ExerciseID": 12, "Measure": "weight_reps"}]])
    crowns = userClient.get(f"{A}/today?date={WED}").get_json()["data"]["crowns"]
    assert [(c["kind"], c["workoutId"], c["exerciseId"]) for c in crowns] == [("heaviest", 70, 12), ("e1rm", 70, 12)]
