#include <QDir>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QSignalSpy>
#include <QTemporaryDir>
#include <QTest>

#include <memory>

#include "FakeServer.h"
#include "api/Api.h"
#include "services/Catalog.h"
#include "services/ExerciseStore.h"


static QJsonObject exercise(int id, const char *name, const char *primary, QJsonArray equipment, const char *measure,
                            const char *level, bool removed = false, QJsonArray secondary = {})
{
    return {{"id", id}, {"key", QString(name).replace(' ', '_')}, {"name", name}, {"primary", QJsonArray{primary}},
            {"secondary", secondary}, {"equipment", equipment}, {"measure", measure}, {"level", level},
            {"region", "upper"}, {"removed", removed}, {"pictures", QJsonArray{}}};
}

// The catalog as ExerciseStore keeps it, by name, with one exercise hidden.
static QJsonArray sample()
{
    return {exercise(1, "3/4 Sit-Up", "abdominals", {"bodyweight"}, "reps", "beginner"),
            exercise(2, "Barbell Curl", "biceps", {"barbell"}, "weight_reps", "beginner", false, {"forearms"}),
            exercise(3, "Dumbbell Bench Press", "chest", {"dumbbell", "bench"}, "weight_reps", "beginner"),
            exercise(4, "Hamstring Stretch", "hamstrings", {"bodyweight"}, "time", "beginner"),
            exercise(6, "Kettlebell Halo", "shoulders", {"kettlebell"}, "weight_reps", "intermediate"),
            exercise(7, "Old Row", "middle back", {"barbell"}, "weight_reps", "beginner", true),
            exercise(5, "Pullups", "lats", {"bodyweight", "pull-up bar"}, "reps", "beginner")};
}

static void writeCatalog(const QString &root, const QJsonArray &exercises)
{
    QDir().mkpath(root + "/catalog");
    QFile file(root + "/catalog/catalog.json");
    QVERIFY(file.open(QIODevice::WriteOnly));
    file.write(QJsonDocument(QJsonObject{{"version", "v1"}, {"exercises", exercises}}).toJson());
}

static QStringList names(const QVariantList &tiles)
{
    QStringList found;
    for (const QVariant &tile : tiles)
        found << tile.toMap().value("name").toString();
    return found;
}

static QVariantList counts(const Catalog &catalog, const QString &facet)
{
    return catalog.options().value(facet).toList();
}


class TestCatalog : public QObject
{
    Q_OBJECT

    QTemporaryDir root;
    std::unique_ptr<Api> api;
    std::unique_ptr<ExerciseStore> store;

private slots:
    void init()
    {
        store.reset();
        api.reset();
        QDir(root.path() + "/catalog").removeRecursively();
        writeCatalog(root.path(), sample());
        api = std::make_unique<Api>();
        api->setBases(QString(), QString());
        store = std::make_unique<ExerciseStore>(*api, root.path());
    }

    void optionsCountTheShownCatalogInPridesOrder()
    {
        Catalog catalog(*store);
        QCOMPARE(catalog.shownCount(), 6);
        const QVariantList equipment = counts(catalog, "equipment");
        QStringList order;
        for (const QVariant &row : equipment)
            order << row.toMap().value("value").toString();
        QCOMPARE(order, (QStringList{"bodyweight", "dumbbell", "barbell", "kettlebell", "bench", "pull-up bar"}));
        QCOMPARE(equipment.at(0).toMap().value("count").toInt(), 3);
        // The hidden Old Row counts for nothing: barbell is Barbell Curl's alone, and middle back is not offered.
        QCOMPARE(equipment.at(2).toMap().value("count").toInt(), 1);
        for (const QVariant &row : counts(catalog, "muscle"))
            QVERIFY(row.toMap().value("value").toString() != QLatin1String("middle back"));
        QCOMPARE(counts(catalog, "level").size(), 2);
    }

    void everyShownExerciseIsATileInTheCatalogsOrder()
    {
        Catalog catalog(*store);
        QCOMPARE(names(catalog.results()), (QStringList{"3/4 Sit-Up", "Barbell Curl", "Dumbbell Bench Press",
                                                        "Hamstring Stretch", "Kettlebell Halo", "Pullups"}));
        const QVariantMap tile = catalog.results().at(1).toMap();
        QCOMPARE(tile.value("id").toInt(), 2);
        QCOMPARE(tile.value("measure").toString(), QStringLiteral("weight_reps"));
        QCOMPARE(tile.value("picture").toString(), QString());
        QVERIFY(!catalog.narrowed());
    }

    void withinAFacetAnyValueMatches()
    {
        Catalog catalog(*store);
        catalog.toggle("equipment", "barbell");
        catalog.toggle("equipment", "dumbbell");
        QCOMPARE(names(catalog.results()), (QStringList{"Barbell Curl", "Dumbbell Bench Press"}));
        QVERIFY(catalog.isChosen("equipment", "barbell"));
        QVERIFY(catalog.narrowed());
    }

    void acrossFacetsAllMustMatch()
    {
        Catalog catalog(*store);
        catalog.toggle("equipment", "bodyweight");
        catalog.toggle("measure", "reps");
        QCOMPARE(names(catalog.results()), (QStringList{"3/4 Sit-Up", "Pullups"}));
    }

    void theMuscleFacetMatchesPrimaryMuscles()
    {
        Catalog catalog(*store);
        catalog.toggle("muscle", "forearms");
        QVERIFY(catalog.results().isEmpty());
        catalog.toggle("muscle", "biceps");
        QCOMPARE(names(catalog.results()), QStringList{"Barbell Curl"});
    }

    void togglingAgainUnchoosesAndAnUnknownFacetIsIgnored()
    {
        Catalog catalog(*store);
        catalog.toggle("level", "intermediate");
        QCOMPARE(names(catalog.results()), QStringList{"Kettlebell Halo"});
        catalog.toggle("level", "intermediate");
        QCOMPARE(catalog.results().size(), 6);
        catalog.toggle("colour", "violet");
        QCOMPARE(catalog.results().size(), 6);
        QVERIFY(!catalog.narrowed());
    }

    void textNarrowsByNameAndResetClearsEverything()
    {
        Catalog catalog(*store);
        QSignalSpy changed(&catalog, &Catalog::resultsChanged);
        catalog.setText("curl");
        QCOMPARE(names(catalog.results()), QStringList{"Barbell Curl"});
        QVERIFY(catalog.narrowed());
        catalog.toggle("level", "beginner");
        catalog.reset();
        QCOMPARE(catalog.results().size(), 6);
        QVERIFY(catalog.text().isEmpty() && !catalog.narrowed() && !catalog.isChosen("level", "beginner"));
        QVERIFY(changed.count() >= 3);
    }

    void searchIgnoresCasePunctuationAndOrder()
    {
        Catalog catalog(*store);
        QCOMPARE(names(catalog.search("PULL-UP")).value(0), QStringLiteral("Pullups"));
        QCOMPARE(names(catalog.search("pullup")).value(0), QStringLiteral("Pullups"));
        QCOMPARE(names(catalog.search("3/4 sit")), QStringList{"3/4 Sit-Up"});
        QCOMPARE(names(catalog.search("curl  barbell")), QStringList{"Barbell Curl"});
        QCOMPARE(names(catalog.search("  Bénch ")), QStringList{"Dumbbell Bench Press"});
        // A hidden exercise is never found, and nothing typed finds nothing.
        QVERIFY(catalog.search("old row").isEmpty());
        QVERIFY(catalog.search("   ").isEmpty());
    }

    void searchPutsNamesStartingWithTheTextFirstAndKeepsToTheLimit()
    {
        Catalog catalog(*store);
        QCOMPARE(names(catalog.search("b", 2)), (QStringList{"Barbell Curl", "Dumbbell Bench Press"}));
        QCOMPARE(catalog.search("e").size(), 4);
        QCOMPARE(catalog.search("e", 3).size(), 3);
    }

    void openingAnExerciseMakesItCurrent()
    {
        Catalog catalog(*store);
        QSignalSpy changed(&catalog, &Catalog::currentChanged);
        catalog.open(2);
        QCOMPARE(changed.count(), 1);
        QCOMPARE(catalog.currentId(), 2);
        QCOMPARE(catalog.current().value("name").toString(), QStringLiteral("Barbell Curl"));
        catalog.open(99);
        QVERIFY(catalog.current().isEmpty());
    }

    void aNewCatalogRebuildsOptionsAndTiles()
    {
        FakeServer server;
        const QJsonObject data{{"version", "v2"}, {"exercises", QJsonArray{exercise(9, "Plank", "abdominals",
                                                                                     {"bodyweight"}, "time", "beginner")}}};
        server.responses["/api/pride/catalog"] =
            QJsonDocument(QJsonObject{{"status", "ok"}, {"data", data}}).toJson(QJsonDocument::Compact);
        api->setBases(QString(), QStringLiteral("http://127.0.0.1:%1/api/pride").arg(server.serverPort()));
        Catalog catalog(*store);
        catalog.open(2);
        QSignalSpy current(&catalog, &Catalog::currentChanged);
        store->refresh();
        QTRY_COMPARE(names(catalog.results()), QStringList{"Plank"});
        QCOMPARE(catalog.shownCount(), 1);
        QCOMPARE(counts(catalog, "measure").size(), 1);
        // The open exercise is looked up again: Barbell Curl has gone from this catalog.
        QVERIFY(current.count() >= 1);
        QVERIFY(catalog.current().isEmpty());
    }

    void foldingAndMatchingNames()
    {
        QCOMPARE(Catalog::folded("  Côte-Rôtie 3/4 SIT-UP "), QStringLiteral("cote rotie 3 4 sit up"));
        QVERIFY(Catalog::nameMatches("Pullups", "pull up"));
        QVERIFY(Catalog::nameMatches("Pullups", ""));
        QVERIFY(!Catalog::nameMatches("Pushups", "pull"));
    }
};

QTEST_MAIN(TestCatalog)
#include "tst_catalog.moc"
