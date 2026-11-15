#pragma once

class AccountStore;
class Catalog;
class ExerciseStore;
class Session;

// What follows a person in and out. The account folder opens and closes with the session (AccountStore). A sign-in,
// a reconnect after an offline start, or the server coming back after a refresh failed asks for the catalog again
// (the catalog belongs to the device and stays). A sign-out clears the filters and the open exercise, so the next
// person starts fresh. main.cpp and tests/tst_pages.cpp wire the app with this one function.
void wireServices(Session &session, AccountStore &store, ExerciseStore &exercises, Catalog &catalog);
