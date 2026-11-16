#include "services/Wiring.h"

#include "services/AccountStore.h"
#include "services/Catalog.h"
#include "services/ExerciseStore.h"
#include "services/Profile.h"
#include "services/Programs.h"
#include "services/Session.h"


void wireServices(Session &session, AccountStore &store, ExerciseStore &exercises, Catalog &catalog, Profile &profile,
                  Programs &programs)
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
                     [&session, &exercises, &catalog, &profile, &programs]() {
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
    });

    QObject::connect(&profile, &Profile::saved, &programs, [&programs]() { programs.loadToday(); });

    QObject::connect(&session, &Session::signedOut, &catalog, [&catalog, &profile, &programs]() {
        catalog.reset();
        catalog.open(0);
        catalog.resetOwn();
        profile.reset();
        programs.reset();
    });
}
