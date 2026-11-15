// How numbers read (spec §1). A weight or distance shows as it was entered, with its own unit; converting is for
// milestone 3's comparisons and charts. Durations read m:ss, or h:mm:ss from an hour.

export function number(value) {
    if (value === null || value === undefined || isNaN(Number(value)))
        return ""
    return String(Math.round(Number(value) * 100) / 100)
}

export function weight(value, unit) {
    return value === null || value === undefined ? "" : `${number(value)} ${unit}`
}

export function distance(value, unit) {
    return value === null || value === undefined ? "" : `${number(value)} ${unit}`
}

function two(n) {
    return n < 10 ? `0${n}` : `${n}`
}

export function duration(seconds) {
    const s = Math.max(0, Math.round(Number(seconds) || 0))
    const h = Math.floor(s / 3600)
    const m = Math.floor((s % 3600) / 60)
    return h > 0 ? `${h}:${two(m)}:${two(s % 60)}` : `${m}:${two(s % 60)}`
}

// "45", "1:30" or "1:00:00" as seconds; NaN for anything else (minutes and seconds under 60 after the first part).
export function parseDuration(text) {
    const parts = String(text === null || text === undefined ? "" : text).trim().split(":")
    if (parts.length > 3 || !parts.every(p => /^\d+$/.test(p)))
        return NaN
    const n = parts.map(Number)
    if (n.slice(1).some(v => v >= 60))
        return NaN
    return n.reduce((total, v) => total * 60 + v, 0)
}

// A routine item's targets in one line, as the mockups show them ("3 × 8–12 · 135 lb").
export function target(item, measure) {
    const sets = item.sets
    if (measure === "weight_reps" || measure === "reps") {
        const reps = item.repsMin === item.repsMax ? `${item.repsMin}` : `${item.repsMin}–${item.repsMax}`
        const parts = [`${sets} × ${reps}`]
        if (item.targetWeight !== null && item.targetWeight !== undefined)
            parts.push((measure === "reps" ? "+" : "") + weight(item.targetWeight, item.targetUnit))
        return parts.join(" · ")
    }
    if (measure === "time")
        return `${sets} × ${duration(item.targetSeconds)}`
    const far = item.targetDistance !== null && item.targetDistance !== undefined ? distance(item.targetDistance, item.distanceUnit) : ""
    const long = item.targetSeconds ? duration(item.targetSeconds) : ""
    const text = far && long ? `${far} in ${long}` : (far || long)
    if (!text)
        return sets === 1 ? "1 set" : `${sets} sets`
    return sets > 1 ? `${sets} × ${text}` : text
}
