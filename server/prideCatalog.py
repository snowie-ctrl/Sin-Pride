"""
The exercise catalog's words and shapes, shared by the app routes (prideRoutes.py: /catalog and the pictures), the
importer's admin routes (prideAdminRoutes.py) and the schema's CHECKs, which tests/test_schema.py keeps in step with
these lists. Pure: no Flask and no database, so every rule here is tested on its own.
"""
import re
from pathlib import Path

# Pictures live on plutus under appFiles, as Gluttony's do, named by their content (see PICTURE_NAME).
MEDIA_ROOT = Path("/pool/appFiles/pride")
PICTURE_DIR = "exercises"
# The first 20 hex of the SHA-1 of the picture's bytes, then .jpg: a changed picture gets a new name, so a copy the
# app keeps never goes stale, and the name alone is safe to join to a folder.
PICTURE_NAME = re.compile(r"[0-9a-f]{20}\.jpg")
HASH = re.compile(r"[0-9a-f]{40}")
SOURCE = re.compile(r"[a-z0-9-]{1,40}")

# free-exercise-db's own words for these four, kept as given (spec §2).
CATEGORIES = ("strength", "stretching", "plyometrics", "strongman", "powerlifting", "cardio", "olympic weightlifting")
LEVELS = ("beginner", "intermediate", "expert")
MUSCLES = ("abdominals", "abductors", "adductors", "biceps", "calves", "chest", "forearms", "glutes", "hamstrings",
           "lats", "lower back", "middle back", "neck", "quadriceps", "shoulders", "traps", "triceps")
ROLES = ("primary", "secondary")
# Pride's own (spec §2, §3).
MEASURES = ("weight_reps", "reps", "time", "distance_time")
REGIONS = ("upper", "lower", "full")
EQUIPMENT = ("barbell", "dumbbell", "kettlebell", "machine", "cable", "bands", "bodyweight", "bench", "pull-up bar",
             "other")

LIMITS = {"key": 100, "name": 120, "licence": 80, "step": 1000, "steps": 50, "pictures": 10, "exercises": 5000}
# An import that would hide more than this share of a source's visible exercises is refused (spec §8).
HIDE_GUARD = 0.10


# ---- Reading the catalog (GET /catalog) ----

# Only the catalog: a person's own exercise names its owner and is theirs alone. Hidden rows are listed (RemovedAt), so
# old workouts can still name what they logged.
EXERCISES_QUERY = ("SELECT ExerciseID, Source, SourceKey, Licence, Name, Category, Level, Measure, Region, RemovedAt "
                   "FROM Exercises WHERE OwnerUserID IS NULL ORDER BY Name, ExerciseID")
_CATALOG_ONLY = "JOIN Exercises e ON e.ExerciseID = c.ExerciseID WHERE e.OwnerUserID IS NULL"
CHILD_QUERIES = (
    ("muscles", f"SELECT c.ExerciseID, c.Muscle, c.Role FROM ExerciseMuscles c {_CATALOG_ONLY} "
                "ORDER BY c.ExerciseID, c.Role, c.Muscle"),
    ("equipment", f"SELECT c.ExerciseID, c.Equipment FROM ExerciseEquipment c {_CATALOG_ONLY} "
                  "ORDER BY c.ExerciseID, c.Equipment"),
    ("steps", f"SELECT c.ExerciseID, c.Text FROM ExerciseSteps c {_CATALOG_ONLY} ORDER BY c.ExerciseID, c.StepNo"),
    ("pictures", f"SELECT c.ExerciseID, c.Path FROM ExercisePictures c {_CATALOG_ONLY} ORDER BY c.ExerciseID, c.Idx"),
)


def exercisesJson(rows, children):
    """The catalog as docs/api.md shapes it: one object per exercise row, in the rows' order, each child table's
    rows gathered onto their exercise."""
    byId = {}
    for r in rows:
        byId[r["ExerciseID"]] = {
            "id": r["ExerciseID"], "key": r["SourceKey"], "source": r["Source"], "licence": r["Licence"],
            "name": r["Name"], "category": r["Category"], "level": r["Level"], "measure": r["Measure"],
            "region": r["Region"], "removed": r["RemovedAt"] is not None,
            "primary": [], "secondary": [], "equipment": [], "steps": [], "pictures": []}
    for m in children["muscles"]:
        if m["ExerciseID"] in byId:
            byId[m["ExerciseID"]][m["Role"]].append(m["Muscle"])
    for name, column in (("equipment", "Equipment"), ("steps", "Text"), ("pictures", "Path")):
        for row in children[name]:
            if row["ExerciseID"] in byId:
                byId[row["ExerciseID"]][name].append(row[column])
    return list(byId.values())
