"""Rows the log routes read, in the order they ask for them, for tests to queue (fakes.FakeCursor)."""
from datetime import date, datetime
from decimal import Decimal

CID = "0f8fad5b-d9cb-469f-a165-70867728950e"
LOCK = {"UserID": 7}
DAY = date(2026, 11, 16)
SAVED = datetime(2026, 11, 16, 18, 0)
PROFILE = {"Units": "lb", "UpperIncrement": Decimal("5.00"), "LowerIncrement": Decimal("10.00")}
ACTIVE = {"ProgramID": 5, "Title": "Upper/Lower"}
ROUTINES = [{"RoutineID": 50, "Title": "Upper"}, {"RoutineID": 51, "Title": "Lower"}]
ITEM = {"ItemID": 500, "RoutineID": 50, "ExerciseID": 12, "Sets": 3, "RepsMin": 8, "RepsMax": 12,
        "TargetWeight": Decimal("135.00"), "TargetUnit": "lb", "TargetSeconds": None, "TargetDistance": None,
        "DistanceUnit": None, "RestSeconds": 90, "Note": None, "Measure": "weight_reps", "Region": "upper"}


def workoutRow(id=70, routineId=50, title="Upper", note=None):
    return {"WorkoutID": id, "ClientID": CID, "PerformedOn": DAY, "StartedAt": None, "EndedAt": None,
            "ProgramID": 5 if routineId else None, "RoutineID": routineId, "Title": title, "Note": note,
            "CreatedAt": SAVED, "UpdatedAt": SAVED}


def setRow(setNo=1, weight=135, reps=12, warmup=0, weId=700, exerciseId=12, itemId=500, measure="weight_reps"):
    return {"WorkoutExerciseID": weId, "ExerciseID": exerciseId, "ItemID": itemId, "Note": None, "Measure": measure,
            "SetNo": setNo, "IsWarmup": warmup, "Weight": None if weight is None else Decimal(str(weight)),
            "WeightUnit": "lb" if weight is not None else None, "Reps": reps, "Seconds": None, "Distance": None,
            "DistanceUnit": None}


def loggedRow(workoutId=70, setNo=1, weight=135, reps=12, day=DAY, itemId=500):
    return {"WorkoutID": workoutId, "PerformedOn": day, "CreatedAt": SAVED, "ExerciseID": 12, "ItemID": itemId,
            "OrderIndex": 0, "SetNo": setNo, "IsWarmup": 0, "Weight": Decimal(str(weight)), "WeightUnit": "lb",
            "Reps": reps, "Seconds": None, "Distance": None, "DistanceUnit": None}


def suggestionRow(id=9, basedOn=70, state="open", weight="140.00"):
    return {"SuggestionID": id, "ItemID": 500, "Kind": "increase", "ProposedWeight": Decimal(weight),
            "ProposedUnit": "lb", "ProposedRepsMin": None, "ProposedRepsMax": None, "ProposedSeconds": None,
            "BasedOnWorkoutID": basedOn, "State": state}


TOP = [loggedRow(setNo=n) for n in (1, 2, 3)]


def answered(raised=(), logged=TOP, latest=50):
    """(fetchone, fetchall) for answerSaved: the workout, its sets, the exercises' rows, the units, the suggestions
    it raised, then the rotation (active program, its routines, the latest workout's routine)."""
    return ([workoutRow(), {"Units": "lb"}, ACTIVE, {"RoutineID": latest}],
            [[setRow(n) for n in (1, 2, 3)], list(logged), list(raised), ROUTINES])
