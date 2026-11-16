// The Profile service against a faked server: loading, saving only what changed, refusals, and sign-out.
#include <QJsonDocument>
#include <QJsonObject>
#include <QSignalSpy>
#include <QTest>

#include "FakeServer.h"
#include "api/Api.h"
#include "services/Profile.h"

static const QByteArray pending = R"({"status":"ok","data":{"units":"lb","goal":"general","daysPerWeek":3,
 "upperIncrement":5.0,"lowerIncrement":10.0,"weekStart":"mon","introState":"pending","equipment":[]}})";
static const QByteArray kg = R"({"status":"ok","data":{"units":"kg","goal":"general","daysPerWeek":3,
 "upperIncrement":2.5,"lowerIncrement":5.0,"weekStart":"mon","introState":"done","equipment":["dumbbell"]}})";

static QString path() { return QStringLiteral("/api/pride/profile"); }
static QString baseOf(const FakeServer &s) { return QStringLiteral("http://127.0.0.1:%1/api/pride").arg(s.serverPort()); }

class TestProfile : public QObject
{
    Q_OBJECT

private slots:
    void aLoadFillsTheProfileAndAnnouncesAPendingIntro()
    {
        FakeServer server;
        server.responses[path()] = pending;
        Api api; api.setBases(QString(), baseOf(server)); api.setSessionToken("tok");
        Profile profile(api);
        QSignalSpy pendingSpy(&profile, &Profile::introPending);
        QVERIFY(!profile.loaded());
        profile.load();
        QTRY_VERIFY(profile.loaded());
        QCOMPARE(profile.profile().value("daysPerWeek").toInt(), 3);
        QCOMPARE(pendingSpy.size(), 1);
    }

    void aSaveSendsOnlyTheChangesAndTakesTheAnswer()
    {
        FakeServer server;
        server.responses[path()] = kg;
        Api api; api.setBases(QString(), baseOf(server)); api.setSessionToken("tok");
        Profile profile(api);
        QSignalSpy saved(&profile, &Profile::saved);
        profile.save({{"units", "kg"}});
        QTRY_COMPARE(saved.size(), 1);
        QCOMPARE(QJsonDocument::fromJson(server.bodies.last()).object(), QJsonObject({{"units", "kg"}}));
        QVERIFY(server.heads.last().startsWith("PUT "));
        QCOMPARE(profile.profile().value("upperIncrement").toDouble(), 2.5);
    }

    void aRefusalNamesTheField()
    {
        FakeServer server;
        server.statuses[path()] = 400;
        server.responses[path()] = R"({"status":"error","field":"daysPerWeek","message":"no"})";
        Api api; api.setBases(QString(), baseOf(server)); api.setSessionToken("tok");
        Profile profile(api);
        QSignalSpy failed(&profile, &Profile::failed);
        profile.save({{"daysPerWeek", 9}});
        QTRY_COMPARE(failed.size(), 1);
        QCOMPARE(failed.first().at(0).toString(), QStringLiteral("invalid"));
        QCOMPARE(failed.first().at(1).toString(), QStringLiteral("daysPerWeek"));
    }

    void noServerIsNetwork()
    {
        Api api; api.setBases(QString(), QStringLiteral("http://127.0.0.1:1/api/pride")); api.setSessionToken("tok");
        Profile profile(api);
        QSignalSpy failed(&profile, &Profile::failed);
        profile.save({{"goal", "muscle"}});
        QTRY_COMPARE_WITH_TIMEOUT(failed.size(), 1, 10000);
        QCOMPARE(failed.first().at(0).toString(), QStringLiteral("network"));
    }

    void aResetForgetsAndDropsALateAnswer()
    {
        FakeServer server;
        server.responses[path()] = pending;
        server.holdNext[path()] = 1;
        Api api; api.setBases(QString(), baseOf(server)); api.setSessionToken("tok");
        Profile profile(api);
        profile.load();
        QTRY_COMPARE(server.requests.size(), 1);
        profile.reset();
        server.releaseHeld();
        QTest::qWait(200);
        QVERIFY(!profile.loaded());
        QVERIFY(profile.profile().isEmpty());
    }
};

QTEST_MAIN(TestProfile)
#include "tst_profile.moc"
