#include <QBuffer>
#include <QDir>
#include <QFile>
#include <QImage>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QSignalSpy>
#include <QTemporaryDir>
#include <QTest>
#include <QUrlQuery>

#include "FakeServer.h"
#include "api/Api.h"
#include "services/ExerciseStore.h"


static QString baseOf(const FakeServer &server)
{
    return QStringLiteral("http://127.0.0.1:%1/api/pride").arg(server.serverPort());
}

static const QString catalogPath = QStringLiteral("/api/pride/catalog");
static const QString pictureA = QStringLiteral("0123456789abcdef0123.jpg");
static const QString pictureB = QStringLiteral("1123456789abcdef0123.jpg");

static QByteArray catalogJson(const QString &version, const QStringList &pictures = {QStringLiteral("0123456789abcdef0123.jpg")})
{
    QJsonArray names;
    for (const QString &name : pictures)
        names.append(name);
    const QJsonObject curl{{"id", 12}, {"key", "Barbell_Curl"}, {"name", "Barbell Curl"}, {"measure", "weight_reps"},
                           {"removed", false}, {"primary", QJsonArray{"biceps"}}, {"pictures", names}};
    const QJsonObject plank{{"id", 13}, {"key", "Plank"}, {"name", "Plank"}, {"measure", "time"},
                            {"removed", false}, {"primary", QJsonArray{"abdominals"}}, {"pictures", QJsonArray()}};
    const QJsonObject data{{"version", version}, {"exercises", QJsonArray{curl, plank}}};
    return QJsonDocument(QJsonObject{{"status", "ok"}, {"data", data}}).toJson(QJsonDocument::Compact);
}

// A real picture's bytes. PNG, because Qt reads it with no plugin; the store keeps any format an image reader knows.
static QByteArray pictureBytes()
{
    QImage image(8, 8, QImage::Format_RGB32);
    image.fill(Qt::darkMagenta);
    QByteArray bytes;
    QBuffer buffer(&bytes);
    buffer.open(QIODevice::WriteOnly);
    image.save(&buffer, "PNG");
    return bytes;
}

static int requestsTo(const FakeServer &server, const QString &path)
{
    int n = 0;
    for (const QUrl &url : server.requests)
        n += url.path() == path;
    return n;
}

static bool writeFile(const QString &path, const QByteArray &bytes)
{
    QFile file(path);
    return file.open(QIODevice::WriteOnly) && file.write(bytes) == bytes.size();
}


class TestExerciseStore : public QObject
{
    Q_OBJECT

    QTemporaryDir dir;

private slots:
    void initTestCase()
    {
        // AppConfig reads this once; it only has to exist so it stays quiet.
        const QString secrets = dir.filePath("secrets.json");
        QFile file(secrets);
        QVERIFY(file.open(QIODevice::WriteOnly));
        file.write("{\"apiBase\": \"http://127.0.0.1:1/api/pride\"}");
        file.close();
        qputenv("PRIDE_SECRETS", secrets.toUtf8());
    }

    void theFirstRefreshAsksWithoutAVersionAndKeepsTheCatalog()
    {
        QTemporaryDir data;
        FakeServer server;
        server.responses[catalogPath] = catalogJson("v1");
        Api api;
        api.setBases(QString(), baseOf(server));
        ExerciseStore store(api, data.path());
        QCOMPARE(store.count(), 0);

        store.refresh();
        QVERIFY(store.loading());
        QTRY_COMPARE(store.count(), 2);
        QTRY_VERIFY(!store.loading());
        QVERIFY(store.error().isEmpty());
        QVERIFY(!QUrlQuery(server.requests.first()).hasQueryItem("version"));
        QCOMPARE(store.version(), QStringLiteral("v1"));
        QCOMPARE(store.exercise(12).value("name").toString(), QStringLiteral("Barbell Curl"));
        QVERIFY(store.exercise(99).isEmpty());
        QVERIFY(QFile::exists(data.path() + "/catalog/catalog.json"));
    }

    void aSecondStartReadsTheCopyAndAsksWithItsVersion()
    {
        QTemporaryDir data;
        FakeServer server;
        server.responses[catalogPath] = catalogJson("v1");
        Api api;
        api.setBases(QString(), baseOf(server));
        {
            ExerciseStore first(api, data.path());
            first.refresh();
            QTRY_COMPARE(first.count(), 2);
        }
        server.responses[catalogPath] = R"({"status":"ok","data":{"version":"v1","unchanged":true}})";
        ExerciseStore again(api, data.path());
        // Read from disk, before any server is asked.
        QCOMPARE(again.count(), 2);
        QCOMPARE(again.version(), QStringLiteral("v1"));
        const int revision = again.revision();
        again.refresh();
        QTRY_VERIFY(!again.loading());
        QCOMPARE(QUrlQuery(server.requests.last()).queryItemValue("version"), QStringLiteral("v1"));
        QCOMPARE(again.revision(), revision);
        QCOMPARE(again.count(), 2);
    }

    void aFailedRefreshKeepsTheCopy()
    {
        QTemporaryDir data;
        FakeServer server;
        server.responses[catalogPath] = catalogJson("v1");
        Api api;
        api.setBases(QString(), baseOf(server));
        ExerciseStore store(api, data.path());
        store.refresh();
        QTRY_COMPARE(store.count(), 2);
        QTRY_VERIFY(!store.loading());

        server.statuses[catalogPath] = 503;
        server.responses[catalogPath] = R"({"status":"error","message":"busy, try again"})";
        store.refresh();
        QTRY_VERIFY(!store.loading());
        QCOMPARE(store.error(), QStringLiteral("busy, try again"));
        QCOMPARE(store.count(), 2);
    }

    void aCatalogItCannotReadKeepsTheCopy()
    {
        QTemporaryDir data;
        FakeServer server;
        server.responses[catalogPath] = catalogJson("v1");
        Api api;
        api.setBases(QString(), baseOf(server));
        ExerciseStore store(api, data.path());
        store.refresh();
        QTRY_COMPARE(store.count(), 2);
        QTRY_VERIFY(!store.loading());

        server.responses[catalogPath] = R"({"status":"ok","data":{"version":"v2","exercises":"not a list"}})";
        store.refresh();
        QTRY_VERIFY(!store.loading());
        QVERIFY(!store.error().isEmpty());
        QCOMPARE(store.version(), QStringLiteral("v1"));
        QCOMPARE(store.count(), 2);
    }

    void aCorruptCopyIsIgnoredAndFetchedWhole()
    {
        QTemporaryDir data;
        QDir().mkpath(data.path() + "/catalog");
        QFile half(data.path() + "/catalog/catalog.json");
        QVERIFY(half.open(QIODevice::WriteOnly));
        // Not a raw string: its odd number of quotes confuses CMake's moc scanner.
        half.write("{\"version\":\"v1\",\"exercises\":[{\"id\":12,\"na");
        half.close();
        FakeServer server;
        server.responses[catalogPath] = catalogJson("v2");
        Api api;
        api.setBases(QString(), baseOf(server));

        ExerciseStore store(api, data.path());
        QCOMPARE(store.count(), 0);
        QVERIFY(store.version().isEmpty());
        store.refresh();
        QTRY_COMPARE(store.count(), 2);
        QVERIFY(!QUrlQuery(server.requests.first()).hasQueryItem("version"));
        QCOMPARE(store.version(), QStringLiteral("v2"));
    }

    void anExerciseWithoutAnIdIsNotACatalog()
    {
        QTemporaryDir data;
        QDir().mkpath(data.path() + "/catalog");
        QVERIFY(writeFile(data.path() + "/catalog/catalog.json",
                          R"({"version":"v1","exercises":[{"name":"Nameless id"}]})"));
        Api api;
        api.setBases(QString(), QString());
        ExerciseStore store(api, data.path());
        QCOMPARE(store.count(), 0);
    }

    void aPictureIsFetchedOnceAndKeptOnDisk()
    {
        QTemporaryDir data;
        FakeServer server;
        server.responses[catalogPath] = catalogJson("v1");
        server.responses["/api/pride/pictures/" + pictureA] = pictureBytes();
        Api api;
        api.setBases(QString(), baseOf(server));
        ExerciseStore store(api, data.path());
        QSignalSpy landed(&store, &ExerciseStore::picturesChanged);

        QVERIFY(store.pictureUrl(pictureA).isEmpty());
        QVERIFY(store.pictureUrl(pictureA).isEmpty());
        QTRY_COMPARE(landed.count(), 1);
        const QString url = store.pictureUrl(pictureA);
        QCOMPARE(url, QUrl::fromLocalFile(data.path() + "/catalog/pictures/" + pictureA).toString());
        QCOMPARE(requestsTo(server, "/api/pride/pictures/" + pictureA), 1);
    }

    void somethingThatIsNotAPictureIsNotKept()
    {
        QTemporaryDir data;
        FakeServer server;
        server.responses["/api/pride/pictures/" + pictureA] = "<html>a captive portal</html>";
        Api api;
        api.setBases(QString(), baseOf(server));
        ExerciseStore store(api, data.path());

        store.pictureUrl(pictureA);
        QTRY_COMPARE(requestsTo(server, "/api/pride/pictures/" + pictureA), 1);
        QTest::qWait(150);
        QVERIFY(!QFile::exists(data.path() + "/catalog/pictures/" + pictureA));
        // Not asked again this session.
        QVERIFY(store.pictureUrl(pictureA).isEmpty());
        QTest::qWait(150);
        QCOMPARE(requestsTo(server, "/api/pride/pictures/" + pictureA), 1);
    }

    void aNameThatIsNotOneAsksNothing()
    {
        QTemporaryDir data;
        FakeServer server;
        Api api;
        api.setBases(QString(), baseOf(server));
        ExerciseStore store(api, data.path());
        QVERIFY(store.pictureUrl("../catalog.json").isEmpty());
        QVERIFY(store.pictureUrl(QString()).isEmpty());
        QVERIFY(store.pictureUrl("0123456789ABCDEF0123.jpg").isEmpty());
        QTest::qWait(150);
        QVERIFY(server.requests.isEmpty());
        QVERIFY(!ExerciseStore::validPictureName("0123456789abcdef0123.png"));
        QVERIFY(ExerciseStore::validPictureName(pictureA));
    }

    void aRefusedPictureIsAskedAgainWithANewSession()
    {
        QTemporaryDir data;
        FakeServer server;
        const QString path = "/api/pride/pictures/" + pictureA;
        server.statuses[path] = 401;
        server.responses[path] = R"({"status":"error","message":"not signed in"})";
        Api api;
        api.setBases(QString(), baseOf(server));
        ExerciseStore store(api, data.path());

        store.pictureUrl(pictureA);
        QTRY_COMPARE(requestsTo(server, path), 1);
        QTest::qWait(150);
        store.pictureUrl(pictureA);
        QTest::qWait(150);
        QCOMPARE(requestsTo(server, path), 1);

        server.statuses.remove(path);
        server.responses[path] = pictureBytes();
        api.setSessionToken("tok");
        store.pictureUrl(pictureA);
        QTRY_COMPARE(requestsTo(server, path), 2);
        QTRY_VERIFY(!store.pictureUrl(pictureA).isEmpty());
    }

    void aPictureTheTunnelCouldNotServeIsAskedAgainOnceTheServerIsBack()
    {
        QTemporaryDir data;
        FakeServer server;
        const QString path = "/api/pride/pictures/" + pictureA;
        server.statuses[path] = 502;
        server.responses[path] = "<html>bad gateway</html>";
        Api api;
        api.setBases(QString(), baseOf(server));
        api.setPingDelays(60000, 60000);
        ExerciseStore store(api, data.path());

        store.pictureUrl(pictureA);
        QTRY_COMPARE(requestsTo(server, path), 1);
        QTRY_VERIFY(!api.online());

        server.statuses.remove(path);
        server.responses[path] = pictureBytes();
        api.checkNow();
        QTRY_VERIFY(api.online());
        // Whatever shows the picture asks again, and this time it is kept.
        QTRY_VERIFY(!store.pictureUrl(pictureA).isEmpty());
        QCOMPARE(requestsTo(server, path), 2);
    }

    void picturesNoExerciseNamesAreDeletedWhenTheCatalogChanges()
    {
        QTemporaryDir data;
        FakeServer server;
        server.responses[catalogPath] = catalogJson("v1", {pictureA, pictureB});
        Api api;
        api.setBases(QString(), baseOf(server));
        ExerciseStore store(api, data.path());
        store.refresh();
        QTRY_COMPARE(store.count(), 2);
        QTRY_VERIFY(!store.loading());
        QDir().mkpath(data.path() + "/catalog/pictures");
        for (const QString &name : {pictureA, pictureB}) {
            QFile file(data.path() + "/catalog/pictures/" + name);
            QVERIFY(file.open(QIODevice::WriteOnly));
            file.write(pictureBytes());
        }

        server.responses[catalogPath] = catalogJson("v2", {pictureA});
        store.refresh();
        QTRY_COMPARE(store.version(), QStringLiteral("v2"));
        QVERIFY(QFile::exists(data.path() + "/catalog/pictures/" + pictureA));
        QVERIFY(!QFile::exists(data.path() + "/catalog/pictures/" + pictureB));
    }
};

QTEST_MAIN(TestExerciseStore)
#include "tst_exercisestore.moc"
