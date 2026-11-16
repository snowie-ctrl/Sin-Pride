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


static QByteArray ownJson()
{
    return R"({"status":"ok","data":[
 {"id":900,"key":"own-0123456789abcdef","source":"own","licence":null,"name":"Sandbag Carry","category":null,
  "level":null,"measure":"distance_time","region":"upper","removed":false,"primary":["forearms"],"secondary":[],
  "equipment":["other"],"steps":[],"pictures":[]},
 {"id":901,"key":"own-1123456789abcdef","source":"own","licence":null,"name":"Zercher Walk","category":null,
  "level":null,"measure":"distance_time","region":"full","removed":true,"primary":["quadriceps"],"secondary":[],
  "equipment":["barbell"],"steps":[],"pictures":[]}]})";
}

static QByteArray farmerWalk()
{
    return R"({"status":"ok","data":{"id":902,"key":"own-2123456789abcdef","source":"own","name":"Farmer Walk",
 "measure":"distance_time","region":"upper","removed":false,"primary":["forearms"],"secondary":[],
 "equipment":["dumbbell"],"steps":[],"pictures":[]}})";
}

// The sample catalog, a server that answers /exercises, a signed-in Api and a Catalog over them.
struct Rig
{
    FakeServer server;
    std::unique_ptr<Catalog> catalog;

    Rig(Api &api, ExerciseStore &store)
    {
        server.responses["/api/pride/exercises"] = ownJson();
        api.setBases(QString(), QStringLiteral("http://127.0.0.1:%1/api/pride").arg(server.serverPort()));
        api.setSessionToken(QStringLiteral("token"));
        catalog = std::make_unique<Catalog>(store, api);
    }
};


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
        Catalog catalog(*store, *api);
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
        Catalog catalog(*store, *api);
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
        Catalog catalog(*store, *api);
        catalog.toggle("equipment", "barbell");
        catalog.toggle("equipment", "dumbbell");
        QCOMPARE(names(catalog.results()), (QStringList{"Barbell Curl", "Dumbbell Bench Press"}));
        QVERIFY(catalog.isChosen("equipment", "barbell"));
        QVERIFY(catalog.narrowed());
    }

    void acrossFacetsAllMustMatch()
    {
        Catalog catalog(*store, *api);
        catalog.toggle("equipment", "bodyweight");
        catalog.toggle("measure", "reps");
        QCOMPARE(names(catalog.results()), (QStringList{"3/4 Sit-Up", "Pullups"}));
    }

    void theMuscleFacetMatchesPrimaryMuscles()
    {
        Catalog catalog(*store, *api);
        catalog.toggle("muscle", "forearms");
        QVERIFY(catalog.results().isEmpty());
        catalog.toggle("muscle", "biceps");
        QCOMPARE(names(catalog.results()), QStringList{"Barbell Curl"});
    }

    void togglingAgainUnchoosesAndAnUnknownFacetIsIgnored()
    {
        Catalog catalog(*store, *api);
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
        Catalog catalog(*store, *api);
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
        Catalog catalog(*store, *api);
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
        Catalog catalog(*store, *api);
        QCOMPARE(names(catalog.search("b", 2)), (QStringList{"Barbell Curl", "Dumbbell Bench Press"}));
        QCOMPARE(catalog.search("e").size(), 4);
        QCOMPARE(catalog.search("e", 3).size(), 3);
    }

    void openingAnExerciseMakesItCurrent()
    {
        Catalog catalog(*store, *api);
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
        Catalog catalog(*store, *api);
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

    // ---- The person's own exercises ----

    void ownExercisesJoinTheCatalogAndMineNarrowsToThem()
    {
        Rig rig(*api, *store);
        Catalog &catalog = *rig.catalog;
        catalog.loadOwn();
        QTRY_COMPARE(catalog.own().size(), 2);
        QVERIFY(!catalog.ownLoading());
        QCOMPARE(catalog.shownCount(), 7);                       // 6 shown catalog + Sandbag Carry
        QCOMPARE(catalog.options().value("mine").toList().size(), 1);
        QCOMPARE(catalog.options().value("mine").toList().first().toMap().value("count").toInt(), 1);
        catalog.toggle("mine", "mine");
        QCOMPARE(catalog.results().size(), 1);
        QCOMPARE(catalog.results().first().toMap().value("name").toString(), QStringLiteral("Sandbag Carry"));
        QCOMPARE(catalog.search("zercher").size(), 0);            // hidden own: never found
        QCOMPARE(catalog.exercise(901).value("name").toString(), QStringLiteral("Zercher Walk"));  // still named
        QCOMPARE(catalog.exercise(2).value("name").toString(), QStringLiteral("Barbell Curl"));
    }

    void thereIsNoMineFacetWithoutOwnExercises()
    {
        Rig rig(*api, *store);
        QVERIFY(rig.catalog->options().value("mine").toList().isEmpty());
    }

    void ownExercisesAreSearchedAndSortedInWithTheCatalog()
    {
        Rig rig(*api, *store);
        rig.catalog->loadOwn();
        QTRY_COMPARE(rig.catalog->own().size(), 2);
        QCOMPARE(names(rig.catalog->results()), (QStringList{"3/4 Sit-Up", "Barbell Curl", "Dumbbell Bench Press",
                                                             "Hamstring Stretch", "Kettlebell Halo", "Pullups",
                                                             "Sandbag Carry"}));
        QCOMPARE(names(rig.catalog->search("sandbag")), QStringList{"Sandbag Carry"});
    }

    void aFailedOwnLoadKeepsTheErrorAsACode()
    {
        Rig rig(*api, *store);
        rig.server.statuses["/api/pride/exercises"] = 500;
        QSignalSpy changed(rig.catalog.get(), &Catalog::ownChanged);
        rig.catalog->loadOwn();
        QTRY_COMPARE(rig.catalog->ownError(), QStringLiteral("server"));
        QVERIFY(!rig.catalog->ownLoading());
        QVERIFY(changed.count() >= 2);
    }

    void thePickerFollowsThePersonsEquipment()
    {
        Rig rig(*api, *store);
        Catalog &catalog = *rig.catalog;
        catalog.loadOwn();
        QTRY_COMPARE(catalog.own().size(), 2);
        QCOMPARE(names(catalog.pick("", {"barbell"}, false)),
                 QStringList({"3/4 Sit-Up", "Barbell Curl", "Hamstring Stretch"}));   // bodyweight always counts
        QCOMPARE(names(catalog.pick("", {"dumbbell", "bench", "pull-up bar"}, false)),
                 QStringList({"3/4 Sit-Up", "Dumbbell Bench Press", "Hamstring Stretch", "Pullups"}));
        QCOMPARE(catalog.pick("", {}, true).size(), 7);
        QCOMPARE(names(catalog.pick("curl", {}, true)), QStringList({"Barbell Curl"}));
        QCOMPARE(catalog.pick("", {}, true, 3).size(), 3);
    }

    void savingAnOwnExercisePostsThenPuts()
    {
        Rig rig(*api, *store);
        Catalog &catalog = *rig.catalog;
        rig.server.methodResponses["POST /api/pride/exercises"] = farmerWalk();
        rig.server.methodResponses["PUT /api/pride/exercises/902"] = farmerWalk();
        QSignalSpy saved(&catalog, &Catalog::ownSaved);
        catalog.saveOwn({{"name", "Farmer Walk"}, {"measure", "distance_time"}, {"primary", QStringList{"forearms"}},
                         {"equipment", QStringList{"dumbbell"}}});
        QTRY_COMPARE(saved.size(), 1);
        QCOMPARE(saved.first().at(0).toInt(), 902);
        QVERIFY(rig.server.heads.last().startsWith("POST /api/pride/exercises "));
        QVERIFY(!QJsonDocument::fromJson(rig.server.bodies.last()).object().contains("id"));
        QCOMPARE(catalog.exercise(902).value("name").toString(), QStringLiteral("Farmer Walk"));
        catalog.saveOwn({{"id", 902}, {"name", "Farmer Walk"}, {"measure", "distance_time"},
                         {"primary", QStringList{"forearms"}}, {"equipment", QStringList{"dumbbell"}}});
        QTRY_COMPARE(saved.size(), 2);
        QVERIFY(rig.server.heads.last().startsWith("PUT /api/pride/exercises/902 "));
        QCOMPARE(catalog.own().size(), 1);                        // replaced, not added twice
    }

    void removingAnOwnExerciseTakesItOut()
    {
        Rig rig(*api, *store);
        Catalog &catalog = *rig.catalog;
        rig.server.methodResponses["DELETE /api/pride/exercises/900"] =
            R"({"status":"ok","data":{"routinesTouched":2,"hidden":false}})";
        catalog.loadOwn();
        QTRY_COMPARE(catalog.own().size(), 2);
        QSignalSpy removed(&catalog, &Catalog::ownRemoved);
        catalog.removeOwn(900);
        QTRY_COMPARE(removed.size(), 1);
        QCOMPARE(removed.first().at(0).toInt(), 900);
        QCOMPARE(removed.first().at(1).toInt(), 2);
        QCOMPARE(removed.first().at(2).toBool(), false);
        QVERIFY(catalog.exercise(900).isEmpty());
        QCOMPARE(catalog.shownCount(), 6);
    }

    void removingAnExerciseARoutineUsesHidesIt()
    {
        Rig rig(*api, *store);
        Catalog &catalog = *rig.catalog;
        rig.server.methodResponses["DELETE /api/pride/exercises/900"] =
            R"({"status":"ok","data":{"routinesTouched":0,"hidden":true}})";
        catalog.loadOwn();
        QTRY_COMPARE(catalog.own().size(), 2);
        QSignalSpy removed(&catalog, &Catalog::ownRemoved);
        catalog.removeOwn(900);
        QTRY_COMPARE(removed.size(), 1);
        QCOMPARE(removed.first().at(2).toBool(), true);
        QVERIFY(catalog.exercise(900).value("removed").toBool());   // still named, no longer shown
        QCOMPARE(catalog.shownCount(), 6);
    }

    void aRefusedOwnExerciseNamesTheField()
    {
        Rig rig(*api, *store);
        rig.server.methodResponses["POST /api/pride/exercises"] =
            R"({"status":"error","field":"name","message":"A name is needed."})";
        rig.server.methodStatuses["POST /api/pride/exercises"] = 400;
        QSignalSpy failed(rig.catalog.get(), &Catalog::ownFailed);
        rig.catalog->saveOwn({{"name", ""}});
        QTRY_COMPARE(failed.size(), 1);
        QCOMPARE(failed.first().at(0).toString(), QStringLiteral("invalid"));
        QCOMPARE(failed.first().at(1).toString(), QStringLiteral("name"));
    }

    void resettingOwnLeavesOnlyTheCatalog()
    {
        Rig rig(*api, *store);
        rig.catalog->loadOwn();
        QTRY_COMPARE(rig.catalog->own().size(), 2);
        rig.catalog->resetOwn();
        QVERIFY(rig.catalog->own().isEmpty());
        QCOMPARE(rig.catalog->shownCount(), 6);
        QVERIFY(rig.catalog->exercise(900).isEmpty());
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
