"""The change report and the hide guard."""
import report


def payload(key, hash="a" * 40, name=None):
    return {"key": key, "name": name or key.replace("_", " "), "hash": hash}


def held(key, hash="a" * 40, removed=False, name=None):
    return {"key": key, "hash": hash, "removed": removed, "name": name or key}


def test_addedChangedHiddenAndUnchanged():
    sent = [payload("A"), payload("B", hash="b" * 40), payload("C"), payload("E")]
    server = {"A": held("A"), "B": held("B"), "D": held("D", name="Deadlift"), "E": held("E", removed=True)}
    r = report.changeReport(sent, server)
    assert r["added"] == ["C"] and r["changed"] == ["B", "E"] and r["hidden"] == ["D"]
    assert r["unchanged"] == 1 and r["visible"] == 3
    assert r["names"]["D"] == "Deadlift" and r["names"]["C"] == "C"


def test_anEmptyServerAddsEverything():
    r = report.changeReport([payload("A"), payload("B")], {})
    assert r["added"] == ["A", "B"] and r["visible"] == 0
    assert report.guardProblem(r, 0.10) is None


def test_theGuardAllowsATenthAndStopsBeyond():
    server = {f"E{n}": held(f"E{n}") for n in range(10)}
    oneGone = report.changeReport([payload(f"E{n}") for n in range(9)], server)
    assert report.guardProblem(oneGone, 0.10) is None
    twoGone = report.changeReport([payload(f"E{n}") for n in range(8)], server)
    assert "hide 2 of 10" in report.guardProblem(twoGone, 0.10)


def test_hiddenOnesAlreadyHiddenDoNotCount():
    server = {f"E{n}": held(f"E{n}", removed=n < 5) for n in range(10)}
    r = report.changeReport([payload(f"E{n}") for n in range(5, 10)], server)
    assert r["hidden"] == [] and report.guardProblem(r, 0.10) is None


def test_stateForKeepsOneSource():
    state = {"exercises": [dict(held("A"), source="free-exercise-db"), dict(held("B"), source="wger")]}
    assert list(report.stateFor(state, "free-exercise-db")) == ["A"]
    assert report.stateFor(None, "free-exercise-db") == {}


def test_theRenderingNamesWhatChanged():
    r = report.changeReport([payload(f"E{n}") for n in range(45)], {"Old": held("Old", name="Old Row")})
    r.update({"source": "free-exercise-db", "commit": "f" * 40, "exercises": 45, "pictures": 90,
              "unmapped": {"sled": 2}, "compared": "empty"})
    text = report.render(r)
    assert "Added 45: E0, E1, E10" in text and "and 5 more" in text
    assert "Hidden 1: Old Row" in text and "Changed 0" in text
    assert "sled (2)" in text and "compared with an empty catalog" in text
