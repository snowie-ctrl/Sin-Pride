"""Checks that the stub serves what docs/api.md promises, so the app is built against the real shapes."""
import json
from pathlib import Path

import pytest

import stub_server as stub

API = stub.API
AUTH = {"X-Session-Token": stub.TOKEN}
SHAPE = {"id", "key", "source", "licence", "name", "category", "level", "measure", "region", "removed", "primary",
         "secondary", "equipment", "steps", "pictures"}


@pytest.fixture
def client(monkeypatch):
    for name in ("STUB_NEW_DEVICE", "STUB_CATALOG_DOWN", "STUB_PICTURES_FAIL", "STUB_SLOW"):
        monkeypatch.delenv(name, raising=False)
    # The fixture, even once a real snapshot sits in snapshot/, so these checks never depend on it.
    monkeypatch.setenv("STUB_SNAPSHOT", str(stub.HERE / "fixture"))
    stub.reset()
    stub.app.config["TESTING"] = True
    return stub.app.test_client()


def test_routesNeedTheTokenButPingDoesNot(client):
    assert client.get(API + "/catalog").status_code == 401
    assert client.get(API + "/ping").get_json() == {"status": "ok"}


def test_aKnownDeviceSignsInAndANewOneDoesNot(client, monkeypatch):
    answer = client.post(API + "/device/identify", json={"fingerprint": "x"}).get_json()
    assert answer == {"status": "ok", "UID": 7, "username": "stub", "token": "stub"}
    monkeypatch.setenv("STUB_NEW_DEVICE", "1")
    stub.reset()
    assert client.post(API + "/device/identify", json={"fingerprint": "x"}).get_json() == {"status": "new"}


def test_signInSignUpAndTheirRefusals(client):
    assert client.post(API + "/auth", json={"username": "stub", "password": "nope", "fingerprint": "x"}).status_code == 401
    made = client.post(API + "/auth", json={"username": "newbie", "password": "long-enough", "fingerprint": "x",
                                            "key": "stub-key"}).get_json()
    assert made["status"] == "ok" and made["UID"] >= 100
    wrongKey = client.post(API + "/auth", json={"username": "other", "password": "long-enough", "fingerprint": "x",
                                                "key": "nope"})
    assert wrongKey.status_code == 403 and wrongKey.get_json()["status"] == "invalid_key"
    taken = client.post(API + "/auth", json={"username": "taken", "password": "long-enough", "fingerprint": "x",
                                             "key": "stub-key"})
    assert taken.status_code == 409 and taken.get_json()["status"] == "username_taken"
    short = client.post(API + "/auth", json={"username": "ab", "password": "long-enough", "fingerprint": "x",
                                             "key": "stub-key"})
    assert short.status_code == 400


def test_signingOutForgetsTheDevice(client):
    assert client.post(API + "/signout", json={"fingerprint": "x"}, headers=AUTH).get_json() == {"status": "ok"}
    assert client.post(API + "/device/identify", json={"fingerprint": "x"}).get_json() == {"status": "new"}
    assert client.get(API + "/catalog", headers=AUTH).status_code == 401


def test_devicesAreListedAndAnotherIsRemoved(client):
    rows = client.get(API + "/devices", headers=AUTH).get_json()["data"]
    assert [r["current"] for r in rows] == [True, False]
    assert client.delete(API + f"/devices/{stub.THIS_DEVICE}", headers=AUTH).status_code == 400
    assert client.delete(API + f"/devices/{stub.OTHER_DEVICE}", headers=AUTH).get_json() == {"status": "ok"}
    assert len(client.get(API + "/devices", headers=AUTH).get_json()["data"]) == 1
    assert client.delete(API + "/devices/nope", headers=AUTH).status_code == 404


def test_theCatalogIsWholeOrUnchanged(client):
    data = client.get(API + "/catalog", headers=AUTH).get_json()["data"]
    assert data["version"] == "fixture-1" and len(data["exercises"]) == 11
    assert all(set(e) == SHAPE for e in data["exercises"])
    names = [e["name"] for e in data["exercises"]]
    assert names == sorted(names, key=str.casefold) and [e["id"] for e in data["exercises"]] == list(range(1, 12))
    same = client.get(API + "/catalog?version=fixture-1", headers=AUTH).get_json()["data"]
    assert same == {"version": "fixture-1", "unchanged": True}


def test_everyPictureTheCatalogNamesIsServed(client):
    data = client.get(API + "/catalog", headers=AUTH).get_json()["data"]
    names = [p for e in data["exercises"] for p in e["pictures"]]
    assert len(names) == 20
    for name in names:
        answer = client.get(API + f"/pictures/{name}", headers=AUTH)
        assert answer.status_code == 200 and answer.data[:3] == b"\xff\xd8\xff", name
    halo = next(e for e in data["exercises"] if e["key"] == "Kettlebell_Halo")
    assert halo["pictures"] == []


def test_aBadOrMissingPictureIs404(client):
    assert client.get(API + "/pictures/..%2Fcatalog.json", headers=AUTH).status_code == 404
    assert client.get(API + f"/pictures/{'0' * 20}.jpg", headers=AUTH).status_code == 404


def test_theSwitchesBreakWhatTheySay(client, monkeypatch):
    monkeypatch.setenv("STUB_CATALOG_DOWN", "1")
    assert client.get(API + "/catalog", headers=AUTH).status_code == 503
    monkeypatch.setenv("STUB_PICTURES_FAIL", "1")
    name = json.loads((stub.HERE / "fixture" / "catalog.json").read_text(encoding="utf-8"))["exercises"][0]["pictures"][0]
    assert client.get(API + f"/pictures/{name}", headers=AUTH).status_code == 404
