"""A whole run on the fixture slice, with fetching and the admin routes faked."""
import copy
import json

import pytest

import adminApi
import config
import fetch
import main
from conftest import FIXTURES

DATA = json.loads((FIXTURES / "exercises.json").read_text(encoding="utf-8"))


def jpeg(path):
    return b"\xff\xd8\xff\xe0" + path.encode()


class Admin:
    """Stands in for adminApi: records every call and answers like the admin routes."""

    def __init__(self, state=None, have=()):
        self.calls = []
        self.state = state or {"status": "ok", "version": None, "exercises": []}
        self.have = list(have)
        self.failImport = None

    def get(self, path):
        self.calls.append(("GET", path))
        return self.state if path == "/state" else {"status": "ok", "pictures": self.have}

    def putBytes(self, path, data):
        self.calls.append(("PUT", path))
        return {"status": "ok"}

    def post(self, path, payload, timeout=300):
        self.calls.append(("POST", path, payload))
        if self.failImport:
            raise adminApi.AdminError(self.failImport)
        return {"status": "ok", "added": len(payload["exercises"]), "changed": 0, "unchanged": 0, "hidden": 0,
                "version": "c" * 40}


@pytest.fixture
def upstream(monkeypatch):
    data = copy.deepcopy(DATA)
    monkeypatch.setattr(fetch, "fetchExercises", lambda source: data)
    monkeypatch.setattr(fetch, "fetchPictures", lambda source, paths: {p: jpeg(p) for p in set(paths)})
    return data


def install(monkeypatch, admin, configured=True, publish="on"):
    monkeypatch.setattr(adminApi, "configured", lambda: configured)
    monkeypatch.setattr(adminApi, "get", admin.get)
    monkeypatch.setattr(adminApi, "putBytes", admin.putBytes)
    monkeypatch.setattr(adminApi, "post", admin.post)
    monkeypatch.setattr(config, "PUBLISH", publish)


def run():
    lines = []
    code = main.run(out=lines.append)
    return code, "\n".join(lines)


def sent(admin):
    return [call for call in admin.calls if call[0] in ("PUT", "POST")]


def test_aDryRunReportsAndSendsNothing(upstream):
    code, text = run()
    assert code == 0
    assert "Added 11" in text and "compared with an empty catalog" in text and "Dry run" in text
    last = json.loads((config.REPORT_DIR / "last-catalog.json").read_text(encoding="utf-8"))
    assert len(last["exercises"]) == 11 and len(last["pictures"]) == 20
    assert all(path.startswith("free-exercise-db/f00c92c7dcf1216a928a52c3706c7ce8e2f71ed5/exercises/")
               for path in last["pictures"].values())
    assert (config.REPORT_DIR / "last-report.json").is_file()


def test_aDryRunWithTheServerConfiguredComparesWithIt(upstream, monkeypatch):
    admin = Admin(state={"status": "ok", "version": "v", "exercises": [
        {"source": "free-exercise-db", "key": "Barbell_Curl", "name": "Barbell Curl", "hash": "0" * 40, "removed": False}]})
    install(monkeypatch, admin, publish="dry")
    code, text = run()
    assert code == 0 and "Changed 1: Barbell Curl" in text and "Added 10" in text
    assert sent(admin) == []


def test_aShapeProblemStopsBeforeAnythingIsSent(upstream, monkeypatch):
    upstream[0]["primaryMuscles"] = ["wings"]
    admin = Admin()
    install(monkeypatch, admin)
    code, text = run()
    assert code == 2 and "does not look as expected" in text and "wings" in text
    assert sent(admin) == []


def test_aPictureThatIsNotAJpegStops(upstream, monkeypatch):
    monkeypatch.setattr(fetch, "fetchPictures", lambda source, paths: {p: b"<html>" for p in set(paths)})
    admin = Admin()
    install(monkeypatch, admin)
    assert run()[0] == 2 and sent(admin) == []


def test_theGuardStopsPublishing(upstream, monkeypatch):
    others = [{"source": "free-exercise-db", "key": f"Old_{n}", "name": f"Old {n}", "hash": "0" * 40, "removed": False}
              for n in range(20)]
    admin = Admin(state={"status": "ok", "version": "v", "exercises": others})
    install(monkeypatch, admin)
    code, text = run()
    assert code == 3 and "hide 20 of 20" in text
    assert sent(admin) == []


def test_publishingSendsMissingPicturesFirstThenTheBatch(upstream, monkeypatch):
    import normalise
    already = normalise.pictureName(jpeg("Plank/0.jpg"))
    admin = Admin(have=[already])
    install(monkeypatch, admin)
    code, text = run()
    assert code == 0 and "Published: 11 added" in text and "19 pictures sent" in text
    calls = sent(admin)
    assert all(call[0] == "PUT" for call in calls[:-1]) and len(calls) == 20
    assert ("PUT", f"/pictures/{already}") not in calls
    last = calls[-1]
    assert last[0] == "POST" and last[1] == "/import"
    assert last[2]["source"] == "free-exercise-db" and len(last[2]["exercises"]) == 11
    assert json.loads((config.REPORT_DIR / "last-report.json").read_text(encoding="utf-8"))["publish"]["added"] == 11


def test_publishOnWithoutTheAdminRouteSendsNothing(upstream, monkeypatch):
    admin = Admin()
    install(monkeypatch, admin, configured=False)
    code, text = run()
    assert code == 4 and "ADMIN_BASE" in text and sent(admin) == []


def test_aRefusalIsReportedNotRaised(upstream, monkeypatch):
    admin = Admin()
    admin.failImport = "POST /import refused (409): would hide 2 of 10"
    install(monkeypatch, admin)
    code, text = run()
    assert code == 5 and "would hide 2 of 10" in text


def test_aFetchThatFailsSaysSo(monkeypatch):
    def fail(source):
        raise fetch.SourceError("free-exercise-db: dist/exercises.json is not JSON")
    monkeypatch.setattr(fetch, "fetchExercises", fail)
    code, text = run()
    assert code == 6 and "not JSON" in text
