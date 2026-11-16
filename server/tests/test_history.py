"""prideHistory's SQL helpers against a FakeCursor: what they ask, in what order, and what they make of the rows."""
from datetime import date, datetime
from decimal import Decimal

from conftest import UID, loadModule
from fakes import FakeCursor

history = loadModule("prideHistory")
DAY = date(2026, 11, 16)
SAVED = datetime(2026, 11, 16, 18, 0)


def logged(workoutId=70, setNo=1, weight=135, reps=12, itemId=500, day=DAY):
    return {"WorkoutID": workoutId, "PerformedOn": day, "CreatedAt": SAVED, "ExerciseID": 12, "ItemID": itemId,
            "OrderIndex": 0, "SetNo": setNo, "IsWarmup": 0, "Weight": Decimal(str(weight)), "WeightUnit": "lb",
            "Reps": reps, "Seconds": None, "Distance": None, "DistanceUnit": None}


ITEM = {"ItemID": 500, "RoutineID": 50, "ExerciseID": 12, "Sets": 3, "RepsMin": 8, "RepsMax": 12,
        "TargetWeight": Decimal("135.00"), "TargetUnit": "lb", "TargetSeconds": None, "TargetDistance": None,
        "DistanceUnit": None, "RestSeconds": 90, "Note": None, "Measure": "weight_reps", "Region": "upper"}
PROFILE = {"Units": "lb", "UpperIncrement": Decimal("5.00"), "LowerIncrement": Decimal("10.00")}


def suggestion(id=9, state="open", basedOn=69, weight="140.00", kind="increase"):
    return {"SuggestionID": id, "ItemID": 500, "Kind": kind, "ProposedWeight": Decimal(weight) if weight else None,
            "ProposedUnit": "lb" if weight else None, "ProposedRepsMin": None, "ProposedRepsMax": None,
            "ProposedSeconds": None, "BasedOnWorkoutID": basedOn, "State": state}


def test_rowsAreFlatAndInTimeOrder():
    cur = FakeCursor(fetchall=[[logged()]])
    found = history.rows(cur, UID, exerciseIds=[12, 12, 13])
    sql, params = cur.executed[0]
    assert "WHERE w.UserID = %s AND we.ExerciseID IN (%s, %s)" in sql
    assert sql.endswith("ORDER BY w.PerformedOn, w.CreatedAt, w.WorkoutID, we.OrderIndex, s.SetNo")
    assert params == (UID, 12, 13)
    assert found == [{"workoutId": 70, "performedOn": DAY, "createdAt": SAVED, "exerciseId": 12, "itemId": 500,
                      "order": 0, "setNo": 1, "warmup": False, "weight": 135.0, "weightUnit": "lb", "reps": 12,
                      "seconds": None, "distance": None, "distanceUnit": None}]


def test_anEmptyFilterAsksNothing():
    cur = FakeCursor()
    assert history.rows(cur, UID, itemIds=[]) == [] and cur.executed == []
    assert history.measuresFor(cur, UID, []) == {} and cur.executed == []


def test_measuresForHidesRemovedExercisesUnlessTheWorkoutHasThem():
    cur = FakeCursor(fetchall=[[{"ExerciseID": 12, "Measure": "weight_reps"}]])
    assert history.measuresFor(cur, UID, [12]) == {12: "weight_reps"}
    assert "AND RemovedAt IS NULL" in cur.executed[0][0] and cur.executed[0][1] == (12, UID)
    cur = FakeCursor(fetchall=[[]])
    history.measuresFor(cur, UID, [12], workoutId=70)
    assert "SELECT ExerciseID FROM WorkoutExercises WHERE WorkoutID = %s" in cur.executed[0][0]
    assert cur.executed[0][1] == (12, UID, 70)


def test_theRotationFollowsTheLatestWorkoutInTheActiveProgram():
    cur = FakeCursor(fetchone=[{"ProgramID": 5, "Title": "Upper/Lower"}, {"RoutineID": 50}],
                     fetchall=[[{"RoutineID": 50, "Title": "Upper"}, {"RoutineID": 51, "Title": "Lower"}]])
    program, routines, nextId = history.rotation(cur, UID)
    assert program["ProgramID"] == 5 and nextId == 51
    assert history.nextUpJson(program, routines, nextId) == {"routineId": 51, "title": "Lower"}
    assert history.rotation(FakeCursor(fetchone=[None]), UID) == (None, [], None)
    assert history.nextUpJson(None, [], None) is None


def test_aDraftItemCarriesItsMeasureLastTimeAndSuggestion():
    cur = FakeCursor(fetchall=[[ITEM], [suggestion()], [logged(69, n) for n in (1, 2, 3)]])
    items = history.draftItems(cur, UID, 50)
    assert items[0]["id"] == 500 and items[0]["measure"] == "weight_reps" and items[0]["targetWeight"] == 135.0
    assert items[0]["last"]["workoutId"] == 69 and len(items[0]["last"]["sets"]) == 3
    assert items[0]["suggestion"]["weight"] == 140.0 and items[0]["suggestion"]["state"] == "open"
    assert history.draftItems(FakeCursor(fetchall=[[]]), UID, 50) == []


def test_recalculatingWritesWhatTheRulesSay():
    # The item's latest workout (70) topped every set at the target: a step-up based on 70 replaces the one on 69.
    cur = FakeCursor(fetchone=[PROFILE],
                     fetchall=[[ITEM], [logged(70, n) for n in (1, 2, 3)], [suggestion(9, basedOn=69)]])
    history.recalculate(cur, UID, [500, None, 500])
    itemSql, itemParams = cur.executed[0]
    assert "p.UserID = %s AND i.ItemID IN (%s)" in itemSql and itemParams == (UID, 500)
    assert cur.statements("UPDATE Suggestions SET State = 'withdrawn'")[0][1] == (9,)
    assert cur.statements("INSERT INTO Suggestions")[0][1] == (UID, 500, "increase", 140.0, "lb", None, None, None, 70)
    assert "FOR UPDATE" in next(sql for sql, _ in cur.executed if sql.startswith("SELECT SuggestionID"))


def test_recalculatingNothingAsksNothing():
    cur = FakeCursor()
    history.recalculate(cur, UID, [None])
    assert cur.executed == []
    cur = FakeCursor(fetchall=[[]])                # every item gone: nothing more is read
    history.recalculate(cur, UID, [501])
    assert len(cur.executed) == 1


def test_unitsDefaultToPounds():
    assert history.unitsOf(FakeCursor(fetchone=[{"Units": "kg"}]), UID) == "kg"
    assert history.unitsOf(FakeCursor(fetchone=[None]), UID) == "lb"
