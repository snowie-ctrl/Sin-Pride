// Gluttony's app/main.cpp at c1ed705 is the model: the same order (services, then the engine declared last so it
// goes first), the same dev hooks under PRIDE_ names.
#include <QCoreApplication>
#include <QDesktopServices>
#include <QGuiApplication>
#include <QIcon>
#include <QMouseEvent>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickWindow>
#include <QSettings>
#include <QStandardPaths>
#include <QTimer>
#include <QtQml/QQmlExtensionPlugin>

#include "LinkSuppressor.h"
#include "api/Api.h"
#include "api/AuthNetworkFactory.h"
#include "assets/Preferences.h"
#include "services/AccountStore.h"
#include "services/Catalog.h"
#include "services/ExerciseStore.h"
#include "services/Nav.h"
#include "services/Session.h"
#include "services/Wiring.h"

// The QML module is a static library (pride_ui), so its plugin is pulled in by hand.
Q_IMPORT_QML_PLUGIN(PridePlugin)

int main(int argc, char *argv[])
{
    QGuiApplication app(argc, argv);
    QCoreApplication::setApplicationName(QStringLiteral("Pride"));
    app.setWindowIcon(QIcon(QStringLiteral(":/icons/prideAppIcon.png")));

    // Screenshot runs (tests/stub/grab.ps1) keep their own preferences and data folders, so trying a page never
    // changes the owner's.
    const QString settingsDir = qEnvironmentVariable("PRIDE_SETTINGS_DIR");
    if (!settingsDir.isEmpty())
        QSettings::setPath(QSettings::IniFormat, QSettings::UserScope, settingsDir);
    QString dataDir = qEnvironmentVariable("PRIDE_DATA_DIR");
    if (dataDir.isEmpty())
        dataDir = QStandardPaths::writableLocation(QStandardPaths::AppDataLocation);

    Preferences preferences;
    Api api;
    Nav nav;
    AccountStore accounts(dataDir);
    Session session(api);
    ExerciseStore exercises(api, dataDir);
    Catalog catalog(exercises, api);
    // Pictures load through managers this makes, so they carry the session token.
    AuthNetworkFactory networkFactory;

    wireServices(session, accounts, exercises, catalog);

    // Declared after everything QML is given, so it is destroyed first.
    QQmlApplicationEngine engine;
    engine.setNetworkAccessManagerFactory(&networkFactory);
    QQmlContext *context = engine.rootContext();
    context->setContextProperty("Preferences", &preferences);
    context->setContextProperty("Nav", &nav);
    context->setContextProperty("Session", &session);
    context->setContextProperty("ExerciseStore", &exercises);
    context->setContextProperty("Catalog", &catalog);

    engine.loadFromModule("Pride", "Main");
    if (engine.rootObjects().isEmpty())
        return -1;

    // Dev affordances for grab.ps1: open on a page, on an exercise, or with the catalog narrowed by name, once signed
    // in. Nothing happens unless the variables are set.
    const QString startPage = qEnvironmentVariable("PRIDE_START_PAGE");
    if (!startPage.isEmpty())
        nav.setStartPage(startPage);
    const int startExercise = qEnvironmentVariableIntValue("PRIDE_START_EXERCISE");
    if (startExercise > 0) {
        nav.setStartPage(QStringLiteral("exercise-page"));
        catalog.open(startExercise);
    }
    const QString startText = qEnvironmentVariable("PRIDE_START_TEXT");
    if (!startText.isEmpty())
        catalog.setText(startText);

    // A known device signs itself in; otherwise the sign-in page asks.
    session.identifyDevice();

    // A grab or a scripted click must never open the owner's browser: such a link is swallowed and logged. A normal
    // run installs nothing.
    LinkSuppressor linkSuppressor;
    if (!qEnvironmentVariable("PRIDE_GRAB").isEmpty() || !qEnvironmentVariable("PRIDE_CLICK").isEmpty()) {
        QDesktopServices::setUrlHandler(QStringLiteral("https"), &linkSuppressor, "suppress");
        QDesktopServices::setUrlHandler(QStringLiteral("http"), &linkSuppressor, "suppress");
    }

    // Dev affordance for layout checks: left clicks at "x,y" (window coordinates), several separated by ';', 1.5 s
    // apart after a first delay, to open something before PRIDE_GRAB takes its picture.
    const QStringList clicks = qEnvironmentVariable("PRIDE_CLICK").split(';', Qt::SkipEmptyParts);
    const int clickDelay = qEnvironmentVariableIntValue("PRIDE_CLICK_DELAY");
    for (int i = 0; i < clicks.size(); ++i) {
        const QStringList clickAt = clicks[i].split(',');
        if (clickAt.size() != 2)
            continue;
        const QPointF point(clickAt[0].toDouble(), clickAt[1].toDouble());
        QTimer::singleShot((clickDelay > 0 ? clickDelay : 5000) + i * 1500, &app, [&engine, point]() {
            auto *window = qobject_cast<QQuickWindow *>(engine.rootObjects().value(0));
            if (!window)
                return;
            QMouseEvent press(QEvent::MouseButtonPress, point, window->mapToGlobal(point),
                              Qt::LeftButton, Qt::LeftButton, Qt::NoModifier);
            QMouseEvent release(QEvent::MouseButtonRelease, point, window->mapToGlobal(point),
                                Qt::LeftButton, Qt::NoButton, Qt::NoModifier);
            QCoreApplication::sendEvent(window, &press);
            QCoreApplication::sendEvent(window, &release);
        });
    }

    // Dev affordance for layout checks: save the window to a PNG after a delay, then quit. The window ignores real
    // input meanwhile, so a stray click on the owner's desktop never changes the grab; PRIDE_CLICK sends its events
    // straight to the window, so it still works. PRIDE_GRAB_SIZE ("2560x1440") grabs at a real screen's size.
    const QString grabPath = qEnvironmentVariable("PRIDE_GRAB");
    if (!grabPath.isEmpty()) {
        if (auto *window = qobject_cast<QQuickWindow *>(engine.rootObjects().value(0))) {
            QSize size = window->size();
            const QStringList asked = qEnvironmentVariable("PRIDE_GRAB_SIZE").split('x');
            if (asked.size() == 2 && asked[0].toInt() > 0 && asked[1].toInt() > 0)
                size = QSize(asked[0].toInt(), asked[1].toInt());
            window->setFlags(window->flags() | Qt::WindowTransparentForInput | Qt::WindowDoesNotAcceptFocus);
            window->resize(size);
        }
        const int grabDelay = qEnvironmentVariableIntValue("PRIDE_GRAB_DELAY");
        QTimer::singleShot(grabDelay > 0 ? grabDelay : 6000, &app, [&engine, grabPath]() {
            if (auto *window = qobject_cast<QQuickWindow *>(engine.rootObjects().value(0)))
                window->grabWindow().save(grabPath);
            QCoreApplication::quit();
        });
    }

    return app.exec();
}
