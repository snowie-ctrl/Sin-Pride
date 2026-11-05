# Pride: the roadmap

Status: approved by the owner 2026-11-05 (designed in conversation section by section).

Pride is the sibling of Gluttony. Gluttony answers "what should I eat?" and is
deliberately not a health app. Pride covers exactly that missing scope: a
low-effort health and fitness tracker for an everyday person or a beginner.
It tracks what a person tells it (what they lifted, what they ate, what they
weigh) and shows them clearly where they stand against the goals they set.

This file is the whole-project picture. Each part gets its own spec, plan and
session. Part 1's spec is `2026-11-05-training-design.md`.

## What Pride is, and is not

- **Is:** routines and splits a person builds and follows, a log of what they
  did, progress they can see, macro targets they choose, and gentle nudges
  ("try a little more weight", "protein has been short this week").
- **Is not:** a medical app. No medical records, no diagnoses, no forcing a
  diet or a training style, no constant body measuring. Every nudge comes from
  a readable rule, can be dismissed, and is worded as a suggestion.
- **Beginner first, never in an expert's way.** A guided start for people who
  want one, and a Skip button for people who already know their routine.

## Decisions that hold for every part

| Topic | Decision |
|---|---|
| Users | Personal for now (the owner and friends), but built so going public needs no rework. |
| Data | Server-backed, like Gluttony: Flask blueprints in Caduceus on plutus, a `prideDB` MySQL database. |
| Accounts | Pride's own accounts (sign-up with a login key, device sign-in), separate from Gluttony's. A later setting links a Pride account to a Gluttony account. |
| Desktop | Windows, Qt 6.11 QML/C++. Planning routines, logging stats, entering or fixing workouts, reviewing progress. |
| iOS | Qt 6.11 for iOS, reusing the desktop's C++ foundations. The in-gym tool: runs the next workout set by set. Same server and database, little overlap with the desktop. |
| Sources | Free only: no paid or premium APIs, no LLM APIs. Rules are readable JSON or Python, never machine learning. |
| Repository | Public on GitHub (`snowie-ctrl/Sin-Pride`). No server addresses, logins, tokens or emails are ever committed (see part 1's spec, section 10). |
| Look | "Superbia": violet into royal purple, gold accents, on a near-black ink ground. The icon is the owner's violet crown (`prideAppIcon.png`). |
| Voice | Proud, with a wink, never shaming. Missed days and failure are not in its vocabulary. |

## The parts

| Part | What it is | Where |
|---|---|---|
| **1. Training** | The exercise catalog (free-exercise-db), accounts, guided start, programs and routines in rotation, entering finished workouts, progress (history, records, charts), and progression suggestions. Ends by writing the iOS handoff onto an `ios` branch. | Desktop, plutus |
| **2. Gym companion** | The iOS app: start Next up, go set by set, rest timer, swap an exercise for today, finish and send. Uses only part 1's API. Built from a session on the owner's MacBook, starting from `docs/ios-handoff.md`. | iOS |
| **3. Nutrition and body** | Calorie and macro targets from a goal (lose / keep / gain, always overridable), food logging (quick-add numbers, or search USDA FoodData Central), and a body-weight log. Places the Gluttony door. | Desktop |
| **4. The watcher** | Gentle, rule-based nudges across training, body and food: weight moving faster than the goal suggests, protein short most days this week, a nutrient low over a fortnight, a lift stalled. Never diagnoses, always dismissable. | Desktop, iOS |
| **5. Through the door** | Link a Gluttony account; Pride lists the meals marked Devoured in Gluttony and asks "log any of these?"; recipe suggestions to close a macro gap or meet a surplus. Waits on Gluttony part 3 (nutrition in Gluttony's catalog). | Pride, plus one Settings row in Gluttony |
| **Later** | Public readiness: open sign-up instead of hand-made keys, export and delete my data, a privacy page. | Both |

Part 3's food source should match whatever Gluttony part 3 uses to map
ingredients to nutrients (likely USDA FoodData Central), so the mapping is
built once and the two apps agree on what a food contains.

## The Gluttony door

Gluttony must never make a person feel judged for the recipe they picked, so
**Gluttony gets no "send to Pride" button and no health wording anywhere.**

- Gluttony already records a **Devoured** mark (one row, with a date, each
  time a person makes a recipe). That is the hook: once two accounts are
  linked, Pride reads "what you marked Devoured today" and offers to log it.
- Gluttony's only change (part 5) is a neutral **Connected apps** row in its
  Settings, where the person approves or removes the link.
- **Part 3 builds Pride's side of the door and leaves the other side empty:**
  - every food entry carries a `source` (`usda`, `custom`, and `gluttony` reserved);
  - Settings shows "Gluttony: coming later";
  - `docs/gluttony-door.md` states exactly what Pride will ask Gluttony for
    (linked-account handshake, Devoured marks by date, a recipe's nutrition
    per serving) so Gluttony part 5 can be written against it.
- Part 1 does nothing for the door beyond this roadmap.

## Order and sessions

Parts are built in the order above, one spec → plan → build cycle per part,
and one fresh session per milestone (the owner's preference from Gluttony).
After each part, the owner gets a whole-project status: what is done, what is
next, what waits on them.
