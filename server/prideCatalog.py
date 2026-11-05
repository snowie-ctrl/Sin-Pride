"""
The exercise catalog's words and shapes, shared by the app routes (prideRoutes.py: /catalog and the pictures), the
importer's admin routes (prideAdminRoutes.py) and the schema's CHECKs, which tests/test_schema.py keeps in step with
these lists. Pure: no Flask and no database, so every rule here is tested on its own.
"""
import hashlib
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


# ---- Checking an import (POST /api/pride-admin/import) ----

def _words(value, allowed):
    return (isinstance(value, list) and all(isinstance(v, str) and v in allowed for v in value)
            and len(set(value)) == len(value))


def _text(value, limit):
    return isinstance(value, str) and 1 <= len(value.strip()) <= limit and len(value) <= limit


def exerciseProblem(e):
    """Why one exercise of an import cannot be stored, naming the field; None when it can. Everything the schema's
    CHECKs would refuse is caught here first, so a refusal names the field instead of a MySQL error."""
    if not isinstance(e, dict):
        return "an exercise must be an object"
    if not _text(e.get("key"), LIMITS["key"]):
        return f"key must be 1 to {LIMITS['key']} characters"
    if not _text(e.get("name"), LIMITS["name"]):
        return f"name must be 1 to {LIMITS['name']} characters"
    for field, allowed in (("category", CATEGORIES), ("level", LEVELS), ("measure", MEASURES), ("region", REGIONS)):
        if e.get(field) not in allowed:
            return f"{field} must be one of {', '.join(allowed)}"
    if not _text(e.get("licence"), LIMITS["licence"]):
        return f"licence must be 1 to {LIMITS['licence']} characters"
    if not _words(e.get("primary"), MUSCLES) or not e["primary"]:
        return "primary must list known muscles, at least one, each once"
    if not _words(e.get("secondary"), MUSCLES) or set(e["primary"]) & set(e["secondary"]):
        return "secondary must list known muscles, each once, none already primary"
    if not _words(e.get("equipment"), EQUIPMENT) or not e["equipment"]:
        return "equipment must list known equipment, at least one, each once"
    steps = e.get("steps")
    if not isinstance(steps, list) or len(steps) > LIMITS["steps"] or not all(_text(s, LIMITS["step"]) for s in steps):
        return f"steps must be up to {LIMITS['steps']} texts of 1 to {LIMITS['step']} characters"
    pictures = e.get("pictures")
    if (not isinstance(pictures, list) or len(pictures) > LIMITS["pictures"] or len(set(pictures)) != len(pictures)
            or not all(isinstance(p, str) and PICTURE_NAME.fullmatch(p) for p in pictures)):
        return f"pictures must be up to {LIMITS['pictures']} distinct names of 20 hex and .jpg"
    if not isinstance(e.get("hash"), str) or not HASH.fullmatch(e["hash"]):
        return "hash must be 40 hex"
    return None


def batchProblem(data):
    """Why an import cannot be taken at all; None when every exercise passes. The first problem is named."""
    source = data.get("source")
    if not isinstance(source, str) or not SOURCE.fullmatch(source):
        return "source must be 1 to 40 lowercase letters, digits or dashes"
    if source == "own":
        return "the source own is kept for a person's own exercises"
    exercises = data.get("exercises")
    if not isinstance(exercises, list) or not exercises:
        return "exercises must be a non-empty list"
    if len(exercises) > LIMITS["exercises"]:
        return f"at most {LIMITS['exercises']} exercises in one import"
    seen = set()
    for e in exercises:
        problem = exerciseProblem(e)
        if problem:
            return f"exercise {e.get('key') if isinstance(e, dict) else '?'}: {problem}"
        if e["key"] in seen:
            return f"exercise {e['key']}: the key appears twice"
        seen.add(e["key"])
    return None


def versionOf(rows):
    """The catalog's version: a hash of every catalog row's source, key, content and whether it is shown, sorted
    here so the database's collation and order never change it."""
    lines = sorted(f"{r['Source']}\t{r['SourceKey']}\t{r['ContentHash'] or ''}\t"
                   f"{'hidden' if r['RemovedAt'] is not None else 'shown'}" for r in rows)
    return hashlib.sha1("\n".join(lines).encode("utf-8")).hexdigest()
