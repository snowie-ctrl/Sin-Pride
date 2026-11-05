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

## Screenshots

    powershell -File app/tests/stub/grab.ps1 -Out catalog.png -Fixture
    powershell -File app/tests/stub/grab.ps1 -Out exercise.png -Fixture -Exercise 1

`grab.ps1` lists every switch at its top.

## Where things are

- `api/`: talking to the server (`Api`), the session token for pictures (`SessionAuth`, `AuthNetworkFactory`),
  `AppConfig` (reads `config/secrets.json` or `$PRIDE_SECRETS`; `config/secrets.example.json` shows the shape).
- `services/`: `Session` (signing in and out, devices), `AccountStore` (the account's folder), `ExerciseStore` (the
  catalog and its pictures on this device), `Catalog` (filters, tiles, search, the open exercise), `Nav`, `Wiring`.
- `qml/`: `Main.qml`, `NavShell.qml`, `pages/` (Sign-in, Catalog, Exercise), `component/`, `logic/words.mjs` (every
  word the app shows).
- `tests/`: the C++ tests, `qml/` (the QML helper tests), `stub/`.
