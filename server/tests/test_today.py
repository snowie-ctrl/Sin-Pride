"""GET /today against spec §5/§6 and plan decisions 21–23."""
from datetime import date

from conftest import UID
from programSamples import ITEM

A = "/api/pride"
WED = "2026-11-18"
WEEK = {"WeekStart": "mon"}
ACTIVE = {"ProgramID": 5, "Title": "Upper/Lower"}
ROUTINES = [{"RoutineID": 50, "Title": "Upper"}, {"RoutineID": 51, "Title": "Lower"}]


def test_todayNeedsASession(anonUserClient):
    assert anonUserClient.get(f"{A}/today?date={WED}").status_code == 401


def test_todayNeedsADate(userClient):
    answer = userClient.get(f"{A}/today")
    assert answer.status_code == 400 and answer.get_json()["field"] == "date"
    assert userClient.get(f"{A}/today?date=18-11-2026").status_code == 400


def test_withNoProgramThereIsOnlyTheWeek(userClient, useDb):
    useDb(fetchone=[WEEK, None], fetchall=[[{"PerformedOn": date(2026, 11, 16)}]])
    data = userClient.get(f"{A}/today?date={WED}").get_json()["data"]
    assert data["program"] is None and data["nextUp"] is None and data["plannedDay"] is None
    assert [d["date"] for d in data["week"]][0] == "2026-11-16" and data["week"][0]["done"] is True
    assert not any(d["planned"] for d in data["week"])


def test_nextUpFollowsTheLatestWorkoutInTheProgram(userClient, useDb):
    conn = useDb(fetchone=[WEEK, ACTIVE, {"RoutineID": 50}],
                 fetchall=[[{"PerformedOn": date(2026, 11, 16)}], [{"Weekday": 0}, {"Weekday": 2}, {"Weekday": 4}],
                           ROUTINES, [{**ITEM, "RoutineID": 51}]])
    data = userClient.get(f"{A}/today?date={WED}").get_json()["data"]
    assert data["program"] == {"id": 5, "title": "Upper/Lower"}
    assert data["nextUp"]["routineId"] == 51 and data["nextUp"]["title"] == "Lower"
    assert [i["id"] for i in data["nextUp"]["items"]] == [500]
    assert data["plannedDay"] == WED
    assert [d["planned"] for d in data["week"]] == [False, False, True, False, True, False, False]
    latest = next(sql for sql, _ in conn.cur.executed if "ORDER BY PerformedOn DESC" in sql)
    assert "WHERE UserID = %s AND ProgramID = %s" in latest and latest.endswith("CreatedAt DESC, WorkoutID DESC LIMIT 1")
    weekSql, weekParams = conn.cur.executed[2]
    assert weekParams == (UID, date(2026, 11, 16), date(2026, 11, 22))


def test_aWorkoutLoggedTodayMovesThePlannedDayOn(userClient, useDb):
    useDb(fetchone=[WEEK, ACTIVE, {"RoutineID": 51}],
          fetchall=[[{"PerformedOn": date(2026, 11, 18)}], [{"Weekday": 2}, {"Weekday": 4}], ROUTINES, [ITEM]])
    data = userClient.get(f"{A}/today?date={WED}").get_json()["data"]
    assert data["plannedDay"] == "2026-11-20" and data["nextUp"]["routineId"] == 50
    assert data["week"][2]["done"] is True and data["week"][2]["planned"] is False


def test_aProgramWithNoRoutinesHasNothingNextUp(userClient, useDb):
    conn = useDb(fetchone=[WEEK, ACTIVE, None], fetchall=[[], [], []])
    data = userClient.get(f"{A}/today?date={WED}").get_json()["data"]
    assert data["nextUp"] is None and data["plannedDay"] is None
    assert not any("FROM RoutineItems" in sql for sql, _ in conn.cur.executed)
