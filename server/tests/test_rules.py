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


# ---- Suggestions (spec §5; plan decisions 14-18) ----

LB = {"units": "lb", "upperIncrement": 5.0, "lowerIncrement": 10.0}
KG = {"units": "kg", "upperIncrement": 2.5, "lowerIncrement": 5.0}


def item(measure="weight_reps", region="upper", sets=3, low=8, high=12, weight=135.0, unit="lb", seconds=None):
    return {"id": 500, "measure": measure, "region": region, "sets": sets, "repsMin": low, "repsMax": high,
            "targetWeight": weight, "targetUnit": unit if weight is not None else None, "targetSeconds": seconds}


@pytest.mark.parametrize("value,unit,want", [
    (140, "lb", 140), (137.5, "lb", 140), (137.4, "lb", 135), (62.5, "kg", 62.5), (63.7, "kg", 62.5),
    (63.8, "kg", 65),
])
def test_roundToStep(value, unit, want):
    assert rules.roundToStep(value, unit) == want


def three(weight, reps, unit="lb", warm=None):
    sets = [row(1, D1, n, weight=weight, reps=r, unit=unit) for n, r in enumerate(reps, start=1)]
    return sets + ([row(1, D1, 9, weight=warm, reps=5, warmup=True)] if warm else [])


@pytest.mark.parametrize("name,it,sets,profile,want", [
    ("upper, lb", item(), three(135, [12, 12, 12]), LB, {"weight": 140.0, "unit": "lb"}),
    ("lower uses the lower step", item(region="lower", weight=185), three(185, [12, 12, 12]), LB,
     {"weight": 195.0, "unit": "lb"}),
    ("full uses the upper step", item(region="full"), three(135, [12, 12, 12]), LB, {"weight": 140.0, "unit": "lb"}),
    ("kg", item(weight=60, unit="kg"), three(60, [12, 12, 12], "kg"), KG, {"weight": 62.5, "unit": "kg"}),
    ("kg increment, lb target", item(), three(135, [12, 12, 12]), KG, {"weight": 140.0, "unit": "lb"}),
    ("lb increment, kg target", item(weight=60, unit="kg"), three(60, [12, 12, 12], "kg"), LB,
     {"weight": 62.5, "unit": "kg"}),
    ("kg sets, lb target", item(), three(62, [12, 12, 12], "kg"), LB, {"weight": 140.0, "unit": "lb"}),
    ("a small increment still steps up", item(), three(135, [12, 12, 12]), {**LB, "upperIncrement": 0.5},
     {"weight": 140.0, "unit": "lb"}),
    ("one set short of the top", item(), three(135, [12, 12, 11]), LB, None),
    ("a warm-up is not a working set", item(), three(135, [12, 12, 12], warm=95), LB,
     {"weight": 140.0, "unit": "lb"}),
    ("fewer working sets than planned", item(), three(135, [12, 12]), LB, None),
    ("below the target weight", item(), three(130, [12, 12, 12]), LB, None),
    ("no target: the lightest set is the base", item(weight=None),
     [row(1, D1, 1, weight=50, reps=12), row(1, D1, 2, weight=55, reps=12), row(1, D1, 3, weight=55, reps=12)],
     LB, {"weight": 55.0, "unit": "lb"}),
    ("over 2,000 is not proposed", item(weight=1998), three(1998, [12, 12, 12]), LB, None),
    ("reps, no weight: the range goes up 2", item("reps", weight=None), [row(1, D1, n, reps=12) for n in (1, 2, 3)],
     LB, {"repsMin": 10, "repsMax": 14}),
    ("reps at 100 stay", item("reps", weight=None, low=98, high=100), [row(1, D1, n, reps=100) for n in (1, 2, 3)],
     LB, None),
    ("reps with added weight step the weight", item("reps", weight=20),
     [row(1, D1, n, weight=20, reps=12) for n in (1, 2, 3)], LB, {"weight": 25.0, "unit": "lb"}),
    ("time: 10 s more", item("time", weight=None, low=None, high=None, seconds=30),
     [row(1, D1, n, seconds=s) for n, s in ((1, 30), (2, 35), (3, 31))], LB, {"seconds": 40}),
    ("time short of the target", item("time", weight=None, low=None, high=None, seconds=30),
     [row(1, D1, n, seconds=s) for n, s in ((1, 30), (2, 25), (3, 31))], LB, None),
    ("distance and time: none in part 1", item("distance_time", weight=None, low=None, high=None, sets=1),
     [row(1, D1, distance=5, dunit="km", seconds=1500)], LB, None),
])
def test_increase(name, it, sets, profile, want):
    assert rules.increase(it, sets, profile) == want, name


@pytest.mark.parametrize("values,want", [
    ([100, 105, 104, 105, 103], True),       # the last three never beat 105
    ([100, 105, 104, 106, 103], False),      # 106 beat it
    ([100, 100, 100], False),                # three workouts are not enough: nothing came before them
    ([100, 100, 100, 100], True),
    ([None, 100, 100, 100], False),          # nothing measurable before the three
])
def test_stalled(values, want):
    assert rules.stalled(values) is want


def test_lastImprovement():
    assert rules.lastImprovement([100, 105, 104, 106, 103]) == 3
    assert rules.lastImprovement([100, 100, 100]) == 0
    assert rules.lastImprovement([]) == -1


def test_bestValue():
    assert round(rules.bestValue("weight_reps", [row(1, D1, weight=100, reps=10, unit="kg")]), 2) == 133.33
    # No set of 12 reps or fewer: the heaviest set stands in.
    assert round(rules.bestValue("weight_reps", [row(1, D1, weight=100, reps=15, unit="kg")]), 2) == 100.0
    assert rules.bestValue("reps", [row(1, D1, reps=9), row(1, D1, 2, reps=11)]) == 11
    assert rules.bestValue("time", [row(1, D1, seconds=40, warmup=True)]) is None
    assert rules.bestValue("distance_time", [row(1, D1, distance=5, dunit="km")]) is None


def session(workout, day, reps, weight=135):
    return [row(workout, day, n, weight=weight, reps=r) for n, r in enumerate(reps, start=1)]


TOP = [12, 12, 12]
SHORT = [12, 11, 10]


def made(kind, basedOn, state="open", id=1, weight=None, unit=None):
    return {"id": id, "kind": kind, "basedOn": basedOn, "state": state, "weight": weight, "unit": unit,
            "repsMin": None, "repsMax": None, "seconds": None}


def test_aQualifyingWorkoutMakesAStepUp():
    withdraw, create = rules.suggestionFor(item(), session(1, D1, SHORT) + session(2, D2, TOP), LB, [])
    assert withdraw == []
    assert create == {"kind": "increase", "basedOn": 2, "weight": 140.0, "unit": "lb", "repsMin": None,
                      "repsMax": None, "seconds": None}


def test_theSameOpenStepUpIsKept():
    existing = [made("increase", 2, weight=140.0, unit="lb")]
    assert rules.suggestionFor(item(), session(2, D2, TOP), LB, existing) == ([], None)


def test_aNewerStepUpReplacesTheOpenOne():
    existing = [made("increase", 1, weight=140.0, unit="lb", id=7)]
    withdraw, create = rules.suggestionFor(item(weight=140), session(1, D1, TOP) + session(2, D2, TOP, 140), LB,
                                           existing)
    assert withdraw == [7] and create["basedOn"] == 2 and create["weight"] == 145.0


def test_aDismissedStepUpWaitsForAnotherQualifyingWorkout():
    existing = [made("increase", 2, state="dismissed", weight=140.0, unit="lb")]
    assert rules.suggestionFor(item(), session(2, D2, TOP), LB, existing) == ([], None)
    withdraw, create = rules.suggestionFor(item(), session(2, D2, TOP) + session(3, D3, TOP), LB, existing)
    assert withdraw == [] and create["basedOn"] == 3


def test_anAcceptedStepUpIsNotMadeAgain():
    # Review focus 1: the target is already 140 and the workout behind it was edited; nothing new for that workout.
    existing = [made("increase", 2, state="accepted", weight=140.0, unit="lb")]
    assert rules.suggestionFor(item(), session(2, D2, TOP, 140), LB, existing) == ([], None)


def test_aWorkoutThatNoLongerQualifiesWithdrawsTheOpenStepUp():
    existing = [made("increase", 2, weight=140.0, unit="lb", id=7)]
    assert rules.suggestionFor(item(), session(2, D2, SHORT), LB, existing) == ([7], None)
    # A newer workout that falls short: the step-up no longer holds either (plan decision 17).
    assert rules.suggestionFor(item(), session(2, D2, TOP) + session(3, D3, SHORT), LB, existing) == ([7], None)


def test_noHistoryLeftWithdrawsEverythingOpen():
    existing = [made("increase", None, id=7), made("stall", 1, state="dismissed", id=8)]
    assert rules.suggestionFor(item(), [], LB, existing) == ([7], None)


FLAT = [10, 9, 8]


def flat(n):
    return [r for w in range(1, n + 1) for r in session(w, date(2026, 10, w), FLAT)]


def test_threeFlatWorkoutsAfterABestMakeAStall():
    withdraw, create = rules.suggestionFor(item(), flat(4), LB, [])
    assert withdraw == [] and create["kind"] == "stall" and create["basedOn"] == 4
    assert rules.suggestionFor(item(), flat(3), LB, []) == ([], None)


def test_aStallIsMadeOnceUntilTheItemImproves():
    open_ = [made("stall", 4, id=9)]
    assert rules.suggestionFor(item(), flat(5), LB, open_) == ([], None)          # kept, not made again
    noted = [made("stall", 4, state="dismissed", id=9)]
    assert rules.suggestionFor(item(), flat(5), LB, noted) == ([], None)          # noted: nothing new
    better = flat(5) + session(6, date(2026, 10, 6), [12, 11, 10])
    later = better + [r for w in (7, 8, 9) for r in session(w, date(2026, 10, w), FLAT)]
    # Workout 6 improved; 7-9 brought nothing above it: a new stall.
    withdraw, create = rules.suggestionFor(item(), later, LB, noted)
    assert create["kind"] == "stall" and create["basedOn"] == 9


def test_aStepUpReplacesAnOpenStall():
    withdraw, create = rules.suggestionFor(item(), flat(4) + session(5, date(2026, 10, 5), TOP), LB,
                                           [made("stall", 4, id=9)])
    assert withdraw == [9] and create["kind"] == "increase"
