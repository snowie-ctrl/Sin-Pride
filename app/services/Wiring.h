#pragma once

class AccountStore;
class Catalog;
class ExerciseStore;
class Profile;
class Programs;
class Session;

// What follows a person in and out. The account folder opens and closes with the session (AccountStore). A sign-in,
// a reconnect after an offline start, or the server coming back after a load failed asks again for what belongs to
// the person: the catalog (which belongs to the device and stays), their profile, programs, Today and own exercises.
// A saved profile asks for Today again, since week start and goal change what it shows. A sign-out clears all of it,
// so the next person starts fresh. main.cpp and tests/tst_pages.cpp wire the app with this one function.
void wireServices(Session &session, AccountStore &store, ExerciseStore &exercises, Catalog &catalog, Profile &profile,
                  Programs &programs);
