"""prideRules' planning rules against spec §5 and plan decision 22: tables, one row per case."""
from datetime import date, timedelta

import pytest

from conftest import loadModule

rules = loadModule("prideRules")
SUN = date(2026, 11, 15)          # a Sunday
MON, TUE, WED, SAT = (SUN + timedelta(days=n) for n in (1, 2, 3, 6))


@pytest.mark.parametrize("routines,latest,want", [
    ([], None, None),                 # a program with no routines has nothing next
    ([10, 11, 12], None, 10),         # no workouts yet: the first
    ([10, 11, 12], 10, 11),
    ([10, 11, 12], 12, 10),           # wraps round
    ([10, 11, 12], 99, 10),           # that routine is gone: the first
    ([10, 11, 12], 11, 12),           # logging a different routine moves on from the one logged
    ([10], 10, 10),
])
def test_nextUp(routines, latest, want):
    assert rules.nextUp(routines, latest) == want


@pytest.mark.parametrize("today,days,logged,want", [
    (MON, set(), False, None),        # no planned days: "whenever you're ready"
    (MON, {0, 2, 4}, False, MON),     # today counts
    (MON, {0, 2, 4}, True, WED),      # unless a workout is already logged today
    (TUE, {0, 2, 4}, False, WED),
    (SAT, {0, 2, 4}, False, SAT + timedelta(days=2)),   # wraps past Sunday
    (MON, {0}, True, MON + timedelta(days=7)),          # only today planned and already logged: next week
    (SUN, {6}, False, SUN),
])
def test_plannedDay(today, days, logged, want):
    assert rules.plannedDay(today, days, logged) == want


@pytest.mark.parametrize("today,start,want", [
    (WED, "mon", MON), (MON, "mon", MON), (SUN, "mon", SUN - timedelta(days=6)),
    (SUN, "sun", SUN), (SAT, "sun", SUN), (WED, "sun", SUN),
])
def test_weekStartDate(today, start, want):
    assert rules.weekStartDate(today, start) == want


def test_week():
    days = rules.week(WED, "mon", {0, 2, 4}, {MON})
    assert [d["date"] for d in days] == [(MON + timedelta(days=n)).isoformat() for n in range(7)]
    assert [d["weekday"] for d in days] == list(range(7))
    assert [d["done"] for d in days] == [True, False, False, False, False, False, False]
    # Planned only today and later, never a past day with no workout, never a done day.
    assert [d["planned"] for d in days] == [False, False, True, False, True, False, False]


def test_aDoneDayIsNotAlsoPlanned():
    days = rules.week(MON, "mon", {0}, {MON})
    assert days[0]["done"] is True and days[0]["planned"] is False


def test_aSundayWeekStartingOnSunday():
    days = rules.week(SUN, "sun", {6, 0}, set())
    assert days[0]["date"] == SUN.isoformat() and days[0]["weekday"] == 6
    assert [d["weekday"] for d in days] == [6, 0, 1, 2, 3, 4, 5]
    assert days[0]["planned"] is True and days[1]["planned"] is True


def test_aMissedDayIsNeverShownAsPlanned():
    # Monday and Tuesday are planned weekdays that passed with no workout: they show nothing, today still plans.
    days = rules.week(WED, "mon", {0, 1, 2}, set())
    assert [d["planned"] for d in days[:3]] == [False, False, True]
    assert [d["done"] for d in days[:3]] == [False, False, False]


# ---- Records, crowns, series, last time (spec §5; plan decisions 10-13) ----

D1, D2, D3, D4 = (date(2026, 11, d) for d in (2, 5, 9, 12))


def row(workout, day, setNo=1, exercise=12, item=500, warmup=False, weight=None, unit="lb", reps=None, seconds=None,
        distance=None, dunit=None, order=0, created=0):
    return {"workoutId": workout, "performedOn": day, "createdAt": created, "exerciseId": exercise, "itemId": item,
            "order": order, "setNo": setNo, "warmup": warmup, "weight": weight,
            "weightUnit": unit if weight is not None else None, "reps": reps, "seconds": seconds,
            "distance": distance, "distanceUnit": dunit}


def lifts(workout, day, *pairs, **more):
    """One workout's sets of (weight, reps) pairs."""
    return [row(workout, day, n, weight=w, reps=r, **more) for n, (w, r) in enumerate(pairs, start=1)]


def test_unitsConvert():
    assert rules.toKg(100, "kg") == 100
    assert round(rules.toKg(135, "lb"), 3) == 61.235
    assert round(rules.fromKg(61.235, "lb"), 1) == 135.0
    assert rules.toKg(None, "lb") is None
    assert round(rules.toKm(3, "mi"), 3) == 4.828 and round(rules.toKm(400, "m"), 6) == 0.4 and rules.toKm(None, "km") is None


@pytest.mark.parametrize("weight,reps,want", [
    (100, 10, 133.33), (100, 1, 103.33), (100, 12, 140.0), (100, 13, None), (None, 5, None), (0, 5, None),
    (100, None, None),
])
def test_epley(weight, reps, want):
    got = rules.epley(weight, reps)
    assert (got is None and want is None) or round(got, 2) == want


def test_recordsCompareAcrossUnitsAndShowAsEntered():
    rows = (lifts(1, D1, (60, 5), unit="kg") + lifts(2, D2, (135, 5))
            + [row(2, D2, 2, weight=150, reps=3, warmup=True)])   # a heavier warm-up never counts
    found = {r["kind"]: r for r in rules.records(rows, "weight_reps", "lb")}
    assert set(found) == {"heaviest", "e1rm"}
    # 135 lb is 61.2 kg, above 60 kg: the lb set holds it, shown as entered.
    assert found["heaviest"]["workoutId"] == 2 and found["heaviest"]["weight"] == 135.0
    assert found["heaviest"]["weightUnit"] == "lb" and found["heaviest"]["performedOn"] == "2026-11-05"
    assert found["e1rm"]["estimate"] == 157.5 and found["e1rm"]["estimateUnit"] == "lb"
    assert found["heaviest"]["estimate"] is None


def test_aTieKeepsTheEarlierSet():
    rows = lifts(1, D1, (100, 5)) + lifts(2, D2, (100, 5))
    assert {r["kind"]: r["workoutId"] for r in rules.records(rows, "weight_reps", "lb")} == {"heaviest": 1, "e1rm": 1}


def test_recordsOfEachMeasure():
    reps = [row(1, D1, reps=15), row(1, D1, 2, reps=18), row(2, D2, weight=25, reps=8)]
    found = {r["kind"]: r for r in rules.records(reps, "reps", "lb")}
    assert found["reps"]["reps"] == 18 and found["heaviest"]["weight"] == 25
    timed = [row(1, D1, seconds=60), row(2, D2, seconds=90)]
    assert [(r["kind"], r["seconds"]) for r in rules.records(timed, "time", "lb")] == [("time", 90)]
    ran = [row(1, D1, distance=5, dunit="km", seconds=1500),       # 300 s a km
           row(2, D2, distance=3, dunit="mi", seconds=1440),       # 298 s a km: faster, shorter
           row(3, D3, distance=6, dunit="km")]                     # longest, no time
    found = {r["kind"]: r["workoutId"] for r in rules.records(ran, "distance_time", "kg")}
    assert found == {"distance": 3, "pace": 2}
    assert rules.records([], "weight_reps", "lb") == []


def test_aFirstWorkoutSetsRecordsQuietly():
    assert rules.crownsOf(1, lifts(1, D1, (100, 5)), {12: "weight_reps"}, "lb") == []


def test_aRecordBeatenIsANewCrown():
    rows = lifts(1, D1, (100, 5)) + lifts(2, D2, (105, 5), (100, 8))
    crowns = rules.crownsOf(2, rows, {12: "weight_reps"}, "lb")
    assert [(c["kind"], c["exerciseId"], c["weight"], c["reps"]) for c in crowns] == [
        ("heaviest", 12, 105.0, 5), ("e1rm", 12, 100.0, 8)]


def test_equallingARecordIsNoCrown():
    rows = lifts(1, D1, (100, 5)) + lifts(2, D2, (100, 5))
    assert rules.crownsOf(2, rows, {12: "weight_reps"}, "lb") == []


def test_aCrownLooksOnlyAtWhatCameBefore():
    # Workout 3 was logged the same day as 2 but saved later, so it is after 2; editing 2 compares it with 1 only.
    rows = (lifts(1, D1, (100, 5)) + lifts(2, D2, (110, 5), created=1) + lifts(3, D2, (120, 5), created=2))
    assert [c["kind"] for c in rules.crownsOf(2, rows, {12: "weight_reps"}, "lb")] == ["heaviest", "e1rm"]
    assert [c["weight"] for c in rules.crownsOf(3, rows, {12: "weight_reps"}, "lb")] == [120.0, 120.0]


def test_noValueBeforeIsNothingToBeat():
    # A reps exercise first logged without added weight: the first weighted workout has no heaviest crown.
    rows = [row(1, D1, reps=10), row(2, D2, weight=10, reps=10)]
    assert rules.crownsOf(2, rows, {12: "reps"}, "lb") == []


def test_latestCrownsAreNewestFirst():
    rows = (lifts(1, D1, (100, 5)) + lifts(2, D2, (105, 5)) + lifts(3, D3, (100, 5))
            + lifts(4, D4, (110, 5)) + [row(4, D4, exercise=13, item=None, seconds=30, order=1)])
    crowns = rules.latestCrowns(rows, {12: "weight_reps", 13: "time"}, "lb", limit=3)
    assert [(c["workoutId"], c["kind"]) for c in crowns] == [(4, "heaviest"), (4, "e1rm"), (2, "heaviest")]
    assert crowns[0]["performedOn"] == "2026-11-12"


def test_recordsByExerciseNewestLoggedFirst():
    rows = lifts(1, D1, (100, 5)) + [row(2, D2, exercise=13, item=None, seconds=30)]
    found = rules.recordsByExercise(rows, {12: "weight_reps", 13: "time"}, "lb")
    assert [(e["exerciseId"], e["measure"], e["lastOn"]) for e in found] == [
        (13, "time", "2026-11-05"), (12, "weight_reps", "2026-11-02")]
    assert [r["kind"] for r in found[1]["records"]] == ["heaviest", "e1rm"]


def test_seriesHasAPointAWorkout():
    rows = (lifts(1, D1, (100, 10), (100, 8)) + [row(1, D1, 3, weight=50, reps=10, warmup=True)]
            + lifts(2, D2, (50, 10), unit="kg"))
    points = rules.series(rows, "weight_reps", "lb")
    assert [p["workoutId"] for p in points] == [1, 2]
    first, second = points
    assert first["performedOn"] == "2026-11-02" and first["value"] == 100.0
    assert first["best"]["reps"] == 10 and first["estimate"] == 133.3
    assert first["volume"] == 1800.0                  # working sets only: 100 x 10 + 100 x 8
    assert first["crowns"] == []
    assert second["value"] == 110.2 and second["crowns"] == ["heaviest", "e1rm"]   # 50 kg is 110.2 lb


def test_seriesOfTheOtherMeasures():
    assert [p["value"] for p in rules.series([row(1, D1, reps=12), row(2, D2, reps=15)], "reps", "lb")] == [12, 15]
    assert rules.series([row(1, D1, reps=12)], "reps", "lb")[0]["volume"] is None
    assert [p["value"] for p in rules.series([row(1, D1, seconds=45)], "time", "lb")] == [45]
    ran = rules.series([row(1, D1, distance=5, dunit="km", seconds=1500)], "distance_time", "lb")
    assert ran[0]["value"] == 3.11                    # in miles for a person who uses lb
    assert ran[0]["estimate"] is None and ran[0]["volume"] is None


def test_lastTimePrefersTheSameItem():
    rows = (lifts(1, D1, (100, 8), item=500) + lifts(2, D2, (90, 8), item=None)
            + [row(1, D1, 2, weight=50, reps=10, warmup=True, item=500)])
    last = rules.lastFor(500, 12, rows)
    assert last["workoutId"] == 1 and last["performedOn"] == "2026-11-02"
    assert [(s["weight"], s["warmup"]) for s in last["sets"]] == [(100.0, False), (50.0, True)]
    # An item never logged falls back to the exercise's latest workout.
    assert rules.lastFor(501, 12, rows)["workoutId"] == 2
    assert rules.lastFor(501, 99, rows) is None


def test_lastTimeKeepsOneLoggingOfTheExercise():
    # A free workout that logged the same exercise twice: last time is the later of the two (by order).
    rows = lifts(1, D1, (80, 8), item=None, order=0) + lifts(1, D1, (90, 6), item=None, order=1)
    assert [s["weight"] for s in rules.lastFor(None, 12, rows)["sets"]] == [90.0]


def test_recentIsNewestFirst():
    rows = lifts(1, D1, (100, 8)) + lifts(2, D2, (105, 8)) + lifts(3, D3, (110, 8))
    assert [r["workoutId"] for r in rules.recent(rows, limit=2)] == [3, 2]
