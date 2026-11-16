// The Progress page's numbers (spec §6): where a chart's points sit, and workouts per week. Pure, so they are
// table-tested; the drawing is ProgressChart.qml's and WeekBars' in ProgressPage.qml.

function dayNumber(iso) {
    const [y, m, d] = String(iso).split("-").map(Number)
    return Date.UTC(y, m - 1, d) / 86400000
}
function isoOf(n) { return new Date(n * 86400000).toISOString().slice(0, 10) }

// values: a number or null per workout, oldest first. A null (that workout has no value for this view) is left out,
// keeping its place on the time line. One value, or values all equal, sit in the middle.
export function plot(values, width, height, pad) {
    const shown = (values || []).map((v, i) => ({ v: v, i: i }))
                                .filter(p => p.v !== null && p.v !== undefined && !isNaN(p.v))
    if (!shown.length)
        return { points: [], low: null, high: null }
    const low = Math.min(...shown.map(p => p.v))
    const high = Math.max(...shown.map(p => p.v))
    const count = values.length
    const innerW = width - 2 * pad
    const innerH = height - 2 * pad
    return { low: low, high: high,
             points: shown.map(p => ({ index: p.i, value: p.v,
                                       x: count === 1 ? width / 2 : pad + innerW * p.i / (count - 1),
                                       y: high === low ? height / 2 : pad + innerH * (1 - (p.v - low) / (high - low)) })) }
}

// The last `weeks` weeks by the profile's week start (plan decision 23), oldest first, each with how many workouts
// it holds. history: [{performedOn}], in any order.
export function weekly(history, weekStart, todayIso, weeks) {
    const today = dayNumber(todayIso)
    const weekday = (new Date(today * 86400000).getUTCDay() + 6) % 7       // 0 = Monday
    const back = weekStart === "sun" ? (weekday + 1) % 7 : weekday
    const first = today - back - 7 * (weeks - 1)
    const out = []
    for (let w = 0; w < weeks; ++w)
        out.push({ start: isoOf(first + 7 * w), count: 0 })
    for (const h of history || []) {
        const d = dayNumber(h.performedOn)
        if (d >= first && d < first + 7 * weeks)
            out[Math.floor((d - first) / 7)].count++
    }
    return out
}
