"""
Keeps every test away from the outside world and the owner's files: downloads are refused, the admin routes are not
configured, publishing is dry, and every folder the importer writes points into the test's own temporary folder.
"""
from pathlib import Path

import pytest

import adminApi
import config
import net

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SOURCE = {"name": "free-exercise-db", "repo": "yuhonas/free-exercise-db",
          "commit": "f00c92c7dcf1216a928a52c3706c7ce8e2f71ed5", "licence": "Unlicense",
          "data": "dist/exercises.json", "pictures": "exercises"}


@pytest.fixture(autouse=True)
def noNetwork(monkeypatch):
    def refuse(*args, **kwargs):
        raise RuntimeError("tests must not touch the network")
    monkeypatch.setattr(net._session, "get", refuse)
    monkeypatch.setattr(net._session, "request", refuse)
    monkeypatch.setattr(adminApi._http, "request", refuse)
    monkeypatch.setattr(adminApi.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(net.time, "sleep", lambda seconds: None)


@pytest.fixture(autouse=True)
def isolatedFiles(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(config, "REPORT_DIR", tmp_path / "reports")
    monkeypatch.setattr(config, "PUBLISH", "dry")
    monkeypatch.setattr(config, "ADMIN_BASE", "")
    monkeypatch.setattr(config, "ADMIN_TOKEN", "")


@pytest.fixture
def source():
    return dict(SOURCE)
