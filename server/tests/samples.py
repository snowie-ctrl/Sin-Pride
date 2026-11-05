"""Valid import payloads, as the importer sends them, for tests to change one thing at a time."""
import hashlib

JPEG = b"\xff\xd8\xff\xe0" + b"a small stand-in picture"
PICTURE = hashlib.sha1(JPEG).hexdigest()[:20] + ".jpg"


def exercise(key="Barbell_Curl", **changes):
    payload = {"key": key, "name": "Barbell Curl", "category": "strength", "level": "beginner",
               "measure": "weight_reps", "region": "upper", "licence": "Unlicense",
               "primary": ["biceps"], "secondary": ["forearms"], "equipment": ["barbell"],
               "steps": ["Stand up straight.", "Curl the bar."], "pictures": [PICTURE], "hash": "a" * 40}
    payload.update(changes)
    return payload


def batch(*exercises, source="free-exercise-db"):
    return {"source": source, "exercises": list(exercises) or [exercise()]}
