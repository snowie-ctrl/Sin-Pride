"""Progress, records and suggestions against docs/api.md and plan decisions 10-13, 19."""
from datetime import date
from decimal import Decimal

from conftest import UID
from logSamples import TOP, loggedRow, suggestionRow

A = "/api/pride"
EARLIER = [loggedRow(69, n, weight=130, day=date(2026, 11, 12)) for n in (1, 2, 3)]


def test_theyNeedASession(anonUserClient):
    assert anonUserClient.get(f"{A}/records").status_code == 401
    assert anonUserClient.post(f"{A}/suggestions/9/accept").status_code == 401


def test_progressHasPointsRecordsAndRecentWorkouts(userClient, useDb):
    conn = useDb(fetchone=[{"ExerciseID": 12, "Measure": "weight_reps"}, {"Units": "lb"}], fetchall=[EARLIER + TOP])
    data = userClient.get(f"{A}/progress/12").get_json()["data"]
    assert data["exerciseId"] == 12 and data["measure"] == "weight_reps" and data["units"] == "lb"
    assert [p["value"] for p in data["points"]] == [130.0, 135.0]
    assert data["points"][1]["crowns"] == ["heaviest", "e1rm"]
    assert [r["kind"] for r in data["records"]] == ["heaviest", "e1rm"] and data["records"][0]["workoutId"] == 70
    assert [r["workoutId"] for r in data["recent"]] == [70, 69]
    assert "(OwnerUserID IS NULL OR OwnerUserID = %s)" in conn.cur.executed[0][0]


def test_progressOfAnExerciseThatIsNotTheirsIsNotFound(userClient, useDb):
    useDb(fetchone=[None])
    assert userClient.get(f"{A}/progress/12").status_code == 404


def test_recordsListEveryLoggedExercise(userClient, useDb):
    useDb(fetchone=[{"Units": "lb"}], fetchall=[EARLIER + TOP, [{"ExerciseID": 12, "Measure": "weight_reps"}]])
    data = userClient.get(f"{A}/records").get_json()["data"]
    assert [(e["exerciseId"], e["lastOn"]) for e in data] == [(12, "2026-11-16")]
    assert data[0]["records"][0]["weight"] == 135.0


def test_noWorkoutsNoRecords(userClient, useDb):
    conn = useDb(fetchone=[{"Units": "lb"}], fetchall=[[]])
    assert userClient.get(f"{A}/records").get_json()["data"] == []
    assert len(conn.cur.executed) == 2


def owned(**changes):
    return {**suggestionRow(), "ProgramID": 5, **changes}


def test_takingAStepUpWritesTheTarget(userClient, useDb):
    conn = useDb(fetchone=[owned()])
    answer = userClient.post(f"{A}/suggestions/9/accept")
    assert answer.status_code == 200
    assert conn.cur.statements("UPDATE RoutineItems SET TargetWeight")[0][1] == (140.0, "lb", 500)
    assert conn.cur.statements("UPDATE Suggestions SET State = 'accepted'")[0][1] == (9,)
    assert conn.cur.statements("UPDATE Programs SET UpdatedAt")[0][1] == (5,)
    data = answer.get_json()["data"]
    assert data["programId"] == 5 and data["suggestion"]["state"] == "accepted" and conn.commits == 1


def test_takingARangeOrATimeWritesThose(userClient, useDb):
    conn = useDb(fetchone=[owned(ProposedWeight=None, ProposedUnit=None, ProposedRepsMin=10, ProposedRepsMax=14)])
    userClient.post(f"{A}/suggestions/9/accept")
    assert conn.cur.statements("UPDATE RoutineItems SET RepsMin")[0][1] == (10, 14, 500)
    conn = useDb(fetchone=[owned(ProposedWeight=None, ProposedUnit=None, ProposedSeconds=40)])
    userClient.post(f"{A}/suggestions/9/accept")
    assert conn.cur.statements("UPDATE RoutineItems SET TargetSeconds")[0][1] == (40, 500)


def test_dismissingLeavesTheRoutineAlone(userClient, useDb):
    conn = useDb(fetchone=[owned()])
    answer = userClient.post(f"{A}/suggestions/9/dismiss")
    assert answer.status_code == 200 and answer.get_json()["data"]["suggestion"]["state"] == "dismissed"
    assert conn.cur.statements("UPDATE Suggestions SET State = 'dismissed'")[0][1] == (9,)
    assert not conn.cur.statements("UPDATE RoutineItems") and conn.commits == 1


def test_aStallIsNotedNotTaken(userClient, useDb):
    useDb(fetchone=[owned(Kind="stall", ProposedWeight=None, ProposedUnit=None)])
    answer = userClient.post(f"{A}/suggestions/9/accept")
    assert answer.status_code == 400 and answer.get_json()["field"] == "kind"
    useDb(fetchone=[owned(Kind="stall", ProposedWeight=None, ProposedUnit=None)])
    assert userClient.post(f"{A}/suggestions/9/dismiss").status_code == 200


def test_aSettledSuggestionIsClosed(userClient, useDb):
    for state in ("accepted", "dismissed", "withdrawn"):
        conn = useDb(fetchone=[owned(State=state)])
        answer = userClient.post(f"{A}/suggestions/9/accept")
        assert answer.status_code == 409 and answer.get_json()["status"] == "closed"
        assert not conn.cur.statements("UPDATE")


def test_someoneElsesSuggestionIsNotFound(userClient, useDb):
    conn = useDb(fetchone=[None])
    assert userClient.post(f"{A}/suggestions/9/dismiss").status_code == 404
    assert conn.cur.executed[0][1] == (9, UID)
