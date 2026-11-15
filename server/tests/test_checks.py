"""prideChecks against spec §3/§4 and the plan's decisions 4, 5, 16 and 17: every refusal names its field."""
from datetime import date

import pytest

from conftest import loadModule

checks = loadModule("prideChecks")
Refusal = checks.Refusal


def refused(fn, *args):
    with pytest.raises(Refusal) as caught:
        fn(*args)
    return caught.value.field


@pytest.mark.parametrize("value,want", [("Push", "Push"), ("  Pull  ", "Pull"), ("x" * 60, "x" * 60)])
def test_aTitleIsTrimmed(value, want):
    assert checks.title(value) == want


@pytest.mark.parametrize("value", ["", "   ", "x" * 61, None, 5])
def test_aBadTitleIsRefused(value):
    assert refused(checks.title, value) == "title"


@pytest.mark.parametrize("value,want", [([], []), ([4, 0, 2], [0, 2, 4]), ([6], [6])])
def test_weekdaysAreSortedAndKept(value, want):
    assert checks.weekdays(value) == want


@pytest.mark.parametrize("value", [None, "0,2", [7], [-1], [1, 1], [True], [1.5]])
def test_badWeekdaysAreRefused(value):
    assert refused(checks.weekdays, value) == "days"


@pytest.mark.parametrize("value", ["2026-11-15", "2024-02-29"])
def test_anIsoDateReads(value):
    assert checks.isoDate(value) == date.fromisoformat(value)


@pytest.mark.parametrize("value", [None, "", "15/11/2026", "2026-13-01", "2026-11-15T00:00:00", "2026-W46-1"])
def test_aBadDateIsRefused(value):
    assert refused(checks.isoDate, value) == "date"


def test_switchingUnitsResetsTheIncrements():
    assert checks.profileChanges({"units": "kg"}, "lb") == {"units": "kg", "upperIncrement": 2.5, "lowerIncrement": 5.0}
    assert checks.profileChanges({"units": "lb"}, "kg") == {"units": "lb", "upperIncrement": 5.0, "lowerIncrement": 10.0}


def test_incrementsSentWithTheSwitchAreKept():
    changes = checks.profileChanges({"units": "kg", "upperIncrement": 1.25}, "lb")
    assert changes == {"units": "kg", "upperIncrement": 1.25, "lowerIncrement": 5.0}


def test_theSameUnitsChangeNothingElse():
    assert checks.profileChanges({"units": "lb"}, "lb") == {"units": "lb"}


def test_equipmentIsKeptInPridesOrder():
    assert checks.profileChanges({"equipment": ["bench", "dumbbell"]}, "lb") == {"equipment": ["dumbbell", "bench"]}
    assert checks.profileChanges({"equipment": []}, "lb") == {"equipment": []}


@pytest.mark.parametrize("body,field", [
    ({"units": "stone"}, "units"), ({"goal": "bulk"}, "goal"), ({"daysPerWeek": 1}, "daysPerWeek"),
    ({"daysPerWeek": 7}, "daysPerWeek"), ({"daysPerWeek": "3"}, "daysPerWeek"), ({"upperIncrement": 0}, "upperIncrement"),
    ({"lowerIncrement": 100.25}, "lowerIncrement"), ({"upperIncrement": 1.1}, "upperIncrement"),
    ({"weekStart": "tue"}, "weekStart"), ({"introState": "maybe"}, "introState"),
    ({"equipment": ["anvil"]}, "equipment"), ({"equipment": ["bench", "bench"]}, "equipment"),
    ({"equipment": "bench"}, "equipment"), ({"colour": "red"}, "colour"), ({}, "profile"),
])
def test_aBadProfileChangeIsRefused(body, field):
    assert refused(checks.profileChanges, body, "lb") == field


@pytest.mark.parametrize("measure,goal,units,want", [
    ("weight_reps", "strength", "lb", {"sets": 3, "repsMin": 5, "repsMax": 8, "targetUnit": None}),
    ("weight_reps", "muscle", "kg", {"sets": 3, "repsMin": 8, "repsMax": 12}),
    ("reps", "general", "lb", {"sets": 3, "repsMin": 10, "repsMax": 15}),
    ("time", "general", "lb", {"sets": 3, "targetSeconds": 30, "repsMin": None}),
    ("distance_time", "muscle", "kg", {"sets": 1, "targetDistance": None, "targetSeconds": None}),
])
def test_newItemsDefaultByMeasureAndGoal(measure, goal, units, want):
    got = checks.itemDefaults(measure, goal, units)
    assert set(got) == set(checks.TARGET_FIELDS)
    for key, value in want.items():
        assert got[key] == value, key


def item(**changes):
    values = {"sets": 3, "repsMin": 8, "repsMax": 12}
    values.update(changes)
    return values


def test_aWeightNeedsItsUnitAndAUnitNeedsAWeight():
    assert checks.itemTargets("weight_reps", item(targetWeight=135, targetUnit="lb"))["targetWeight"] == 135
    assert refused(checks.itemTargets, "weight_reps", item(targetWeight=135)) == "targetUnit"
    assert refused(checks.itemTargets, "weight_reps", item(targetUnit="kg")) == "targetWeight"


def test_aNoteIsTrimmedAndBlankIsNone():
    assert checks.itemTargets("reps", item(note="  slow  "))["note"] == "slow"
    assert checks.itemTargets("reps", item(note="   "))["note"] is None


@pytest.mark.parametrize("measure,values,field", [
    ("weight_reps", item(sets=0), "sets"), ("weight_reps", item(sets=21), "sets"), ("weight_reps", item(sets=None), "sets"),
    ("weight_reps", item(repsMin=0), "repsMin"), ("weight_reps", item(repsMax=101), "repsMax"),
    ("weight_reps", item(repsMin=12, repsMax=8), "repsMax"), ("weight_reps", item(repsMin=None), "repsMin"),
    ("weight_reps", item(targetWeight=2000.5, targetUnit="lb"), "targetWeight"),
    ("weight_reps", item(targetWeight=-1, targetUnit="lb"), "targetWeight"),
    ("weight_reps", item(targetWeight=100, targetUnit="st"), "targetUnit"),
    ("weight_reps", item(targetSeconds=30), "targetSeconds"), ("reps", item(targetDistance=5), "targetDistance"),
    ("weight_reps", item(restSeconds=3601), "restSeconds"), ("weight_reps", item(restSeconds=1.5), "restSeconds"),
    ("weight_reps", item(note="x" * 1001), "note"), ("weight_reps", item(sets=True), "sets"),
    ("time", {"sets": 3}, "targetSeconds"), ("time", {"sets": 3, "targetSeconds": 36001}, "targetSeconds"),
    ("time", {"sets": 3, "targetSeconds": 30, "repsMin": 5}, "repsMin"),
    ("time", {"sets": 3, "targetSeconds": 30, "targetWeight": 10, "targetUnit": "lb"}, "targetWeight"),
    ("distance_time", {"sets": 1, "targetDistance": 0, "distanceUnit": "km"}, "targetDistance"),
    ("distance_time", {"sets": 1, "targetDistance": 1001, "distanceUnit": "km"}, "targetDistance"),
    ("distance_time", {"sets": 1, "targetDistance": 5}, "distanceUnit"),
    ("distance_time", {"sets": 1, "distanceUnit": "km"}, "targetDistance"),
    ("distance_time", {"sets": 1, "repsMax": 5}, "repsMax"),
    ("laps", {"sets": 1}, "measure"),
])
def test_eachMeasureTakesOnlyItsOwnFields(measure, values, field):
    assert refused(checks.itemTargets, measure, values) == field


def test_eachMeasuresOwnFieldsPass():
    assert checks.itemTargets("time", {"sets": 3, "targetSeconds": 45, "restSeconds": 60})["targetSeconds"] == 45
    distance = checks.itemTargets("distance_time", {"sets": 1, "targetDistance": 5, "distanceUnit": "km", "targetSeconds": 1800})
    assert (distance["targetDistance"], distance["distanceUnit"], distance["targetSeconds"]) == (5, "km", 1800)
    assert checks.itemTargets("distance_time", {"sets": 1})["targetDistance"] is None
    assert checks.itemTargets("reps", item(targetWeight=20, targetUnit="kg"))["targetUnit"] == "kg"


def own(**changes):
    body = {"name": "Sandbag Carry", "measure": "distance_time", "primary": ["forearms"], "secondary": ["traps"],
            "equipment": ["other"], "steps": ["Pick it up.", "Walk."]}
    body.update(changes)
    return body


def test_anOwnExerciseIsCleanedAndGivenItsRegion():
    clean = checks.ownExercise(own(name="  Sandbag Carry "))
    assert clean == {"name": "Sandbag Carry", "measure": "distance_time", "primary": ["forearms"],
                     "secondary": ["traps"], "equipment": ["other"], "steps": ["Pick it up.", "Walk."],
                     "region": "upper"}
    assert checks.ownExercise(own(secondary=None, steps=None))["steps"] == []


@pytest.mark.parametrize("changes,field", [
    ({"name": ""}, "name"), ({"name": "x" * 121}, "name"), ({"measure": "laps"}, "measure"),
    ({"primary": []}, "primary"), ({"primary": ["wings"]}, "primary"), ({"secondary": ["forearms"]}, "secondary"),
    ({"equipment": []}, "equipment"), ({"equipment": ["anvil"]}, "equipment"),
    ({"steps": ["ok"] * 51}, "steps"), ({"steps": [""]}, "steps"), ({"steps": ["x" * 1001]}, "steps"),
])
def test_aBadOwnExerciseIsRefused(changes, field):
    assert refused(checks.ownExercise, own(**changes)) == field
