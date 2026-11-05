# Pride's catalog importer

Fetches free-exercise-db at the commit pinned in `sources.json`, normalises it with the rules in `rules/`, and prints
the change report. It publishes only when `.env` says `PUBLISH=on` (spec §2).

## Running it

    py -3.12 -m venv importer/.venv
    importer/.venv/Scripts/python.exe -m pip install -r importer/requirements-dev.txt
    importer/.venv/Scripts/python.exe importer/main.py        (a dry run: the report, nothing sent)
    importer/.venv/Scripts/python.exe -m pytest importer -q   (the tests; no network)

The first run downloads the data file and every picture into `importer/cache/` (git-ignored); later runs read the
cache. Each run leaves `importer/reports/last-report.json` and `last-catalog.json` (git-ignored).

To publish, copy `.env.example` to `.env` and fill in the admin route's address and token (never committed), then set
`PUBLISH=on`. Pictures the server lacks go first, then the whole catalog as one batch. Nothing is sent if the upstream
file has changed shape, a picture is not a JPEG, or more than 10% of the catalog would be hidden.

Exit codes: 0 done or a dry run, 2 the upstream shape or a non-JPEG picture, 3 the hide guard, 4 publishing asked for
but not configured, 5 the server refused or failed, 6 fetching failed.

## Moving the pin

Read what changed upstream between the pinned commit and the new one, update `commit` in `sources.json`, run a dry
run, and read the report before publishing. A new equipment word shows in the report (stored as `other`); add a rule
to `rules/equipment.json`. A new muscle, category or level stops the run until `rules/` and `server/prideCatalog.py`
both learn it.

## Licence check

Checked 2026-11-05 at `f00c92c7dcf1216a928a52c3706c7ce8e2f71ed5`: `LICENSE.md` is the Unlicense, which dedicates the
whole repository to the public domain, and the pictures (`exercises/<id>/<n>.jpg`) are part of it. The README calls
the project an "Open Public Domain Exercise Dataset", shows the Unlicense badge, and says the JSON files and images
can be used locally or through GitHub's hosting, with no exception for the pictures. Each exercise records its source
and licence, and the app's Exercise page shows them.
