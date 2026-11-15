"""Normalising free-exercise-db with rules/*.json, table-tested on the fixture slice, and the payloads checked
against the server's own checks so the two can never drift."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

import normalise
from conftest import FIXTURES, SOURCE

REPO = Path(__file__).resolve().parents[2]
DATA = json.loads((FIXTURES / "exercises.json").read_text(encoding="utf-8"))
RULES = normalise.loadRules()


def entry(key):
    return copy.deepcopy(next(e for e in DATA if e["id"] == key))


def serverCatalog():
    """server/prideCatalog.py, which is pure, loaded on its own."""
    spec = importlib.util.spec_from_file_location("serverPrideCatalog", REPO / "server" / "prideCatalog.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def payloadOf(key, pictures=None):
    e = entry(key)
    names = pictures if pictures is not None else [f"{n:020x}.jpg" for n in range(len(e["images"]))]
    return normalise.normalise(e, SOURCE, RULES, names)[0]


EXPECTED = {
    "Barbell_Curl": (["barbell"], "weight_reps", "upper"),
    "Barbell_Squat": (["barbell"], "weight_reps", "lower"),
    "Dumbbell_Bench_Press": (["dumbbell", "bench"], "weight_reps", "upper"),
    "Hamstring_Stretch": (["bodyweight"], "time", "lower"),
    "Kettlebell_Halo": (["kettlebell"], "weight_reps", "upper"),
    "Plank": (["bodyweight"], "time", "full"),
    "Pullups": (["bodyweight", "pull-up bar"], "reps", "upper"),
    "Pushups": (["bodyweight"], "reps", "upper"),
    "Rope_Jumping": (["other"], "time", "lower"),
    "Side_Bridge": (["bodyweight"], "time", "full"),
    "Upper_Back_Stretch": (["bodyweight"], "time", "upper"),
}


def test_theFixtureIsUpstreamsShape():
    assert normalise.shapeProblem(DATA, RULES) is None
    assert sorted(e["id"] for e in DATA) == sorted(EXPECTED)


@pytest.mark.parametrize("key", sorted(EXPECTED))
def test_eachExerciseGetsPridesWords(key):
    payload = payloadOf(key)
    assert (payload["equipment"], payload["measure"], payload["region"]) == EXPECTED[key]


@pytest.mark.parametrize("key", sorted(EXPECTED))
def test_everyPayloadPassesTheServersChecks(key):
    assert serverCatalog().exerciseProblem(payloadOf(key)) is None


def test_thePayloadCarriesTheSourceAndKeepsWhatUpstreamSaid():
    payload = payloadOf("Barbell_Curl", ["0123456789abcdef0123.jpg", "1123456789abcdef0123.jpg"])
    assert payload["key"] == "Barbell_Curl" and payload["name"] == "Barbell Curl"
    assert payload["licence"] == "Unlicense" and payload["level"] == "beginner" and payload["category"] == "strength"
    assert payload["primary"] == ["biceps"] and payload["secondary"] == ["forearms"]
    assert len(payload["steps"]) == 5 and payload["steps"][0].startswith("Stand up with your torso upright")
    assert payload["pictures"] == ["0123456789abcdef0123.jpg", "1123456789abcdef0123.jpg"]
    assert set(payload) == {"key", "name", "category", "level", "measure", "region", "licence", "primary",
                            "secondary", "equipment", "steps", "pictures", "hash"}


def test_anExerciseWithoutPicturesKeepsNone():
    payload = payloadOf("Kettlebell_Halo", [])
    assert payload["pictures"] == []
    assert serverCatalog().exerciseProblem(payload) is None


def test_aMuscleBothPrimaryAndSecondaryStaysPrimaryOnly():
    payload = payloadOf("Upper_Back_Stretch")
    assert payload["primary"] == ["middle back"] and payload["secondary"] == []


def test_noStepsIsNoSteps():
    assert payloadOf("Side_Bridge")["steps"] == []


def test_blankStepsAreDroppedAndSpacesTidied():
    e = entry("Plank")
    e["instructions"] = ["  Hold   it. ", "", "   "]
    assert normalise.normalise(e, SOURCE, RULES, [])[0]["steps"] == ["Hold it."]


def test_aStepOverTheLimitIsClipped():
    e = entry("Plank")
    e["instructions"] = ["word " * 400]
    step = normalise.normalise(e, SOURCE, RULES, [])[0]["steps"][0]
    assert len(step) <= 1000 and step.endswith("…")


def test_theSamePictureTwiceIsNamedOnce():
    assert payloadOf("Plank", ["0123456789abcdef0123.jpg"] * 2)["pictures"] == ["0123456789abcdef0123.jpg"]


def test_anUnknownEquipmentWordBecomesOtherAndIsReported():
    e = entry("Barbell_Curl")
    e["equipment"] = "sled"
    payload, unmapped = normalise.normalise(e, SOURCE, RULES, [])
    assert payload["equipment"] == ["other"] and unmapped == "sled"


def test_aKnownWordReportsNothing():
    assert normalise.normalise(entry("Barbell_Curl"), SOURCE, RULES, [])[1] is None


def test_theHashFollowsTheContent():
    a = payloadOf("Plank")
    assert a["hash"] == payloadOf("Plank")["hash"] and len(a["hash"]) == 40
    changed = entry("Plank")
    changed["name"] = "Plank Hold"
    assert normalise.normalise(changed, SOURCE, RULES, ["0" * 20 + ".jpg", "1" + "0" * 19 + ".jpg"])[0]["hash"] != a["hash"]


def test_aPictureIsNamedByItsContent():
    assert normalise.pictureName(b"abc") == "a9993e364706816aba3e.jpg"
    assert normalise.isJpeg(b"\xff\xd8\xff\xe0rest") and not normalise.isJpeg(b"<html>")


@pytest.mark.parametrize("change, words", [
    (lambda d: d[0].update(primaryMuscles=["wings"]), "muscle"),
    (lambda d: d[0].update(secondaryMuscles=["wings"]), "muscle"),
    (lambda d: d[0].update(category="yoga"), "category"),
    (lambda d: d[0].update(level="pro"), "level"),
    (lambda d: d[0].update(images=["../../secrets.jpg"]), "picture"),
    (lambda d: d[0].update(images=["Other_Exercise/0.jpg"]), "picture"),
    (lambda d: d[0].update(id="has space"), "id"),
    (lambda d: d[0].update(name=""), "name"),
    (lambda d: d[0].update(primaryMuscles=[]), "primary"),
    (lambda d: d[0].update(instructions="one long text"), "instructions"),
    (lambda d: d[0].pop("equipment") and d[0].update(equipment=["barbell"]), "equipment"),
    (lambda d: d.append(copy.deepcopy(d[0])), "twice"),
])
def test_aShapeProblemIsNamed(change, words):
    data = copy.deepcopy(DATA)
    change(data)
    problem = normalise.shapeProblem(data, RULES)
    assert problem and words in problem


@pytest.mark.parametrize("path", [
    "Barbell_Curl/../../x.jpg", "../Barbell_Curl/0.jpg", "/Barbell_Curl/0.jpg", "/etc/passwd.jpg",
    "Barbell_Curl\\0.jpg", "..\\x.jpg", "C:/Barbell_Curl/0.jpg", "C:\\Barbell_Curl\\0.jpg", "C:Barbell_Curl/0.jpg",
    "Barbell_Curl/0.jpg/", "Barbell_Curl/0.jpg\n", "Barbell_Curl//0.jpg", "Barbell_Curl/0.png", "./Barbell_Curl/0.jpg",
])
def test_aPicturePathThatCouldLeaveTheCacheFolderIsAShapeProblem(path):
    data = copy.deepcopy(DATA)
    data[0]["images"] = [path]
    problem = normalise.shapeProblem(data, RULES)
    assert problem and "picture" in problem


def test_anUnknownMuscleIsAShapeProblem():
    data = copy.deepcopy(DATA)
    data[3]["primaryMuscles"] = ["rotator cuff"]
    assert "unknown muscle 'rotator cuff'" in normalise.shapeProblem(data, RULES)


@pytest.mark.parametrize("data", [{}, [], "text", [1]])
def test_somethingThatIsNotAListOfExercisesIsAShapeProblem(data):
    assert normalise.shapeProblem(data, RULES)


def test_theRulesKnowEveryMuscleOnceAndMatchTheServer():
    server = serverCatalog()
    region = RULES["region"]
    listed = region["upper"] + region["lower"] + region["core"]
    assert sorted(listed) == sorted(server.MUSCLES) and len(set(listed)) == len(listed)
    assert tuple(RULES["words"]["categories"]) == server.CATEGORIES
    assert tuple(RULES["words"]["levels"]) == server.LEVELS
    equipment = RULES["equipment"]
    produced = set(equipment["map"].values()) | {equipment["none"]} | {r["add"] for r in equipment["addByName"]}
    assert produced <= set(server.EQUIPMENT)
    measure = RULES["measure"]
    assert set(measure["exceptions"].values()) | set(measure["byCategory"].values()) | {measure["default"], "reps"} \
        <= set(server.MEASURES)
