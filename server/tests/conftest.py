"""
Loads Pride's server modules the way Caduceus does, minus the server. They do `from . import DBUtils, prideSession`,
so they are imported as submodules of a stand-in package whose DBUtils refuses to connect: a test that reaches the
database by accident fails loudly instead of touching data. Gluttony's server/tests/conftest.py at c1ed705 is the
model; later tasks add the session, the app routes and the admin routes here.
"""
import importlib.util
import pathlib
import sys
import types

import pytest

SERVER = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from fakes import FakeConn, FakeCursor  # noqa: E402

PACKAGE = "pride_server"


def _refuseConnection(name):
    raise RuntimeError("tests must not open a database connection")


def _load(name):
    if PACKAGE not in sys.modules:
        package = types.ModuleType(PACKAGE)
        package.__path__ = [str(SERVER)]
        dbutils = types.ModuleType(f"{PACKAGE}.DBUtils")
        dbutils.initConnection = _refuseConnection
        package.DBUtils = dbutils
        sys.modules[PACKAGE] = package
        sys.modules[f"{PACKAGE}.DBUtils"] = dbutils
    spec = importlib.util.spec_from_file_location(f"{PACKAGE}.{name}", SERVER / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def loadModule(name):
    """Any server module, loaded inside the stand-in package."""
    return sys.modules.get(f"{PACKAGE}.{name}") or _load(name)


loadModule("prideCatalog")


@pytest.fixture
def catalog():
    return loadModule("prideCatalog")


@pytest.fixture(autouse=True)
def noDatabase(monkeypatch):
    monkeypatch.setattr(sys.modules[f"{PACKAGE}.DBUtils"], "initConnection", _refuseConnection)


@pytest.fixture
def useDb(monkeypatch):
    """Installs a FakeConn answering the queued rows; returns it."""
    def install(fetchone=(), fetchall=(), lastrowids=None, failOn=None, rowcounts=()):
        conn = FakeConn(FakeCursor(fetchone, fetchall, lastrowids, failOn, rowcounts))

        def connect(name):
            assert name == "pride", f"connected to {name!r}"
            return conn

        monkeypatch.setattr(sys.modules[f"{PACKAGE}.DBUtils"], "initConnection", connect)
        return conn
    return install
