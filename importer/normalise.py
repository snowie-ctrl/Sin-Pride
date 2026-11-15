"""
free-exercise-db's exercises in Pride's words (spec §2), by the readable rules in rules/*.json: equipment.json maps
upstream equipment onto Pride's list, measure.json sets how each exercise is measured, region.json sets the body
region from the primary muscles, and words.json names the categories and levels Pride knows. shapeProblem() says
whether the upstream file still looks as expected; an exercise that passes it is normalised, never guessed at.
"""
import hashlib
import json
import re
from pathlib import Path

KEY = re.compile(r"[A-Za-z0-9_-]{1,100}")
PICTURE_PATH = re.compile(r"[A-Za-z0-9_-]{1,100}/[0-9]{1,2}\.jpg")
JPEG_MAGIC = b"\xff\xd8\xff"
NAME_LIMIT = 120
STEP_LIMIT = 1000
STEPS_LIMIT = 50
PICTURES_LIMIT = 10


def loadRules(folder=None):
    if folder is None:
        # Only here, so a tool that only normalises (the app stub's makeFixture.py) needs no .env reader.
        import config
        folder = config.RULES_DIR
    return {name: json.loads((Path(folder) / f"{name}.json").read_text(encoding="utf-8"))
            for name in ("equipment", "measure", "region", "words")}


def knownMuscles(rules):
    region = rules["region"]
    return set(region["upper"]) | set(region["lower"]) | set(region["core"])


def shapeProblem(data, rules):
    """Why the upstream file does not look as expected (naming the first exercise and field); None when it does."""
    if not isinstance(data, list) or not data:
        return "the file is not a non-empty list of exercises"
    muscles, words, seen = knownMuscles(rules), rules["words"], set()
    for n, e in enumerate(data, start=1):
        if not isinstance(e, dict):
            return f"exercise {n} is not an object"
        key = e.get("id")
        if not isinstance(key, str) or not KEY.fullmatch(key):
            return f"exercise {n}: id {key!r} is not letters, digits, _ or -"
        where = f"exercise {key}"
        if key in seen:
            return f"{where} appears twice"
        seen.add(key)
        if not isinstance(e.get("name"), str) or not e["name"].strip():
            return f"{where}: no name"
        if e.get("category") not in words["categories"]:
            return f"{where}: unknown category {e.get('category')!r}"
        if e.get("level") not in words["levels"]:
            return f"{where}: unknown level {e.get('level')!r}"
        if e.get("equipment") is not None and not isinstance(e["equipment"], str):
            return f"{where}: equipment is not one word"
        for field in ("primaryMuscles", "secondaryMuscles"):
            value = e.get(field)
            if not isinstance(value, list) or not all(isinstance(m, str) for m in value):
                return f"{where}: {field} is not a list of words"
            unknown = [m for m in value if m not in muscles]
            if unknown:
                return f"{where}: unknown muscle {unknown[0]!r}"
        if not e["primaryMuscles"]:
            return f"{where}: no primary muscle"
        steps = e.get("instructions")
        if not isinstance(steps, list) or not all(isinstance(s, str) for s in steps):
            return f"{where}: instructions is not a list of texts"
        images = e.get("images")
        if (not isinstance(images, list) or len(images) > PICTURES_LIMIT
                or not all(isinstance(p, str) and PICTURE_PATH.fullmatch(p) and p.startswith(key + "/") for p in images)):
            return f"{where}: a picture path is not <id>/<n>.jpg"
    return None


def equipmentOf(entry, rules):
    """(Pride's equipment for an exercise, and the upstream word when no rule knew it)."""
    r = rules["equipment"]
    word = entry.get("equipment")
    unmapped = None
    if word is None:
        base = r["none"]
    elif word in r["map"]:
        base = r["map"][word]
    else:
        base, unmapped = "other", word
    equipment = [base]
    name = entry["name"].lower()
    for rule in r["addByName"]:
        if (rule["add"] not in equipment and base in rule["whenEquipment"]
                and any(part.lower() in name for part in rule["nameContains"])):
            equipment.append(rule["add"])
    return equipment, unmapped


def measureOf(entry, equipment, rules):
    r = rules["measure"]
    if entry["id"] in r["exceptions"]:
        return r["exceptions"][entry["id"]]
    if entry["category"] in r["byCategory"]:
        return r["byCategory"][entry["category"]]
    if all(piece in r["repsWhenOnly"] for piece in equipment):
        return "reps"
    return r["default"]


def regionOf(primary, rules):
    r = rules["region"]
    regions = {"upper" for m in primary if m in r["upper"]} | {"lower" for m in primary if m in r["lower"]}
    return regions.pop() if len(regions) == 1 else "full"


def pictureName(data):
    """A picture's name on the server: the first 20 hex of the SHA-1 of its bytes (server/prideCatalog.PICTURE_NAME)."""
    return hashlib.sha1(data).hexdigest()[:20] + ".jpg"


def isJpeg(data):
    return data.startswith(JPEG_MAGIC)


def contentHash(payload):
    body = {k: v for k, v in payload.items() if k != "hash"}
    return hashlib.sha1(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def clip(text, limit):
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def normalise(entry, source, rules, pictureNames):
    """(the exercise as POST /api/pride-admin/import takes it, and the upstream equipment word no rule knew)."""
    equipment, unmapped = equipmentOf(entry, rules)
    primary = list(dict.fromkeys(entry["primaryMuscles"]))
    secondary = [m for m in dict.fromkeys(entry["secondaryMuscles"]) if m not in primary]
    payload = {
        "key": entry["id"], "name": clip(entry["name"], NAME_LIMIT), "category": entry["category"],
        "level": entry["level"], "measure": measureOf(entry, equipment, rules), "region": regionOf(primary, rules),
        "licence": source["licence"], "primary": primary, "secondary": secondary, "equipment": equipment,
        "steps": [clip(step, STEP_LIMIT) for step in entry["instructions"] if step.strip()][:STEPS_LIMIT],
        # Two upstream pictures with the same bytes have one name; the server wants each once.
        "pictures": list(dict.fromkeys(pictureNames)),
    }
    payload["hash"] = contentHash(payload)
    return payload, unmapped
