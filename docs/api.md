# Pride API (part 1)

The contract between Pride's apps (the desktop app in `app/`, and the iOS app of part 2) and the routes on plutus:
`server/prideRoutes.py` and `server/prideUserRoutes.py` at `/api/pride` and, for the catalog importer only, `server/prideAdminRoutes.py` at
`/api/pride-admin`. The desktop app's stub (`app/tests/stub/stub_server.py`) imitates `/api/pride`. Milestones 1
to 3's routes are below; each later milestone adds its own.

## Conventions

- JSON bodies. Every answer has `status`: `"ok"`, `"error"`, or a named outcome (`"new"`, `"invalid_key"`, …). Errors
  carry `message`. Data is under `data`, except the sign-in answers, which put `UID`, `username` and `token` beside
  `status` (Gluttony's shape).
- Every route needs the header `X-Session-Token` except `GET /ping`, `POST /auth` and `POST /device/identify`.
  Without a live session: `401 {"status":"error","message":"not signed in"}`, which the app takes as "signed out".
- The app also sends `X-Device-Fingerprint` (SHA-256 of the machine id) on every request.
- `POST /auth` allows 5 attempts a minute and `POST /device/identify` 10, per caller: `429 "too many attempts"`.
- A 5xx through the tunnel is `{"status":"error","message":"server error"}`; at home it names the cause.
- Dates are ISO 8601; moments are UTC with a `Z`.
- A refusal of what was sent is `400 {status:"error", field, message}`, naming the body field. An id that is not the
  caller's is `404 "not found"`. Past a limit: `409 {status:"limit", field, message}`; a suggestion no longer open: `409 {status:"closed", message}`.

## Account

| Route | Body | Answer |
|---|---|---|
| `GET /ping` | | `{"status":"ok"}` |
| `POST /device/identify` | `{fingerprint}` | known device: `{status:"ok", UID, username, token}`; unknown: `{status:"new"}`; `400 "missing fingerprint"` when none is sent |
| `POST /auth` | `{username, password, fingerprint, key?}` | `{status:"ok", UID, username, token}`. With `key` it signs up (and makes the person's profile, intro pending): `403 invalid_key` for an unknown or used key, `409 username_taken`, `400` for a username outside 3–32 characters or a password outside 8–256. Without `key`: `401 invalid_credentials` (also for an unknown username or a password over 256 characters). |
| `POST /signout` | none | `{status:"ok"}`. The server reads no body: the device is the one the presented session was made for (a fingerprint sent anyway is ignored), so only that device is forgotten and its sessions end, and the presented session always ends. There is no `400`; the session is the only thing it needs. |
| `GET /devices` | | `data: [{id, label, current, lastSignIn}]`, newest first. `id` is the first 16 hex of the fingerprint's SHA-256; the fingerprint itself never leaves the server. `lastSignIn` is when the device's newest session began (null when it has none). |
| `DELETE /devices/<id>` | | `{status:"ok"}`, that device signed out and forgotten (an id that is none of this person's devices is nothing to remove, also `ok`); `400` for the device asking (it signs out instead); `404` for an id that is not 16 hex |

## Catalog

`GET /catalog?version=<v>` → `data: {version, exercises: [exercise]}`, or `data: {version, unchanged: true}` when
`<v>` is the current version. `version` is `null` while nothing has been imported (and `exercises` is `[]`).

An exercise:

```json
{"id": 12, "key": "Barbell_Curl", "source": "free-exercise-db", "licence": "Unlicense",
 "name": "Barbell Curl", "category": "strength", "level": "beginner",
 "measure": "weight_reps", "region": "upper", "removed": false,
 "primary": ["biceps"], "secondary": ["forearms"], "equipment": ["barbell"],
 "steps": ["Stand up with your torso upright…", "…"],
 "pictures": ["0123456789abcdef0123.jpg", "…"]}
```

- Every catalog exercise is listed, ordered by name. One that has gone from its source has `removed: true`: history
  still names it, but browsing and search leave it out.
- Words: `measure` is `weight_reps`, `reps`, `time` or `distance_time`; `region` is `upper`, `lower` or `full`;
  `equipment` words are `barbell`, `dumbbell`, `kettlebell`, `machine`, `cable`, `bands`, `bodyweight`, `bench`,
  `pull-up bar`, `other`; muscles, `category` and `level` are free-exercise-db's.
- A person's own exercises are not here; they are at `/api/pride/exercises` (see Own exercises).

`GET /pictures/<name>` → the JPEG, `Cache-Control: private, max-age=86400`; `404` for a name that is not
`<20 hex>.jpg` or not there. A picture's name is the first 20 hex of the SHA-1 of its bytes, so a name never changes
meaning and the app can keep a copy for good.

## Own exercises

A person's own exercises, at `/api/pride/exercises`; every route needs a session and sees only that person's.

| Route | Body | Answer |
|---|---|---|
| `GET /exercises` | | `data: [own exercise]` by name, hidden ones included |
| `POST /exercises` | `{name, measure, primary, secondary?, equipment, steps?}` | `data: own exercise`; `409` (`status: "limit"`) at 200 shown own exercises |
| `PUT /exercises/<id>` | as POST | `data: own exercise` |
| `DELETE /exercises/<id>` | | `data: {routinesTouched, hidden}` |

An own exercise is the catalog's exercise shape with `source: "own"`, `key: "own-<16 hex>"`, `licence`, `category` and
`level` `null`, `pictures: []`, `region` from the primary muscles, and `removed` true once hidden:

```json
{"id": 900, "key": "own-0123456789abcdef", "source": "own", "licence": null,
 "name": "Sandbag Carry", "category": null, "level": null,
 "measure": "distance_time", "region": "upper", "removed": false,
 "primary": ["forearms"], "secondary": ["traps"], "equipment": ["other"],
 "steps": ["Pick it up.", "Walk."], "pictures": []}
```

A refused field is `400` naming it; an id that is not the person's, or is hidden, is `404`. The measure can't change
once a routine item or a workout names the exercise (`400`, field `measure`). Deleting one takes it out of the
person's routines, then deletes it, or hides it (`removed: true`) when a workout names it; `routinesTouched` is how
many routines it was taken out of.

## Profile

| Route | Body | Answer |
|---|---|---|
| `GET /profile` | | `data: profile` (a person with no profile row gets one made with the defaults) |
| `PUT /profile` | any of the profile's keys (`equipment` replaces the whole list) | `data: profile`. Units changed without increments: the increments become that unit's defaults (5/10 lb, 2.5/5 kg). |

A profile: `{units, goal, daysPerWeek, upperIncrement, lowerIncrement, weekStart, introState, equipment: [words]}`;
`equipment` is in the catalog's equipment order and the increments are numbers (0.25 to 100 in steps of 0.25; days a
week 2 to 6).

## Programs

A person's programs, at `/api/pride/programs`; every route needs a session and sees only that person's. Every write
to a program answers with the whole program, so the app replaces its copy; activate and delete answer with the list.

| Route | Body | Answer |
|---|---|---|
| `GET /programs` | | `data: [program row]` by creation |
| `POST /programs` | `{title}` | `data: program` (the person's first is active); `409` (`status: "limit"`) at 20 programs |
| `GET /programs/<id>` | | `data: program` |
| `PUT /programs/<id>` | `{title}` | `data: program` |
| `POST /programs/<id>/duplicate` | | `data: program` (new, not active); `409` at 20 programs |
| `DELETE /programs/<id>` | | `data: [program row]` |
| `POST /programs/<id>/activate` | | `data: [program row]` |
| `PUT /programs/<id>/days` | `{days: [weekdays]}` | `data: program` |

Weekdays are 0 (Monday) to 6 (Sunday). A program, a program row and an item (absent targets are `null`):

```json
{"id": 5, "title": "Upper/Lower", "active": true, "starterKey": "upperLower", "days": [0, 3],
 "updatedAt": "2026-11-15T09:00:00Z",
 "routines": [{"id": 50, "title": "Upper", "items": [
   {"id": 500, "exerciseId": 12, "sets": 3, "repsMin": 8, "repsMax": 12, "targetWeight": 135.0,
    "targetUnit": "lb", "targetSeconds": null, "targetDistance": null, "distanceUnit": null,
    "restSeconds": 90, "note": null}]}]}
```

```json
{"id": 5, "title": "Upper/Lower", "active": true, "starterKey": "upperLower", "days": [0, 3],
 "routineCount": 2, "updatedAt": "2026-11-15T09:00:00Z"}
```

The first program a person makes is active. Duplicate makes "<title> copy" (60 characters at most), not active, with
the same days, routines and items. Deleting the active program leaves none active. A refused field is `400` naming it
(a blank or over-long `title`, `days` that are not distinct weekdays 0 to 6); an id that is not the person's is `404`.

## Routines and items

A program's routines and their exercises, at `/api/pride/routines` and `/api/pride/routine-items`; every route needs a
session and sees only that person's. Every write answers with the whole program (see Programs). New routines and items
go last; a reorder sends the whole new order, refused (`400`, field `order`) unless it lists exactly the program's
routines (or the routine's items), each once.

| Route | Body | Answer |
|---|---|---|
| `POST /routines` | `{programId, title}` | `data: program`; `409` (`status: "limit"`) at 14 routines |
| `PUT /routines/<id>` | `{title}` | `data: program` |
| `DELETE /routines/<id>` | | `data: program` (its items go with it) |
| `POST /routines/reorder` | `{programId, order: [ids]}` | `data: program` |
| `POST /routine-items` | `{routineId, exerciseId, ...targets?}` | `data: program`; `409` at 30 items |
| `PUT /routine-items/<id>` | every target field | `data: program` |
| `DELETE /routine-items/<id>` | | `data: program` |
| `POST /routine-items/reorder` | `{routineId, order: [ids]}` | `data: program` |

A new item's targets default by its exercise's measure and the person's goal (3 sets of the goal's rep range; 3 x 30 s;
one set for distance and time); targets sent with it replace those. `PUT` sends every target: one left out is cleared.
Only exercises in the catalog or the person's own, not hidden, can be added; one hidden later stays in its routines.
A refused field is `400` naming it; an id that is not the person's is `404`.

## Starters

| Route | Body | Answer |
|---|---|---|
| `GET /starters` | | `data: [starter]` (Foundations, Upper/Lower, Push/Pull/Legs) |
| `POST /starters/<key>/adopt` | | `data: program` (new, the active one); `404` for an unknown key; `409` (`status: "limit"`) at 20 programs; `409` (`status: "unavailable"`) when none of its exercises are in the catalog |

A starter: `{key, title, blurb, suggested, variant, days, routines: [{title, items: [{exerciseId, name, measure, sets, repsMin, repsMax, targetSeconds, restSeconds}]}], missing: [keys]}`.

Each starter is filled for the caller: the variant their equipment allows (gym, dumbbell, bodyweight), the planned weekdays for their days a week, 3 sets of their goal's rep range (timed items keep their own seconds), 90 s rest for weight × reps and 60 s otherwise. An exercise not in the catalog is left out and listed in `missing`. `suggested` marks the starter for their days a week. Adopting makes a new program, the active one. A routine whose exercises are all missing from the catalog comes back with no items (the starters are left as written); the rest of the starter is still adopted.

## Today

| Route | Body | Answer |
|---|---|---|
| `GET /today?date=YYYY-MM-DD` | | `data: {program, nextUp, plannedDay, week}`; `400` naming `date` when it is missing or not a date |

`date` is the app's local date. `nextUp` is the routine after the latest workout's in the active program (by rotation, wrapping round), or the first. `plannedDay` is the first planned weekday from `date`, `date` itself unless a workout is already logged that day. `week` is the 7 days from the profile's week start holding `date`: `done` when any workout is logged that day; `planned` only on `date` and later and never on a done day. The answer: `program` is `{id, title}` or `null` (no active program); `nextUp` is `{routineId, title, items: [item]}` or `null`; `plannedDay` is a date or `null`; `week` is `[{date, weekday, planned, done}]`. Milestone 3 adds last time's sets, open suggestions and the latest crowns.

## Workouts

A person's finished workouts, at `/api/pride/workouts`; every route needs a session and sees only that person's
(`prideLogRoutes.py`).

| Route | Body | Answer |
|---|---|---|
| `GET /routines` | | `data: [{id, title, programId, programTitle, active}]`: every routine of the person, the active program's first, each program's in rotation order (the Log page's menu) |
| `GET /workouts/draft?routineId=<id>` | | `data: {routineId, title, programId, items: [draft item]}`; `400` naming `routineId` without one; `404` for a routine that is not the person's |
| `GET /workouts` | | `data: [workout row]`, newest first (by date, then by when it was saved) |
| `GET /workouts/<id>` | | `data: workout` |
| `POST /workouts` | a workout | `data: {workout, crowns: [crown], suggestions: [suggestion], nextUp: {routineId, title} \| null}`. A `clientId` already stored for this person answers that workout the same way, storing nothing; one another person used is `400` naming `clientId`. |
| `PUT /workouts/<id>` | a workout (`clientId` may be left out) | as POST. The date, note, exercises and sets are replaced; the routine stays as logged. |
| `DELETE /workouts/<id>` | | `data: {deleted: id, nextUp}` |

A workout as sent: `{clientId, performedOn, routineId, note, exercises: [{exerciseId, itemId, note, sets: [set]}]}`.
`clientId` is a UUID the app makes, so a resend is stored once. `performedOn` is the person's own date, at most
tomorrow by the server's. `routineId` is `null` for a free workout; the program is taken from the routine. `itemId`
is the routine item an exercise was planned as, or `null`. A routine or item that is not the person's (say, deleted
on another device meanwhile) is not refused: the link is dropped and the workout or exercise saved as free.

A set: `{warmup, weight, weightUnit, reps, seconds, distance, distanceUnit}`, by the exercise's measure: weight ×
reps needs `weight` (0 to 2,000) with `weightUnit` (`lb`/`kg`) and `reps` (1 to 1,000); reps needs `reps` and may
carry a weight; time needs `seconds` (1 to 36,000); distance and time needs `distance` (above 0, up to 1,000, with
`distanceUnit` `km`/`mi`/`m`), `seconds`, or both. Fields the measure does not log must be `null` or absent. 1 to 20
sets an exercise, 1 to 30 exercises a workout, a routine item at most once. Each set keeps the number and unit as
entered. A refused field is `400` naming it.

A workout as answered: `{id, clientId, performedOn, startedAt, endedAt, programId, routineId, title, note,
createdAt, updatedAt, exercises: [{exerciseId, itemId, measure, note, sets: [set]}]}`; `title` is the routine's,
`null` for a free workout or a routine since deleted. A workout row: `{id, performedOn, routineId, title, note,
exerciseCount, setCount, updatedAt}`. A draft item: a routine item (see Programs) with `measure`, `last` (`{workoutId,
performedOn, sets: [set]}`: the latest workout that logged this item, or else this exercise; `null` when none) and
`suggestion` (its open suggestion or `null`).

Saving, editing or deleting a workout settles the suggestions of every routine item it logged (see Suggestions). The
result card's `crowns` are the records this workout beat (see Progress); an exercise's first workout earns none.
`suggestions` are the open ones based on this workout.

## Admin (`/api/pride-admin`, LAN only)

For the catalog importer (`importer/`). The tunnel never routes this prefix. Every request needs `X-Admin-Token`, the
token in `server/prideAdminConfig.json` on plutus (never committed); without it: `401`. A request carrying `CF-Connecting-IP` (anything the tunnel carries) is refused `404` before the token is looked at, so the prefix is LAN only in the server itself, not only in the proxy.

| Route | Body | Answer |
|---|---|---|
| `GET /state` | | `{status:"ok", version, exercises: [{source, key, name, hash, removed}]}`: every catalog row, for the change report |
| `GET /pictures` | | `{status:"ok", pictures: [name]}`: the pictures the server has |
| `PUT /pictures/<name>` | the JPEG's bytes | `{status:"ok", stored: name}`; `400` when the name is not `<20 hex>.jpg`, the bytes are not a JPEG or do not hash to the name; `413` over 2 MB. Sending one already there is `ok`. |
| `POST /import` | `{source, exercises: [import exercise]}`: `source` is once for the whole batch (1 to 40 lowercase letters, digits or dashes; not `own`), and an import exercise is an exercise as above without `id`, `source` and `removed`, plus `hash` (40 hex, the importer's hash of the exercise's content). Checks, each naming the field on a `400`: at most 5000 exercises per import; `key` 1 to 100 characters and unique within the batch; `name` 1 to 120 and `licence` 1 to 80 (not blank); `category`, `level`, `measure`, `region` one of the words above; `primary` and `equipment` at least one known word, each word once; `secondary` known words, each once, none already in `primary`; `steps` at most 50, each 1 to 1000 characters (not blank); `pictures` at most 10, distinct, each `<20 hex>.jpg`; `hash` 40 hex. | `{status:"ok", added, changed, unchanged, hidden, version}`. The whole source in one transaction: new keys are added, changed ones replaced, ones missing from the batch hidden, hidden ones that return shown again. `400` naming the first exercise that fails a check, or a picture the server does not have yet; `409` when it would hide more than 10% of the source's visible exercises. Nothing is written on any refusal. |
