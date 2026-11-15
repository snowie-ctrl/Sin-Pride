"""checkStarters finds every problem a starter key can have against a catalog."""
import checkStarters

STARTER = {"key": "s", "variants": [{"name": "gym", "routines": [{"title": "A", "items": [
    {"exercise": "Squat"}, {"exercise": "Plank", "seconds": 30}, {"exercise": "Gone"}, {"exercise": "Hard"},
    {"exercise": "Run", "seconds": 60}, {"exercise": "Hold"}]}]}]}
CATALOG = [
    {"key": "Squat", "level": "beginner", "measure": "weight_reps", "removed": False},
    {"key": "Plank", "level": "beginner", "measure": "time", "removed": False},
    {"key": "Hard", "level": "expert", "measure": "weight_reps", "removed": False},
    {"key": "Run", "level": "beginner", "measure": "distance_time", "removed": False},
    {"key": "Hold", "level": "beginner", "measure": "time", "removed": False},
]


def test_everyKindOfProblemIsNamed():
    found = checkStarters.check([STARTER], CATALOG)
    assert found == ["s: Gone is not in the catalog", "s: Hard is expert, not beginner",
                     "s: Run has seconds but is measured distance_time", "s: Hold is timed but has no seconds"]


def test_aCleanStarterHasNone():
    clean = {"key": "c", "variants": [{"name": "gym", "routines": [{"title": "A", "items": [
        {"exercise": "Squat"}, {"exercise": "Plank", "seconds": 30}]}]}]}
    assert checkStarters.check([clean], CATALOG) == []
