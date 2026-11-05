# Pride API (part 1)

The contract between Pride's apps (the desktop app in `app/`, and the iOS app of part 2) and the routes on plutus:
`server/prideRoutes.py` at `/api/pride` and, for the catalog importer only, `server/prideAdminRoutes.py` at
`/api/pride-admin`. The desktop app's stub (`app/tests/stub/stub_server.py`) imitates `/api/pride`. Milestone 1's
routes are below; each later milestone adds its own.

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

## Account

| Route | Body | Answer |
|---|---|---|
| `GET /ping` | | `{"status":"ok"}` |
| `POST /device/identify` | `{fingerprint}` | known device: `{status:"ok", UID, username, token}`; unknown: `{status:"new"}` |
| `POST /auth` | `{username, password, fingerprint, key?}` | `{status:"ok", UID, username, token}`. With `key` it signs up (and makes the person's profile, intro pending): `403 invalid_key` for an unknown or used key, `409 username_taken`, `400` for a username outside 3–32 characters or a password outside 8–256. Without `key`: `401 invalid_credentials`. |
| `POST /signout` | `{fingerprint}` | `{status:"ok"}`; this device is forgotten and its sessions end |
| `GET /devices` | | `data: [{id, label, current, lastSignIn}]`, newest first. `id` is the first 16 hex of the fingerprint's SHA-256; the fingerprint itself never leaves the server. |
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
- A person's own exercises are not here; milestone 2 adds them at `/exercises`.

`GET /pictures/<name>` → the JPEG, `Cache-Control: private, max-age=86400`; `404` for a name that is not
`<20 hex>.jpg` or not there. A picture's name is the first 20 hex of the SHA-1 of its bytes, so a name never changes
meaning and the app can keep a copy for good.

## Admin (`/api/pride-admin`, LAN only)

For the catalog importer (`importer/`). The tunnel never routes this prefix. Every request needs `X-Admin-Token`, the
token in `server/prideAdminConfig.json` on plutus (never committed); without it: `401`. A request carrying `CF-Connecting-IP` (anything the tunnel carries) is refused `404` before the token is looked at, so the prefix is LAN only in the server itself, not only in the proxy.

| Route | Body | Answer |
|---|---|---|
| `GET /state` | | `{status:"ok", version, exercises: [{source, key, name, hash, removed}]}`: every catalog row, for the change report |
| `GET /pictures` | | `{status:"ok", pictures: [name]}`: the pictures the server has |
| `PUT /pictures/<name>` | the JPEG's bytes | `{status:"ok", stored: name}`; `400` when the name is not `<20 hex>.jpg`, the bytes are not a JPEG or do not hash to the name; `413` over 2 MB. Sending one already there is `ok`. |
| `POST /import` | `{source, exercises: [import exercise]}`: `source` is once for the whole batch (1 to 40 lowercase letters, digits or dashes; not `own`), and an import exercise is an exercise as above without `id`, `source` and `removed`, plus `hash` (40 hex, the importer's hash of the exercise's content). Checks, each naming the field on a `400`: at most 5000 exercises per import; `key` 1 to 100 characters and unique within the batch; `name` 1 to 120 and `licence` 1 to 80 (not blank); `category`, `level`, `measure`, `region` one of the words above; `primary` and `equipment` at least one known word, each word once; `secondary` known words, each once, none already in `primary`; `steps` at most 50, each 1 to 1000 characters (not blank); `pictures` at most 10, distinct, each `<20 hex>.jpg`; `hash` 40 hex. | `{status:"ok", added, changed, unchanged, hidden, version}`. The whole source in one transaction: new keys are added, changed ones replaced, ones missing from the batch hidden, hidden ones that return shown again. `400` naming the first exercise that fails a check, or a picture the server does not have yet; `409` when it would hide more than 10% of the source's visible exercises. Nothing is written on any refusal. |
