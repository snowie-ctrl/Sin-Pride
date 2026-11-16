"""The starters (spec §6's mapping, plan decisions 10–12) and their routes."""
import pytest

from conftest import UID, loadModule
from programSamples import LOCK, PROGRAM, whole

A = "/api/pride"
starters = loadModule("prideStarters")
ALL = starters.load()
FOUND = {key: {"id": n, "name": key.replace("_", " "), "measure": "weight_reps"} for n, key in
         enumerate(sorted(starters.keysOf(ALL)), start=100)}
for timed in ("Plank", "Superman", "Side_Bridge"):
    FOUND[timed]["measure"] = "time"
for reps in ("Pushups", "Bodyweight_Squat", "Inverted_Row", "Dead_Bug"):
    FOUND[reps]["measure"] = "reps"
byKey = {s["key"]: s for s in ALL}


def test_theThreeStartersAreWellFormedAndCoverEveryDayCount():
    assert [s["key"] for s in ALL] == ["foundations", "upperLower", "pushPullLegs"]
    for s in ALL:
        assert starters.problems(s) == [], s["key"]
    assert sorted(d for s in ALL for d in s["forDays"]) == [2, 3, 4, 5, 6]


@pytest.mark.parametrize("equipment,want", [
    (["barbell", "bench", "cable", "machine", "dumbbell", "bodyweight"], "gym"),
    (["dumbbell", "bench", "bodyweight"], "dumbbell"),
    (["dumbbell"], "bodyweight"),          # no bench: the dumbbell variant needs one
    (["bodyweight", "bands"], "bodyweight"),
    ([], "bodyweight"),
])
def test_theVariantIsTheFirstWhoseNeedsThePersonHas(equipment, want):
    assert starters.variantFor(byKey["foundations"], equipment)["name"] == want


@pytest.mark.parametrize("key,days,want", [
    ("foundations", 3, [0, 2, 4]), ("foundations", 2, [1, 4]), ("upperLower", 4, [0, 1, 3, 4]),
    ("pushPullLegs", 5, [0, 1, 2, 3, 4]), ("pushPullLegs", 6, [0, 1, 2, 3, 4, 5]),
    ("foundations", 6, [0, 2, 4]), ("pushPullLegs", 2, [0, 1, 2, 3, 4]),   # not its days: its nearest
])
def test_plannedDaysFollowTheSpecsMapping(key, days, want):
    assert starters.daysFor(byKey[key], days) == want


def test_fillingUsesTheGoalsRepsAndTheItemsOwnSeconds():
    filled = starters.fill(byKey["foundations"], ["bodyweight"], "strength", 3, FOUND)
    assert filled["suggested"] is True and filled["variant"] == "bodyweight" and filled["days"] == [0, 2, 4]
    first = filled["routines"][0]["items"]
    assert first[0] == {"exerciseId": FOUND["Bodyweight_Squat"]["id"], "name": "Bodyweight Squat", "measure": "reps",
                        "sets": 3, "repsMin": 5, "repsMax": 8, "targetSeconds": None, "restSeconds": 60}
    plank = first[-1]
    assert (plank["targetSeconds"], plank["repsMin"], plank["restSeconds"]) == (30, None, 60)
    superman = filled["routines"][1]["items"][2]
    assert superman["targetSeconds"] == 20
    assert starters.fill(byKey["upperLower"], ["bodyweight"], "general", 3, FOUND)["suggested"] is False


def test_aWeightedItemRestsLonger():
    filled = starters.fill(byKey["upperLower"], ["dumbbell", "bench"], "muscle", 4, FOUND)
    bench = filled["routines"][0]["items"][0]
    assert (bench["restSeconds"], bench["repsMin"], bench["repsMax"]) == (90, 8, 12)


def test_aVariantsOwnBlurbWins():
    assert "No bar at home" in starters.fill(byKey["pushPullLegs"], [], "general", 5, FOUND)["blurb"]
    assert "No bar" not in starters.fill(byKey["pushPullLegs"], ["dumbbell", "bench"], "general", 5, FOUND)["blurb"]


def test_missingExercisesAreLeftOutAndListed():
    partial = {k: v for k, v in FOUND.items() if k not in ("Plank", "Dead_Bug")}
    filled = starters.fill(byKey["foundations"], [], "general", 3, partial)
    assert filled["missing"] == ["Dead_Bug", "Plank"]
    assert [len(r["items"]) for r in filled["routines"]] == [4, 4]


def test_startersNeedASession(anonUserClient):
    assert anonUserClient.get(f"{A}/starters").status_code == 401
    assert anonUserClient.post(f"{A}/starters/foundations/adopt").status_code == 401


PROFILE = {"Units": "lb", "Goal": "muscle", "DaysPerWeek": 4, "UpperIncrement": 5, "LowerIncrement": 10,
           "WeekStart": "mon", "IntroState": "pending"}


def catalogRows(found=FOUND):
    return [{"ExerciseID": v["id"], "SourceKey": k, "Name": v["name"], "Measure": v["measure"]} for k, v in found.items()]


def test_theStartersAreFilledForThePerson(userClient, useDb):
    conn = useDb(fetchone=[PROFILE], fetchall=[[{"Equipment": "dumbbell"}, {"Equipment": "bench"}], catalogRows()])
    data = userClient.get(f"{A}/starters").get_json()["data"]
    assert [s["key"] for s in data] == ["foundations", "upperLower", "pushPullLegs"]
    assert [s["suggested"] for s in data] == [False, True, False]
    assert {s["variant"] for s in data} == {"dumbbell"}
    sql, params = conn.cur.executed[-1]
    assert "OwnerUserID IS NULL" in sql and "RemovedAt IS NULL" in sql and params[0] == "free-exercise-db"


def test_adoptingMakesAnActiveProgramWithItsDaysRoutinesAndItems(userClient, useDb):
    conn = useDb(fetchone=[LOCK, {"n": 1}, PROFILE, PROGRAM],
                 fetchall=[[{"Equipment": "dumbbell"}, {"Equipment": "bench"}], catalogRows(), *whole()],
                 lastrowids={"Programs": [5], "Routines": [50, 51]})
    assert userClient.post(f"{A}/starters/upperLower/adopt").status_code == 200
    assert conn.cur.statements("INSERT INTO Programs")[0][1] == (UID, "Upper/Lower", 0, "upperLower")
    assert conn.cur.statements("UPDATE Programs SET IsActive")[0][1] == (5, UID)
    assert [p for _, p in conn.cur.statements("INSERT INTO ProgramDays")] == [(5, 0), (5, 1), (5, 3), (5, 4)]
    assert [p[1:] for _, p in conn.cur.statements("INSERT INTO Routines")] == [("Upper", 0), ("Lower", 1)]
    items = conn.cur.statements("INSERT INTO RoutineItems")
    assert len(items) == 12 and items[0][1][:6] == (50, FOUND["Dumbbell_Bench_Press"]["id"], 0, 3, 8, 12)
    assert conn.commits == 1


def test_anUnknownStarterIs404(userClient, useDb):
    useDb(fetchone=[LOCK, {"n": 0}])
    assert userClient.post(f"{A}/starters/nope/adopt").status_code == 404


def test_aStarterWithNothingLeftCannotBeAdopted(userClient, useDb):
    conn = useDb(fetchone=[LOCK, {"n": 0}, PROFILE], fetchall=[[], []])
    answer = userClient.post(f"{A}/starters/foundations/adopt")
    assert answer.status_code == 409 and answer.get_json()["status"] == "unavailable"
    assert not conn.cur.statements("INSERT")


def test_the21stProgramCannotBeAStarter(userClient, useDb):
    useDb(fetchone=[LOCK, {"n": 20}])
    assert userClient.post(f"{A}/starters/foundations/adopt").status_code == 409
