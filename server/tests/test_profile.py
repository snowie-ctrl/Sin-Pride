"""GET/PUT /profile against docs/api.md and plan decisions 4 and 17."""
from decimal import Decimal

from conftest import UID

A = "/api/pride"
ROW = {"Units": "lb", "Goal": "general", "DaysPerWeek": 3, "UpperIncrement": Decimal("5.00"),
       "LowerIncrement": Decimal("10.00"), "WeekStart": "mon", "IntroState": "pending"}
GEAR = [{"Equipment": "dumbbell"}, {"Equipment": "bench"}]


def test_theProfileNeedsASession(anonUserClient):
    assert anonUserClient.get(f"{A}/profile").status_code == 401
    assert anonUserClient.put(f"{A}/profile", json={"goal": "muscle"}).status_code == 401


def test_theProfileComesWithItsEquipmentInPridesOrder(userClient, useDb):
    conn = useDb(fetchone=[ROW], fetchall=[[{"Equipment": "bench"}, {"Equipment": "dumbbell"}]])
    data = userClient.get(f"{A}/profile").get_json()["data"]
    assert data == {"units": "lb", "goal": "general", "daysPerWeek": 3, "upperIncrement": 5.0,
                    "lowerIncrement": 10.0, "weekStart": "mon", "introState": "pending",
                    "equipment": ["dumbbell", "bench"]}
    assert conn.cur.executed[0][1] == (UID,)


def test_aMissingProfileRowIsMadeWithTheDefaults(userClient, useDb):
    conn = useDb(fetchone=[None, ROW], fetchall=[[]])
    assert userClient.get(f"{A}/profile").get_json()["data"]["introState"] == "pending"
    assert conn.cur.statements("INSERT IGNORE INTO Profiles")[0][1] == (UID,)
    assert conn.commits == 1


def test_changingTheGoalWritesOnlyTheGoal(userClient, useDb):
    conn = useDb(fetchone=[ROW], fetchall=[GEAR])
    data = userClient.put(f"{A}/profile", json={"goal": "muscle"}).get_json()["data"]
    assert data["goal"] == "muscle" and data["equipment"] == ["dumbbell", "bench"]
    update = conn.cur.statements("UPDATE Profiles")[0]
    assert update == ("UPDATE Profiles SET Goal = %s WHERE UserID = %s", ("muscle", UID))
    assert not conn.cur.statements("DELETE FROM UserEquipment")
    assert conn.commits == 1


def test_switchingToKgResetsTheIncrements(userClient, useDb):
    conn = useDb(fetchone=[ROW], fetchall=[GEAR])
    data = userClient.put(f"{A}/profile", json={"units": "kg"}).get_json()["data"]
    assert (data["units"], data["upperIncrement"], data["lowerIncrement"]) == ("kg", 2.5, 5.0)
    sql, params = conn.cur.statements("UPDATE Profiles")[0]
    assert "Units = %s" in sql and "UpperIncrement = %s" in sql and params[-1] == UID


def test_equipmentIsReplacedWhole(userClient, useDb):
    conn = useDb(fetchone=[ROW], fetchall=[GEAR])
    data = userClient.put(f"{A}/profile", json={"equipment": ["bands", "bodyweight"]}).get_json()["data"]
    assert data["equipment"] == ["bands", "bodyweight"]
    assert conn.cur.statements("DELETE FROM UserEquipment")[0][1] == (UID,)
    inserts = conn.cur.statements("INSERT INTO UserEquipment")
    assert [p for _, p in inserts] == [(UID, "bands"), (UID, "bodyweight")]
    assert not conn.cur.statements("UPDATE Profiles")


def test_aRefusalNamesTheFieldAndWritesNothing(userClient, useDb):
    conn = useDb(fetchone=[ROW], fetchall=[GEAR])
    answer = userClient.put(f"{A}/profile", json={"daysPerWeek": 9})
    assert answer.status_code == 400
    assert answer.get_json() == {"status": "error", "field": "daysPerWeek",
                                 "message": "daysPerWeek must be a whole number from 2 to 6"}
    assert not conn.cur.statements("UPDATE") and conn.commits == 0
