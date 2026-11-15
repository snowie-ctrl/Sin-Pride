"""Fetching at a pinned commit, through the cache."""
import json

import pytest

import config
import fetch
import net


class Answer:
    def __init__(self, status, content=b""):
        self.status_code = status
        self.content = content


def test_theRealSourcesFileIsPinned():
    sources = fetch.loadSources()
    assert [s["name"] for s in sources] == ["free-exercise-db"]
    assert sources[0]["commit"] == "f00c92c7dcf1216a928a52c3706c7ce8e2f71ed5"
    assert sources[0]["licence"] == "Unlicense"


@pytest.mark.parametrize("commit", ["main", "f00c92c", "F00C92C7DCF1216A928A52C3706C7CE8E2F71ED5"])
def test_aSourceNotPinnedToAFullCommitIsRefused(tmp_path, source, commit):
    path = tmp_path / "sources.json"
    path.write_text(json.dumps([dict(source, commit=commit)]))
    with pytest.raises(fetch.SourceError):
        fetch.loadSources(path)


def test_aSourceMissingAFieldIsRefused(tmp_path, source):
    path = tmp_path / "sources.json"
    path.write_text(json.dumps([{k: v for k, v in source.items() if k != "licence"}]))
    with pytest.raises(fetch.SourceError, match="licence"):
        fetch.loadSources(path)


def test_theUrlNamesTheCommit(source):
    assert fetch.rawUrl(source, "dist/exercises.json") == (
        "https://raw.githubusercontent.com/yuhonas/free-exercise-db/"
        "f00c92c7dcf1216a928a52c3706c7ce8e2f71ed5/dist/exercises.json")


def test_aCachedFileIsReadWithoutTheNetwork(source):
    target = fetch.cachePath(source, "dist/exercises.json")
    target.parent.mkdir(parents=True)
    target.write_bytes(b"[]")
    assert fetch.cached(source, "dist/exercises.json") == b"[]"
    assert str(target).startswith(str(config.CACHE_DIR))


def test_aFetchedFileIsKeptSoTheNextRunDownloadsNothing(source, monkeypatch):
    asked = []
    monkeypatch.setattr(net, "fetchBytes", lambda url, timeout=60: asked.append(url) or b"[1]")
    assert fetch.cached(source, "dist/exercises.json") == b"[1]"
    assert fetch.cached(source, "dist/exercises.json") == b"[1]"
    assert len(asked) == 1 and "/f00c92c7dcf1216a928a52c3706c7ce8e2f71ed5/" in asked[0]
    assert not list(config.CACHE_DIR.rglob("*.part"))


def test_picturesComeFromThePictureFolderOnceEach(source, monkeypatch):
    asked = []
    monkeypatch.setattr(net, "fetchBytes", lambda url, timeout=60: asked.append(url) or url.encode())
    got = fetch.fetchPictures(source, ["A/0.jpg", "A/0.jpg", "B/1.jpg"])
    assert sorted(got) == ["A/0.jpg", "B/1.jpg"]
    assert sorted(asked) == [fetch.rawUrl(source, "exercises/A/0.jpg"), fetch.rawUrl(source, "exercises/B/1.jpg")]


def test_dataThatIsNotJsonIsASourceError(source, monkeypatch):
    monkeypatch.setattr(net, "fetchBytes", lambda url, timeout=60: b"<html>rate limited</html>")
    with pytest.raises(fetch.SourceError, match="not JSON"):
        fetch.fetchExercises(source)


def test_aServerErrorIsTriedThreeTimes(monkeypatch):
    answers = [Answer(503), Answer(502), Answer(200, b"ok")]
    monkeypatch.setattr(net._session, "get", lambda url, timeout: answers.pop(0))
    assert net.fetchBytes("https://raw.githubusercontent.com/x") == b"ok"


def test_aMissingFileIsNotTriedAgain(monkeypatch):
    calls = []
    monkeypatch.setattr(net._session, "get", lambda url, timeout: calls.append(url) or Answer(404))
    with pytest.raises(net.FetchError, match="404"):
        net.fetchBytes("https://raw.githubusercontent.com/x")
    assert len(calls) == 1
