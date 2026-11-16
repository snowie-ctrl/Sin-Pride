// The Programs service against a faked server: the list, the open program and routine, every write replacing the
// open copy, Today with the app's own date, the starters, refusals, and something deleted elsewhere.
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QSignalSpy>
#include <QTest>
#include <QUrlQuery>

#include "FakeServer.h"
#include "api/Api.h"
#include "services/Programs.h"

static QString p(const char *route) { return QStringLiteral("/api/pride") + QLatin1String(route); }
static QString baseOf(const FakeServer &s) { return QStringLiteral("http://127.0.0.1:%1/api/pride").arg(s.serverPort()); }

static const QByteArray list = R"({"status":"ok","data":[
 {"id":5,"title":"Upper/Lower","active":true,"starterKey":"upperLower","days":[0,1,3,4],"routineCount":2,"updatedAt":"2026-11-15T09:00:00Z"},
 {"id":6,"title":"Mine","active":false,"starterKey":null,"days":[],"routineCount":0,"updatedAt":"2026-11-14T09:00:00Z"}]})";
static const QByteArray program = R"({"status":"ok","data":{"id":5,"title":"Upper/Lower","active":true,
 "starterKey":"upperLower","days":[0,1,3,4],"updatedAt":"2026-11-15T09:00:00Z","routines":[
 {"id":50,"title":"Upper","items":[{"id":500,"exerciseId":1,"sets":3,"repsMin":8,"repsMax":12,"targetWeight":135,
  "targetUnit":"lb","targetSeconds":null,"targetDistance":null,"distanceUnit":null,"restSeconds":90,"note":null}]},
 {"id":51,"title":"Lower","items":[]}]}})";
static const QByteArray today = R"({"status":"ok","data":{"program":{"id":5,"title":"Upper/Lower"},
 "nextUp":{"routineId":51,"title":"Lower","items":[]},"plannedDay":"2026-11-19","week":[]}})";

class TestPrograms : public QObject
{
    Q_OBJECT

    std::unique_ptr<FakeServer> server;
    std::unique_ptr<Api> api;
    std::unique_ptr<Programs> programs;

    QJsonObject lastBody(const QString &method, const QString &route) const
    {
        for (int i = server->requests.size() - 1; i >= 0; --i)
            if (server->methods[i] == method.toLatin1() && server->requests[i].path() == route)
                return QJsonDocument::fromJson(server->bodies[i]).object();
        return {};
    }

    int count(const QString &method, const QString &route) const
    {
        int n = 0;
        for (int i = 0; i < server->requests.size(); ++i)
            n += server->methods[i] == method.toLatin1() && server->requests[i].path() == route;
        return n;
    }

private slots:
    void init()
    {
        server = std::make_unique<FakeServer>();
        server->responses[p("/programs")] = list;
        server->responses[p("/programs/5")] = program;
        server->responses[p("/today")] = today;
        api = std::make_unique<Api>();
        api->setBases(QString(), baseOf(*server));
        api->setSessionToken("tok");
        programs = std::make_unique<Programs>(*api);
        programs->setToday(QDate(2026, 11, 17));
    }

    void cleanup() { programs.reset(); api.reset(); server.reset(); }

    void theListAndAProgramLoad()
    {
        programs->loadList();
        QTRY_COMPARE(programs->programs().size(), 2);
        programs->open(5);
        QTRY_COMPARE(programs->currentId(), 5);
        QCOMPARE(programs->current().value("routines").toList().size(), 2);
        programs->openRoutine(50);
        QCOMPARE(programs->currentRoutine().value("title").toString(), QStringLiteral("Upper"));
    }

    void aWriteReplacesTheOpenProgramAndRefreshesTheListAndToday()
    {
        programs->open(5);
        QTRY_COMPARE(programs->currentId(), 5);
        programs->openRoutine(50);
        QByteArray renamed = program;
        renamed.replace(R"("title":"Upper","items")", R"("title":"Upper A","items")");
        server->methodResponses["PUT " + p("/routines/50")] = renamed;
        QSignalSpy saved(programs.get(), &Programs::saved);
        const int listsBefore = count("GET", p("/programs"));
        programs->renameRoutine(50, "Upper A");
        QTRY_COMPARE(saved.size(), 1);
        QCOMPARE(saved.first().at(0).toString(), QStringLiteral("routine"));
        QCOMPARE(lastBody("PUT", p("/routines/50")).value("title").toString(), QStringLiteral("Upper A"));
        QCOMPARE(programs->currentRoutine().value("title").toString(), QStringLiteral("Upper A"));
        QTRY_COMPARE(count("GET", p("/programs")), listsBefore + 1);
        QTRY_VERIFY(count("GET", p("/today")) >= 1);
    }

    void creatingOpensTheNewProgram()
    {
        server->methodResponses["POST " + p("/programs")] = program;
        QSignalSpy saved(programs.get(), &Programs::saved);
        programs->create("Upper/Lower");
        QTRY_COMPARE(saved.size(), 1);
        QCOMPARE(programs->currentId(), 5);
        QCOMPARE(lastBody("POST", p("/programs")).value("title").toString(), QStringLiteral("Upper/Lower"));
    }

    void removingTheOpenProgramClosesIt()
    {
        programs->open(5);
        QTRY_COMPARE(programs->currentId(), 5);
        server->methodResponses["DELETE " + p("/programs/5")] = R"({"status":"ok","data":[]})";
        programs->remove(5);
        QTRY_COMPARE(programs->currentId(), 0);
        QVERIFY(programs->programs().isEmpty());
    }

    void itemsAndOrdersSendWhatTheServerExpects()
    {
        server->methodResponses["POST " + p("/routine-items")] = program;
        server->methodResponses["PUT " + p("/routine-items/500")] = program;
        server->methodResponses["POST " + p("/routines/reorder")] = program;
        server->methodResponses["PUT " + p("/programs/5/days")] = program;
        QSignalSpy saved(programs.get(), &Programs::saved);
        programs->addItem(50, 1);
        programs->updateItem(500, {{"sets", 4}, {"repsMin", 8}, {"repsMax", 12}});
        programs->reorderRoutines(5, {51, 50});
        programs->setDays(5, {0, 2});
        QTRY_COMPARE(saved.size(), 4);
        QCOMPARE(lastBody("POST", p("/routine-items")), QJsonObject({{"routineId", 50}, {"exerciseId", 1}}));
        QCOMPARE(lastBody("PUT", p("/routine-items/500")).value("sets").toInt(), 4);
        QCOMPARE(lastBody("POST", p("/routines/reorder")),
                 QJsonObject({{"programId", 5}, {"order", QJsonArray{51, 50}}}));
        QCOMPARE(lastBody("PUT", p("/programs/5/days")).value("days").toArray(), QJsonArray({0, 2}));
    }

    void todaySendsTheAppsOwnDate()
    {
        programs->loadToday();
        QTRY_COMPARE(programs->today().value("plannedDay").toString(), QStringLiteral("2026-11-19"));
        const QUrl asked = server->requests.last();
        QCOMPARE(QUrlQuery(asked).queryItemValue("date"), QStringLiteral("2026-11-17"));
    }

    void startersLoadAndAdoptingOpensTheNewProgram()
    {
        server->responses[p("/starters")] = R"({"status":"ok","data":[{"key":"upperLower","title":"Upper/Lower",
          "blurb":"…","suggested":true,"variant":"dumbbell","days":[0,1,3,4],"routines":[],"missing":[]}]})";
        server->methodResponses["POST " + p("/starters/upperLower/adopt")] = program;
        programs->loadStarters();
        QTRY_COMPARE(programs->starters().size(), 1);
        QSignalSpy saved(programs.get(), &Programs::saved);
        programs->adopt("upperLower");
        QTRY_COMPARE(saved.size(), 1);
        QCOMPARE(saved.first().at(0).toString(), QStringLiteral("adopted"));
        QCOMPARE(saved.first().at(1).toInt(), 5);
        QCOMPARE(programs->currentId(), 5);
    }

    void refusalsAreCodedWithTheirField()
    {
        server->methodStatuses["POST " + p("/programs")] = 409;
        server->methodResponses["POST " + p("/programs")] = R"({"status":"limit","field":"program","message":"…"})";
        server->methodStatuses["PUT " + p("/routine-items/500")] = 400;
        server->methodResponses["PUT " + p("/routine-items/500")] = R"({"status":"error","field":"repsMax","message":"…"})";
        server->methodStatuses["POST " + p("/starters/foundations/adopt")] = 409;
        server->methodResponses["POST " + p("/starters/foundations/adopt")] = R"({"status":"unavailable","message":"…"})";
        QSignalSpy failed(programs.get(), &Programs::failed);
        programs->create("One more");
        programs->updateItem(500, {{"sets", 3}});
        programs->adopt("foundations");
        QTRY_COMPARE(failed.size(), 3);
        QStringList seen;
        for (const auto &f : failed)
            seen << f.at(0).toString() + "/" + f.at(1).toString() + "/" + f.at(2).toString();
        seen.sort();
        QCOMPARE(seen, QStringList({"adopted/unavailable/", "item/invalid/repsMax", "program/limit/program"}));
    }

    void aProgramGoneElsewhereClosesAndSaysSo()
    {
        programs->open(5);
        QTRY_COMPARE(programs->currentId(), 5);
        server->methodStatuses["PUT " + p("/programs/5")] = 404;
        server->methodResponses["PUT " + p("/programs/5")] = R"({"status":"error","message":"not found"})";
        QSignalSpy gone(programs.get(), &Programs::gone);
        QSignalSpy failed(programs.get(), &Programs::failed);
        const int listsBefore = count("GET", p("/programs"));
        programs->rename(5, "Anything");
        QTRY_COMPARE(gone.size(), 1);
        QCOMPARE(gone.first().at(0).toString(), QStringLiteral("program"));
        QCOMPARE(programs->currentId(), 0);
        QTRY_COMPARE(count("GET", p("/programs")), listsBefore + 1);
        QCOMPARE(failed.size(), 0);
    }

    void activatingTheOpenProgramKeepsItOpen()
    {
        programs->open(5);
        QTRY_COMPARE(programs->currentId(), 5);
        server->methodResponses["POST " + p("/programs/5/activate")] = list;
        QSignalSpy saved(programs.get(), &Programs::saved);
        programs->activate(5);
        QTRY_COMPARE(saved.size(), 1);
        QCOMPARE(saved.first().at(0).toString(), QStringLiteral("activated"));
        QCOMPARE(saved.first().at(1).toInt(), 5);
        QCOMPARE(programs->currentId(), 5);
        QTRY_VERIFY(count("GET", p("/programs/5")) >= 2);
    }

    void openingAProgramGoneElsewhereClosesIt()
    {
        programs->open(5);
        QTRY_COMPARE(programs->currentId(), 5);
        server->statuses[p("/programs/5")] = 404;
        QSignalSpy gone(programs.get(), &Programs::gone);
        programs->open(5);
        QTRY_COMPARE(gone.size(), 1);
        QCOMPARE(programs->currentId(), 0);
    }

    void aGoneOtherProgramLeavesTheOpenOneOpen()
    {
        programs->open(5);
        QTRY_COMPARE(programs->currentId(), 5);
        server->methodStatuses["DELETE " + p("/programs/6")] = 404;
        server->methodResponses["DELETE " + p("/programs/6")] = R"({"status":"error","message":"not found"})";
        QSignalSpy gone(programs.get(), &Programs::gone);
        programs->remove(6);
        QTRY_COMPARE(gone.size(), 1);
        QCOMPARE(programs->currentId(), 5);
    }

    void noServerIsNetworkAndChangesNothing()
    {
        programs->open(5);
        QTRY_COMPARE(programs->currentId(), 5);
        api->setBases(QString(), QStringLiteral("http://127.0.0.1:1/api/pride"));
        QSignalSpy failed(programs.get(), &Programs::failed);
        programs->rename(5, "Anything");
        QTRY_COMPARE_WITH_TIMEOUT(failed.size(), 1, 10000);
        QCOMPARE(failed.first().at(1).toString(), QStringLiteral("network"));
        QCOMPARE(programs->current().value("title").toString(), QStringLiteral("Upper/Lower"));
    }

    void aResetForgetsAndDropsLateAnswers()
    {
        server->holdNext[p("/programs")] = 1;
        programs->loadList();
        QTRY_COMPARE(server->requests.size(), 1);
        programs->reset();
        server->releaseHeld();
        QTest::qWait(200);
        QVERIFY(programs->programs().isEmpty());
        QCOMPARE(programs->currentId(), 0);
        QVERIFY(programs->today().isEmpty());
    }
};

QTEST_MAIN(TestPrograms)
#include "tst_programs.moc"
