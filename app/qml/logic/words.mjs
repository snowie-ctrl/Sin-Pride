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
}

// Why a save or a load failed (the services' codes; Task 13 adds the rest).
export function failure(code) {
    return failures[code] || failures.server
}

export const navCatalog = "Catalog"
export const signOut = "Sign out"

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

export const facetTitles = { muscle: "Muscle", equipment: "Equipment", measure: "Measured by", level: "Level" }

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
