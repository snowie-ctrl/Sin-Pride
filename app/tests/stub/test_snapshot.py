"""snapshot.py turns the importer's last run into a catalog the stub serves."""
import json

import snapshot


def test_theImportersLastRunBecomesTheStubsCatalog(tmp_path):
    reports, cache, out = tmp_path / "reports", tmp_path / "cache", tmp_path / "snapshot"
    reports.mkdir()
    picture = cache / "free-exercise-db" / "c0ffee" / "exercises" / "Plank" / "0.jpg"
    picture.parent.mkdir(parents=True)
    picture.write_bytes(b"\xff\xd8\xff plank")
    exercises = [
        {"key": "Plank", "name": "Plank", "hash": "a" * 40, "pictures": ["0123456789abcdef0123.jpg"]},
        {"key": "Air_Bike", "name": "air bike", "hash": "b" * 40, "pictures": []},
    ]
    (reports / "last-catalog.json").write_text(json.dumps({
        "source": "free-exercise-db", "commit": "c0ffee", "exercises": exercises,
        "pictures": {"0123456789abcdef0123.jpg": "free-exercise-db/c0ffee/exercises/Plank/0.jpg"}}))
    (out / "stale").mkdir(parents=True)

    assert snapshot.build(reports, cache, out) == (2, 1)
    catalog = json.loads((out / "catalog.json").read_text(encoding="utf-8"))
    assert [(e["id"], e["key"]) for e in catalog["exercises"]] == [(1, "Air_Bike"), (2, "Plank")]
    assert all("hash" not in e and e["removed"] is False and e["source"] == "free-exercise-db"
               for e in catalog["exercises"])
    assert len(catalog["version"]) == 40
    assert (out / "pictures" / "0123456789abcdef0123.jpg").read_bytes() == b"\xff\xd8\xff plank"
    assert not (out / "stale").exists()
