"""prideSession's hooks, on the real ping and on a probe blueprint that installs them the way every app blueprint
does (Gluttony's test_session at c1ed705 checked the same on its read routes)."""
import flask

from conftest import REAL_SESSION_UID, SESSION


def probeClient(sessions, view, signedIn=True, tunnel=False):
    blueprint = flask.Blueprint("probe", __name__)
    sessions.install(blueprint)
    blueprint.add_url_rule("/probe", "probe", view)
    app = flask.Flask("probe-tests")
    app.register_blueprint(blueprint, url_prefix="/api/pride")
    client = app.test_client()
    if signedIn:
        client.environ_base["HTTP_X_SESSION_TOKEN"] = SESSION
    if tunnel:
        client.environ_base["HTTP_CF_CONNECTING_IP"] = "203.0.113.9"
    return client


def test_pingNeedsNoSessionAndNoDatabase(anonClient):
    # isolated() refuses every connection, so this also proves ping opens none.
    assert anonClient.get("/api/pride/ping").get_json() == {"status": "ok"}


def test_aRouteNeedsASession(sessions):
    anon = probeClient(sessions, lambda: {"status": "ok"}, signedIn=False)
    answer = anon.get("/api/pride/probe")
    assert answer.status_code == 401
    assert answer.get_json() == {"status": "error", "message": "not signed in"}
    assert probeClient(sessions, lambda: {"status": "ok"}).get("/api/pride/probe").status_code == 200


def test_aSessionIsLookedUpByTokenAndExpiry(useDb):
    conn = useDb(fetchone=[{"UserID": 7}])
    assert REAL_SESSION_UID("abc") == 7
    sql, params = conn.cur.executed[0]
    assert sql == "SELECT UserID FROM Sessions WHERE Token = %s AND ExpiresAt > NOW()" and params == ("abc",)
    assert conn.closed


def test_aMissingTokenNeedsNoDatabase():
    assert REAL_SESSION_UID("") is None and REAL_SESSION_UID(None) is None


def test_theRateLimiterRefusesPastTheLimitUntilTheWindowMoves(sessions):
    clock = [0.0]
    limiter = sessions.RateLimiter(clock=lambda: clock[0])
    assert all(limiter.allow("k", 3, 60) for _ in range(3))
    assert not limiter.allow("k", 3, 60)
    clock[0] = 61.0
    assert limiter.allow("k", 3, 60)


def test_ipv6CallersAreCountedByTheirSlash64(sessions):
    assert sessions.limiterKey("2001:db8::1") == sessions.limiterKey("2001:db8::ffff") == "2001:db8::/64"
    assert sessions.limiterKey("203.0.113.9") == "203.0.113.9"


def boom():
    raise RuntimeError("the database fell over")


def test_aServerErrorThroughTheTunnelSaysNothingInside(sessions):
    answer = probeClient(sessions, boom, tunnel=True).get("/api/pride/probe")
    assert answer.status_code == 500
    assert answer.get_json() == {"status": "error", "message": "server error"}


def test_aServerErrorAtHomeKeepsItsDetail(sessions):
    answer = probeClient(sessions, boom).get("/api/pride/probe")
    assert answer.status_code == 500 and "RuntimeError" in answer.get_json()["message"]


def test_theDatabaseIsPrides(sessions, useDb):
    conn = useDb(fetchone=[None])
    with sessions.database() as (_, cur):
        cur.execute("SELECT 1")
        cur.fetchone()
    assert conn.rollbacks == 1 and conn.closed
