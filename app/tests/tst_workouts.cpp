// The Workouts service against a faked server: the routines menu, a routine's draft, a new workout and an edit, the
// result card, a resend after a refusal, deleting, the history, and refusals.
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QSignalSpy>
#include <QTest>
#include <QUrlQuery>

#include "FakeServer.h"
#include "api/Api.h"
#include "services/Workouts.h"

static QString p(const char *route) { return QStringLiteral("/api/pride") + QLatin1String(route); }

static const QByteArray result = R"({"status":"ok","data":{"workout":{"id":70,"performedOn":"2026-11-17","exercises":[]},
 "crowns":[{"exerciseId":1,"kind":"heaviest","weight":140,"weightUnit":"lb","reps":8}],
 "suggestions":[],"nextUp":{"routineId":51,"title":"Lower"}}})";

class TestWorkouts : public QObject
{
    Q_OBJECT

    std::unique_ptr<FakeServer> server;
    std::unique_ptr<Api> api;
    std::unique_ptr<Workouts> workouts;

    QJsonObject lastBody(const char *method, const QString &route) const
    {
        for (int i = server->requests.size() - 1; i >= 0; --i)
            if (server->methods[i] == method && server->requests[i].path() == route)
                return QJsonDocument::fromJson(server->bodies[i]).object();
        return {};
    }

    int count(const char *method, const QString &route) const
    {
        int n = 0;
        for (int i = 0; i < server->requests.size(); ++i)
            n += server->methods[i] == method && server->requests[i].path() == route;
        return n;
    }

    static QVariantMap body(const QString &clientId)
    {
        return QVariantMap{{"clientId", clientId}, {"performedOn", "2026-11-17"}, {"routineId", 50},
                           {"note", QVariant()}, {"exercises", QVariantList()}};
    }

private slots:
    void init()
    {
        server = std::make_unique<FakeServer>();
        server->responses[p("/routines")] = R"({"status":"ok","data":[{"id":50,"title":"Upper","programId":5,"programTitle":"Upper/Lower","active":true}]})";
        server->responses[p("/workouts/draft")] = R"({"status":"ok","data":{"routineId":50,"title":"Upper","programId":5,"items":[{"id":500}]}})";
        server->responses[p("/workouts")] = R"({"status":"ok","data":[{"id":70,"performedOn":"2026-11-17"}]})";
        server->methodResponses["POST " + p("/workouts")] = result;
        server->responses[p("/workouts/70")] = R"({"status":"ok","data":{"id":70,"performedOn":"2026-11-16","routineId":50,"exercises":[]}})";
        server->methodResponses["PUT " + p("/workouts/70")] = result;
        server->methodResponses["DELETE " + p("/workouts/70")] = R"({"status":"ok","data":{"deleted":70,"nextUp":null}})";
        api = std::make_unique<Api>();
        api->setBases(QString(), QStringLiteral("http://127.0.0.1:%1/api/pride").arg(server->serverPort()));
        api->setSessionToken("tok");
        workouts = std::make_unique<Workouts>(*api);
    }

    void cleanup() { workouts.reset(); api.reset(); server.reset(); }

    void theRoutinesMenuLoads()
    {
        workouts->loadRoutines();
        QTRY_COMPARE(workouts->routines().size(), 1);
        QCOMPARE(workouts->routines().first().toMap().value("programTitle").toString(), QStringLiteral("Upper/Lower"));
    }

    void startingANewWorkoutAsksForItsRoutinesDraft()
    {
        QSignalSpy changed(workouts.get(), &Workouts::draftChanged);
        workouts->startNew(50);
        QCOMPARE(workouts->routineId(), 50);
        QVERIFY(workouts->draftLoading());
        QTRY_COMPARE(workouts->draft().value("routineId").toInt(), 50);
        QVERIFY(!workouts->draftLoading());
        QCOMPARE(QUrlQuery(server->requests.last()).queryItemValue("routineId"), QStringLiteral("50"));
        QCOMPARE(workouts->editingId(), 0);
    }

    void aFreeWorkoutAsksForNoDraft()
    {
        workouts->startNew(0);
        QCOMPARE(workouts->routineId(), 0);
        QVERIFY(workouts->draft().isEmpty());
        QTest::qWait(100);
        QCOMPARE(count("GET", p("/workouts/draft")), 0);
    }

    void aDraftThatCannotLoadSaysWhy()
    {
        server->statuses[p("/workouts/draft")] = 404;
        workouts->startNew(50);
        QTRY_COMPARE(workouts->draftError(), QStringLiteral("not_found"));
    }

    void savingANewWorkoutPostsAndKeepsTheResult()
    {
        workouts->startNew(0);
        QSignalSpy saved(workouts.get(), &Workouts::saved);
        workouts->save(body("0f8fad5b-d9cb-469f-a165-70867728950e"));
        QVERIFY(workouts->busy());
        QTRY_COMPARE(saved.size(), 1);
        QCOMPARE(saved.first().first().toInt(), 70);
        QVERIFY(!workouts->busy());
        QCOMPARE(lastBody("POST", p("/workouts")).value("clientId").toString(),
                 QStringLiteral("0f8fad5b-d9cb-469f-a165-70867728950e"));
        QCOMPARE(workouts->result().value("crowns").toList().size(), 1);
        workouts->clearResult();
        QVERIFY(workouts->result().isEmpty());
    }

    void aRefusedSaveNamesTheFieldAndAResendUsesTheSameClientId()
    {
        server->queuedStatuses[p("/workouts")] = {400};
        server->queued[p("/workouts")] = {R"({"status":"error","field":"reps","message":"reps must be a whole number"})"};
        QSignalSpy failed(workouts.get(), &Workouts::failed);
        QSignalSpy saved(workouts.get(), &Workouts::saved);
        workouts->startNew(0);
        workouts->save(body("0f8fad5b-d9cb-469f-a165-70867728950e"));
        QTRY_COMPARE(failed.size(), 1);
        QCOMPARE(failed.first().value(0).toString(), QStringLiteral("save"));
        QCOMPARE(failed.first().value(1).toString(), QStringLiteral("invalid"));
        QCOMPARE(failed.first().value(2).toString(), QStringLiteral("reps"));
        workouts->save(body("0f8fad5b-d9cb-469f-a165-70867728950e"));
        QTRY_COMPARE(saved.size(), 1);
        QCOMPARE(count("POST", p("/workouts")), 2);
    }

    void openingAPastWorkoutAndSavingItPuts()
    {
        workouts->open(70);
        QCOMPARE(workouts->editingId(), 70);
        QTRY_COMPARE(workouts->editing().value("id").toInt(), 70);
        QSignalSpy saved(workouts.get(), &Workouts::saved);
        workouts->save(body(QString()));
        QTRY_COMPARE(saved.size(), 1);
        QCOMPARE(count("PUT", p("/workouts/70")), 1);
        QCOMPARE(count("POST", p("/workouts")), 0);
    }

    void aPastWorkoutGoneElsewhereSaysSo()
    {
        server->statuses[p("/workouts/70")] = 404;
        QSignalSpy failed(workouts.get(), &Workouts::failed);
        workouts->open(70);
        QTRY_COMPARE(failed.size(), 1);
        QCOMPARE(failed.first().value(0).toString(), QStringLiteral("open"));
        QCOMPARE(failed.first().value(1).toString(), QStringLiteral("not_found"));
        QCOMPARE(workouts->editingError(), QStringLiteral("not_found"));
    }

    void deletingSaysRemovedAndClosesTheOpenWorkout()
    {
        workouts->open(70);
        QTRY_COMPARE(workouts->editing().value("id").toInt(), 70);
        QSignalSpy removed(workouts.get(), &Workouts::removed);
        workouts->remove(70);
        QTRY_COMPARE(removed.size(), 1);
        QCOMPARE(workouts->editingId(), 0);
    }

    void theHistoryLoadsAndAFailureIsKept()
    {
        workouts->loadHistory();
        QTRY_VERIFY(workouts->historyLoaded());
        QCOMPARE(workouts->history().size(), 1);
        server->statuses[p("/workouts")] = 500;
        workouts->loadHistory();
        QTRY_COMPARE(workouts->historyError(), QStringLiteral("server"));
        QCOMPARE(workouts->history().size(), 1);       // the last answer stays shown
    }

    void aClientIdIsAFreshUuid()
    {
        const QString one = workouts->newClientId();
        QCOMPARE(one.size(), 36);
        QVERIFY(one != workouts->newClientId());
        QCOMPARE(one, one.toLower());
    }

    void resetForgetsEverythingAndLateAnswersAreIgnored()
    {
        server->holdNext[p("/workouts")] = 1;
        workouts->loadHistory();
        QTRY_COMPARE(server->requests.size(), 1);
        workouts->reset();
        server->releaseHeld();
        QTest::qWait(150);
        QVERIFY(workouts->history().isEmpty());
        QVERIFY(!workouts->historyLoaded());
    }
};

QTEST_MAIN(TestWorkouts)
#include "tst_workouts.moc"
