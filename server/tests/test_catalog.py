"""GET /catalog and GET /pictures/<name> against docs/api.md."""
from datetime import datetime

import pytest

A = "/api/pride"
VERSION = "a" * 40
CURL = {"ExerciseID": 12, "Source": "free-exercise-db", "SourceKey": "Barbell_Curl", "Licence": "Unlicense",
        "Name": "Barbell Curl", "Category": "strength", "Level": "beginner", "Measure": "weight_reps",
        "Region": "upper", "RemovedAt": None}
PLANK = {"ExerciseID": 13, "Source": "free-exercise-db", "SourceKey": "Plank", "Licence": "Unlicense",
         "Name": "Plank", "Category": "strength", "Level": "beginner", "Measure": "time", "Region": "full",
         "RemovedAt": datetime(2026, 11, 1, 3, 0)}
CHILDREN = [
    [{"ExerciseID": 12, "Muscle": "biceps", "Role": "primary"}, {"ExerciseID": 12, "Muscle": "forearms", "Role": "secondary"},
     {"ExerciseID": 13, "Muscle": "abdominals", "Role": "primary"}],
    [{"ExerciseID": 12, "Equipment": "barbell"}, {"ExerciseID": 13, "Equipment": "bodyweight"}],
    [{"ExerciseID": 12, "Text": "Stand up straight."}, {"ExerciseID": 12, "Text": "Curl the bar."}],
    [{"ExerciseID": 12, "Path": "0123456789abcdef0123.jpg"}, {"ExerciseID": 12, "Path": "1123456789abcdef0123.jpg"}],
]


def test_everyRouteNeedsASession(anonClient):
    for path in ("/catalog", "/pictures/0123456789abcdef0123.jpg", "/devices"):
        assert anonClient.get(f"{A}{path}").status_code == 401, path


def test_theWholeCatalogComesWithItsChildren(client, useDb):
    conn = useDb(fetchone=[{"Version": VERSION}], fetchall=[[CURL, PLANK], *CHILDREN])
    data = client.get(f"{A}/catalog").get_json()["data"]
    assert data["version"] == VERSION
    curl, plank = data["exercises"]
    assert curl == {"id": 12, "key": "Barbell_Curl", "source": "free-exercise-db", "licence": "Unlicense",
                    "name": "Barbell Curl", "category": "strength", "level": "beginner", "measure": "weight_reps",
                    "region": "upper", "removed": False, "primary": ["biceps"], "secondary": ["forearms"],
                    "equipment": ["barbell"], "steps": ["Stand up straight.", "Curl the bar."],
                    "pictures": ["0123456789abcdef0123.jpg", "1123456789abcdef0123.jpg"]}
    # A hidden exercise is listed, marked, so history can still name it.
    assert plank["removed"] is True and plank["steps"] == [] and plank["pictures"] == []
    # Only the catalog: a person's own exercises (an owner set) are never in it.
    sqls = [sql for sql, _ in conn.cur.executed]
    assert all("OwnerUserID IS NULL" in sql for sql in sqls[1:])


def test_theSameVersionIsUnchangedAndReadsNothingMore(client, useDb):
    conn = useDb(fetchone=[{"Version": VERSION}])
    data = client.get(f"{A}/catalog?version={VERSION}").get_json()["data"]
    assert data == {"version": VERSION, "unchanged": True}
    assert len(conn.cur.executed) == 1


def test_anotherVersionGetsTheWholeCatalog(client, useDb):
    useDb(fetchone=[{"Version": VERSION}], fetchall=[[CURL], *CHILDREN])
    data = client.get(f"{A}/catalog?version={'b' * 40}").get_json()["data"]
    assert data["version"] == VERSION and len(data["exercises"]) == 1


def test_nothingImportedYetIsAnEmptyCatalog(client, useDb):
    useDb(fetchone=[None], fetchall=[[], [], [], [], []])
    data = client.get(f"{A}/catalog?version=").get_json()["data"]
    assert data == {"version": None, "exercises": []}


def test_childrenAreReadInTheirOrder(catalog):
    sqls = dict(catalog.CHILD_QUERIES)
    assert sqls["steps"].endswith("ORDER BY c.ExerciseID, c.StepNo")
    assert sqls["pictures"].endswith("ORDER BY c.ExerciseID, c.Idx")
    assert catalog.EXERCISES_QUERY.endswith("ORDER BY Name, ExerciseID")


def test_aPictureIsServedFromTheMediaFolder(client, media):
    (media / "0123456789abcdef0123.jpg").write_bytes(b"\xff\xd8\xff\xe0picture")
    answer = client.get(f"{A}/pictures/0123456789abcdef0123.jpg")
    assert answer.status_code == 200 and answer.data == b"\xff\xd8\xff\xe0picture"
    assert answer.mimetype == "image/jpeg"
    assert answer.headers["Cache-Control"] == "private, max-age=86400"


@pytest.mark.parametrize("name", ["0123456789abcdef0123.png", "..%2Fschema.sql", "0123456789ABCDEF0123.jpg", "x.jpg"])
def test_aNameThatIsNotOneIs404(client, name):
    assert client.get(f"{A}/pictures/{name}").status_code == 404


def test_aMissingPictureIs404(client):
    # isolated() refuses the database, so this also proves pictures need none.
    assert client.get(f"{A}/pictures/0123456789abcdef0123.jpg").status_code == 404
