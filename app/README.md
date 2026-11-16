# Pride's desktop app

Qt 6.11 (MSVC 2022 64-bit), C++17 and QML. The foundations (`api/`, `services/AccountStore`, `services/Session`,
`services/Nav`, `assets/Preferences`, the test harness, the stub-and-grab pattern) are copied from Gluttony at
`c1ed705`; each copied file says so in its first line.

## Build and test

    powershell -File app/tests/build.ps1      (configures and builds the test build in app/build/tests)
    powershell -File app/tests/run.ps1        (the C++ tests through ctest, then the QML helper tests)
    powershell -File app/tests/run.ps1 -R tst_catalog -NoQml

Paths default to the owner's machine; `PRIDE_QT`, `PRIDE_QT_TOOLS` and `PRIDE_VCVARS` override them.

## Running against the stub

`app/tests/stub/stub_server.py` imitates `docs/api.md` on `127.0.0.1:5089`. Sign in as `stub` / `stub-password`, or
sign up with the key `stub-key`. It serves `snapshot/` when present (`snapshot.py`, from the importer's last dry
run) and the fixture's 11 exercises otherwise.

To use the stub without `grab.ps1`, start `python app/tests/stub/stub_server.py` and run the app with two
environment variables set first:

- `PRIDE_SECRETS`: the path of a secrets file that points at the stub, for example

      {"apiBase": "http://127.0.0.1:5089/api/pride"}

  (`lanApiBase` is optional; without it the app uses `apiBase` alone. Without `PRIDE_SECRETS` the app reads the
  real `config/secrets.json`, so it would talk to the real server. A mistyped `PRIDE_SECRETS` path falls through to
  the real secrets, so check it before a run.)
- `PRIDE_DATA_DIR`: an empty folder of your own, such as `<scratch>/pride-stub-data`. The account's folder and the
  catalog copy go there instead of the real AppData folder, so the stub's account and exercises never mix with
  real ones. `PRIDE_SETTINGS_DIR` does the same for the preferences.

`grab.ps1` sets all three itself, under a scratch folder in `%TEMP%`; it writes the stub's secrets file to `%TEMP%`,
beside its scratch folder, not inside it.

The stub imports `server/`'s checks, rules and starters, so it refuses and answers as the server does. Its switches
are environment variables (`grab.ps1` has a switch for each):

- `STUB_SEED=1`: the reader starts with the Upper/Lower starter adopted, four days a week, the intro done and one
  workout on the Monday of the current week.
- `STUB_INTRO=1`: the reader's intro is pending, so the app opens it.
- `STUB_TODAY=<YYYY-MM-DD>`: the day `STUB_SEED`'s workout is placed by, instead of the real today.

## Screenshots

    powershell -File app/tests/stub/grab.ps1 -Out catalog.png -Fixture
    powershell -File app/tests/stub/grab.ps1 -Out exercise.png -Fixture -Exercise 1
    powershell -File app/tests/stub/grab.ps1 -Out today.png -Seed -Page today-page
    powershell -File app/tests/stub/grab.ps1 -Out routine.png -Seed -Page routine-page -Program 1013 -Routine 1014
    powershell -File app/tests/stub/grab.ps1 -Out intro.png -Intro

The app's own hooks behind these are `PRIDE_START_PAGE`, `PRIDE_START_EXERCISE`, `PRIDE_START_PROGRAM` and
`PRIDE_START_ROUTINE`.

`grab.ps1` lists every switch at its top.

## Where things are

- `api/`: talking to the server (`Api`), the session token for pictures (`SessionAuth`, `AuthNetworkFactory`),
  `AppConfig` (reads `config/secrets.json` or `$PRIDE_SECRETS`; `config/secrets.example.json` shows the shape).
- `services/`: `Session` (signing in and out, devices), `AccountStore` (the account's folder), `ExerciseStore` (the
  catalog and its pictures on this device), `Catalog` (filters, tiles, search, the open exercise, and the person's own
  exercises), `Profile` (units, goal, days, equipment, the intro's state), `Programs` (programs, routines, items,
  starters and Today), `Nav`, `Wiring`.
- `qml/`: `Main.qml`, `NavShell.qml`, `pages/` (Sign-in, Intro, Today, Programs, Routine editor, Catalog, Exercise,
  Settings), `component/`, and `logic/`: `words.mjs` (every word the pages show, the error codes' words included),
  `forms.mjs` (field checks that match the server's) and `units.mjs` (weights, durations and distances as shown and
  as typed).
- `tests/`: the C++ tests, `qml/` (the QML helper tests), `stub/`.
