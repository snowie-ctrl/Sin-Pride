"""Rows the program routes read, in the order they ask for them, for tests to queue (fakes.FakeCursor)."""
from datetime import datetime
from decimal import Decimal

PROGRAM = {"ProgramID": 5, "Title": "Upper/Lower", "IsActive": 1, "StarterKey": "upperLower",
           "UpdatedAt": datetime(2026, 11, 15, 9, 0)}
DAYS = [{"Weekday": 0}, {"Weekday": 3}]
ROUTINES = [{"RoutineID": 50, "Title": "Upper"}, {"RoutineID": 51, "Title": "Lower"}]
ITEM = {"ItemID": 500, "RoutineID": 50, "ExerciseID": 12, "Sets": 3, "RepsMin": 8, "RepsMax": 12,
        "TargetWeight": Decimal("135.00"), "TargetUnit": "lb", "TargetSeconds": None, "TargetDistance": None,
        "DistanceUnit": None, "RestSeconds": 90, "Note": None}
ITEMS = [ITEM]
ROWS = [{"ProgramID": 5, "Title": "Upper/Lower", "IsActive": 1, "StarterKey": "upperLower",
         "UpdatedAt": datetime(2026, 11, 15, 9, 0), "RoutineCount": 2},
        {"ProgramID": 6, "Title": "Mine", "IsActive": 0, "StarterKey": None,
         "UpdatedAt": datetime(2026, 11, 14, 9, 0), "RoutineCount": 0}]
ROW_DAYS = [{"ProgramID": 5, "Weekday": 0}, {"ProgramID": 5, "Weekday": 3}]
LOCK = {"UserID": 7}


def whole():
    """The three reads programJson makes after the program's row."""
    return [DAYS, ROUTINES, ITEMS]
