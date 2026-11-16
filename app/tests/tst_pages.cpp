// Gluttony's app/tests/tst_pages.cpp at c1ed705 is the model: the real Main.qml, NavShell and pages over the real
// services, the server faked, clicks sent to the offscreen window only. Each page task adds its cases here.
#include <QBuffer>
#include <QDir>
#include <QFile>
#include <QImage>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickItem>
#include <QQuickWindow>
#include <QSettings>
#include <QSignalSpy>
#include <QTemporaryDir>
#include <QTest>
#include <QUrlQuery>
#include <QtQml/QQmlExtensionPlugin>

#include <memory>

#include "FakeServer.h"
#include "api/Api.h"
#include "assets/Preferences.h"
#include "services/AccountStore.h"
#include "services/Catalog.h"
#include "services/ExerciseStore.h"
#include "services/Nav.h"
#include "services/Profile.h"
#include "services/Programs.h"
#include "services/Session.h"
#include "services/Wiring.h"

Q_IMPORT_QML_PLUGIN(PridePlugin)

static QString path(const char *route)
{
    return QStringLiteral("/api/pride") + QLatin1String(route);
}

static const QByteArray signedIn = R"({"status":"ok","UID":7,"username":"stub","token":"tok"})";
static const QString pictureOne = QStringLiteral("0123456789abcdef0123.jpg");
static const QString pictureTwo = QStringLiteral("1123456789abcdef0123.jpg");

// Three shown exercises and one hidden, by name. Barbell Curl has two pictures; Kettlebell Halo has none and no
// steps; Old Row has left the catalog.
static QByteArray catalogJson()
{
    return R"({"status":"ok","data":{"version":"v1","exercises":[
 {"id":1,"key":"Barbell_Curl","source":"free-exercise-db","licence":"Unlicense","name":"Barbell Curl",
  "category":"strength","level":"beginner","measure":"weight_reps","region":"upper","removed":false,
  "primary":["biceps"],"secondary":["forearms"],"equipment":["barbell"],
  "steps":["Stand up with the bar.","Curl it up.","Lower it slowly."],
  "pictures":["0123456789abcdef0123.jpg","1123456789abcdef0123.jpg"]},
 {"id":5,"key":"Kettlebell_Halo","source":"free-exercise-db","licence":"Unlicense","name":"Kettlebell Halo",
  "category":"strength","level":"beginner","measure":"weight_reps","region":"upper","removed":false,
  "primary":["shoulders"],"secondary":[],"equipment":["kettlebell"],"steps":[],"pictures":[]},
 {"id":9,"key":"Old_Row","source":"free-exercise-db","licence":"Unlicense","name":"Old Row",
  "category":"strength","level":"beginner","measure":"weight_reps","region":"upper","removed":true,
  "primary":["middle back"],"secondary":[],"equipment":["barbell"],"steps":["Row."],"pictures":[]},
 {"id":7,"key":"Pullups","source":"free-exercise-db","licence":"Unlicense","name":"Pullups",
  "category":"strength","level":"beginner","measure":"reps","region":"upper","removed":false,
  "primary":["lats"],"secondary":["biceps"],"equipment":["bodyweight","pull-up bar"],
  "steps":["Hang.","Pull."],"pictures":[]}]}})";
}

static QByteArray profileJson(const char *intro, const char *equipment = R"(["barbell","bodyweight"])")
{
    return QByteArray(R"({"status":"ok","data":{"units":"lb","goal":"general","daysPerWeek":3,"upperIncrement":5.0,)"
                      R"("lowerIncrement":10.0,"weekStart":"mon","introState":")") + intro + R"(","equipment":)"
           + equipment + "}}";
}

static QByteArray startersJson(bool withItems = true)
{
    const QByteArray items = withItems
        ? R"([{"exerciseId":1,"name":"Barbell Curl","measure":"weight_reps","sets":3,"repsMin":8,"repsMax":12,"targetSeconds":null,"restSeconds":90}])"
        : "[]";
    return R"({"status":"ok","data":[
 {"key":"foundations","title":"Foundations","blurb":"Two full-body days.","suggested":false,"variant":"dumbbell",
  "days":[0,2,4],"routines":[{"title":"Full body A","items":)" + items + R"(}],"missing":[]},
 {"key":"upperLower","title":"Upper/Lower","blurb":"Upper one day, legs the next.","suggested":true,"variant":"dumbbell",
  "days":[0,1,3,4],"routines":[{"title":"Upper","items":)" + items + R"(},{"title":"Lower","items":)" + items + R"(}],
  "missing":["Plank"]}]})";
}

static QByteArray programJson(int id = 5)
{
    return QByteArray(R"({"status":"ok","data":{"id":)") + QByteArray::number(id) + R"(,"title":"Upper/Lower","active":true,
 "starterKey":"upperLower","days":[0,1,3,4],"updatedAt":"2026-11-15T09:00:00Z","routines":[
 {"id":50,"title":"Upper","items":[{"id":500,"exerciseId":1,"sets":3,"repsMin":8,"repsMax":12,"targetWeight":135,
  "targetUnit":"lb","targetSeconds":null,"targetDistance":null,"distanceUnit":null,"restSeconds":90,"note":null}]},
 {"id":51,"title":"Lower","items":[]}]}})";
}

static QByteArray pictureBytes()
{
    QImage image(32, 24, QImage::Format_RGB32);
    image.fill(Qt::darkMagenta);
    QByteArray bytes;
    QBuffer buffer(&bytes);
    buffer.open(QIODevice::WriteOnly);
    image.save(&buffer, "PNG");
    return bytes;
}


class TestPages : public QObject
{
    Q_OBJECT

    QTemporaryDir dir;
    int runs = 0;
    QString dataDir;
    std::unique_ptr<FakeServer> server;
    std::unique_ptr<Preferences> preferences;
    std::unique_ptr<Api> api;
    std::unique_ptr<Nav> nav;
    std::unique_ptr<AccountStore> accounts;
    std::unique_ptr<Session> session;
    std::unique_ptr<ExerciseStore> exercises;
    std::unique_ptr<Catalog> catalog;
    std::unique_ptr<Profile> profile;
    std::unique_ptr<Programs> programs;
    // Declared last, so it is destroyed first: pages go before the services they call.
    std::unique_ptr<QQmlApplicationEngine> engine;

    QQuickWindow *window() const
    {
        return engine ? qobject_cast<QQuickWindow *>(engine->rootObjects().value(0)) : nullptr;
    }

    static QQuickItem *findIn(QQuickItem *root, const QString &name, bool visibleOnly = false)
    {
        QList<QQuickItem *> pending{root};
        while (!pending.isEmpty()) {
            QQuickItem *item = pending.takeFirst();
            if (item->objectName() == name && (!visibleOnly || item->isVisible()))
                return item;
            pending += item->childItems();
        }
        return nullptr;
    }

    QQuickItem *find(const QString &name) const
    {
        return window() ? findIn(window()->contentItem(), name) : nullptr;
    }

    QQuickItem *findVisible(const QString &name) const
    {
        return window() ? findIn(window()->contentItem(), name, true) : nullptr;
    }

    int countVisible(const QString &name) const
    {
        if (!window())
            return 0;
        int found = 0;
        QList<QQuickItem *> pending{window()->contentItem()};
        while (!pending.isEmpty()) {
            QQuickItem *item = pending.takeFirst();
            found += item->objectName() == name && item->isVisible();
            pending += item->childItems();
        }
        return found;
    }

    // A long page (Settings) holds controls below the window's edge; a click there would miss. Scrolls every Flickable
    // above the item just far enough to show it.
    static void scrollIntoView(QQuickItem *item)
    {
        for (QQuickItem *flick = item->parentItem(); flick; flick = flick->parentItem()) {
            const auto content = qvariant_cast<QQuickItem *>(flick->property("contentItem"));
            if (!content || !flick->property("contentY").isValid() || !flick->property("contentHeight").isValid())
                continue;
            const qreal top = item->mapToItem(content, QPointF(0, 0)).y();
            const qreal viewTop = flick->property("contentY").toReal();
            if (top >= viewTop && top + item->height() <= viewTop + flick->height())
                continue;
            const qreal farthest = qMax<qreal>(0, flick->property("contentHeight").toReal() - flick->height());
            flick->setProperty("contentY", qBound<qreal>(0, top - 20, farthest));
        }
    }

    // A page lays itself out in the frame after it appears; tests that map an item to the window wait for that first.
    void settle()
    {
        QSignalSpy framed(window(), &QQuickWindow::frameSwapped);
        window()->update();
        framed.wait(250);
    }

    void click(QQuickItem *item)
    {
        QVERIFY(item);
        // A page lays itself out in the frame after it appears; without this wait a click now and then landed beside
        // its target on a busy machine (Gluttony's lesson). The item is scrolled into view only after that layout,
        // and given a frame more to settle there.
        QSignalSpy framed(window(), &QQuickWindow::frameSwapped);
        window()->update();
        framed.wait(250);
        scrollIntoView(item);
        window()->update();
        framed.wait(250);
        const QPointF centre = item->mapToScene(QPointF(item->width() / 2, item->height() / 2));
        QTest::mouseClick(window(), Qt::LeftButton, Qt::NoModifier, centre.toPoint());
    }

    // QTest has no keyClicks for a window, so the letters go one by one.
    void type(const QString &text)
    {
        for (const QChar ch : text) {
            if (ch == QLatin1Char(' '))
                QTest::keyClick(window(), Qt::Key_Space);
            else
                QTest::keyClick(window(), ch.toLatin1());
        }
    }

    QList<QUrl> requestsTo(const char *route) const
    {
        QList<QUrl> found;
        for (const QUrl &url : server->requests)
            if (url.path() == path(route))
                found << url;
        return found;
    }

    QJsonObject lastBodyTo(const char *route) const
    {
        for (int i = server->requests.size() - 1; i >= 0; --i)
            if (server->requests[i].path() == path(route) && !server->bodies[i].isEmpty())
                return QJsonDocument::fromJson(server->bodies[i]).object();
        return {};
    }

    // By method too, for routes that answer a GET and a PUT.
    QList<QUrl> requestsTo(const char *method, const QString &route) const
    {
        QList<QUrl> found;
        for (int i = 0; i < server->requests.size(); ++i)
            if (server->methods[i] == method && server->requests[i].path() == path(route.toUtf8().constData()))
                found << server->requests[i];
        return found;
    }

    QJsonObject lastBodyTo(const char *method, const QString &route) const
    {
        for (int i = server->requests.size() - 1; i >= 0; --i)
            if (server->methods[i] == method && server->requests[i].path() == path(route.toUtf8().constData())
                && !server->bodies[i].isEmpty())
                return QJsonDocument::fromJson(server->bodies[i]).object();
        return {};
    }

    // The app as main.cpp builds it; the device signs itself in at once unless a test answers otherwise.
    void start()
    {
        engine = std::make_unique<QQmlApplicationEngine>();
        QQmlContext *context = engine->rootContext();
        context->setContextProperty("Preferences", preferences.get());
        context->setContextProperty("Nav", nav.get());
        context->setContextProperty("Session", session.get());
        context->setContextProperty("ExerciseStore", exercises.get());
        context->setContextProperty("Catalog", catalog.get());
        context->setContextProperty("Profile", profile.get());
        context->setContextProperty("Programs", programs.get());
        engine->loadFromModule("Pride", "Main");
        QVERIFY(window());
        window()->resize(1600, 1000);
        session->identifyDevice();
    }

    // Signed in and on Today, for the Today page's tests.
    void startOnToday()
    {
        start();
        QTRY_VERIFY(findVisible("todayPage"));
    }

    // Signed in and on the Catalog, the catalog arrived. Signing in lands on Today, so these tests ask for the
    // Catalog as the start page.
    void startSignedIn()
    {
        nav->setStartPage("catalog-page");
        start();
        QTRY_VERIFY(findVisible("catalogPage"));
        QTRY_COMPARE(catalog->shownCount(), 3);
    }

    // A new account, intro pending; PUT /profile answers done, as the server would once the intro is finished.
    void startInTheIntro()
    {
        server->responses[path("/profile")] = profileJson("pending", "[]");
        server->methodResponses["PUT " + path("/profile")] = profileJson("done", R"(["dumbbell","bodyweight","bench"])");
        server->responses[path("/starters")] = startersJson();
        start();
        QTRY_VERIFY(findVisible("introPage"));
    }

    void walkToTheStarter()
    {
        click(find("introNext"));
        QTRY_VERIFY(findVisible("introDays-4"));
        click(find("introDays-4"));
        click(find("introNext"));
        QTRY_VERIFY(findVisible("introPreset-dumbbells"));
        click(find("introPreset-dumbbells"));
        click(find("introNext"));
        QTRY_VERIFY(findVisible("introGoal-muscle"));
        click(find("introGoal-muscle"));
        click(find("introNext"));
        QTRY_VERIFY(findVisible("introStarterTitle"));
    }

private slots:
    void initTestCase()
    {
        const QString secrets = dir.filePath("secrets.json");
        QFile file(secrets);
        QVERIFY(file.open(QIODevice::WriteOnly));
        file.write("{\"apiBase\": \"http://127.0.0.1:1/api/pride\"}");
        file.close();
        qputenv("PRIDE_SECRETS", secrets.toUtf8());
        // Before any Preferences exists, so the owner's real ini is never read or written.
        QSettings::setPath(QSettings::IniFormat, QSettings::UserScope, dir.filePath("settings"));
    }

    void init()
    {
        server = std::make_unique<FakeServer>();
        server->responses[path("/device/identify")] = signedIn;
        server->responses[path("/catalog")] = catalogJson();
        server->responses[path("/profile")] = profileJson("done");
        server->responses[path("/programs")] = R"({"status":"ok","data":[]})";
        server->responses[path("/today")] = R"({"status":"ok","data":{"program":null,"nextUp":null,"plannedDay":null,"week":[
 {"date":"2026-11-16","weekday":0,"planned":false,"done":false},{"date":"2026-11-17","weekday":1,"planned":false,"done":false},
 {"date":"2026-11-18","weekday":2,"planned":false,"done":false},{"date":"2026-11-19","weekday":3,"planned":false,"done":false},
 {"date":"2026-11-20","weekday":4,"planned":false,"done":false},{"date":"2026-11-21","weekday":5,"planned":false,"done":false},
 {"date":"2026-11-22","weekday":6,"planned":false,"done":false}]}})";
        server->responses[path("/exercises")] = R"({"status":"ok","data":[]})";
        // A fresh data folder each test: no account and no catalog copy carry over.
        dataDir = dir.filePath(QStringLiteral("data-%1").arg(++runs));
        preferences = std::make_unique<Preferences>();
        api = std::make_unique<Api>();
        api->setBases(QString(), QStringLiteral("http://127.0.0.1:%1/api/pride").arg(server->serverPort()));
        nav = std::make_unique<Nav>();
        accounts = std::make_unique<AccountStore>(dataDir);
        session = std::make_unique<Session>(*api);
        exercises = std::make_unique<ExerciseStore>(*api, dataDir);
        catalog = std::make_unique<Catalog>(*exercises, *api);
        profile = std::make_unique<Profile>(*api);
        programs = std::make_unique<Programs>(*api);
        programs->setToday(QDate(2026, 11, 17));
        wireServices(*session, *accounts, *exercises, *catalog, *profile, *programs);
    }

    void cleanup()
    {
        engine.reset();
        programs.reset();
        profile.reset();
        catalog.reset();
        exercises.reset();
        session.reset();
        accounts.reset();
        nav.reset();
        api.reset();
        preferences.reset();
        server.reset();
    }

    // ---- Sign-in and the shell ----

    void aKnownDeviceLandsOnTodayAndLoadsWhatIsTheirs()
    {
        start();
        QTRY_VERIFY(findVisible("navShell"));
        QCOMPARE(nav->currentPage(), QStringLiteral("today-page"));
        QTRY_VERIFY(findVisible("todayPage"));
        for (const char *route : {"/catalog", "/profile", "/programs", "/today", "/exercises"})
            QTRY_COMPARE(requestsTo(route).size(), 1);
    }

    static QByteArray todayJson(const char *items, const char *planned = R"("2026-11-19")")
    {
        return QByteArray(R"({"status":"ok","data":{"program":{"id":5,"title":"Upper/Lower"},
 "nextUp":{"routineId":51,"title":"Lower","items":)") + items + R"(},"plannedDay":)" + planned + R"(,"week":[
 {"date":"2026-11-16","weekday":0,"planned":false,"done":true},{"date":"2026-11-17","weekday":1,"planned":false,"done":false},
 {"date":"2026-11-18","weekday":2,"planned":false,"done":false},{"date":"2026-11-19","weekday":3,"planned":true,"done":false},
 {"date":"2026-11-20","weekday":4,"planned":true,"done":false},{"date":"2026-11-21","weekday":5,"planned":false,"done":false},
 {"date":"2026-11-22","weekday":6,"planned":false,"done":false}]}})";
    }

    static const char *curlItem()
    {
        return R"([{"id":510,"exerciseId":1,"sets":3,"repsMin":8,"repsMax":12,"targetWeight":135,"targetUnit":"lb",
  "targetSeconds":null,"targetDistance":null,"distanceUnit":null,"restSeconds":90,"note":null}])";
    }

    // ---- Today ----

    void todayShowsNextUpWithItsTargets()
    {
        server->responses[path("/today")] = todayJson(curlItem());
        startOnToday();
        QTRY_VERIFY(findVisible("nextUpCard"));
        QCOMPARE(find("nextUpTitle")->property("text").toString(), QStringLiteral("Lower"));
        QCOMPARE(find("nextUpWhen")->property("text").toString(), QStringLiteral("· planned for Thursday"));
        QTRY_COMPARE(countVisible("todayItem"), 1);
        QCOMPARE(find("todayItemName")->property("text").toString(), QStringLiteral("Barbell Curl"));
        QCOMPARE(find("todayItemTarget")->property("text").toString(), QStringLiteral("3 × 8–12 · 135 lb"));
        QVERIFY(!findVisible("todayItemGone"));
    }

    void withNoPlannedDaysItIsWheneverYoureReady()
    {
        server->responses[path("/today")] = todayJson(curlItem(), "null");
        startOnToday();
        QTRY_COMPARE(find("nextUpWhen")->property("text").toString(), QStringLiteral("· whenever you're ready"));
    }

    void theWeekStripShowsDoneAndPlannedAndNeverAMiss()
    {
        server->responses[path("/today")] = todayJson(curlItem());
        startOnToday();
        QTRY_VERIFY(findVisible("dayCell-0"));
        QVERIFY(find("dayCell-0")->property("done").toBool());
        QVERIFY(find("dayCell-1")->property("isToday").toBool());
        QVERIFY(find("dayCell-3")->property("planned").toBool());
        // Wednesday is neither done nor planned: no marker at all, and no word for it.
        QVERIFY(!findIn(find("dayCell-2"), "dayMarker", true));
    }

    void todayAsksWithTheAppsOwnDate()
    {
        startOnToday();
        QTRY_VERIFY(!requestsTo("/today").isEmpty());
        QCOMPARE(QUrlQuery(requestsTo("/today").last()).queryItemValue("date"), QStringLiteral("2026-11-17"));
    }

    void withNoProgramTodayOffersTheIntroAndAnEmptyProgram()
    {
        server->methodResponses["POST " + path("/programs")] = programJson();
        startOnToday();
        QTRY_VERIFY(findVisible("noProgramCard"));
        QVERIFY(findVisible("todayShowIntro"));
        click(find("todayEmptyProgram"));
        QTRY_COMPARE(lastBodyTo("POST", "/programs"), QJsonObject({{"title", "My program"}}));
        QTRY_COMPARE(nav->currentPage(), QStringLiteral("programs-page"));
    }

    void programsButNoneActiveAsksToPickOne()
    {
        server->responses[path("/programs")] = R"({"status":"ok","data":[{"id":6,"title":"Mine","active":false,
 "starterKey":null,"days":[],"routineCount":0,"updatedAt":"2026-11-14T09:00:00Z"}]})";
        startOnToday();
        QTRY_VERIFY(findVisible("pickProgramCard"));
        QVERIFY(!findVisible("noProgramCard"));
    }

    void aRemovedExerciseIsNamedAndMarked()
    {
        server->responses[path("/today")] = todayJson(R"([{"id":511,"exerciseId":9,"sets":3,"repsMin":8,"repsMax":12,
 "targetWeight":null,"targetUnit":null,"targetSeconds":null,"targetDistance":null,"distanceUnit":null,"restSeconds":null,"note":null}])");
        startOnToday();
        QTRY_COMPARE(countVisible("todayItem"), 1);
        QCOMPARE(find("todayItemName")->property("text").toString(), QStringLiteral("Old Row"));
        QVERIFY(findVisible("todayItemGone"));
    }

    void noLogButtonOrCrownsYet()
    {
        server->responses[path("/today")] = todayJson(curlItem());
        startOnToday();
        QTRY_VERIFY(findVisible("nextUpCard"));
        QVERIFY(!find("logThisWorkout"));
        QVERIFY(!find("crownsRow"));
    }

    static QByteArray twoPrograms()
    {
        return R"({"status":"ok","data":[
 {"id":5,"title":"Upper/Lower","active":true,"starterKey":"upperLower","days":[0,1,3,4],"routineCount":2,"updatedAt":"2026-11-15T09:00:00Z"},
 {"id":6,"title":"Mine","active":false,"starterKey":null,"days":[],"routineCount":0,"updatedAt":"2026-11-14T09:00:00Z"}]})";
    }

    void startOnPrograms()
    {
        server->responses[path("/programs")] = twoPrograms();
        server->responses[path("/programs/5")] = programJson();
        start();
        QTRY_VERIFY(findVisible("todayPage"));
        nav->navigateTo("programs-page");
        QTRY_VERIFY(findVisible("programsPage"));
        QTRY_COMPARE(countVisible("routineRow"), 2);
    }

    // ---- Programs ----

    void theListMarksTheActiveProgramAndOpensIt()
    {
        startOnPrograms();
        QCOMPARE(countVisible("programRow"), 2);
        QCOMPARE(countVisible("programRowActive"), 1);
        QCOMPARE(find("programTitleField")->property("text").toString(), QStringLiteral("Upper/Lower"));
        QVERIFY(!findVisible("programActivate"));
    }

    void creatingAProgramOpensIt()
    {
        startOnPrograms();
        server->methodResponses["POST " + path("/programs")] = programJson(7);
        click(find("newProgramField"));
        type("Summer");
        click(find("newProgramButton"));
        QTRY_COMPARE(lastBodyTo("POST", "/programs"), QJsonObject({{"title", "Summer"}}));
        QTRY_COMPARE(programs->currentId(), 7);
    }

    void aBlankNameIsCaughtBeforeSending()
    {
        startOnPrograms();
        click(find("newProgramButton"));
        QTRY_VERIFY(findVisible("programsError"));
        QVERIFY(requestsTo("POST", "/programs").isEmpty());
    }

    void renamingOnEnter()
    {
        startOnPrograms();
        server->methodResponses["PUT " + path("/programs/5")] = programJson();
        click(find("programTitleField"));
        QTest::keyClick(window(), Qt::Key_A, Qt::ControlModifier);
        type("UL");
        QTest::keyClick(window(), Qt::Key_Return);
        QTRY_COMPARE(lastBodyTo("PUT", "/programs/5"), QJsonObject({{"title", "UL"}}));
    }

    void theTitleFieldStillFollowsTheOpenProgramAfterARefusedRename()
    {
        startOnPrograms();
        QByteArray mine = programJson(6);
        mine.replace("Upper/Lower", "Mine");
        mine.replace(R"("active":true)", R"("active":false)");
        server->responses[path("/programs/6")] = mine;
        click(find("programTitleField"));
        QTest::keyClick(window(), Qt::Key_A, Qt::ControlModifier);
        QTest::keyClick(window(), Qt::Key_Space);
        QTest::keyClick(window(), Qt::Key_Return);
        QTRY_VERIFY(findVisible("programsError"));
        programs->open(6);
        QTRY_COMPARE(find("programTitleField")->property("text").toString(), QStringLiteral("Mine"));
    }

    void aDayChipSendsTheWholeSet()
    {
        startOnPrograms();
        server->methodResponses["PUT " + path("/programs/5/days")] = programJson();
        click(find("day-2"));
        QTRY_COMPARE(lastBodyTo("PUT", "/programs/5/days").value("days").toArray(), QJsonArray({0, 1, 2, 3, 4}));
    }

    void addingARoutine()
    {
        startOnPrograms();
        server->methodResponses["POST " + path("/routines")] = programJson();
        click(find("newRoutineField"));
        type("Arms");
        click(find("newRoutineButton"));
        QTRY_COMPARE(lastBodyTo("POST", "/routines"), QJsonObject({{"programId", 5}, {"title", "Arms"}}));
    }

    void deletingAProgramAsksFirst()
    {
        startOnPrograms();
        server->methodResponses["DELETE " + path("/programs/5")] = R"({"status":"ok","data":[]})";
        click(find("programDelete"));
        QTRY_VERIFY(findVisible("confirmDialog"));
        click(find("confirmNo"));
        QTRY_VERIFY(!findVisible("confirmDialog"));
        QVERIFY(requestsTo("DELETE", "/programs/5").isEmpty());
        click(find("programDelete"));
        QTRY_VERIFY(findVisible("confirmYes"));
        click(find("confirmYes"));
        QTRY_COMPARE(requestsTo("DELETE", "/programs/5").size(), 1);
        QTRY_COMPARE(programs->currentId(), 0);
    }

    void followingAndDuplicatingAnotherProgram()
    {
        startOnPrograms();
        QByteArray mine = programJson(6);
        mine.replace(R"("active":true)", R"("active":false)");
        server->responses[path("/programs/6")] = mine;
        server->methodResponses["POST " + path("/programs/6/activate")] = twoPrograms();
        server->methodResponses["POST " + path("/programs/6/duplicate")] = programJson(8);
        programs->open(6);
        QTRY_VERIFY(findVisible("programActivate"));
        click(find("programActivate"));
        QTRY_COMPARE(requestsTo("POST", "/programs/6/activate").size(), 1);
        click(find("programDuplicate"));
        QTRY_COMPARE(requestsTo("POST", "/programs/6/duplicate").size(), 1);
    }

    void altDownMovesARoutine()
    {
        startOnPrograms();
        server->methodResponses["POST " + path("/routines/reorder")] = programJson();
        click(find("routineTitle"));
        QTest::keyClick(window(), Qt::Key_Down, Qt::AltModifier);
        QTRY_COMPARE(lastBodyTo("POST", "/routines/reorder"),
                     QJsonObject({{"programId", 5}, {"order", QJsonArray{51, 50}}}));
    }

    void draggingTheGripMovesARoutine()
    {
        startOnPrograms();
        server->methodResponses["POST " + path("/routines/reorder")] = programJson();
        settle();
        settle();
        QQuickItem *grip = find("routineGrip");
        QVERIFY(grip);
        QQuickItem *row = find("routineRow");
        const QPoint from = grip->mapToScene(QPointF(grip->width() / 2, grip->height() / 2)).toPoint();
        const QPoint to = from + QPoint(0, int(row->height() * 1.5));
        QTest::mousePress(window(), Qt::LeftButton, Qt::NoModifier, from);
        for (int step = 1; step <= 10; ++step)
            QTest::mouseMove(window(), from + (to - from) * step / 10, 20);
        QTest::mouseRelease(window(), Qt::LeftButton, Qt::NoModifier, to);
        QTRY_COMPARE(lastBodyTo("POST", "/routines/reorder").value("order").toArray(), QJsonArray({51, 50}));
    }

    void editOpensTheRoutineEditor()
    {
        startOnPrograms();
        click(find("routineEdit"));
        QTRY_COMPARE(nav->currentPage(), QStringLiteral("routine-page"));
        QCOMPARE(programs->currentRoutineId(), 50);
    }

    void aProgramGoneElsewhereClosesAndSaysSo()
    {
        startOnPrograms();
        server->methodStatuses["PUT " + path("/programs/5")] = 404;
        server->methodResponses["PUT " + path("/programs/5")] = R"({"status":"error","message":"not found"})";
        click(find("programTitleField"));
        QTest::keyClick(window(), Qt::Key_A, Qt::ControlModifier);
        type("UL");
        QTest::keyClick(window(), Qt::Key_Return);
        QTRY_VERIFY(findVisible("programsNotice"));
        QVERIFY(!findVisible("programTitleField"));
    }

    // ---- The shell and Settings ----

    void theRailHasTodayProgramsCatalogAndSettings()
    {
        startSignedIn();
        for (const char *name : {"railToday", "railPrograms", "railCatalog", "railSettings", "railSignOut"})
            QVERIFY2(findVisible(name), name);
        click(find("railSettings"));
        QTRY_VERIFY(findVisible("settingsPage"));
    }

    void settingsShowsTheProfileAndSavesAPickAtOnce()
    {
        startSignedIn();
        nav->navigateTo("settings-page");
        QTRY_VERIFY(findVisible("settingsPage"));
        QTRY_COMPARE(find("units-lb")->property("chosen").toBool(), true);
        server->methodResponses["PUT " + path("/profile")] = profileJson("done");
        click(find("units-kg"));
        QTRY_COMPARE(requestsTo("PUT", "/profile").size(), 1);
        QCOMPARE(lastBodyTo("PUT", "/profile"), QJsonObject({{"units", "kg"}}));
    }

    void anIncrementIsCheckedBeforeItIsSaved()
    {
        startSignedIn();
        nav->navigateTo("settings-page");
        QTRY_VERIFY(findVisible("upperIncrementField"));
        click(find("upperIncrementField"));
        QTest::keyClick(window(), Qt::Key_A, Qt::ControlModifier);
        type("0.3");
        QTest::keyClick(window(), Qt::Key_Return);
        QTRY_VERIFY(findVisible("settingsError"));
        QCOMPARE(find("settingsError")->property("text").toString(), QStringLiteral("An increment is 0.25 to 100, in steps of 0.25"));
        QVERIFY(requestsTo("PUT", "/profile").isEmpty());
    }

    void anEquipmentChipSendsTheWholeList()
    {
        startSignedIn();
        nav->navigateTo("settings-page");
        QTRY_VERIFY(findVisible("equipment-dumbbell"));
        click(find("equipment-dumbbell"));
        QTRY_COMPARE(requestsTo("PUT", "/profile").size(), 1);
        QCOMPARE(lastBodyTo("PUT", "/profile").value("equipment").toArray(),
                 QJsonArray({"barbell", "dumbbell", "bodyweight"}));
    }

    void aRefusedSettingSaysWhyAndKeepsTheRest()
    {
        startSignedIn();
        nav->navigateTo("settings-page");
        QTRY_VERIFY(findVisible("goal-muscle"));
        server->methodStatuses["PUT " + path("/profile")] = 503;
        server->methodResponses["PUT " + path("/profile")] = R"({"status":"error","message":"down"})";
        click(find("goal-muscle"));
        QTRY_VERIFY(findVisible("settingsError"));
        QCOMPARE(find("goal-general")->property("chosen").toBool(), true);   // the profile is unchanged
    }

    void devicesAreListedAndAnotherCanBeSignedOut()
    {
        server->responses[path("/devices")] = R"({"status":"ok","data":[
 {"id":"f00dfeedf00dfeed","label":"f00dfeed","current":true,"lastSignIn":"2026-11-05T08:00:00Z"},
 {"id":"0a1b2c3d4e5f6071","label":"0a1b2c3d","current":false,"lastSignIn":null}]})";
        startSignedIn();
        nav->navigateTo("settings-page");
        QTRY_COMPARE(countVisible("deviceRow"), 2);
        QCOMPARE(countVisible("removeDevice"), 1);                 // never on this device's own row
        click(find("removeDevice"));
        QTRY_COMPARE(requestsTo("DELETE", "/devices/0a1b2c3d4e5f6071").size(), 1);
    }

    void resetTheLookRestoresTheTokens()
    {
        startSignedIn();
        preferences->setProperty("accentColor", QColor("#123456"));
        nav->navigateTo("settings-page");
        QTRY_VERIFY(findVisible("resetLook"));
        QTRY_VERIFY(profile->loaded());   // the Training section grows once it has, which moves what is below it
        click(find("resetLook"));
        QTRY_COMPARE(preferences->property("accentColor").value<QColor>(), QColor("#8E5CF5"));
    }

    // ---- The Intro ----

    void aPendingIntroShowsAfterSignIn()
    {
        startInTheIntro();
        QVERIFY(findVisible("introSkip"));
        QCOMPARE(find("introStep")->property("step").toInt(), 0);
    }

    void theAnswersAreSavedOnceAndTheSuggestedStarterShows()
    {
        startInTheIntro();
        walkToTheStarter();
        QCOMPARE(requestsTo("PUT", "/profile").size(), 1);
        QCOMPARE(lastBodyTo("PUT", "/profile"),
                 QJsonObject({{"daysPerWeek", 4}, {"equipment", QJsonArray{"dumbbell", "bodyweight", "bench"}},
                              {"goal", "muscle"}}));
        QCOMPARE(find("introStarterTitle")->property("text").toString(), QStringLiteral("Upper/Lower"));
        QCOMPARE(countVisible("introPreviewRoutine"), 2);
        QVERIFY(findVisible("introMissing"));
    }

    void useThisAdoptsAndLandsOnToday()
    {
        startInTheIntro();
        server->methodResponses["POST " + path("/starters/upperLower/adopt")] = programJson();
        walkToTheStarter();
        click(find("introUseThis"));
        QTRY_COMPARE(requestsTo("POST", "/starters/upperLower/adopt").size(), 1);
        QTRY_COMPARE(lastBodyTo("PUT", "/profile"), QJsonObject({{"introState", "done"}}));
        QTRY_COMPARE(nav->currentPage(), QStringLiteral("today-page"));
        QTRY_VERIFY(findVisible("navShell"));
    }

    void tweakItFirstOpensTheFirstRoutine()
    {
        startInTheIntro();
        server->methodResponses["POST " + path("/starters/upperLower/adopt")] = programJson();
        walkToTheStarter();
        click(find("introTweak"));
        QTRY_COMPARE(nav->currentPage(), QStringLiteral("routine-page"));
        QCOMPARE(programs->currentRoutineId(), 50);
    }

    void buildMyOwnMakesAnEmptyProgram()
    {
        startInTheIntro();
        server->methodResponses["POST " + path("/programs")] = programJson();
        walkToTheStarter();
        click(find("introBuildOwn"));
        QTRY_COMPARE(lastBodyTo("POST", "/programs"), QJsonObject({{"title", "My program"}}));
        QTRY_COMPARE(nav->currentPage(), QStringLiteral("programs-page"));
    }

    void skipFirstTimeMarksItSkippedAndMakesAnEmptyProgram()
    {
        startInTheIntro();
        server->methodResponses["POST " + path("/programs")] = programJson();
        click(find("introSkip"));
        QTRY_COMPARE(lastBodyTo("PUT", "/profile"), QJsonObject({{"introState", "skipped"}}));
        QTRY_COMPARE(lastBodyTo("POST", "/programs"), QJsonObject({{"title", "My program"}}));
        QTRY_COMPARE(nav->currentPage(), QStringLiteral("programs-page"));
    }

    void aReplaysSkipChangesNothing()
    {
        startSignedIn();
        nav->navigateTo("intro-page");
        QTRY_VERIFY(findVisible("introPage"));
        click(find("introNext"));
        QTRY_VERIFY(findVisible("introDays-4"));
        click(find("introSkip"));
        QTRY_COMPARE(nav->currentPage(), QStringLiteral("settings-page"));
        QVERIFY(requestsTo("PUT", "/profile").isEmpty());
        QVERIFY(requestsTo("POST", "/programs").isEmpty());
    }

    void aStarterWithNothingInTheCatalogSaysSo()
    {
        startInTheIntro();
        server->responses[path("/starters")] = startersJson(false);
        walkToTheStarter();
        QVERIFY(findVisible("introUnavailable"));
        QVERIFY(!find("introUseThis")->isEnabled());
        QVERIFY(find("introBuildOwn")->isEnabled());
    }

    void anyoneElsesSaveNeverMovesTheIntro()
    {
        startInTheIntro();
        walkToTheStarter();
        // A program made elsewhere (Programs' own page, say) must not look like this page's Build my own.
        programs->create(QStringLiteral("Elsewhere"));
        QTRY_VERIFY(!requestsTo("POST", "/programs").isEmpty());
        QTest::qWait(300);
        QVERIFY(findVisible("introPage"));
    }

    void anUnknownDeviceShowsTheForm()
    {
        server->responses[path("/device/identify")] = R"({"status":"new"})";
        start();
        QTRY_VERIFY(findVisible("usernameField"));
        QVERIFY(!findVisible("catalogPage"));
        QVERIFY(!findVisible("keyField"));
    }

    void aWrongPasswordSaysSo()
    {
        server->responses[path("/device/identify")] = R"({"status":"new"})";
        server->statuses[path("/auth")] = 401;
        server->responses[path("/auth")] = R"({"status":"invalid_credentials","message":"invalid_credentials"})";
        start();
        QTRY_VERIFY(findVisible("usernameField"));
        click(find("usernameField"));
        type("stub");
        click(find("passwordField"));
        type("nope-nope-nope");
        click(find("loginButton"));
        QTRY_VERIFY(findVisible("loginError"));
        QCOMPARE(find("loginError")->property("text").toString(), QStringLiteral("Wrong username or password"));
    }

    void signingUpSendsTheKey()
    {
        server->responses[path("/device/identify")] = R"({"status":"new"})";
        server->responses[path("/auth")] = signedIn;
        start();
        QTRY_VERIFY(findVisible("usernameField"));
        click(find("usernameField"));
        type("newbie");
        click(find("passwordField"));
        type("long-enough");
        click(find("keyBox"));
        QTRY_VERIFY(findVisible("keyField"));
        click(find("keyField"));
        type("stub-key");
        click(find("loginButton"));
        QTRY_VERIFY(findVisible("todayPage"));
        QCOMPARE(lastBodyTo("/auth").value("key").toString(), QStringLiteral("stub-key"));
        QCOMPARE(lastBodyTo("/auth").value("username").toString(), QStringLiteral("newbie"));
    }

    void aShortPasswordIsCaughtBeforeAnythingIsSent()
    {
        server->responses[path("/device/identify")] = R"({"status":"new"})";
        start();
        QTRY_VERIFY(findVisible("usernameField"));
        click(find("usernameField"));
        type("newbie");
        click(find("passwordField"));
        type("short");
        click(find("keyBox"));
        QTRY_VERIFY(findVisible("keyField"));
        click(find("keyField"));
        type("stub-key");
        click(find("loginButton"));
        QTRY_VERIFY(findVisible("loginError"));
        QCOMPARE(find("loginError")->property("text").toString(), QStringLiteral("A password is 8 to 256 characters"));
        QVERIFY(requestsTo("/auth").isEmpty());
    }

    void aTakenUsernameIsWordedByThePage()
    {
        server->responses[path("/device/identify")] = R"({"status":"new"})";
        server->statuses[path("/auth")] = 409;
        server->responses[path("/auth")] = R"({"status":"username_taken","message":"username_taken"})";
        start();
        QTRY_VERIFY(findVisible("usernameField"));
        click(find("usernameField"));
        type("taken");
        click(find("passwordField"));
        type("long-enough");
        click(find("keyBox"));
        QTRY_VERIFY(findVisible("keyField"));
        click(find("keyField"));
        type("stub-key");
        click(find("loginButton"));
        QTRY_COMPARE(find("loginError")->property("text").toString(), QStringLiteral("That username is taken"));
    }

    void noServerAndNoAccountHereShowsTheConnectionScreen()
    {
        api->setBases(QString(), QStringLiteral("http://127.0.0.1:1/api/pride"));
        api->setPingDelays(60000, 60000);
        start();
        QTRY_VERIFY_WITH_TIMEOUT(findVisible("unreachable"), 10000);
        QVERIFY(!findVisible("usernameField"));
    }

    void signingOutReturnsToSignIn()
    {
        startSignedIn();
        click(find("railSignOut"));
        QTRY_VERIFY(findVisible("loginPage"));
        QTRY_COMPARE(requestsTo("/signout").size(), 1);
        QVERIFY(!session->authenticated());
    }

    void theBannerShowsWhileTheServerIsAway()
    {
        // The tunnel's own page for a server that is down: the app is offline, and says so under the top bar.
        server->statuses[path("/catalog")] = 502;
        server->responses[path("/catalog")] = "<html>origin unreachable</html>";
        nav->setStartPage("catalog-page");
        start();
        QTRY_VERIFY(findVisible("catalogPage"));
        QTRY_VERIFY(findVisible("offlineBanner"));
    }

    void theBannerIsHiddenWhileOnline()
    {
        startSignedIn();
        QVERIFY(find("offlineBanner"));
        QVERIFY(!findVisible("offlineBanner"));
    }

    void aSessionEndedMidwayReturnsToSignIn()
    {
        startSignedIn();
        server->statuses[path("/catalog")] = 401;
        server->responses[path("/catalog")] = R"({"status":"error","message":"not signed in"})";
        exercises->refresh();
        QTRY_VERIFY(findVisible("loginPage"));
        QVERIFY(!session->authenticated());
    }

    // ---- The Catalog page ----

    void theCatalogNeverSaysUnavailableBeforeItsFirstAnswer()
    {
        server->holdNext[path("/catalog")] = 1;
        nav->setStartPage("catalog-page");
        start();
        QTRY_VERIFY(findVisible("catalogPage"));
        QTRY_COMPARE(requestsTo("/catalog").size(), 1);
        QVERIFY(findVisible("catalogLoading"));
        QVERIFY(!findVisible("catalogUnavailable"));
        server->releaseHeld();
        QTRY_COMPARE(countVisible("exerciseTile"), 3);
    }

    void theTilesAreTheShownCatalog()
    {
        startSignedIn();
        QTRY_COMPARE(countVisible("exerciseTile"), 3);
        QCOMPARE(find("catalogCount")->property("text").toString(), QStringLiteral("3 exercises"));
    }

    void aFilterChipNarrowsTheTilesAndResetBringsThemBack()
    {
        startSignedIn();
        QTRY_VERIFY(findVisible("chip-equipment-barbell"));
        click(find("chip-equipment-barbell"));
        QTRY_COMPARE(countVisible("exerciseTile"), 1);
        QCOMPARE(find("catalogCount")->property("text").toString(), QStringLiteral("1 of 3 exercises"));
        QTRY_VERIFY(findVisible("resetFilters"));
        click(find("resetFilters"));
        QTRY_COMPARE(countVisible("exerciseTile"), 3);
        QVERIFY(!findVisible("resetFilters"));
    }

    void typingNarrowsByName()
    {
        startSignedIn();
        click(find("catalogFilterField"));
        type("curl");
        QTRY_COMPARE(countVisible("exerciseTile"), 1);
        QCOMPARE(catalog->text(), QStringLiteral("curl"));
    }

    void nothingMatchingSaysSo()
    {
        startSignedIn();
        click(find("catalogFilterField"));
        type("zzz");
        QTRY_VERIFY(findVisible("nothingMatches"));
        QCOMPARE(countVisible("exerciseTile"), 0);
    }

    void anEmptyCatalogWithNoServerSaysSo()
    {
        // This account signed in here before, but the catalog never arrived, and now there is no server: an offline
        // start on nothing. The page says so and offers Try again, never an empty grid with no words.
        accounts->open(7, "stub");
        accounts->close();
        api->setBases(QString(), QStringLiteral("http://127.0.0.1:1/api/pride"));
        api->setPingDelays(60000, 60000);
        nav->setStartPage("catalog-page");
        start();
        QTRY_VERIFY_WITH_TIMEOUT(findVisible("catalogUnavailable"), 10000);
        QVERIFY(findVisible("catalogRetry"));
        QVERIFY(!findVisible("filterPanel"));
        QCOMPARE(countVisible("exerciseTile"), 0);
    }

    void aPictureThatDoesNotComeShowsThePlaceholder()
    {
        server->statuses[path("/pictures/0123456789abcdef0123.jpg")] = 404;
        startSignedIn();
        QTRY_COMPARE(countVisible("exerciseTile"), 3);
        QTRY_COMPARE(requestsTo("/pictures/0123456789abcdef0123.jpg").size(), 1);
        QTest::qWait(200);
        // Every tile shows the placeholder: Barbell Curl's picture failed, the other two have none.
        QCOMPARE(countVisible("picturePlaceholder"), 3);
    }

    void aPictureThatComesReplacesThePlaceholder()
    {
        server->responses[path("/pictures/0123456789abcdef0123.jpg")] = pictureBytes();
        startSignedIn();
        QTRY_COMPARE(countVisible("picture"), 1);
        QCOMPARE(countVisible("picturePlaceholder"), 2);
        QVERIFY(QFile::exists(dataDir + "/catalog/pictures/" + pictureOne));
    }

    // ---- The Exercise page and Ctrl+K ----

    void aTileOpensItsExercise()
    {
        startSignedIn();
        click(find("catalogFilterField"));
        type("curl");
        QTRY_COMPARE(countVisible("exerciseTile"), 1);
        click(find("exerciseTile"));
        QTRY_VERIFY(findVisible("exercisePage"));
        QCOMPARE(find("exerciseName")->property("text").toString(), QStringLiteral("Barbell Curl"));
        QCOMPARE(find("exercisePrimary")->property("text").toString(), QStringLiteral("Biceps"));
        QCOMPARE(find("exerciseSecondary")->property("text").toString(), QStringLiteral("Forearms"));
        QCOMPARE(find("exerciseEquipment")->property("text").toString(), QStringLiteral("Barbell"));
        QCOMPARE(countVisible("exerciseStep"), 3);
        QVERIFY(find("exerciseCredit")->property("text").toString().contains(QStringLiteral("public domain")));
        QVERIFY(!findVisible("exerciseGone"));
    }

    void theSecondPictureIsOneClickAway()
    {
        startSignedIn();
        catalog->open(1);
        nav->navigateTo("exercise-page");
        QTRY_VERIFY(findVisible("pictureChip1"));
        QCOMPARE(find("exercisePicture")->property("name").toString(), pictureOne);
        click(find("pictureChip1"));
        QTRY_COMPARE(find("exercisePicture")->property("name").toString(), pictureTwo);
    }

    void anExerciseWithoutPicturesShowsThePlaceholder()
    {
        startSignedIn();
        catalog->open(5);
        nav->navigateTo("exercise-page");
        QTRY_VERIFY(findVisible("exercisePage"));
        QCOMPARE(find("exercisePicture")->property("name").toString(), QString());
        QVERIFY(findIn(find("exercisePicture"), "picturePlaceholder", true));
        QVERIFY(!findVisible("pictureChip0"));
        QVERIFY(findVisible("exerciseNoSteps"));
        QVERIFY(!findVisible("exerciseSecondary"));
    }

    void anExerciseThatLeftTheCatalogStillOpensAndSaysSo()
    {
        startSignedIn();
        catalog->open(9);
        nav->navigateTo("exercise-page");
        QTRY_VERIFY(findVisible("exerciseGone"));
        QCOMPARE(find("exerciseName")->property("text").toString(), QStringLiteral("Old Row"));
    }

    void anExerciseNotInTheCatalogSaysSo()
    {
        startSignedIn();
        catalog->open(999);
        nav->navigateTo("exercise-page");
        QTRY_VERIFY(findVisible("exerciseMissing"));
        QVERIFY(!findVisible("exerciseName"));
        QVERIFY(findVisible("exerciseBack"));
    }

    void backReturnsToTheCatalog()
    {
        startSignedIn();
        click(find("chip-equipment-barbell"));
        QTRY_COMPARE(countVisible("exerciseTile"), 1);
        click(find("exerciseTile"));
        QTRY_VERIFY(findVisible("exercisePage"));
        click(find("exerciseBack"));
        QTRY_VERIFY(findVisible("catalogPage"));
        // The filters are as they were left.
        QTRY_COMPARE(countVisible("exerciseTile"), 1);
    }

    void ctrlKFindsAnExerciseAndEnterOpensIt()
    {
        startSignedIn();
        QTest::keyClick(window(), Qt::Key_K, Qt::ControlModifier);
        QTRY_VERIFY(find("quickSearchField")->hasActiveFocus());
        type("pull");
        QTRY_VERIFY(findVisible("quickSearchRow"));
        QCOMPARE(countVisible("quickSearchRow"), 1);
        QTest::keyClick(window(), Qt::Key_Return);
        QTRY_VERIFY(findVisible("exercisePage"));
        QCOMPARE(find("exerciseName")->property("text").toString(), QStringLiteral("Pullups"));
        QVERIFY(!findVisible("quickSearchResults"));
    }

    void ctrlKFollowsACatalogChange()
    {
        startSignedIn();
        QTest::keyClick(window(), Qt::Key_K, Qt::ControlModifier);
        QTRY_VERIFY(find("quickSearchField")->hasActiveFocus());
        type("pull");
        QTRY_COMPARE(countVisible("quickSearchRow"), 1);
        // Pullups leaves the catalog while the list is open.
        QByteArray changed = catalogJson();
        changed.replace(R"("version":"v1")", R"("version":"v2")");
        const QByteArray before = R"("level":"beginner","measure":"reps","region":"upper","removed":false)";
        QVERIFY(changed.contains(before));
        changed.replace(before, R"("level":"beginner","measure":"reps","region":"upper","removed":true)");
        server->responses[path("/catalog")] = changed;
        exercises->refresh();
        QTRY_VERIFY(findVisible("quickSearchNothing"));
        QCOMPARE(countVisible("quickSearchRow"), 0);
    }

    void ctrlKWithNoMatchSaysSoAndEscapeCloses()
    {
        startSignedIn();
        QTest::keyClick(window(), Qt::Key_K, Qt::ControlModifier);
        QTRY_VERIFY(find("quickSearchField")->hasActiveFocus());
        type("row");
        // Old Row has left the catalog, so nothing is found.
        QTRY_VERIFY(findVisible("quickSearchNothing"));
        QTest::keyClick(window(), Qt::Key_Escape);
        QTRY_VERIFY(!findVisible("quickSearchResults"));
        QCOMPARE(find("quickSearchField")->property("text").toString(), QString());
    }

    // ---- The Routine editor ----

    void startInTheEditor(const QByteArray &answer = QByteArray())
    {
        server->responses[path("/programs")] = twoPrograms();
        server->responses[path("/programs/5")] = answer.isEmpty() ? programJson() : answer;
        start();
        QTRY_VERIFY(findVisible("todayPage"));
        programs->open(5);
        QTRY_COMPARE(programs->currentId(), 5);
        programs->openRoutine(50);
        nav->navigateTo("routine-page");
        QTRY_VERIFY(findVisible("routinePage"));
        QTRY_COMPARE(countVisible("itemRow"), 1);
    }

    void replaceText(const char *name, const QString &text)
    {
        click(find(name));
        QTest::keyClick(window(), Qt::Key_A, Qt::ControlModifier);
        type(text);
        QTest::keyClick(window(), Qt::Key_Return);
    }

    void theEditorShowsItsItems()
    {
        startInTheEditor();
        QCOMPARE(find("routineNameField")->property("text").toString(), QStringLiteral("Upper"));
        QCOMPARE(find("itemName")->property("text").toString(), QStringLiteral("Barbell Curl"));
        QCOMPARE(find("itemSets")->property("text").toString(), QStringLiteral("3"));
        QCOMPARE(find("itemWeight")->property("text").toString(), QStringLiteral("135"));
        QCOMPARE(find("itemRest")->property("text").toString(), QStringLiteral("1:30"));
        QVERIFY(!findVisible("itemGone"));
    }

    void changingOneFieldSendsTheWholeRow()
    {
        startInTheEditor();
        server->methodResponses["PUT " + path("/routine-items/500")] = programJson();
        replaceText("itemSets", "4");
        QTRY_COMPARE(requestsTo("PUT", "/routine-items/500").size(), 1);
        const QJsonObject sent = lastBodyTo("PUT", "/routine-items/500");
        QCOMPARE(sent.value("sets").toInt(), 4);
        QCOMPARE(sent.value("repsMin").toInt(), 8);
        QCOMPARE(sent.value("targetWeight").toDouble(), 135.0);
        QCOMPARE(sent.value("targetUnit").toString(), QStringLiteral("lb"));
        QCOMPARE(sent.value("restSeconds").toInt(), 90);
        QVERIFY(sent.contains("note") && sent.value("note").isNull());
    }

    void aReversedRangeIsCaughtBeforeSending()
    {
        startInTheEditor();
        replaceText("itemRepsMin", "15");
        QTRY_VERIFY(findVisible("itemError"));
        QCOMPARE(find("itemError")->property("text").toString(),
                 QStringLiteral("The top of the range is 1 to 100, and not below the bottom"));
        QVERIFY(requestsTo("PUT", "/routine-items/500").isEmpty());
        QCOMPARE(find("itemRepsMin")->property("text").toString(), QStringLiteral("15"));
    }

    void anOfflineSaveKeepsWhatWasTyped()
    {
        startInTheEditor();
        api->setBases(QString(), QStringLiteral("http://127.0.0.1:1/api/pride"));
        api->setPingDelays(60000, 60000);
        replaceText("itemSets", "4");
        QTRY_VERIFY_WITH_TIMEOUT(findVisible("itemError"), 10000);
        QCOMPARE(find("itemError")->property("text").toString(),
                 QStringLiteral("Can't reach Pride right now. Nothing was lost; try again."));
        QCOMPARE(find("itemSets")->property("text").toString(), QStringLiteral("4"));
    }

    void thePickerFollowsTheProfilesEquipmentAndAdds()
    {
        startInTheEditor();
        server->methodResponses["POST " + path("/routine-items")] = programJson();
        click(find("addExercise"));
        QTRY_VERIFY(findVisible("exercisePicker"));
        // The profile has barbell and bodyweight: Barbell Curl fits; Kettlebell Halo and Pullups (a pull-up bar) don't.
        QTRY_COMPARE(countVisible("pickerRow"), 1);
        click(find("pickerEverything"));
        QTRY_COMPARE(countVisible("pickerRow"), 3);
        // The rows are replaced as the list grows; the click waits for the new ones to be laid out.
        settle();
        QTRY_VERIFY(findVisible("pickerRow") && findVisible("pickerRow")->height() > 0);
        click(findVisible("pickerRow"));
        QTRY_COMPARE(lastBodyTo("POST", "/routine-items"), QJsonObject({{"routineId", 50}, {"exerciseId", 1}}));
        QTRY_VERIFY(!findVisible("exercisePicker"));
    }

    void aRemovedExerciseIsStillNamedInTheEditor()
    {
        QByteArray answer = programJson();
        answer.replace(R"("id":500,"exerciseId":1)", R"("id":500,"exerciseId":9)");
        startInTheEditor(answer);
        QCOMPARE(find("itemName")->property("text").toString(), QStringLiteral("Old Row"));
        QVERIFY(findVisible("itemGone"));
    }

    void removingAndReorderingItems()
    {
        QByteArray two = programJson();
        two.replace(R"("restSeconds":90,"note":null}]})",
                    R"("restSeconds":90,"note":null},{"id":501,"exerciseId":7,"sets":3,"repsMin":5,"repsMax":8,"targetWeight":null,"targetUnit":null,"targetSeconds":null,"targetDistance":null,"distanceUnit":null,"restSeconds":null,"note":null}]})");
        server->responses[path("/programs")] = twoPrograms();
        server->responses[path("/programs/5")] = two;
        start();
        QTRY_VERIFY(findVisible("todayPage"));
        programs->open(5);
        QTRY_COMPARE(programs->currentId(), 5);
        programs->openRoutine(50);
        nav->navigateTo("routine-page");
        QTRY_COMPARE(countVisible("itemRow"), 2);
        server->methodResponses["POST " + path("/routine-items/reorder")] = two;
        click(find("itemName"));
        QTest::keyClick(window(), Qt::Key_Down, Qt::AltModifier);
        QTRY_COMPARE(lastBodyTo("POST", "/routine-items/reorder"),
                     QJsonObject({{"routineId", 50}, {"order", QJsonArray{501, 500}}}));
        server->methodResponses["DELETE " + path("/routine-items/500")] = programJson();
        click(find("itemDelete"));
        QTRY_COMPARE(requestsTo("DELETE", "/routine-items/500").size(), 1);
    }

    void renamingTheRoutine()
    {
        startInTheEditor();
        server->methodResponses["PUT " + path("/routines/50")] = programJson();
        replaceText("routineNameField", "Upper A");
        QTRY_COMPARE(lastBodyTo("PUT", "/routines/50"), QJsonObject({{"title", "Upper A"}}));
    }

    // The program with routine 50's one item replaced by `item` (an item's JSON).
    static QByteArray programWithItem(const QByteArray &item)
    {
        QByteArray answer = programJson();
        const QByteArray tail = R"("note":null})";
        const int start = answer.indexOf(R"({"id":500)");
        const int end = answer.indexOf(tail, start) + tail.size();
        answer.replace(start, end - start, item);
        return answer;
    }

    // Pullups (7) as a distance item holding 5 in `unit` and `seconds` (JSON text) for its time.
    static QByteArray distanceItem(const QByteArray &seconds, const QByteArray &unit)
    {
        return "{\"id\":500,\"exerciseId\":7,\"sets\":1,\"repsMin\":null,\"repsMax\":null,\"targetWeight\":null,"
               "\"targetUnit\":null,\"targetSeconds\":" + seconds + ",\"targetDistance\":5,\"distanceUnit\":\"" + unit
               + "\",\"restSeconds\":null,\"note\":null}";
    }

    // Kettlebell Halo (5) becomes a timed exercise and Pullups (7) a distance one, which the fixture has none of.
    void makeTimedAndDistanceExercises()
    {
        QByteArray changed = catalogJson();
        const QByteArray halo = R"("measure":"weight_reps","region":"upper","removed":false,
  "primary":["shoulders"])";
        const QByteArray pullups = R"("measure":"reps","region":"upper","removed":false,
  "primary":["lats"])";
        QVERIFY(changed.contains(halo) && changed.contains(pullups));
        changed.replace(halo, QByteArray(halo).replace("weight_reps", "time"));
        changed.replace(pullups, QByteArray(pullups).replace("\"reps\"", "\"distance_time\""));
        server->responses[path("/catalog")] = changed;
    }

    void aTimeRowSavesItsSeconds()
    {
        makeTimedAndDistanceExercises();
        startInTheEditor(programWithItem(R"({"id":500,"exerciseId":5,"sets":3,"repsMin":null,"repsMax":null,"targetWeight":null,"targetUnit":null,"targetSeconds":30,"targetDistance":null,"distanceUnit":null,"restSeconds":null,"note":null})"));
        QCOMPARE(find("itemSeconds")->property("text").toString(), QStringLiteral("0:30"));
        QVERIFY(!findVisible("itemWeight"));
        server->methodResponses["PUT " + path("/routine-items/500")] = programJson();
        replaceText("itemSeconds", "1:30");
        QTRY_COMPARE(requestsTo("PUT", "/routine-items/500").size(), 1);
        const QJsonObject sent = lastBodyTo("PUT", "/routine-items/500");
        QCOMPARE(sent.value("targetSeconds").toInt(), 90);
        QCOMPARE(sent.value("sets").toInt(), 3);
        QVERIFY(sent.value("repsMin").isNull() && sent.value("targetWeight").isNull());
    }

    void aDistanceRowSavesDistanceUnitAndSeconds()
    {
        makeTimedAndDistanceExercises();
        const QByteArray item = R"({"id":500,"exerciseId":7,"sets":1,"repsMin":null,"repsMax":null,"targetWeight":null,"targetUnit":null,"targetSeconds":null,"targetDistance":null,"distanceUnit":null,"restSeconds":null,"note":null})";
        startInTheEditor(programWithItem(item));
        QVERIFY(findVisible("itemDistance") && findVisible("itemDistanceSeconds"));
        QVERIFY(!findVisible("itemSeconds") && !findVisible("itemWeight"));
        // Each answer is the program as the server would now hold it, so the rebuilt row is still a distance row.
        server->methodResponses["PUT " + path("/routine-items/500")] = programWithItem(distanceItem("null", "mi"));
        replaceText("itemDistance", "5");
        QTRY_COMPARE(requestsTo("PUT", "/routine-items/500").size(), 1);
        // The profile counts in pounds, so the distance starts in miles.
        QJsonObject sent = lastBodyTo("PUT", "/routine-items/500");
        QCOMPARE(sent.value("targetDistance").toDouble(), 5.0);
        QCOMPARE(sent.value("distanceUnit").toString(), QStringLiteral("mi"));
        QVERIFY(sent.value("targetSeconds").isNull());
        server->methodResponses["PUT " + path("/routine-items/500")] = programWithItem(distanceItem("1500", "mi"));
        settle();
        replaceText("itemDistanceSeconds", "25:00");
        QTRY_COMPARE(requestsTo("PUT", "/routine-items/500").size(), 2);
        sent = lastBodyTo("PUT", "/routine-items/500");
        QCOMPARE(sent.value("targetSeconds").toInt(), 1500);
        QCOMPARE(sent.value("targetDistance").toDouble(), 5.0);
        server->methodResponses["PUT " + path("/routine-items/500")] = programWithItem(distanceItem("1500", "km"));
        settle();
        click(find("itemDistanceUnit-km"));
        QTRY_COMPARE(requestsTo("PUT", "/routine-items/500").size(), 3);
        QCOMPARE(lastBodyTo("PUT", "/routine-items/500").value("distanceUnit").toString(), QStringLiteral("km"));
    }

    void choosingTheWeightUnitSendsIt()
    {
        startInTheEditor();
        server->methodResponses["PUT " + path("/routine-items/500")] = programJson();
        click(find("itemUnit-kg"));
        QTRY_COMPARE(requestsTo("PUT", "/routine-items/500").size(), 1);
        const QJsonObject sent = lastBodyTo("PUT", "/routine-items/500");
        QCOMPARE(sent.value("targetUnit").toString(), QStringLiteral("kg"));
        QCOMPARE(sent.value("targetWeight").toDouble(), 135.0);
    }

    void withNoRoutineOpenTheEditorSaysSoAndGoesBack()
    {
        server->responses[path("/programs")] = twoPrograms();
        start();
        QTRY_VERIFY(findVisible("todayPage"));
        nav->navigateTo("routine-page");
        QTRY_VERIFY(findVisible("routineMissing"));
        QVERIFY(!findVisible("addExercise"));
        click(find("routineMissingBack"));
        QTRY_COMPARE(nav->currentPage(), QStringLiteral("programs-page"));
    }

    void anExerciseTheCatalogDoesNotKnowShowsOnlyItsNameAndRemove()
    {
        startInTheEditor(programWithItem(R"({"id":500,"exerciseId":99,"sets":3,"repsMin":8,"repsMax":12,"targetWeight":null,"targetUnit":null,"targetSeconds":null,"targetDistance":null,"distanceUnit":null,"restSeconds":null,"note":null})"));
        QCOMPARE(find("itemName")->property("text").toString(), QStringLiteral("An exercise this device doesn't know"));
        QVERIFY(findVisible("itemGone"));
        QVERIFY(findVisible("itemDelete"));
        QVERIFY(!findVisible("itemSets") && !findVisible("itemNote"));
    }

    void anItemGoneElsewhereLandsOnProgramsWithTheNotice()
    {
        startInTheEditor();
        server->methodStatuses["PUT " + path("/routine-items/500")] = 404;
        server->methodResponses["PUT " + path("/routine-items/500")] = R"({"status":"error","message":"not found"})";
        replaceText("itemSets", "4");
        QTRY_COMPARE(nav->currentPage(), QStringLiteral("programs-page"));
        QTRY_VERIFY(findVisible("programsNotice"));
        QCOMPARE(find("programsNotice")->property("text").toString(),
                 QStringLiteral("That was changed or removed on another device, so it's been closed here."));
    }

    void todayNamesAnExerciseItDoesNotKnow()
    {
        server->responses[path("/today")] = todayJson(R"([{"id":511,"exerciseId":99,"sets":3,"repsMin":8,"repsMax":12,
 "targetWeight":null,"targetUnit":null,"targetSeconds":null,"targetDistance":null,"distanceUnit":null,"restSeconds":null,"note":null}])");
        startOnToday();
        QTRY_COMPARE(countVisible("todayItem"), 1);
        QCOMPARE(find("todayItemName")->property("text").toString(), QStringLiteral("An exercise this device doesn't know"));
        QVERIFY(findVisible("todayItemGone"));
    }

    // ---- Own exercises and Add to a routine ----

    // Built from plain strings: moc stumbles on a raw string that opens a brace it does not close.
    static QByteArray sandbag(int id = 900, const char *name = "Sandbag Carry")
    {
        const QByteArray fields = R"("key":"own-0123456789abcdef","source":"own","licence":null,"category":null,)"
                                  R"("level":null,"measure":"distance_time","region":"upper","removed":false,)"
                                  R"("primary":["forearms"],"secondary":[],"equipment":["other"],"steps":["Walk."],"pictures":[])";
        return "{\"id\":" + QByteArray::number(id) + ",\"name\":\"" + name + "\"," + fields + "}";
    }

    void addingAnOwnExerciseOpensIt()
    {
        server->methodResponses["POST " + path("/exercises")] = "{\"status\":\"ok\",\"data\":" + sandbag() + "}";
        startSignedIn();
        click(find("addOwnExercise"));
        QTRY_VERIFY(findVisible("ownForm"));
        click(find("ownName"));
        type("Sandbag Carry");
        click(find("ownMeasure-distance_time"));
        click(find("ownPrimary-forearms"));
        click(find("ownEquipment-other"));
        click(find("ownSave"));
        QTRY_COMPARE(requestsTo("POST", "/exercises").size(), 1);
        const QJsonObject sent = lastBodyTo("POST", "/exercises");
        QCOMPARE(sent.value("name").toString(), QStringLiteral("Sandbag Carry"));
        QCOMPARE(sent.value("primary").toArray(), QJsonArray({"forearms"}));
        QTRY_VERIFY(findVisible("exercisePage"));
        QCOMPARE(find("exerciseName")->property("text").toString(), QStringLiteral("Sandbag Carry"));
    }

    void ownExerciseFormKeepsItsFieldsWhenRefused()
    {
        server->methodStatuses["POST " + path("/exercises")] = 503;
        server->methodResponses["POST " + path("/exercises")] = R"({"status":"error","message":"down"})";
        startSignedIn();
        click(find("addOwnExercise"));
        QTRY_VERIFY(findVisible("ownForm"));
        click(find("ownSave"));                       // nothing filled in: caught before sending
        QTRY_VERIFY(findVisible("ownError"));
        QCOMPARE(find("ownError")->property("text").toString(), QStringLiteral("A name is 1 to 120 characters"));
        QVERIFY(requestsTo("POST", "/exercises").isEmpty());
        click(find("ownName"));
        type("Sandbag Carry");
        click(find("ownMeasure-distance_time"));
        click(find("ownPrimary-forearms"));
        click(find("ownEquipment-other"));
        click(find("ownSave"));
        QTRY_COMPARE(find("ownError")->property("text").toString(), QStringLiteral("Pride couldn't do that just now. Try again."));
        QVERIFY(findVisible("ownForm"));
        QCOMPARE(find("ownName")->property("text").toString(), QStringLiteral("Sandbag Carry"));
    }

    void mineNarrowsToOwnExercises()
    {
        server->responses[path("/exercises")] = "{\"status\":\"ok\",\"data\":[" + sandbag() + "]}";
        startSignedIn();
        QTRY_VERIFY(findVisible("chip-mine-mine"));
        QTRY_COMPARE(countVisible("exerciseTile"), 4);
        click(find("chip-mine-mine"));
        QTRY_COMPARE(countVisible("exerciseTile"), 1);
    }

    void editingAndDeletingAnOwnExercise()
    {
        server->responses[path("/exercises")] = "{\"status\":\"ok\",\"data\":[" + sandbag() + "]}";
        server->methodResponses["PUT " + path("/exercises/900")] = "{\"status\":\"ok\",\"data\":" + sandbag(900, "Sandbag Walk") + "}";
        server->methodResponses["DELETE " + path("/exercises/900")] = R"({"status":"ok","data":{"routinesTouched":1,"hidden":false}})";
        startSignedIn();
        QTRY_COMPARE(catalog->own().size(), 1);
        catalog->open(900);
        nav->navigateTo("exercise-page");
        QTRY_VERIFY(findVisible("editOwn"));
        QVERIFY(find("exerciseCredit")->property("text").toString().contains(QStringLiteral("your own")));
        click(find("editOwn"));
        QTRY_VERIFY(findVisible("ownForm"));
        QCOMPARE(find("ownName")->property("text").toString(), QStringLiteral("Sandbag Carry"));
        click(find("ownName"));
        QTest::keyClick(window(), Qt::Key_A, Qt::ControlModifier);
        type("Sandbag Walk");
        click(find("ownSave"));
        QTRY_COMPARE(lastBodyTo("PUT", "/exercises/900").value("name").toString(), QStringLiteral("Sandbag Walk"));
        QTRY_VERIFY(!findVisible("ownForm"));
        click(find("deleteOwn"));
        QTRY_VERIFY(findVisible("confirmYes"));
        click(find("confirmYes"));
        QTRY_COMPARE(requestsTo("DELETE", "/exercises/900").size(), 1);
        QTRY_VERIFY(findVisible("catalogPage"));
    }

    void addingToARoutineFromTheExercisePage()
    {
        server->responses[path("/programs")] = twoPrograms();
        server->responses[path("/programs/5")] = programJson();
        server->methodResponses["POST " + path("/routine-items")] = programJson();
        startSignedIn();
        catalog->open(7);
        nav->navigateTo("exercise-page");
        QTRY_VERIFY(findVisible("addToRoutine"));
        click(find("addToRoutine"));
        QTRY_VERIFY(findVisible("addToRoutinePopup"));
        QTRY_COMPARE(countVisible("addProgramRow"), 2);
        click(find("addProgramRow"));                  // the active one is listed first
        QTRY_COMPARE(countVisible("addRoutineRow"), 2);
        click(find("addRoutineRow"));
        QTRY_COMPARE(lastBodyTo("POST", "/routine-items"), QJsonObject({{"routineId", 50}, {"exerciseId", 7}}));
        QTRY_VERIFY(findVisible("addToRoutineDone"));
    }

    void aRemovedExerciseCannotBeAddedToARoutine()
    {
        startSignedIn();
        catalog->open(9);
        nav->navigateTo("exercise-page");
        QTRY_VERIFY(findVisible("exerciseGone"));
        QVERIFY(!findVisible("addToRoutine"));
    }
};

QTEST_MAIN(TestPages)
#include "tst_pages.moc"
