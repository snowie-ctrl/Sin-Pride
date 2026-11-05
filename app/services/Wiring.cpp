#include "services/Wiring.h"

#include "services/AccountStore.h"
#include "services/Catalog.h"
#include "services/ExerciseStore.h"
#include "services/Session.h"


void wireServices(Session &session, AccountStore &store, ExerciseStore &exercises, Catalog &catalog)
{
    session.setStore(&store);

    const auto refresh = [&exercises]() { exercises.refresh(); };
    QObject::connect(&session, &Session::loginSucceeded, &exercises, refresh);
    QObject::connect(&session, &Session::reconnected, &exercises, refresh);
    // Signed in, but the catalog's refresh failed while the server was away: asked again once it answers.
    QObject::connect(&session, &Session::onlineChanged, &exercises, [&session, &exercises]() {
        if (session.online() && session.authenticated() && !session.offline() && !exercises.error().isEmpty())
            exercises.refresh();
    });

    QObject::connect(&session, &Session::signedOut, &catalog, [&catalog]() {
        catalog.reset();
        catalog.open(0);
    });
}
