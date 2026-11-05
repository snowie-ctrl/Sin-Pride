"""The admin routes' client: the token on every call, retries for a server that failed, none for a refusal."""
import pytest

import adminApi
import config


class Answer:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body

    def json(self):
        if self._body is None:
            raise ValueError("no JSON")
        return self._body


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_BASE", "http://admin.example.test:5000")
    monkeypatch.setattr(config, "ADMIN_TOKEN", "tok")


def test_unconfiguredSendsNothing():
    assert not adminApi.configured()
    with pytest.raises(adminApi.AdminError, match="ADMIN_BASE"):
        adminApi.get("/state")


def test_everyCallCarriesTheToken(configured, monkeypatch):
    seen = []
    monkeypatch.setattr(adminApi._http, "request",
                        lambda method, url, **kw: seen.append((method, url, kw)) or Answer(200, {"status": "ok"}))
    adminApi.get("/state")
    adminApi.putBytes("/pictures/x.jpg", b"\xff\xd8\xff")
    assert seen[0][1] == "http://admin.example.test:5000/api/pride-admin/state"
    assert all(kw["headers"]["X-Admin-Token"] == "tok" for _, _, kw in seen)
    assert seen[1][0] == "PUT" and seen[1][2]["data"] == b"\xff\xd8\xff"
    assert seen[1][2]["headers"]["Content-Type"] == "image/jpeg"


def test_aFailingServerIsTriedThreeTimes(configured, monkeypatch):
    answers = [Answer(502, None), Answer(503, {"status": "error"}), Answer(200, {"status": "ok", "pictures": []})]
    monkeypatch.setattr(adminApi._http, "request", lambda *a, **kw: answers.pop(0))
    assert adminApi.get("/pictures") == {"status": "ok", "pictures": []}


def test_aRefusalIsFinalAtOnceAndNamesNoAddress(configured, monkeypatch):
    calls = []
    monkeypatch.setattr(adminApi._http, "request",
                        lambda *a, **kw: calls.append(1) or Answer(409, {"status": "error", "message": "would hide 2 of 10"}))
    with pytest.raises(adminApi.AdminError) as raised:
        adminApi.post("/import", {})
    assert len(calls) == 1 and "would hide 2 of 10" in str(raised.value)
    assert "admin.example.test" not in str(raised.value)
