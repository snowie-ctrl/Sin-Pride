#include "services/Wiring.h"

#include "services/AccountStore.h"
#include "services/Catalog.h"
#include "services/ExerciseStore.h"
#include "services/Profile.h"
#include "services/Programs.h"
#include "services/Progress.h"
#include "services/Session.h"
#include "services/Workouts.h"


void wireServices(Session &session, AccountStore &store, ExerciseStore &exercises, Catalog &catalog, Profile &profile,
                  Programs &programs, Workouts &workouts, Progress &progress)
{
    session.setStore(&store);

    // Everything that is the person's own, asked for once they are in.
    const auto loadAll = [&exercises, &catalog, &profile, &programs]() {
        exercises.refresh();
        profile.load();
        programs.loadList();
        programs.loadToday();
        catalog.loadOwn();
    };
    QObject::connect(&session, &Session::loginSucceeded, &exercises, loadAll);
    QObject::connect(&session, &Session::reconnected, &exercises, loadAll);
    // Signed in, but a load failed while the server was away: the ones that last failed are asked again once it answers.
    QObject::connect(&session, &Session::onlineChanged, &exercises,
                     [&session, &exercises, &catalog, &profile, &programs, &workouts, &progress]() {
        if (!session.online() || !session.authenticated() || session.offline())
            return;
        if (!exercises.error().isEmpty())
            exercises.refresh();
        if (!profile.error().isEmpty())
            profile.load();
        if (!programs.listError().isEmpty())
            programs.loadList();
        if (!programs.todayError().isEmpty())
            programs.loadToday();
        if (!catalog.ownError().isEmpty())
            catalog.loadOwn();
        if (!workouts.historyError().isEmpty())
            workouts.loadHistory();
        if (!progress.recordsError().isEmpty())
            progress.loadRecords();
    });

    // An own exercise taken out of routines changes the open program and what Today shows; nothing else is asked.
    QObject::connect(&catalog, &Catalog::ownRemoved, &programs, [&programs](int, int touched, bool) {
        if (touched <= 0)
            return;
        if (programs.currentId())
            programs.open(programs.currentId());
        programs.loadToday();
    });

    QObject::connect(&profile, &Profile::saved, &programs, [&programs]() { programs.loadToday(); });

    // A workout saved, edited or deleted changes Today (next up, the week, suggestions, crowns), the records, the
    // history and the series on show.
    const auto afterWorkout = [&programs, &workouts, &progress]() {
        programs.loadToday();
        workouts.loadHistory();
        progress.loadRecords();
        if (progress.seriesId())
            progress.loadSeries(progress.seriesId());
    };
    QObject::connect(&workouts, &Workouts::saved, &programs, afterWorkout);
    QObject::connect(&workouts, &Workouts::removed, &programs, afterWorkout);

    // Taking a step-up writes a routine's target: Today, and the program when it is the one open. A dismissal only
    // changes Today. A suggestion settled or gone elsewhere: Today is asked again so it shows what is true now.
    QObject::connect(&progress, &Progress::decided, &programs, [&programs](int, const QString &what, int programId) {
        programs.loadToday();
        if (what == QLatin1String("accepted") && programId && programs.currentId() == programId)
            programs.open(programId);
    });
    QObject::connect(&progress, &Progress::failed, &programs, [&programs](const QString &what, const QString &code) {
        if ((what == QLatin1String("accept") || what == QLatin1String("dismiss"))
            && (code == QLatin1String("closed") || code == QLatin1String("not_found")))
            programs.loadToday();
    });

    QObject::connect(&session, &Session::signedOut, &catalog, [&catalog, &profile, &programs, &workouts, &progress]() {
        catalog.reset();
        catalog.open(0);
        catalog.resetOwn();
        profile.reset();
        programs.reset();
        workouts.reset();
        progress.reset();
    });
}
