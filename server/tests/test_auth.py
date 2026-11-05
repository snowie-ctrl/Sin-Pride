"""The account routes against docs/api.md (Gluttony's test_account.py at c1ed705, with Pride's routes and a profile
row instead of a Cravings list)."""
import hashlib
from datetime import datetime

import pytest
from werkzeug.security import generate_password_hash

from conftest import UID

A = "/api/pride"
HASH = generate_password_hash("right-password")


def post(client, path, body):
    return client.post(f"{A}{path}", json=body)


def deviceOf(fingerprint):
    return hashlib.sha256(fingerprint.encode()).hexdigest()[:16]


def test_anUnknownDeviceIsNew(anonClient, useDb):
    useDb(fetchone=[None])
    assert post(anonClient, "/device/identify", {"fingerprint": "f1"}).get_json() == {"status": "new"}


def test_aKnownDeviceGetsANewSession(anonClient, useDb):
    conn = useDb(fetchone=[{"UserID": 7}, {"Username": "ann"}])
    answer = post(anonClient, "/device/identify", {"fingerprint": "f1"}).get_json()
    assert answer["status"] == "ok" and answer["UID"] == 7 and answer["username"] == "ann"
    assert len(answer["token"]) == 64
    insert = conn.cur.statements("INSERT INTO Sessions")[0]
    assert insert[1][:3] == (answer["token"], 7, "f1") and conn.commits == 1


def test_identifyNeedsAFingerprint(anonClient):
    assert post(anonClient, "/device/identify", {}).status_code == 400


def test_signInWithTheRightPassword(anonClient, useDb):
    conn = useDb(fetchone=[{"UserID": 7, "Username": "ann", "PasswordHash": HASH}])
    answer = post(anonClient, "/auth", {"username": "ann", "password": "right-password", "fingerprint": "f1"})
    assert answer.status_code == 200 and answer.get_json()["UID"] == 7
    assert conn.cur.statements("INSERT INTO Devices")[0][1] == ("f1", 7)


def test_aWrongPasswordIs401(anonClient, useDb):
    useDb(fetchone=[{"UserID": 7, "Username": "ann", "PasswordHash": HASH}])
    answer = post(anonClient, "/auth", {"username": "ann", "password": "nope", "fingerprint": "f1"})
    assert answer.status_code == 401 and answer.get_json()["status"] == "invalid_credentials"


def test_anUnknownUsernameIs401LikeAWrongPassword(anonClient, useDb):
    useDb(fetchone=[None])
    answer = post(anonClient, "/auth", {"username": "nobody", "password": "whatever", "fingerprint": "f1"})
    assert answer.status_code == 401 and answer.get_json()["status"] == "invalid_credentials"


def test_signUpSpendsTheKeyInOneTransaction(anonClient, useDb):
    conn = useDb(fetchone=[{"KeyValue": "k1", "Used": 0}, None], lastrowids={"Users": [12]})
    answer = post(anonClient, "/auth", {"username": "bea", "password": "long-enough", "fingerprint": "f2",
                                        "key": "k1"}).get_json()
    assert answer["status"] == "ok" and answer["UID"] == 12 and answer["username"] == "bea"
    executed = [sql for sql, _ in conn.cur.executed]
    assert executed[0] == "SELECT KeyValue, Used FROM LoginKeys WHERE KeyValue = %s FOR UPDATE"
    assert conn.cur.statements("UPDATE LoginKeys SET Used = 1, UsedBy = %s")[0][1] == (12, "k1")
    assert conn.commits == 1


def test_signUpMakesTheProfileInTheSameTransaction(anonClient, useDb):
    conn = useDb(fetchone=[{"KeyValue": "k1", "Used": 0}, None], lastrowids={"Users": [12]})
    post(anonClient, "/auth", {"username": "bea", "password": "long-enough", "fingerprint": "f2", "key": "k1"})
    # The columns' defaults are the spec's: lb, general, 3 days, 5 lb / 10 lb, Monday, the intro pending.
    assert conn.cur.statements("INSERT INTO Profiles") == [("INSERT INTO Profiles (UserID) VALUES (%s)", (12,))]
    assert conn.commits == 1


def test_signingInMakesNoProfile(anonClient, useDb):
    conn = useDb(fetchone=[{"UserID": 7, "Username": "ann", "PasswordHash": HASH}])
    post(anonClient, "/auth", {"username": "ann", "password": "right-password", "fingerprint": "f1"})
    assert not conn.cur.statements("INSERT INTO Profiles")


@pytest.mark.parametrize("found", [None, {"KeyValue": "k1", "Used": 1}])
def test_anUnknownOrUsedKeyIs403(anonClient, useDb, found):
    useDb(fetchone=[found])
    answer = post(anonClient, "/auth", {"username": "bea", "password": "long-enough", "fingerprint": "f2", "key": "k1"})
    assert answer.status_code == 403 and answer.get_json()["status"] == "invalid_key"


def test_aTakenUsernameIs409(anonClient, useDb):
    useDb(fetchone=[{"KeyValue": "k1", "Used": 0}, {"UserID": 3}])
    answer = post(anonClient, "/auth", {"username": "ann", "password": "long-enough", "fingerprint": "f2", "key": "k1"})
    assert answer.status_code == 409 and answer.get_json()["status"] == "username_taken"


@pytest.mark.parametrize("username, password", [("ab", "long-enough"), ("x" * 33, "long-enough"),
                                                ("bea", "short"), ("bea", "y" * 257)])
def test_signUpChecksLengthsBeforeAnyQuery(anonClient, username, password):
    # No database installed: a refusal must come before any query.
    answer = post(anonClient, "/auth", {"username": username, "password": password, "fingerprint": "f2", "key": "k1"})
    assert answer.status_code == 400


def test_missingCredentialsAre400(anonClient):
    assert post(anonClient, "/auth", {"username": "ann", "fingerprint": "f"}).status_code == 400


def test_theSixthSignInAMinuteIsRefused(anonClient, useDb):
    for _ in range(5):
        useDb(fetchone=[None])
        post(anonClient, "/auth", {"username": "ann", "password": "x", "fingerprint": "f"})
    assert post(anonClient, "/auth", {"username": "ann", "password": "x", "fingerprint": "f"}).status_code == 429


def test_signingOutForgetsThisDeviceOnly(client, useDb):
    conn = useDb()
    assert post(client, "/signout", {"fingerprint": "f1"}).get_json() == {"status": "ok"}
    assert conn.cur.statements("DELETE FROM Devices")[0][1] == ("f1", UID)
    assert conn.cur.statements("DELETE FROM Sessions")[0][1] == ("f1", UID)
    assert conn.commits == 1


def test_signingOutNeedsASession(anonClient):
    assert post(anonClient, "/signout", {"fingerprint": "f1"}).status_code == 401


def test_devicesAreNamedNeverByTheirFingerprint(client, useDb):
    useDb(fetchone=[{"DeviceFingerprint": "here"}],
          fetchall=[[{"Fingerprint": "here", "LastExpiry": datetime(2026, 12, 5, 8, 0)},
                     {"Fingerprint": "there", "LastExpiry": None}]])
    rows = client.get(f"{A}/devices").get_json()["data"]
    here = deviceOf("here")
    assert rows[0] == {"id": here, "label": here[:8], "current": True, "lastSignIn": "2026-11-05T08:00:00Z"}
    assert rows[1]["current"] is False and rows[1]["lastSignIn"] is None
    assert "here" not in str(rows) and "there" not in str(rows)


def test_thisDeviceCannotBeRemoved(client, useDb):
    useDb(fetchone=[{"DeviceFingerprint": "here"}])
    assert client.delete(f"{A}/devices/{deviceOf('here')}").status_code == 400


def test_anotherDeviceIsRemovedWithItsSessions(client, useDb):
    conn = useDb(fetchone=[{"DeviceFingerprint": "here"}], fetchall=[[{"Fingerprint": "here"}, {"Fingerprint": "there"}]])
    assert client.delete(f"{A}/devices/{deviceOf('there')}").get_json() == {"status": "ok"}
    assert conn.cur.statements("DELETE FROM Sessions")[0][1] == (UID, "there")
    assert conn.cur.statements("DELETE FROM Devices")[0][1] == (UID, "there")
    assert conn.commits == 1


def test_aDeviceOfNobodyHereIsNothingToRemove(client, useDb):
    conn = useDb(fetchone=[{"DeviceFingerprint": "here"}], fetchall=[[{"Fingerprint": "here"}]])
    assert client.delete(f"{A}/devices/{'0' * 16}").get_json() == {"status": "ok"}
    assert not conn.cur.statements("DELETE")


@pytest.mark.parametrize("wanted", ["short", "G" * 16, "0" * 17])
def test_anIdThatIsNotOneIs404BeforeAnyQuery(client, wanted):
    assert client.delete(f"{A}/devices/{wanted}").status_code == 404


def test_devicesNeedASession(anonClient):
    assert anonClient.get(f"{A}/devices").status_code == 401
    assert anonClient.delete(f"{A}/devices/{'0' * 16}").status_code == 401
