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

    // Until the Today page exists (a later task's) the shell shows nothing for today-page, so this checks where Nav
    // is and what was asked for.
    void aKnownDeviceLandsOnTodayAndLoadsWhatIsTheirs()
    {
        start();
        QTRY_VERIFY(findVisible("navShell"));
        QCOMPARE(nav->currentPage(), QStringLiteral("today-page"));
        for (const char *route : {"/catalog", "/profile", "/programs", "/today", "/exercises"})
            QTRY_COMPARE(requestsTo(route).size(), 1);
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
        QTRY_VERIFY(findVisible("catalogPage"));
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
};

QTEST_MAIN(TestPages)
#include "tst_pages.moc"
