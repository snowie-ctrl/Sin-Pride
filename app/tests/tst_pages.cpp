// Gluttony's app/tests/tst_pages.cpp at c1ed705 is the model: the real Main.qml, NavShell and pages over the real
// services, the server faked, clicks sent to the offscreen window only. Each page task adds its cases here.
#include <QBuffer>
#include <QDir>
#include <QFile>
#include <QImage>
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

    void click(QQuickItem *item)
    {
        QVERIFY(item);
        // A page lays itself out in the frame after it appears; without this wait a click now and then landed beside
        // its target on a busy machine (Gluttony's lesson).
        QSignalSpy framed(window(), &QQuickWindow::frameSwapped);
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
        engine->loadFromModule("Pride", "Main");
        QVERIFY(window());
        window()->resize(1600, 1000);
        session->identifyDevice();
    }

    // Signed in and on the Catalog, the catalog arrived.
    void startSignedIn()
    {
        start();
        QTRY_VERIFY(findVisible("catalogPage"));
        QTRY_COMPARE(catalog->shownCount(), 3);
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
        // A fresh data folder each test: no account and no catalog copy carry over.
        dataDir = dir.filePath(QStringLiteral("data-%1").arg(++runs));
        preferences = std::make_unique<Preferences>();
        api = std::make_unique<Api>();
        api->setBases(QString(), QStringLiteral("http://127.0.0.1:%1/api/pride").arg(server->serverPort()));
        nav = std::make_unique<Nav>();
        accounts = std::make_unique<AccountStore>(dataDir);
        session = std::make_unique<Session>(*api);
        exercises = std::make_unique<ExerciseStore>(*api, dataDir);
        catalog = std::make_unique<Catalog>(*exercises);
        wireServices(*session, *accounts, *exercises, *catalog);
    }

    void cleanup()
    {
        engine.reset();
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

    void aKnownDeviceGoesStraightToTheCatalog()
    {
        start();
        QTRY_VERIFY(findVisible("catalogPage"));
        QVERIFY(findVisible("railCatalog"));
        // Signing in asks for the catalog.
        QTRY_COMPARE(requestsTo("/catalog").size(), 1);
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
        type("nope");
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

    // ---- The Catalog page ----

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
};

QTEST_MAIN(TestPages)
#include "tst_pages.moc"
