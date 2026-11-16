// Log a workout's working copy (spec §6, layout L2) as plain values: a card per exercise, each with its sets. Every
// function returns new values and never changes what it was given, so the page assigns the result and QML sees the
// change. Filling a routine's cards follows plan decision 8; what is sent follows docs/api.md (Workouts).
import * as Words from "words.mjs"
import * as Units from "units.mjs"

const LB_IN_KG = 0.45359237

function given(v) { return v !== null && v !== undefined && v !== "" }
function kg(weight, unit) { return given(weight) ? Number(weight) * (unit === "lb" ? LB_IN_KG : 1) : null }
function dayNumber(iso) {
    const [y, m, d] = String(iso).split("-").map(Number)
    return Date.UTC(y, m - 1, d) / 86400000
}
function isoOf(n) { return new Date(n * 86400000).toISOString().slice(0, 10) }

export function shiftDay(iso, days) { return isoOf(dayNumber(iso) + days) }

// A set with nothing filled, in the person's units for a weight × reps exercise (the only one that must carry one).
export function emptySet(measure, units) {
    return { warmup: false, weight: null, weightUnit: measure === "weight_reps" ? units : null, reps: null,
             seconds: null, distance: null, distanceUnit: null }
}

let nextKey = 1
function card(exerciseId, itemId, measure, sets, more) {
    return Object.assign({ key: nextKey++, exerciseId: exerciseId, itemId: itemId, measure: measure, suggestion: null,
                           item: null, note: null, sets: sets }, more || {})
}

// Plan decision 8: as many sets as planned; set n copies last time's working set n (or its last one); a target now
// above last time's weight (a step-up taken) wins, with the bottom of the range; no last time: the targets.
function plannedSets(item, units) {
    const last = item.last ? item.last.sets.filter(s => !s.warmup) : []
    const sets = []
    for (let i = 0; i < Math.max(1, item.sets || 1); ++i) {
        const from = last.length ? last[Math.min(i, last.length - 1)] : null
        const set = emptySet(item.measure, units)
        if (item.measure === "weight_reps" || item.measure === "reps") {
            const target = item.targetWeight
            const raised = given(target) && (!from || !given(from.weight)
                                             || kg(target, item.targetUnit) > kg(from.weight, from.weightUnit) + 1e-6)
            if (raised) {
                set.weight = target
                set.weightUnit = item.targetUnit
                set.reps = item.repsMin
            } else if (from) {
                set.weight = from.weight
                if (given(from.weight))
                    set.weightUnit = from.weightUnit
                set.reps = from.reps
            } else {
                set.reps = item.repsMin
            }
            if (item.measure === "reps" && !given(set.weight))
                set.weightUnit = null
        } else if (item.measure === "time") {
            set.seconds = from ? from.seconds : item.targetSeconds
        } else {
            set.distance = from ? from.distance : item.targetDistance
            set.distanceUnit = from ? from.distanceUnit : item.distanceUnit
            set.seconds = from ? from.seconds : item.targetSeconds
        }
        sets.push(set)
    }
    return sets
}

export function fromDraft(draft, units) {
    return (draft.items || []).map(item => card(item.exerciseId, item.id, item.measure, plannedSets(item, units),
                                                { suggestion: item.suggestion || null, item: item }))
}

export function fromWorkout(workout) {
    return (workout.exercises || []).map(e => card(e.exerciseId, e.itemId, e.measure,
                                                   e.sets.map(s => Object.assign({}, s)), { note: e.note }))
}

export function newCard(exerciseId, measure, units) {
    return card(exerciseId, null, measure, [emptySet(measure, units)])
}

function replaced(cards, index, changed) {
    return cards.map((c, i) => i === index ? Object.assign({}, c, changed) : c)
}

export function withSet(cards, cardIndex, setIndex, set) {
    return replaced(cards, cardIndex, { sets: cards[cardIndex].sets.map((s, i) => i === setIndex ? set : s) })
}

export function withoutSet(cards, cardIndex, setIndex) {
    return replaced(cards, cardIndex, { sets: cards[cardIndex].sets.filter((s, i) => i !== setIndex) })
}

// "+": a copy of the card's last set as a working set, or an empty one.
export function addSet(cards, cardIndex, units) {
    const sets = cards[cardIndex].sets
    const next = sets.length ? Object.assign({}, sets[sets.length - 1], { warmup: false })
                             : emptySet(cards[cardIndex].measure, units)
    return replaced(cards, cardIndex, { sets: sets.concat([next]) })
}

export function withCard(cards, added) { return cards.concat([added]) }
export function withoutCard(cards, cardIndex) { return cards.filter((c, i) => i !== cardIndex) }

export function counts(cards) {
    return { exercises: cards.length, sets: cards.reduce((n, c) => n + c.sets.length, 0) }
}

// Only the measure's own fields go (spec §4), and a unit only with its number.
function cleanSet(s, measure) {
    const set = { warmup: !!s.warmup, weight: null, weightUnit: null, reps: null, seconds: null, distance: null,
                  distanceUnit: null }
    if (measure === "weight_reps" || measure === "reps") {
        set.reps = given(s.reps) ? s.reps : null
        if (given(s.weight)) {
            set.weight = s.weight
            set.weightUnit = s.weightUnit
        } else if (measure === "weight_reps") {
            set.weightUnit = null
        }
    } else if (measure === "time") {
        set.seconds = given(s.seconds) ? s.seconds : null
    } else {
        if (given(s.distance)) {
            set.distance = s.distance
            set.distanceUnit = s.distanceUnit
        }
        set.seconds = given(s.seconds) ? s.seconds : null
    }
    return set
}

export function toBody(clientId, performedOn, routineId, note, cards) {
    return { clientId: clientId, performedOn: performedOn, routineId: routineId ? routineId : null,
             note: given(note) && String(note).trim().length ? String(note) : null,
             exercises: cards.map(c => ({ exerciseId: c.exerciseId, itemId: c.itemId || null, note: c.note || null,
                                          sets: c.sets.map(s => cleanSet(s, c.measure)) })) }
}

function n(v) { return given(v) ? Units.number(v) : "—" }

// A chip's words (the mockups' "135 × 12").
export function setLabel(s, measure) {
    if (measure === "weight_reps")
        return `${n(s.weight)} × ${n(s.reps)}`
    if (measure === "reps")
        return given(s.weight) ? `${n(s.reps)} reps +${Units.weight(s.weight, s.weightUnit)}` : `${n(s.reps)} reps`
    if (measure === "time")
        return given(s.seconds) ? Units.duration(s.seconds) : "—"
    const parts = []
    if (given(s.distance))
        parts.push(Units.distance(s.distance, s.distanceUnit))
    if (given(s.seconds))
        parts.push(Units.duration(s.seconds))
    return parts.length ? parts.join(" · ") : "—"
}

// Last time's working sets in a line: "135 × 12, 12, 11" when the weight held, else each set.
export function setsLine(sets, measure) {
    const working = (sets || []).filter(s => !s.warmup)
    if (!working.length)
        return ""
    if (measure === "weight_reps" && working.every(s => s.weight === working[0].weight && s.weightUnit === working[0].weightUnit))
        return `${n(working[0].weight)} × ${working.map(s => n(s.reps)).join(", ")}`
    return working.map(s => setLabel(s, measure)).join(", ")
}

// The suggestion chip's "3×12": how many sets of what, when they were all the same.
export function lastShort(last, measure) {
    const working = last ? last.sets.filter(s => !s.warmup) : []
    if (!working.length)
        return ""
    const key = measure === "time" ? "seconds" : "reps"
    const values = working.map(s => s[key])
    const show = v => measure === "time" ? Units.duration(v) : n(v)
    if (values.every(v => v === values[0]))
        return `${working.length}×${show(values[0])}`
    return values.map(show).join(", ")
}

// What a step-up proposes, in words.
export function proposal(s) {
    if (given(s.weight))
        return Units.weight(s.weight, s.unit)
    if (given(s.repsMin))
        return `${s.repsMin}–${s.repsMax} reps`
    return Units.duration(s.seconds)
}

// A record as its set was entered (spec §5: a set entered in lb shows in lb).
export function recordText(r) {
    if (r.kind === "heaviest")
        return given(r.reps) ? `${Units.weight(r.weight, r.weightUnit)} × ${r.reps}` : Units.weight(r.weight, r.weightUnit)
    if (r.kind === "e1rm")
        return `${Words.estimatedShort} ${Units.weight(r.estimate, r.estimateUnit)}`
    if (r.kind === "reps")
        return `${r.reps} reps`
    if (r.kind === "time")
        return Units.duration(r.seconds)
    if (r.kind === "distance")
        return Units.distance(r.distance, r.distanceUnit)
    const unit = r.distanceUnit === "m" ? "km" : r.distanceUnit
    const per = r.distanceUnit === "m" ? r.seconds / (r.distance / 1000) : r.seconds / r.distance
    return `${Units.duration(per)} /${unit}`
}
