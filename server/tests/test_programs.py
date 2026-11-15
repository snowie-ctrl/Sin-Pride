"""Programs against docs/api.md and plan decisions 13, 14 and 15."""
from conftest import UID
from programSamples import DAYS, ITEMS, LOCK, PROGRAM, ROUTINES, ROW_DAYS, ROWS, whole

A = "/api/pride"
WHOLE = {"id": 5, "title": "Upper/Lower", "active": True, "starterKey": "upperLower", "days": [0, 3],
         "updatedAt": "2026-11-15T09:00:00Z",
         "routines": [{"id": 50, "title": "Upper", "items": [
             {"id": 500, "exerciseId": 12, "sets": 3, "repsMin": 8, "repsMax": 12, "targetWeight": 135.0,
              "targetUnit": "lb", "targetSeconds": None, "targetDistance": None, "distanceUnit": None,
              "restSeconds": 90, "note": None}]},
                      {"id": 51, "title": "Lower", "items": []}]}


def test_programsNeedASession(anonUserClient):
    for method, path in (("get", "/programs"), ("post", "/programs"), ("get", "/programs/5"),
                         ("post", "/programs/5/activate"), ("put", "/programs/5/days")):
        assert getattr(anonUserClient, method)(f"{A}{path}").status_code == 401, path


def test_theListHasEachProgramsDaysAndRoutineCount(userClient, useDb):
    conn = useDb(fetchall=[ROWS, ROW_DAYS])
    data = userClient.get(f"{A}/programs").get_json()["data"]
    assert data == [{"id": 5, "title": "Upper/Lower", "active": True, "starterKey": "upperLower", "days": [0, 3],
                     "routineCount": 2, "updatedAt": "2026-11-15T09:00:00Z"},
                    {"id": 6, "title": "Mine", "active": False, "starterKey": None, "days": [],
                     "routineCount": 0, "updatedAt": "2026-11-14T09:00:00Z"}]
    assert all(params == (UID,) for _, params in conn.cur.executed)
    assert conn.cur.executed[0][0].endswith("ORDER BY p.CreatedAt, p.ProgramID")


def test_aProgramComesWhole(userClient, useDb):
    conn = useDb(fetchone=[PROGRAM], fetchall=whole())
    assert userClient.get(f"{A}/programs/5").get_json()["data"] == WHOLE
    assert conn.cur.executed[0][1] == (5, UID)
    assert conn.cur.executed[-1][0].endswith("ORDER BY r.OrderIndex, r.RoutineID, i.OrderIndex, i.ItemID")


def test_someoneElsesProgramIs404(userClient, useDb):
    useDb(fetchone=[None])
    assert userClient.get(f"{A}/programs/5").status_code == 404


def test_aPersonsFirstProgramIsActive(userClient, useDb):
    conn = useDb(fetchone=[LOCK, {"n": 0}, PROGRAM], fetchall=whole(), lastrowids={"Programs": [5]})
    assert userClient.post(f"{A}/programs", json={"title": "  Upper/Lower "}).get_json()["data"]["id"] == 5
    assert conn.cur.statements("INSERT INTO Programs")[0][1] == (UID, "Upper/Lower", 1)
    assert conn.commits == 1


def test_aLaterProgramIsNotActive(userClient, useDb):
    conn = useDb(fetchone=[LOCK, {"n": 1}, PROGRAM], fetchall=whole(), lastrowids={"Programs": [6]})
    userClient.post(f"{A}/programs", json={"title": "Mine"})
    assert conn.cur.statements("INSERT INTO Programs")[0][1] == (UID, "Mine", 0)


def test_the21stProgramIsRefused(userClient, useDb):
    conn = useDb(fetchone=[LOCK, {"n": 20}])
    answer = userClient.post(f"{A}/programs", json={"title": "One more"})
    assert answer.status_code == 409 and answer.get_json()["status"] == "limit"
    assert not conn.cur.statements("INSERT")


def test_aBlankTitleIsRefusedBeforeTheDatabase(userClient):
    answer = userClient.post(f"{A}/programs", json={"title": "  "})
    assert answer.status_code == 400 and answer.get_json()["field"] == "title"


def test_renaming(userClient, useDb):
    conn = useDb(fetchone=[PROGRAM, PROGRAM], fetchall=whole())
    assert userClient.put(f"{A}/programs/5", json={"title": "UL"}).status_code == 200
    assert conn.cur.statements("UPDATE Programs SET Title")[0][1] == ("UL", 5, UID)


def test_duplicatingCopiesDaysRoutinesAndItemsInactive(userClient, useDb):
    conn = useDb(fetchone=[LOCK, {"n": 1}, PROGRAM, {**PROGRAM, "ProgramID": 6, "IsActive": 0}],
                 fetchall=[ROUTINES, *whole()], lastrowids={"Programs": [6], "Routines": [60, 61]})
    data = userClient.post(f"{A}/programs/5/duplicate").get_json()["data"]
    assert data["id"] == 6
    assert conn.cur.statements("INSERT INTO Programs")[0][1] == (UID, "Upper/Lower copy", 0, "upperLower")
    assert conn.cur.statements("INSERT INTO ProgramDays")[0][1] == (6, 5)
    assert [p for _, p in conn.cur.statements("INSERT INTO Routines")] == [(6, "Upper", 0), (6, "Lower", 1)]
    assert [p for _, p in conn.cur.statements("INSERT INTO RoutineItems")] == [(60, 50), (61, 51)]


def test_aDuplicatesTitleIsCutTo60(userClient, useDb):
    conn = useDb(fetchone=[LOCK, {"n": 1}, {**PROGRAM, "Title": "x" * 60}, PROGRAM],
                 fetchall=[[], *whole()], lastrowids={"Programs": [6]})
    userClient.post(f"{A}/programs/5/duplicate")
    assert conn.cur.statements("INSERT INTO Programs")[0][1][1] == "x" * 55 + " copy"


def test_deletingAnswersTheList(userClient, useDb):
    conn = useDb(fetchone=[LOCK, PROGRAM], fetchall=[ROWS[1:], []])
    data = userClient.delete(f"{A}/programs/5").get_json()["data"]
    assert [p["id"] for p in data] == [6]
    assert conn.cur.statements("DELETE FROM Programs")[0][1] == (5, UID)


def test_activatingLeavesOnlyOneActive(userClient, useDb):
    conn = useDb(fetchone=[LOCK, PROGRAM], fetchall=[ROWS, ROW_DAYS])
    userClient.post(f"{A}/programs/6/activate")
    assert conn.cur.statements("UPDATE Programs SET IsActive")[0] == (
        "UPDATE Programs SET IsActive = (ProgramID = %s) WHERE UserID = %s", (6, UID))


def test_settingTheDaysReplacesThem(userClient, useDb):
    conn = useDb(fetchone=[PROGRAM, PROGRAM], fetchall=whole())
    userClient.put(f"{A}/programs/5/days", json={"days": [4, 0]})
    assert conn.cur.statements("DELETE FROM ProgramDays")[0][1] == (5,)
    assert [p for _, p in conn.cur.statements("INSERT INTO ProgramDays")] == [(5, 0), (5, 4)]
    assert conn.cur.statements("UPDATE Programs SET UpdatedAt")


def test_badDaysAreRefusedNamingDays(userClient, useDb):
    conn = useDb(fetchone=[PROGRAM])
    answer = userClient.put(f"{A}/programs/5/days", json={"days": [7]})
    assert answer.status_code == 400 and answer.get_json()["field"] == "days"
    assert not conn.cur.statements("DELETE")
