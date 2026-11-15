// Gluttony's app/tests/tst_preferences.cpp at c1ed705 is the model; Superbia's values, goldColor, and no units.
#include <QColor>
#include <QSettings>
#include <QTemporaryDir>
#include <QTest>

#include "assets/Preferences.h"


class TestPreferences : public QObject
{
    Q_OBJECT

    QTemporaryDir dir;

    static QSettings file()
    {
        return QSettings(QSettings::IniFormat, QSettings::UserScope, QStringLiteral("Pride"), QStringLiteral("preferences"));
    }

private slots:
    void initTestCase()
    {
        // Before any Preferences exists, so the owner's real ini is never read or written.
        QSettings::setPath(QSettings::IniFormat, QSettings::UserScope, dir.path());
    }

    void init()
    {
        QSettings settings = file();
        settings.clear();
        settings.sync();
    }

    void theDefaultsAreSuperbia()
    {
        Preferences p;
        QCOMPARE(p.backgroundPrimary, QColor(0x0e0b14));
        QCOMPARE(p.backgroundSecondary, QColor(0x1a1424));
        QCOMPARE(p.accentColor, QColor(0x8e5cf5));
        QCOMPARE(p.accentDeep, QColor(0x6b3fd9));
        QCOMPARE(p.goldColor, QColor(0xe3b341));
        QCOMPARE(p.textPrimary, QColor(0xede7f6));
        QCOMPARE(p.appFont, QStringLiteral("Segoe UI"));
        QVERIFY(p.storagePath().contains(QStringLiteral("Pride")));
    }

    void onlyWhatDiffersIsSavedAndReadBack()
    {
        {
            Preferences p;
            p.setProperty("tileWidth", 240);
            p.setProperty("goldColor", QColor(0x112233));
        }
        QSettings settings = file();
        QCOMPARE(settings.value("tileWidth").toInt(), 240);
        QCOMPARE(settings.value("goldColor").toString(), QStringLiteral("#112233"));
        QVERIFY(!settings.contains("accentColor"));
        Preferences again;
        QCOMPARE(again.goldColor, QColor(0x112233));
        QCOMPARE(again.tileWidth, 240);
    }

    void aValueOutOfRangeIsClampedWhenRead()
    {
        {
            QSettings settings = file();
            settings.setValue("tileWidth", 9999);
            settings.setValue("cornerRadius", -4);
            settings.sync();
        }
        Preferences p;
        QCOMPARE(p.tileWidth, 320);
        QCOMPARE(p.cornerRadius, 0);
    }

    void aColourThatDoesNotReadKeepsTheDefault()
    {
        {
            QSettings settings = file();
            settings.setValue("accentColor", "not a colour");
            settings.sync();
        }
        Preferences p;
        QCOMPARE(p.accentColor, QColor(0x8e5cf5));
    }

    void resetColoursPutsEveryColourBackAndNothingElse()
    {
        Preferences p;
        p.setProperty("accentColor", QColor(0x00ff00));
        p.setProperty("goldColor", QColor(0x0000ff));
        p.setProperty("tileWidth", 260);
        p.resetColours();
        QCOMPARE(p.accentColor, QColor(0x8e5cf5));
        QCOMPARE(p.goldColor, QColor(0xe3b341));
        QCOMPARE(p.tileWidth, 260);
        p.reset("tileWidth");
        QCOMPARE(p.tileWidth, 200);
    }

    void thereAreNoUnitsHere()
    {
        Preferences p;
        // Pride keeps units on the server, in the profile (spec §3).
        QCOMPARE(p.metaObject()->indexOfProperty("units"), -1);
        QVERIFY(p.choices("units").isEmpty());
    }
};

QTEST_MAIN(TestPreferences)
#include "tst_preferences.moc"
