// Every word Pride shows, in one place, so the app's voice can be changed in one file (spec §7). The voice is proud,
// with a wink, and never shaming; where something went wrong the words stay plain. Missed days, failure and guilt are
// not in its vocabulary.

export const appName = "Pride"
export const signInTitle = "Pride"
export const signInTagline = "Where do you stand?"
export const signingIn = "Taking your throne…"
export const username = "Username"
export const password = "Password"
export const signUpKey = "Sign-up key"
export const haveAKey = "I have a sign-up key"
export const signIn = "Sign in"
export const createAccount = "Claim my account"
export const enterUsernameAndPassword = "Enter your username and password"
export const enterKey = "Enter your sign-up key"
export const unreachable = "Pride can't be reached right now. Check the connection and try again."
export const tryAgain = "Try again"
export const offline = "Pride can't be reached. What's on this device still works."
export const usernameLength = "A username is 3 to 32 characters"
export const passwordLength = "A password is 8 to 256 characters"

const signInErrors = {
    invalid_credentials: "Wrong username or password",
    invalid_key: "That key has been used or does not exist",
    username_taken: "That username is taken",
    bad_form: "A username is 3 to 32 characters and a password 8 to 256",
    too_many: "Too many tries for now. Wait a minute, then try again.",
    network: "Pride can't be reached right now. Check the connection and try again.",
    bad_reply: "Pride answered in a way this app doesn't understand. Try again later.",
    server: "Pride couldn't sign you in just now. Try again.",
}

// Session hands the Sign-in page a code (Session::loginFailed); the words live here.
export function signInError(code) {
    return signInErrors[code] || signInErrors.server
}

const deviceErrors = {
    not_yours: "That isn't one of your devices",
    this_device: "This is the device you're using. Sign out instead.",
    network: "Can't reach Pride right now. Try again.",
    server: "Pride couldn't do that just now. Try again.",
}

export function deviceError(code) {
    return deviceErrors[code] || deviceErrors.server
}

const failures = {
    network: "Can't reach Pride right now. Nothing was lost; try again.",
    server: "Pride couldn't do that just now. Try again.",
    bad_reply: "Pride sent a catalog this app can't read. Try again later.",
    not_found: "That's gone: it was changed or removed somewhere else.",
    unavailable: "None of that starter's exercises are in the catalog yet.",
}

// Why a save or a load failed, by the code a service reports; a code nobody taught the app reads as a server problem.
export function failure(code) {
    return failures[code] || failures.server
}

// A tile's second line: its primary muscles and how it is measured, leaving out whichever is missing.
export function tileCaption(primary, measure) {
    return [listLabel("muscle", primary), measure ? valueLabel("measure", measure) : ""].filter(s => s.length).join(" · ")
}

export const navToday = "Today"
export const navPrograms = "Programs"
export const navCatalog = "Catalog"
export const navSettings = "Settings"
export const signOut = "Sign out"

// Settings (spec §6). "neverSignedIn" avoids the banned word "late" that "lately" holds, so it says "recently".
export const settingsTitle = "Settings"
export const accountTitle = "Account"
export const signedInAs = "Signed in as"
export const devicesTitle = "Devices that sign in by themselves"
export const thisDevice = "This device"
export const removeDevice = "Sign it out"
export const lastSignIn = "Last signed in"
export const neverSignedIn = "Not signed in recently"
export const trainingTitle = "Training"
export const unitsTitle = "Units"
export const incrementsTitle = "Step-ups"
export const upperIncrement = "Upper body"
export const lowerIncrement = "Lower body"
export const incrementsHint = "How much a suggestion adds when you've earned it."
export const goalTitle = "Goal"
export const daysPerWeekTitle = "Days a week"
export const weekStartTitle = "Week starts on"
export const equipmentTitleSettings = "Your equipment"
export const introTitleSettings = "Introduction"
export const replayIntro = "Show the introduction again"
export const replayHint = "It only ever adds a program; yours stay as they are."
export const lookTitle = "Look"
export const resetLook = "Reset the look"
export const settingsSaved = "Saved"
export const profileUnavailable = "Your settings can't be loaded right now."

export const catalogTitle = "Catalog"
export const catalogFilter = "Narrow by name"
export const quickSearch = "Find an exercise (Ctrl+K)"
export const nothingFound = "No exercise by that name"
export const filtersTitle = "Filters"
export const resetFilters = "Reset"
export const nothingMatches = "Nothing matches those filters"
export const catalogLoading = "Gathering the catalog…"
export const catalogUnavailable = "The catalog isn't on this device yet."
export const catalogOffline = "Pride can't be reached to fetch it."

export const back = "Back"
export const works = "Works"
export const alsoWorks = "Also works"
export const equipmentTitle = "Equipment"
export const stepsTitle = "How it's done"
export const noSteps = "No steps written down for this one yet."
export const exerciseGone = "This exercise has left the catalog. Workouts that logged it keep it."
export const exerciseMissing = "That exercise isn't in the catalog."

export const facetTitles = { muscle: "Muscle", equipment: "Equipment", measure: "Measured by", level: "Level", mine: "Mine" }

const measures = { weight_reps: "Weight × reps", reps: "Reps", time: "Time", distance_time: "Distance and time" }
const levels = { beginner: "Beginner", intermediate: "Intermediate", expert: "Expert" }
const regions = { upper: "Upper body", lower: "Lower body", full: "Full body" }

// How a word from the catalog reads: Pride's own words for measures, levels and regions; muscles and equipment as
// they come, with a capital. A word the app doesn't know yet shows as it came.
export function valueLabel(facet, value) {
    if (facet === "measure")
        return measures[value] || value
    if (facet === "level")
        return levels[value] || value
    if (facet === "region")
        return regions[value] || value
    if (facet === "mine")
        return "Only mine"
    const text = String(value || "")
    return text.length ? text[0].toUpperCase() + text.slice(1) : text
}

export function listLabel(facet, values) {
    return (values || []).map(v => valueLabel(facet, v)).join(", ")
}

export function countLabel(n) {
    return n === 1 ? "1 exercise" : `${n} exercises`
}

export function shownOf(shown, total) {
    return shown === total ? countLabel(total) : `${shown} of ${countLabel(total)}`
}

export function pictureCount(index, total) {
    return `${index + 1} of ${total}`
}

// The credit a source asks for (spec §2), shown on every Exercise page.
export function creditLine(source, licence) {
    if (source === "free-exercise-db")
        return `From free-exercise-db, released into the public domain (${licence}).`
    return licence ? `From ${source} (${licence}).` : `From ${source}.`
}

// ---- Planning (milestone 2) ----

const weekdaysShort = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
const weekdaysLong = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

export function weekdayShort(weekday) { return weekdaysShort[weekday] || "" }
export function weekdayLong(weekday) { return weekdaysLong[weekday] || "" }

function dayNumber(iso) {
    const [y, m, d] = String(iso).split("-").map(Number)
    return Date.UTC(y, m - 1, d) / 86400000
}

// When next up is planned (spec §6, "Pull · planned for Wednesday"); with no planned days, whenever you're ready.
export function plannedFor(dateIso, todayIso) {
    if (!dateIso)
        return "whenever you're ready"
    const ahead = dayNumber(dateIso) - dayNumber(todayIso)
    if (ahead === 0)
        return "planned for today"
    if (ahead === 1)
        return "planned for tomorrow"
    const weekday = (new Date(dayNumber(dateIso) * 86400000).getUTCDay() + 6) % 7
    return `planned for ${weekdaysLong[weekday]}`
}

const goals = { strength: "Strength", muscle: "Muscle", general: "General fitness" }
const goalHints = { strength: "Heavier, fewer reps (5–8)", muscle: "The middle ground (8–12)",
                    general: "Lighter, more reps (10–15)" }
export function goalLabel(goal) { return goals[goal] || goal }
export function goalHint(goal) { return goalHints[goal] || "" }

const units = { lb: "Pounds (lb)", kg: "Kilograms (kg)" }
export function unitsLabel(unit) { return units[unit] || unit }

const presets = { gym: "Full gym", dumbbells: "Dumbbells and a bench", bodyweight: "Bodyweight and bands" }
export function presetLabel(preset) { return presets[preset] || preset }

const variants = { gym: "For a full gym", dumbbell: "For dumbbells and a bench", bodyweight: "For bodyweight" }
export function starterVariant(variant) { return variants[variant] || "" }

const fieldProblems = {
    title: "A name is 1 to 60 characters",
    note: "A note is up to 1,000 characters",
    sets: "Sets are 1 to 20",
    repsMin: "Reps are 1 to 100",
    repsMax: "The top of the range is 1 to 100, and not below the bottom",
    targetWeight: "A weight is 0 to 2,000",
    targetUnit: "Pick lb or kg for the weight",
    targetSeconds: "A time is 1 second to 10 hours, like 45 or 1:30",
    targetDistance: "A distance is above 0 and up to 1,000",
    distanceUnit: "Pick km, mi or m for the distance",
    restSeconds: "Rest is up to an hour, like 90 or 1:30",
    name: "A name is 1 to 120 characters",
    measure: "Pick how it's measured",
    primary: "Pick at least one main muscle",
    secondary: "A muscle can't be both main and also worked",
    equipment: "Pick at least one piece of equipment",
    steps: "Up to 50 steps, each up to 1,000 characters",
    upperIncrement: "An increment is 0.25 to 100, in steps of 0.25",
    lowerIncrement: "An increment is 0.25 to 100, in steps of 0.25",
    daysPerWeek: "Pick 2 to 6 days a week",
    days: "Pick days of the week",
    exerciseId: "That exercise isn't available any more",
    order: "Something changed meanwhile. Try again.",
}
export function fieldProblem(field) { return fieldProblems[field] || "That doesn't look right" }

const limits = { program: "20 programs is the most Pride keeps for you.",
                 routine: "14 routines is the most a program holds.",
                 item: "30 exercises is the most a routine holds.",
                 exercise: "200 exercises of your own is the most Pride keeps." }
export function limitReached(field) { return limits[field] || "That's the most Pride keeps." }

// What a page says when a service's save or load fails (Programs, Profile, Catalog: failed(code, field)).
export function saveProblem(code, field) {
    if (code === "invalid")
        return fieldProblem(field)
    if (code === "limit")
        return limitReached(field)
    return failure(code)
}

// The intro (spec §6): four questions and a suggested starter.
export const introWelcomeTitle = "Welcome to Pride"
export const introWelcomeBody = "Four quick questions and you'll have a program to follow. Already know your routine? Skip, and build it yourself."
export const introDaysTitle = "How many days a week can you train?"
export const introEquipmentTitle = "What do you have to train with?"
export const introGoalTitle = "What are you after?"
export const introStarterHeading = "Here's a place to start"
export const introNext = "Next"
export const introBack = "Back"
export const introSkip = "Skip"
export const introUseThis = "Use this"
export const introTweak = "Tweak it first"
export const introBuildOwn = "Build my own"
export const introOthers = "Other starters"
export const introMissing = "A few of its exercises aren't in the catalog yet, so they're left out."
export const introUnavailable = "This starter's exercises aren't in the catalog yet. Build your own, or try another."
export const introLoading = "Picking a starter for you…"
export const introPlanned = "Planned for"
export const myProgram = "My program"
export function introStepOf(n) { return `Step ${n} of 4` }

// ---- Today ----
export const navTodayTitle = "Today"
export const nextUp = "Next up"
export const thisWeek = "This week"
export const today = "Today"
export const dayDone = "Done"
export const dayPlanned = "Planned"
export const leftCatalog = "left the catalog"
export const todayLoadingText = "Looking at your week…"
export const todayUnavailable = "Today can't be loaded right now."
export const noProgram = "No program yet. Take the four questions, or start with an empty one."
export const showIntro = "Show me the introduction"
export const startEmptyProgram = "Start an empty program"
export const pickProgram = "None of your programs is the one you're following. Pick one."
export const openPrograms = "Open Programs"
export function noRoutinesYet(title) { return `${title} has no routines yet.` }

// ---- Programs ----
export const programsTitle = "Programs"
export const activeBadge = "Active"
export const newProgram = "New program"
export const programName = "Name a program"
export const programsEmpty = "No programs yet. Name one to begin, or take the introduction from Settings."
export const followThis = "Follow this one"
export const duplicate = "Duplicate"
export const deleteWord = "Delete"
export const keepIt = "Keep it"
export const plannedDays = "Planned days"
export const plannedDaysHint = "Next up follows the rotation whatever the day; these just say when you mean to train."
export const routinesTitle = "Routines, in rotation"
export const addRoutine = "Add routine"
export const routineName = "Name a routine"
export const edit = "Edit"
export const noRoutines = "No routines yet. Add the first below."
export const goneElsewhere = "That was changed or removed on another device, so it's been closed here."
export function routineCount(n) { return n === 1 ? "1 routine" : `${n} routines` }
export function exerciseCount(n) { return n === 1 ? "1 exercise" : `${n} exercises` }
export function deleteProgramQuestion(title) {
    return `Delete ${title}? Its routines go with it. Workouts you've logged keep everything.`
}
export function deleteRoutineQuestion(title) { return `Delete ${title}? Workouts you've logged keep everything.` }

// ---- The Routine editor ----
export function backTo(title) { return `Back to ${title}` }
export const addExercise = "Add exercise"
export const remove = "Remove"
export const setsLabel = "Sets"
export const repsLabel = "Reps"
export const weightLabel = "Weight"
export const timeLabel = "Time"
export const distanceLabel = "Distance"
export const restLabel = "Rest"
export const noteLabel = "Note"
export const unknownExercise = "An exercise this device doesn't know"
export const pickerTitle = "Add an exercise"
export const pickerFilter = "Narrow by name"
export const showEverything = "Show everything"
export const pickerNothing = "Nothing that fits your equipment. Show everything?"
export const routineMissing = "That routine isn't open any more."
export const backToPrograms = "Back to Programs"

// ---- Own exercises and Add to a routine ----
export const addOwnExercise = "Add my own exercise"
export const ownFormTitle = "Your own exercise"
export const ownEditTitle = "Edit your exercise"
export const ownName = "Name"
export const ownMeasure = "Measured by"
export const ownPrimary = "Works"
export const ownSecondary = "Also works"
export const ownEquipment = "Equipment"
export const ownSteps = "How it's done (one step a line, optional)"
export const save = "Save"
export const cancel = "Cancel"
export const ownCredit = "One of your own."
export const addToRoutine = "Add to a routine…"
export const addToRoutineTitle = "Add to which routine?"
export const noProgramsForAdd = "No programs yet. Make one in Programs first."
export function addedTo(title) { return `Added to ${title}.` }
export function deleteOwnQuestion(name) {
    return `Delete ${name}? It comes out of any routine it's in. Workouts that logged it keep it.`
}
