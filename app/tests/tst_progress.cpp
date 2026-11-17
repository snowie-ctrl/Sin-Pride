// The Progress service against a faked server: records, one exercise's series, taking and dismissing a suggestion,
// a suggestion already settled.
#include <QSignalSpy>
#include <QTest>

#include "FakeServer.h"
#include "api/Api.h"
#include "services/Progress.h"

static QString p(const char *route) { return QStringLiteral("/api/pride") + QLatin1String(route); }

class TestProgress : public QObject
{
    Q_OBJECT

    std::unique_ptr<FakeServer> server;
    std::unique_ptr<Api> api;
    std::unique_ptr<Progress> progress;

private slots:
    void init()
    {
        server = std::make_unique<FakeServer>();
        server->responses[p("/records")] = R"({"status":"ok","data":[{"exerciseId":1,"measure":"weight_reps","lastOn":"2026-11-16","records":[]}]})";
        server->responses[p("/progress/1")] = R"({"status":"ok","data":{"exerciseId":1,"measure":"weight_reps","units":"lb","points":[{"workoutId":70}],"records":[],"recent":[]}})";
        server->responses[p("/suggestions/9/accept")] = R"({"status":"ok","data":{"suggestion":{"id":9,"state":"accepted"},"programId":5}})";
        server->responses[p("/suggestions/9/dismiss")] = R"({"status":"ok","data":{"suggestion":{"id":9,"state":"dismissed"}}})";
        api = std::make_unique<Api>();
        api->setBases(QString(), QStringLiteral("http://127.0.0.1:%1/api/pride").arg(server->serverPort()));
        api->setSessionToken("tok");
        progress = std::make_unique<Progress>(*api);
    }

    void cleanup() { progress.reset(); api.reset(); server.reset(); }

    void recordsAndASeriesLoad()
    {
        progress->loadRecords();
        QTRY_VERIFY(progress->recordsLoaded());
        QCOMPARE(progress->records().size(), 1);
        progress->loadSeries(1);
        QCOMPARE(progress->seriesId(), 1);
        QTRY_COMPARE(progress->series().value("points").toList().size(), 1);
    }

    void onlyTheLatestSeriesAnswers()
    {
        server->responses[p("/progress/2")] = R"({"status":"ok","data":{"exerciseId":2,"points":[]}})";
        server->holdNext[p("/progress/1")] = 1;
        progress->loadSeries(1);
        progress->loadSeries(2);
        QTRY_COMPARE(progress->series().value("exerciseId").toInt(), 2);
        server->releaseHeld();
        QTest::qWait(150);
        QCOMPARE(progress->series().value("exerciseId").toInt(), 2);
    }

    void takingAndDismissingSayWhatWasDecided()
    {
        QSignalSpy decided(progress.get(), &Progress::decided);
        progress->accept(9);
        QTRY_COMPARE(decided.size(), 1);
        QCOMPARE(decided.first().value(0).toInt(), 9);
        QCOMPARE(decided.first().value(1).toString(), QStringLiteral("accepted"));
        QCOMPARE(decided.first().value(2).toInt(), 5);
        progress->dismiss(9);
        QTRY_COMPARE(decided.size(), 2);
        QCOMPARE(decided.last().value(1).toString(), QStringLiteral("dismissed"));
    }

    void aSettledSuggestionIsClosed()
    {
        server->statuses[p("/suggestions/9/accept")] = 409;
        server->responses[p("/suggestions/9/accept")] = R"({"status":"closed","message":"that suggestion is no longer open"})";
        QSignalSpy failed(progress.get(), &Progress::failed);
        progress->accept(9);
        QTRY_COMPARE(failed.size(), 1);
        QCOMPARE(failed.first().value(0).toString(), QStringLiteral("accept"));
        QCOMPARE(failed.first().value(1).toString(), QStringLiteral("closed"));
    }

    void resetForgetsEverything()
    {
        progress->loadRecords();
        QTRY_VERIFY(progress->recordsLoaded());
        progress->reset();
        QVERIFY(progress->records().isEmpty());
        QVERIFY(!progress->recordsLoaded());
        QCOMPARE(progress->seriesId(), 0);
    }
};

QTEST_MAIN(TestProgress)
#include "tst_progress.moc"
