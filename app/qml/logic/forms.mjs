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
                        seconds: 36000, distance: 1000, rest: 3600, increment: 100 }

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
