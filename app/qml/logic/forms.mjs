// Field checks that match the server's (spec §4), so a person hears what's wrong before anything is sent. Each
// returns "" when the value is fine, otherwise the words to show (words.mjs). server/prideRoutes.py and
// server/prideChecks.py hold the same limits.
import * as Words from "words.mjs"

export const USERNAME = { min: 3, max: 32 }
export const PASSWORD = { min: 8, max: 256 }

export function signInProblem(username, password) {
    const name = String(username || "").trim()
    const secret = String(password || "")
    if (!name.length || !secret.length)
        return Words.enterUsernameAndPassword
    if (name.length < USERNAME.min || name.length > USERNAME.max)
        return Words.usernameLength
    if (secret.length < PASSWORD.min || secret.length > PASSWORD.max)
        return Words.passwordLength
    return ""
}

export const LIMITS = { title: 60, note: 1000, name: 120, steps: 50, step: 1000, sets: 20, reps: 100, weight: 2000,
                        seconds: 36000, distance: 1000, rest: 3600, increment: 100, setReps: 1000, workoutExercises: 30 }

// A number as people type it: digits with one point, or a comma for the point. NaN for anything else (no signs).
export function parseNumber(text) {
    const t = String(text === null || text === undefined ? "" : text).trim().replace(",", ".")
    return /^\d+(\.\d+)?$/.test(t) ? Number(t) : NaN
}

function whole(v, low, high) {
    return typeof v === "number" && Number.isInteger(v) && v >= low && v <= high
}

function given(v) {
    return v !== null && v !== undefined && v !== ""
}

function problem(field) {
    return { field: field, words: Words.fieldProblem(field) }
}

const fine = { field: "", words: "" }

export function titleProblem(text) {
    const t = String(text || "").trim()
    return t.length >= 1 && t.length <= LIMITS.title ? "" : Words.fieldProblem("title")
}

export function noteProblem(text) {
    return String(text || "").length <= LIMITS.note ? "" : Words.fieldProblem("note")
}

export function incrementProblem(text) {
    const n = parseNumber(text)
    return n > 0 && n <= LIMITS.increment && Math.abs(n * 4 - Math.round(n * 4)) < 1e-9 ? ""
                                                                                       : Words.fieldProblem("upperIncrement")
}

const measureFields = {
    weight_reps: ["repsMin", "repsMax", "targetWeight", "targetUnit"],
    reps: ["repsMin", "repsMax", "targetWeight", "targetUnit"],
    time: ["targetSeconds"],
    distance_time: ["targetDistance", "distanceUnit", "targetSeconds"],
}
const targetFields = ["sets", "repsMin", "repsMax", "targetWeight", "targetUnit", "targetSeconds", "targetDistance",
                      "distanceUnit", "restSeconds", "note"]

// server/prideChecks.py itemTargets, field for field, in the same order, so the first problem named is the same.
export function itemProblem(measure, item) {
    const own = measureFields[measure]
    if (!own)
        return problem("measure")
    for (const key of targetFields)
        if (own.indexOf(key) < 0 && ["sets", "restSeconds", "note"].indexOf(key) < 0 && given(item[key]))
            return problem(key)
    if (!whole(item.sets, 1, LIMITS.sets))
        return problem("sets")
    if (given(item.restSeconds) && !whole(item.restSeconds, 0, LIMITS.rest))
        return problem("restSeconds")
    if (noteProblem(item.note))
        return problem("note")
    if (own.indexOf("repsMin") >= 0) {
        if (!whole(item.repsMin, 1, LIMITS.reps))
            return problem("repsMin")
        if (!whole(item.repsMax, 1, LIMITS.reps) || item.repsMin > item.repsMax)
            return problem("repsMax")
    }
    if (own.indexOf("targetWeight") >= 0) {
        if (given(item.targetWeight) && !(item.targetWeight >= 0 && item.targetWeight <= LIMITS.weight))
            return problem("targetWeight")
        if (given(item.targetUnit) && ["lb", "kg"].indexOf(item.targetUnit) < 0)
            return problem("targetUnit")
        if (given(item.targetWeight) && !given(item.targetUnit))
            return problem("targetUnit")
        if (given(item.targetUnit) && !given(item.targetWeight))
            return problem("targetWeight")
    }
    if (measure === "time" && !whole(item.targetSeconds, 1, LIMITS.seconds))
        return problem("targetSeconds")
    if (measure === "distance_time") {
        if (given(item.targetDistance) && !(item.targetDistance > 0 && item.targetDistance <= LIMITS.distance))
            return problem("targetDistance")
        if (given(item.distanceUnit) && ["km", "mi", "m"].indexOf(item.distanceUnit) < 0)
            return problem("distanceUnit")
        if (given(item.targetDistance) && !given(item.distanceUnit))
            return problem("distanceUnit")
        if (given(item.distanceUnit) && !given(item.targetDistance))
            return problem("targetDistance")
        if (given(item.targetSeconds) && !whole(item.targetSeconds, 1, LIMITS.seconds))
            return problem("targetSeconds")
    }
    return fine
}

// server/prideChecks.py ownExercise, in the same order.
export function ownExerciseProblem(e) {
    const name = String(e.name || "").trim()
    if (!name.length || name.length > LIMITS.name)
        return problem("name")
    if (["weight_reps", "reps", "time", "distance_time"].indexOf(e.measure) < 0)
        return problem("measure")
    if (!e.primary || !e.primary.length)
        return problem("primary")
    if ((e.secondary || []).some(m => e.primary.indexOf(m) >= 0))
        return problem("secondary")
    if (!e.equipment || !e.equipment.length)
        return problem("equipment")
    const steps = e.steps || []
    if (steps.length > LIMITS.steps || steps.some(s => !String(s).trim().length || String(s).length > LIMITS.step))
        return problem("steps")
    return fine
}

const setMeasureFields = {
    weight_reps: ["weight", "weightUnit", "reps"],
    reps: ["weight", "weightUnit", "reps"],
    time: ["seconds"],
    distance_time: ["distance", "distanceUnit", "seconds"],
}
const setFields = ["weight", "weightUnit", "reps", "seconds", "distance", "distanceUnit"]

// server/prideChecks.py workoutSet, field for field, in the same order.
export function setProblem(measure, s) {
    const own = setMeasureFields[measure]
    if (!own)
        return problem("measure")
    for (const key of setFields)
        if (own.indexOf(key) < 0 && given(s[key]))
            return problem(key)
    if (given(s.warmup) && typeof s.warmup !== "boolean")
        return problem("warmup")
    if (own.indexOf("weight") >= 0) {
        if (!given(s.weight) && measure === "weight_reps" && !given(s.weightUnit))
            return problem("weight")
        if (given(s.weight) && !(typeof s.weight === "number" && s.weight >= 0 && s.weight <= LIMITS.weight))
            return problem("weight")
        if (given(s.weightUnit) && ["lb", "kg"].indexOf(s.weightUnit) < 0)
            return problem("weightUnit")
        if (given(s.weight) && !given(s.weightUnit))
            return problem("weightUnit")
        if (given(s.weightUnit) && !given(s.weight))
            return problem("weight")
    }
    if (own.indexOf("reps") >= 0 && !whole(s.reps, 1, LIMITS.setReps))
        return problem("reps")
    if (measure === "time" && !whole(s.seconds, 1, LIMITS.seconds))
        return problem("seconds")
    if (measure === "distance_time") {
        if (!given(s.distance) && !given(s.distanceUnit) && !given(s.seconds))
            return problem("distance")
        if (given(s.distance) && !(typeof s.distance === "number" && s.distance > 0 && s.distance <= LIMITS.distance))
            return problem("distance")
        if (given(s.distanceUnit) && ["km", "mi", "m"].indexOf(s.distanceUnit) < 0)
            return problem("distanceUnit")
        if (given(s.distance) && !given(s.distanceUnit))
            return problem("distanceUnit")
        if (given(s.distanceUnit) && !given(s.distance))
            return problem("distance")
        if (given(s.seconds) && !whole(s.seconds, 1, LIMITS.seconds))
            return problem("seconds")
    }
    return fine
}

// server/prideChecks.py workout, for what the Log page can get wrong: the date (latestIso is the page's today), the
// note, the exercises and each set. `card` and `set` say where (-1 when it is not one card's or one set's).
export function workoutProblem(performedOn, latestIso, note, cards) {
    const at = (found, card, set) => ({ field: found.field, words: found.words, card: card, set: set })
    if (String(performedOn) > String(latestIso))
        return at(problem("performedOn"), -1, -1)
    if (noteProblem(note))
        return at(problem("note"), -1, -1)
    if (!cards.length || cards.length > LIMITS.workoutExercises)
        return at(problem("exercises"), -1, -1)
    for (let c = 0; c < cards.length; ++c) {
        if (!cards[c].sets.length || cards[c].sets.length > LIMITS.sets)
            return at(problem("sets"), c, -1)
        for (let s = 0; s < cards[c].sets.length; ++s) {
            const found = setProblem(cards[c].measure, cards[c].sets[s])
            if (found.field)
                return at(found, c, s)
        }
    }
    return { field: "", words: "", card: -1, set: -1 }
}
