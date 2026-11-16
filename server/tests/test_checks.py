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


# ---- Workouts (plan decisions 1-3) ----

MEASURES = {12: "weight_reps", 13: "reps", 14: "time", 15: "distance_time"}
LATEST = date(2026, 11, 18)
CID = "0f8fad5b-d9cb-469f-a165-70867728950e"


def lifted(weight=135, reps=12, **more):
    return {"weight": weight, "weightUnit": "lb", "reps": reps, **more}


def workoutBody(**changes):
    data = {"clientId": CID, "performedOn": "2026-11-17", "routineId": 50, "note": None,
            "exercises": [{"exerciseId": 12, "itemId": 500,
                           "sets": [lifted(95, 10, warmup=True), lifted(), lifted()]}]}
    data.update(changes)
    return data


def test_aWorkoutIsCleaned():
    clean = checks.workout(workoutBody(), LATEST, MEASURES.get)
    assert clean["clientId"] == CID and clean["performedOn"] == date(2026, 11, 17) and clean["routineId"] == 50
    first = clean["exercises"][0]
    assert first["exerciseId"] == 12 and first["itemId"] == 500 and first["note"] is None
    assert first["sets"][0] == {"warmup": True, "weight": 95.0, "weightUnit": "lb", "reps": 10, "seconds": None,
                                "distance": None, "distanceUnit": None}
    assert first["sets"][1]["warmup"] is False


def test_aClientIdIsKeptInLowerCase():
    assert checks.workout(workoutBody(clientId=CID.upper()), LATEST, MEASURES.get)["clientId"] == CID


def test_tomorrowIsTheLatestDay():
    assert checks.workout(workoutBody(performedOn="2026-11-18"), LATEST, MEASURES.get)["performedOn"] == LATEST


def test_aFreeWorkoutHasNoRoutineAndUnplannedExercisesNoItem():
    clean = checks.workout(workoutBody(routineId=None, exercises=[{"exerciseId": 13, "sets": [{"reps": 20}]}]),
                           LATEST, MEASURES.get)
    assert clean["routineId"] is None and clean["exercises"][0]["itemId"] is None


def test_anEditNeedsNoClientId():
    clean = checks.workout(workoutBody(clientId=None), LATEST, MEASURES.get, needClientId=False)
    assert clean["clientId"] is None


ONE = [lifted(1, 1)]


@pytest.mark.parametrize("changes,field", [
    ({"clientId": "not-a-uuid"}, "clientId"),
    ({"clientId": None}, "clientId"),
    ({"performedOn": "2026-11-19"}, "performedOn"),          # after tomorrow
    ({"performedOn": "17/11/2026"}, "performedOn"),
    ({"routineId": "50"}, "routineId"),
    ({"note": "x" * 1001}, "note"),
    ({"exercises": []}, "exercises"),
    ({"exercises": "squats"}, "exercises"),
    ({"exercises": [{"exerciseId": 12, "sets": ONE}] * 31}, "exercises"),
    ({"exercises": ["squats"]}, "exercises"),
    ({"exercises": [{"exerciseId": "12", "sets": ONE}]}, "exerciseId"),
    ({"exercises": [{"exerciseId": 99, "sets": ONE}]}, "exerciseId"),   # not one the person may log
    ({"exercises": [{"exerciseId": 12, "itemId": 0, "sets": ONE}]}, "itemId"),
    ({"exercises": [{"exerciseId": 12, "itemId": 500, "sets": ONE},
                    {"exerciseId": 12, "itemId": 500, "sets": ONE}]}, "itemId"),
    ({"exercises": [{"exerciseId": 12, "sets": []}]}, "sets"),
    ({"exercises": [{"exerciseId": 12, "sets": ONE * 21}]}, "sets"),
    ({"exercises": [{"exerciseId": 12, "sets": ONE, "note": 5}]}, "note"),
])
def test_aWorkoutIsRefusedNamingTheField(changes, field):
    with pytest.raises(checks.Refusal) as refused:
        checks.workout(workoutBody(**changes), LATEST, MEASURES.get)
    assert refused.value.field == field


@pytest.mark.parametrize("measure,given,field", [
    ("weight_reps", {"reps": 8}, "weight"),
    ("weight_reps", {"weight": 100, "reps": 8}, "weightUnit"),
    ("weight_reps", {"weightUnit": "lb", "reps": 8}, "weight"),
    ("weight_reps", {"weight": 2001, "weightUnit": "lb", "reps": 8}, "weight"),
    ("weight_reps", {"weight": -1, "weightUnit": "lb", "reps": 8}, "weight"),
    ("weight_reps", {"weight": 100, "weightUnit": "st", "reps": 8}, "weightUnit"),
    ("weight_reps", {"weight": 100, "weightUnit": "lb", "reps": 0}, "reps"),
    ("weight_reps", {"weight": 100, "weightUnit": "lb"}, "reps"),
    ("weight_reps", {"weight": 100, "weightUnit": "lb", "reps": 8, "seconds": 30}, "seconds"),
    ("weight_reps", {"warmup": "yes", "weight": 1, "weightUnit": "lb", "reps": 1}, "warmup"),
    ("reps", {"reps": 1001}, "reps"),
    ("reps", {"reps": 5, "weight": 20}, "weightUnit"),
    ("time", {}, "seconds"),
    ("time", {"seconds": 0}, "seconds"),
    ("time", {"seconds": 36001}, "seconds"),
    ("time", {"seconds": 30, "reps": 5}, "reps"),
    ("distance_time", {}, "distance"),
    ("distance_time", {"distance": 5}, "distanceUnit"),
    ("distance_time", {"distanceUnit": "km"}, "distance"),
    ("distance_time", {"distance": 0, "distanceUnit": "km"}, "distance"),
    ("distance_time", {"distance": 5, "distanceUnit": "yd"}, "distanceUnit"),
    ("distance_time", {"distance": 5, "distanceUnit": "km", "seconds": 0}, "seconds"),
])
def test_aSetTakesOnlyItsMeasuresFields(measure, given, field):
    with pytest.raises(checks.Refusal) as refused:
        checks.workoutSet(measure, given)
    assert refused.value.field == field


def test_eachMeasuresGoodSets():
    assert checks.workoutSet("reps", {"reps": 12})["weight"] is None
    assert checks.workoutSet("reps", {"reps": 12, "weight": 20, "weightUnit": "kg"})["weight"] == 20.0
    assert checks.workoutSet("time", {"seconds": 45})["seconds"] == 45
    assert checks.workoutSet("distance_time", {"seconds": 1500})["distance"] is None
    ran = checks.workoutSet("distance_time", {"distance": 5, "distanceUnit": "km"})
    assert ran["distance"] == 5.0 and ran["seconds"] is None
    # Nulls for fields the measure does not use are fine: the app sends every field.
    assert checks.workoutSet("time", {"seconds": 45, "weight": None, "reps": None})["reps"] is None
