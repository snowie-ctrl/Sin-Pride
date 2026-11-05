# Pride part 1: training

Status: approved by the owner 2026-11-05 (designed in conversation section by
section). The whole-project picture is `2026-11-05-pride-roadmap.md`.

Part 1 makes Pride useful for training on the desktop. It covers an exercise
catalog, accounts, a guided start a person can skip, programs of routines in
rotation, entering finished workouts, progress, and suggestions for when to go
up in weight. It ends by writing the handoff for the iOS gym companion
(part 2) onto an `ios` branch.

## Why

A beginner opening a blank routine builder beside an 800-exercise catalog is
the "overwhelmed" moment Pride exists to avoid. An experienced lifter only
wants to type in the routine they already follow. Part 1 serves both:
- the guided start proposes a sensible program in four questions;
- Skip goes straight to the builder.

Either way, the person ends with a plan, a log, and a clear picture of their
progress.

## Decisions

| Topic | Decision |
|---|---|
| First part | Training first. Nutrition is part 3, partly so its food source can match Gluttony part 3's. |
| Desktop's job | Preparing programs and routines, entering finished workouts afterwards (and fixing them later), reviewing progress. Live in-gym use is iOS's job (part 2). |
| Server | Flask blueprints in Caduceus on plutus, a `prideDB` MySQL database, Pride's own accounts. Built like Gluttony part 2. |
| Catalog source | free-exercise-db only (public domain, about 870 exercises with pictures), pinned to a commit. A person can add their own exercises. A second source (wger) stays possible later because the importer takes a list of sources. |
| Beginner start | Guided start (days a week, equipment, goal → a starter program), with Skip on every step and a replay in Settings. |
| Splits | A rotation of routines, with optional planned weekdays. "Next up" follows the rotation whatever the weekday; a missed day is never marked. |
| Measures | Each exercise is measured as weight × reps, reps (optional added weight), time, or distance + time. |
| Progression | Suggest, the person decides. Nothing in a plan changes without a click. |
| Rules | Run on the server, so the desktop and iOS always agree, with one set of rule tests. |
| Offline (desktop) | The catalog and pictures are cached on disk. Saving needs the server; when it can't be reached the app says so and keeps what was typed. No desktop queue. |
| Layouts | Chosen from mockups at the start of milestone 1, before any QML is written. |
| Not in part 1 | Supersets and circuits, drop sets, per-set notes, nutrition, body weight, nudges beyond progression, the Gluttony door, iOS itself. |

## 1. Architecture

```
 QML pages (Sign-in, Intro, Today, Programs, Routine editor, Catalog, Exercise, Log a workout, Progress, Settings)
   │
 Session  Catalog  Programs  Workouts  Progress  Profile  ── ExerciseStore (disk: catalog + pictures)
   └────────┴─────────┴─────────┴─────────┴────────┘
                Api ── SessionAuth   (LAN address if it answers, the tunnel hostname otherwise)
                  ▼
   prideRoutes.py (sessions, catalog) + prideUserRoutes.py (everything a person owns) → prideDB
                  ▲
   importer/ (Python, run by hand) → prideAdminRoutes.py (rows); pictures copied to appFiles/pride
```

### Repository layout

```
Pride/                       public repository, snowie-ctrl/Sin-Pride
  importer/                  Python 3.12: fetch → normalise → publish; rules/*.json; tests/
  server/                    prideRoutes.py, prideUserRoutes.py, prideAdminRoutes.py, prideRules.py,
                             schema.sql, starters/*.json, tests/
  app/                       Qt 6.11 project (CMakeLists.txt, target appPride, QML module Pride)
    main.cpp
    api/                     Api, SessionAuth, AuthNetworkFactory, AppConfig (copied from Gluttony)
    services/                Session, Catalog, Programs, Workouts, Progress, Profile, ExerciseStore,
                             AccountStore (copied)
    assets/                  Preferences (copied, Pride's tokens), fonts, icons (the crown), placeholders
    qml/                     Main.qml, NavShell.qml, pages/, component/, logic/*.mjs
    tests/                   C++ tests, qml/, stub/ (stub server, grab.ps1)
    config/secrets.example.json
  tools/check-public.ps1     the pre-push sensitive-data check (section 10)
  docs/                      api.md (the contract iOS also uses), specs; ios-handoff.md on the ios branch
```

### Copied foundations

These are copied from Gluttony. Each copied file names its source and commit,
and Gluttony is not changed.
- `Api` (the envelope, `whenReady`, LAN/public switching, the offline state and backing-off `/ping`)
- `SessionAuth`, `AuthNetworkFactory`
- `AppConfig` (with `$PRIDE_SECRETS`)
- `Preferences` (in `Pride/preferences.ini`)
- `AccountStore`
- the stub server pattern, `grab.ps1` with `PRIDE_GRAB` / `PRIDE_CLICK` hooks, and the C++ and QML test harness

Not copied: anything recipe-, cook- or offline-queue-specific.

### Services

Each service is a context property declared before the `QQmlApplicationEngine`.
- **Session:** device sign-in, sign-in, sign-up with a key, sign-out, devices. An ended session returns to Sign-in.
- **Catalog:** filter options, one filtered query, Ctrl+K search, and the person's own exercises (add, edit, delete).
- **Programs:** programs and their routines (in rotation order), planned weekdays, routine items, activate, reorder.
- **Workouts:** enter, edit and delete a finished workout, and the history list.
- **Progress:** chart series per exercise, records, and suggestions (accept, dismiss).
- **Profile:** units, goal, days a week, equipment, the two increments, the intro state, and the week start.
- **ExerciseStore:** the cached catalog and its pictures. It refreshes when the server's catalog version changes.

### Logic helpers

These are pure functions in `qml/logic/*.mjs`, table-tested with `qmltestrunner`.
- `units.mjs`: kg/lb conversion, display rounding, durations, distances.
- `forms.mjs`: field checks that match the server's (section 4).
- `words.mjs`: every word the app shows.

Rules (suggestions, stalls, records, next up) are **not** in the app; they live in `server/prideRules.py`.

## 2. The catalog import

`importer/` fetches free-exercise-db's `dist/exercises.json` and pictures at the
commit named in `importer/sources.json`. It normalises each exercise and then
publishes.
- **It is a dry run unless `.env` sets `PUBLISH=on`.** A dry run prints the change report: added, changed and hidden, with counts and names.
- **Pictures are copied to `/pool/appFiles/pride/`.** They are served the way Gluttony serves its pictures.

Normalising uses readable rules in `importer/rules/*.json`:
- **`equipment.json`** maps upstream equipment words onto Pride's equipment list (barbell, dumbbell, kettlebell, machine, cable, bands, bodyweight, bench, pull-up bar, other).
- **`measure.json`** sets each exercise's measure:
  - `cardio` → `distance_time`
  - `stretching` → `time`
  - strength with no equipment → `reps`
  - otherwise `weight_reps`
  - a list of named exceptions (plank → `time`, …)
- **`region.json`** sets the body region from the primary muscles.
  - Chest, shoulders, arms, back and traps are upper. Quads, hamstrings, glutes, calves, adductors and abductors are lower. Abdominals and lower back count as neither.
  - Mixed regions, or core alone, give `full`.
- **Level** is kept as given (beginner / intermediate / expert). The intro's starters only use beginner exercises.
- **Credit:** every exercise records its source and licence, and the Exercise page shows them. Before pictures are first published, the importer's README records that the repository's LICENSE was checked for the pictures as well as the data.

An exercise that disappears upstream is hidden (`RemovedAt`), never deleted, so
old workouts keep it. The admin route accepts the import as one batch behind a
token, the way Gluttony's scraper publishes.

## 3. Data (`prideDB`)

Multi-valued facts live in child tables, never in SET, ENUM or JSON columns.
Single-valued word columns are `VARCHAR` with a `CHECK`. `server/schema.sql`
creates all of these.

**Accounts** (as in Gluttony):
- `Users` (`UserID`, `Username` unique, `PasswordHash`, `CreatedAt`)
- `Devices` (`Fingerprint` PK, `UserID`)
- `Sessions` (`Token` CHAR(64) PK, `UserID`, `DeviceFingerprint`, `ExpiresAt`)
- `LoginKeys` (`KeyValue` PK, `Used`, `UsedBy`, `CreatedAt`). The owner inserts these by hand.

**Profile:**
- `Profiles` has these columns:
  - `UserID` PK
  - `Units` (`lb` / `kg`, default `lb`)
  - `Goal` (`strength` / `muscle` / `general`)
  - `DaysPerWeek` (2–6)
  - `UpperIncrement` and `LowerIncrement`, in the profile's units (defaults 5 lb / 10 lb; 2.5 kg / 5 kg after a switch to kg)
  - `WeekStart` (`mon` / `sun`)
  - `IntroState` (`pending` / `done` / `skipped`)

  Sign-up makes the row with the intro `pending`.
- `UserEquipment` (`UserID`, `Equipment`)

**Catalog:**
- `Exercises` has these columns:
  - `ExerciseID`, `SourceKey` (unique per source), `Source`, `Licence`, `Name`
  - `Category`, `Level`
  - `Measure` (`weight_reps` / `reps` / `time` / `distance_time`)
  - `Region` (`upper` / `lower` / `full`)
  - `OwnerUserID` (NULL for the catalog; set for a person's own exercise, which only they see)
  - `RemovedAt`, `UpdatedAt`
- Child tables:
  - `ExerciseMuscles` (`ExerciseID`, `Muscle`, `Role` primary / secondary)
  - `ExerciseEquipment` (`ExerciseID`, `Equipment`)
  - `ExerciseSteps` (`ExerciseID`, `StepNo`, `Text`)
  - `ExercisePictures` (`ExerciseID`, `Idx`, `Path`)
- `CatalogVersion` holds one row: the hash of the last import. The app compares it before refreshing its cache.

**Programs:**
- `Programs` (`ProgramID`, `UserID`, `Title`, `IsActive`, `StarterKey` nullable, `CreatedAt`, `UpdatedAt`). At most one active program per person, enforced by the server.
- `ProgramDays` (`ProgramID`, `Weekday` 0–6): the planned weekdays. It can be empty.
- `Routines` (`RoutineID`, `ProgramID`, `Title`, `OrderIndex`)
- `RoutineItems` has these columns:
  - `ItemID`, `RoutineID`, `ExerciseID`, `OrderIndex`
  - `Sets`, `RepsMin`, `RepsMax`
  - `TargetWeight` and `TargetUnit`
  - `TargetSeconds`, `TargetDistance` and `DistanceUnit`
  - `RestSeconds`, `Note`

**Workouts:**
- `Workouts` has these columns:
  - `WorkoutID`, `UserID`
  - `ClientID` CHAR(36) unique, made by the app, so a resend is stored once
  - `PerformedOn` DATE (the person's local date), `StartedAt` and `EndedAt` (nullable; iOS fills them)
  - `ProgramID` and `RoutineID` (nullable, `ON DELETE SET NULL`; both NULL for a free workout)
  - `Note`, `CreatedAt`, `UpdatedAt`
- `WorkoutExercises` (`WorkoutExerciseID`, `WorkoutID`, `ExerciseID`, `OrderIndex`, `ItemID` nullable `ON DELETE SET NULL`, `Note`)
- `WorkoutSets` (`WorkoutExerciseID`, `SetNo`, `IsWarmup`, `Weight`, `WeightUnit`, `Reps`, `Seconds`, `Distance`, `DistanceUnit`). Each set keeps the number and unit **as entered**. Conversion happens only for comparisons and charts.

**Suggestions:**
- `Suggestions` has these columns:
  - `SuggestionID`, `UserID`, `ItemID`
  - `Kind` (`increase` / `stall`)
  - `ProposedWeight` and `ProposedUnit`, or `ProposedRepsMin` and `ProposedRepsMax`, or `ProposedSeconds`
  - `BasedOnWorkoutID`
  - `State` (`open` / `accepted` / `dismissed` / `withdrawn`)
  - `CreatedAt`

**Indexes:** `Workouts (UserID, PerformedOn)`, `WorkoutExercises (ExerciseID)`,
`Suggestions (ItemID, State)`, `Sessions (UserID)`, `Exercises (OwnerUserID)`.

**Limits:**
- 20 programs per person
- 14 routines per program
- 30 items per routine
- 1–20 sets
- 200 own exercises per person
- notes up to 1,000 characters

## 4. Server routes

Everything is under `/api/pride/` and follows Gluttony's conventions (the
envelope, session tokens, 401 meaning signed out, ISO dates). `docs/api.md` is
the contract for both apps.

| Route | What it does |
|---|---|
| `POST /auth`, `POST /device/identify`, `POST /signout`, `GET/DELETE /devices` | Sign-in, sign-up with a key, device sign-in, sign-out, devices. |
| `GET /catalog?version=` | The whole catalog (with muscles, equipment, steps, picture paths), or "unchanged" when the version matches. |
| `GET/POST/PUT/DELETE /exercises` | The person's own exercises. Deleting one that appears in a workout hides it instead. |
| `GET/PUT /profile` | Profile and equipment. |
| `GET /starters`, `POST /starters/<key>/adopt` | Starter programs; adopting copies one into the person's programs (variant chosen by their equipment, rep ranges by their goal). |
| `GET/POST/PUT/DELETE /programs`, `POST /programs/<id>/activate`, `PUT /programs/<id>/days` | Programs, the active program, planned weekdays. |
| `POST/PUT/DELETE /routines`, `POST /routines/reorder` | Routines and their rotation order. |
| `POST/PUT/DELETE /routine-items`, `POST /routine-items/reorder` | A routine's exercises. |
| `GET /today` | Next up, the next planned day, its items with last time's sets, and open suggestions for it. |
| `GET/POST/PUT/DELETE /workouts` | Workouts; `POST` with a known `ClientID` returns the stored one. Saving returns the result card (new records, new suggestions). |
| `GET /progress/<exerciseId>` | The series for charts (best set, estimated one-rep max, volume) by date. |
| `GET /records` | Records per exercise. |
| `POST /suggestions/<id>/accept`, `POST /suggestions/<id>/dismiss` | Accepting writes the proposed target onto the routine item. |
| `POST /api/pride-admin/import` | The importer's batch, behind the admin token. |

**Checks**, matched by `forms.mjs`:
- rep range low ≤ high, both 1–100
- sets 1–20
- weights 0–2,000
- seconds 1–36,000
- each measure only accepts its own fields
- a workout has at least one set
- `PerformedOn` is not later than tomorrow (time zones)

## 5. Rules (`server/prideRules.py`)

The rules run on the server whenever a workout is saved, edited or deleted.
Each is a plain function, table-tested.

**Next up:**
- In the active program, next up is the routine after (by `OrderIndex`, wrapping round) the routine of the person's latest workout in that program. Latest means by `PerformedOn`, then `CreatedAt`.
- With no workouts yet, or if that routine is gone, next up is the first routine.
- Logging a different routine moves the rotation on from the one logged.

**Next planned day:**
- It is the first planned weekday from today. Today counts unless a workout is already logged today.
- With no planned days, Today says "whenever you're ready".
- Missed days are never stored or shown.

**Increase suggestion** (for `weight_reps`, and `reps` with added weight):
- **When:** in the latest workout of a routine item, every working set (not warm-ups) reached `RepsMax` at or above the target weight.
- **Proposed weight:** the target plus the increment for the exercise's region. `upper` and `full` use `UpperIncrement`; `lower` uses `LowerIncrement`. It is rounded to the nearest loadable step (5 lb or 2.5 kg).
- **`reps` with no added weight:** it proposes the rep range raised by 2.
- **`time`:** when every working set reached `TargetSeconds`, it proposes the target plus 10 seconds.
- **`distance_time`:** no suggestion in part 1.

**Stall:**
- **When:** an item's last 3 workouts brought no improvement in its best set (estimated one-rep max for `weight_reps`, reps for `reps`, seconds for `time`) over the best before them.
- **What:** a `stall` suggestion with a tip: "try a lighter week, or swap the exercise".
- **How often:** at most one until the item improves again.

**Lifecycle:**
- At most one open suggestion per item. A newer one replaces it, and the old one becomes `withdrawn`.
- A suggestion whose workout is edited or deleted is recalculated, and withdrawn if it no longer holds.
- **Dismissed:** that item gets nothing more until another qualifying workout.

**Records** (per exercise, across all of a person's workouts):
- heaviest weight
- best estimated one-rep max (Epley, `w × (1 + r/30)`, sets of 12 reps or fewer, always labelled "estimated")
- most reps in a set
- longest time
- longest distance, and fastest pace

A record that is beaten shows as **New crown** on the result card.

**Units:** comparisons convert to kg internally. Displayed numbers are always in
the person's units, and a set entered in lb is shown in lb.

## 6. The pages

**Navigation:** a side rail: Today, Programs, Catalog, Progress, Settings.
Ctrl+K searches the catalog from anywhere.

- **Sign-in:** device sign-in, otherwise username/password, or sign-up with a key.
- **Intro:** shown after sign-up while the state is `pending`.
  - **Steps:** welcome → days a week (2–6) → equipment → goal → a suggested starter. The equipment presets are full gym, dumbbells and a bench, or bodyweight and bands; each fills `UserEquipment` and can be changed piece by piece in Settings.
  - **The starter:** shown with a preview of its week, then **Use this**, **Tweak it first** (adopt, then open the routine editor) or **Build my own** (an empty program).
  - **Skip** on every step sets `skipped` and opens Programs with an empty program. Finishing sets `done`.
  - **Settings › Show the introduction again** replays it. Replaying only ever adds a program, never changes one.
  - **Starter mapping:**
    - 2–3 days → "Foundations" (full body, A/B rotation), planned Mon/Wed/Fri (or Tue/Fri for 2)
    - 4 → Upper/Lower, Mon/Tue/Thu/Fri
    - 5–6 → Push/Pull/Legs, Mon–Fri or Mon–Sat
  - **Rep ranges by goal:** strength 5–8, muscle 8–12, general 10–15, at 3 sets.
- **Today:**
  - the **Next up** card ("Pull · planned for Wednesday") with its exercises and targets
  - open suggestions beside the exercises they belong to ("3×12 last time: try 140 lb", **Take it** / **Not yet**), and stall notes with their tip
  - **Log this workout**
  - a week strip of planned and done days (never "missed")
  - the latest crowns
  - With no program yet: a card offering the intro or an empty program.
- **Programs:** a person's programs with the active one marked; create, rename, duplicate, delete, activate.
  - Inside a program: routines in rotation order (drag to reorder) and the planned-weekday chips.
- **Routine editor:** one row per item, dragged into order: exercise, sets, rep range (or target time or distance), target weight, rest, note.
  - **Add exercise** opens the catalog picker, filtered by the person's equipment by default (one click shows everything).
- **Catalog:** a filter side panel (muscle, equipment, measure, level, mine only), search, and tiles with pictures. **Add my own exercise** (name, equipment, muscles, measure, optional steps) lives here.
- **Exercise page:**
  - pictures, primary and secondary muscles, steps, equipment
  - the person's history and records for it
  - **Add to a routine…**
  - the source's credit and licence
- **Log a workout:** date (today by default) and routine (next up by default, any routine, or a free workout).
  - Rows come filled from the targets and from last time, with suggestions shown. The person changes what differed.
  - Sets and exercises can be added or removed, and sets marked as warm-ups.
  - Saving shows the **result card** (new crowns, new suggestions, the next up after this).
  - Past workouts open in the same page for editing, or to delete with a confirmation.
- **Progress:**
  - a chart per exercise (best set, estimated one-rep max, volume; choose the exercise from a list of those logged)
  - records
  - the workout history, newest first
  - workouts per week
- **Settings:**
  - account and devices
  - units
  - the two increments
  - equipment, goal, days a week, week start
  - **Show the introduction again**
  - the look tokens, resettable

## 7. Look and voice

**"Superbia":** violet into royal purple, gold accents for crowns and
suggestions, on a near-black ink ground. Tokens live in `Preferences`, are
resettable, and follow Gluttony's token names.
- **Starting values** (final ones are picked from the milestone 1 mockups): ink `#0E0B14`, surface `#1A1424`, violet `#6B3FD9`, royal `#8E5CF5`, gold `#E3B341`, text `#EDE7F6`.
- **Fonts:** the heading face is chosen in the same mockups from fonts under the SIL Open Font License, bundled with their licence. Body text uses a system face, as Gluttony does.
- **The icon:** the owner's violet crown on black (`prideAppIcon.png`, from the owner's sin app logos). It is committed to `app/assets/icons/`, with a Windows `.ico` made from it.

**The voice** is proud, with a wink, and never shaming:
- **"New crown"** for a record
- **"Earned it"** for an accepted step up
- **"Holding steady"** for a stall
- **"Next up"** on Today

Missed days, failure and guilt are not in the vocabulary. Every word lives in
`words.mjs`.

## 8. Errors

- **Server out of reach:**
  - the cached catalog and every screen stay usable
  - a banner says Pride can't be reached
  - saving is refused with "Can't reach Pride right now. Nothing was lost; try again."
  - the form keeps what was typed
- **401** returns to Sign-in.
- **Checks fail:** the field says why in plain words, and the server's refusal names the field.
- **History is never broken by deleting:**
  - a deleted routine or item leaves past workouts with their exercises
  - an own exercise that was logged is hidden, not deleted
  - catalog exercises are only ever hidden
- **Two devices editing the same thing:** the last write wins. `UpdatedAt` is returned, so a later change can warn if it is needed.
- **The importer** stops, publishing nothing, if the upstream file doesn't match the expected shape or the change report would hide more than 10% of the catalog.

## 9. Testing

- **Server:** pytest with Gluttony's MySQL fake (it refuses what real MySQL refuses, such as unread cursors), plus a real-MySQL smoke test at rollout.
- **Rules:** table tests for next up, the planned day, increases (each measure, each region, rounding in lb and kg), stalls, records, and recalculation after an edit or delete.
- **Importer:** tests against a small checked-in fixture slice of free-exercise-db. The fixture is public domain.
- **App:** Qt Test (ctest) for services, qmltestrunner for `units.mjs`, `forms.mjs` and page logic, all against the stub server.
  - The stub serves a fixture catalog unless a real snapshot is taken. The snapshot is git-ignored.
  - `grab.ps1` takes screenshots of every page for review.

## 10. Keeping the public repository clean

- **Git-ignored:**
  - `.env`, `config/secrets.json`, `app/config/secrets.json`, and the server's admin config
  - `docs/superpowers/plans/`
  - `app/tests/stub/snapshot/`, `importer/cache/`, `build/`, `.venv/`, `__pycache__/`, `.worktrees/`, `.superpowers/`
- **Commits:** the repository's local git config uses the GitHub no-reply email.
- **Never committed:** server addresses (LAN or tunnel), SSH logins, tokens, passwords or emails, in code, specs, tests or fixtures. Specs say "the tunnel hostname" and "plutus", never addresses.
- **`tools/check-public.ps1`** (written in milestone 1) greps the tracked tree and the commits about to be pushed for:
  - private IP ranges
  - `user@host` logins
  - token-shaped strings (long hex or base64)
  - email addresses other than the no-reply one
  - files named `.env` or `secrets.json`

  It fails on any hit. It runs before every push; a hit stops the push and goes to the owner.

## 11. The iOS handoff

At the end of milestone 4, an `ios` branch is cut from `main`. It adds
`docs/ios-handoff.md`, written so a session on the owner's MacBook can start
from it and `docs/api.md` alone. The handoff covers:

- **What the app is:** the gym companion, in Qt 6.11 for iOS.
  - **Start:** Next up from `/today`, or any routine.
  - **Set by set:** each set is filled from the target and from last time, with an open suggestion shown on its exercise.
  - **Ticking a set:** nudge the weight or reps, then tick. The rest timer starts, notifies while the phone is locked, and the screen stays awake.
  - **Swap for today:** if a machine is busy, swap an exercise for this session only, without changing the plan.
  - **Finish** sends the whole workout once with its `ClientID`, with `StartedAt` and `EndedAt`, and shows the result card.
- **What it isn't:** no program editing, no catalog browsing beyond the swap picker, no charts.
- **Offline:** a finished workout waits on the phone until the server answers. The server already stores a resent `ClientID` once.
- **What it reuses:**
  - the C++ foundations (`Api`, `SessionAuth`, `AuthNetworkFactory`, `AppConfig`, `AccountStore`)
  - the Superbia tokens, `words.mjs` and `units.mjs`
  - the crown icon (the App Store needs a 1024×1024 export, which may be larger than the current file)
- **Platform notes to work out on the Mac:** the Qt for iOS kit, signing, keep-awake, local notifications for the rest timer, and keychain storage for the session token.

## 12. Milestones

Each milestone is planned and built in its own fresh session.

1. **Foundations and catalog:**
   - mockups (Today and Log a workout, three options each; tokens and heading font)
   - repository, `.gitignore`, `check-public.ps1`
   - the importer, the schema, the catalog and auth routes
   - the app shell with the copied foundations
   - Sign-in, Catalog and Exercise pages, and ExerciseStore
2. **Planning:**
   - Profile, and the intro with Skip and replay
   - starter programs (written by Claude, reviewed by the owner)
   - Programs and the routine editor
   - own exercises
   - `/today` with next up and the planned day
3. **Logging and progress:**
   - log, edit and delete workouts
   - `prideRules.py` (suggestions, stalls, records, recalculation)
   - the result card, Progress, and accepting or dismissing suggestions
4. **Rollout and the iOS handoff:**
   - **On plutus:** `prideDB` and the schema, the DBUtils mapping, the Caduceus registration, and pictures in `appFiles/pride`. nginx for the tunnel hostname, which the owner creates.
   - the first real import
   - a release package with the icon and the MSVC runtime
   - a live check
   - the `ios` branch with `ios-handoff.md`
   - `check-public.ps1`, then the public push

## Done when

- A new account can sign up with a key, take the intro or skip it, and end with an active program.
- An experienced person can skip the intro and type their own program in, including their own exercises.
- A finished workout can be entered, edited and deleted. Today's next up follows the rotation, and the week strip never shows a miss.
- Hitting the top of a rep range on every set produces an increase suggestion. Accepting it changes the routine's target, and dismissing it leaves the routine alone.
- Records show as New crown on the result card, and the Progress charts show them.
- All tests pass (server, rules, importer, app), and `check-public.ps1` is clean on the pushed tree.
- The server runs live on plutus, and the `ios` branch holds a handoff a Mac session can start from.

## Owner's calls still open

- A LICENSE file: none means all rights reserved, as in Gluttony.
- Creating the tunnel hostname before milestone 4, as for Gluttony.
- The final colours, heading font and layouts, picked from the milestone 1 mockups.
