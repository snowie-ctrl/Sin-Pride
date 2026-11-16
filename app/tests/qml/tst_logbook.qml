import QtQuick
import QtTest
import "../../qml/logic/logbook.mjs" as Log

TestCase {
    name: "Logbook"

    function item(changes) {
        return Object.assign({ id: 500, exerciseId: 1, measure: "weight_reps", sets: 3, repsMin: 8, repsMax: 12,
                               targetWeight: null, targetUnit: null, targetSeconds: null, targetDistance: null,
                               distanceUnit: null, last: null, suggestion: null }, changes || {})
    }
    function lifted(weight, reps, warmup) {
        return { warmup: !!warmup, weight: weight, weightUnit: "lb", reps: reps, seconds: null, distance: null,
                 distanceUnit: null }
    }

    function test_shiftDay() {
        compare(Log.shiftDay("2026-11-17", -1), "2026-11-16")
        compare(Log.shiftDay("2026-03-01", -1), "2026-02-28")
        compare(Log.shiftDay("2026-12-31", 1), "2027-01-01")
    }

    function test_withNoLastTimeTheTargetsFillTheSets() {
        const cards = Log.fromDraft({ items: [item({ targetWeight: 135, targetUnit: "lb" })] }, "lb")
        compare(cards.length, 1)
        compare(cards[0].itemId, 500)
        compare(cards[0].sets.length, 3)
        compare(cards[0].sets[0].weight, 135)
        compare(cards[0].sets[0].reps, 8)
        // No target weight: the weight is left to fill, in the person's units.
        const empty = Log.fromDraft({ items: [item()] }, "kg")[0].sets[0]
        compare(empty.weight, null)
        compare(empty.weightUnit, "kg")
        compare(empty.reps, 8)
    }

    function test_lastTimeFillsSetBySetAndWarmUpsAreNotCopied() {
        const last = { workoutId: 69, performedOn: "2026-11-12",
                       sets: [lifted(95, 10, true), lifted(135, 12), lifted(135, 11)] }
        const sets = Log.fromDraft({ items: [item({ targetWeight: 135, targetUnit: "lb", last: last })] }, "lb")[0].sets
        compare(sets.length, 3)
        compare(sets.map(s => s.reps), [12, 11, 11])         // the third copies last time's last working set
        verify(sets.every(s => s.weight === 135 && !s.warmup))
    }

    function test_aRaisedTargetBeatsLastTime() {
        // A step-up was taken: the new target and the bottom of the range, not last time's lighter weight.
        const last = { sets: [lifted(135, 12), lifted(135, 12), lifted(135, 12)] }
        const sets = Log.fromDraft({ items: [item({ targetWeight: 140, targetUnit: "lb", last: last })] }, "lb")[0].sets
        compare(sets.map(s => [s.weight, s.reps]), [[140, 8], [140, 8], [140, 8]])
        // A target in kg below last time's lb weight does not raise it.
        const kg = Log.fromDraft({ items: [item({ targetWeight: 60, targetUnit: "kg", last: last })] }, "lb")[0].sets
        compare(kg[0].weight, 135)
        compare(kg[0].weightUnit, "lb")
    }

    function test_timeAndDistanceFillFromLastTimeOrTargets() {
        const timed = Log.fromDraft({ items: [item({ measure: "time", targetSeconds: 30, repsMin: null, repsMax: null })] }, "lb")
        compare(timed[0].sets[0].seconds, 30)
        compare(timed[0].sets[0].weightUnit, null)
        const ran = Log.fromDraft({ items: [item({ measure: "distance_time", sets: 1, targetDistance: 5, distanceUnit: "km",
                                                   last: { sets: [{ warmup: false, weight: null, weightUnit: null, reps: null,
                                                                    seconds: 1500, distance: 5.5, distanceUnit: "km" }] } })] }, "lb")
        compare(ran[0].sets[0].distance, 5.5)
        compare(ran[0].sets[0].seconds, 1500)
    }

    function test_cardsChangeWithoutTouchingWhatTheyWere() {
        const cards = Log.fromDraft({ items: [item({ targetWeight: 135, targetUnit: "lb" })] }, "lb")
        const more = Log.addSet(cards, 0, "lb")
        compare(cards[0].sets.length, 3)
        compare(more[0].sets.length, 4)
        compare(more[0].sets[3].weight, 135)
        verify(!more[0].sets[3].warmup)
        const edited = Log.withSet(more, 0, 0, lifted(95, 10, true))
        verify(edited[0].sets[0].warmup)
        verify(!more[0].sets[0].warmup)
        compare(Log.withoutSet(edited, 0, 0)[0].sets.length, 3)
        const plus = Log.withCard(edited, Log.newCard(7, "reps", "lb"))
        compare(plus.length, 2)
        compare(plus[1].sets.length, 1)
        compare(plus[1].itemId, null)
        verify(plus[1].key !== plus[0].key)
        compare(Log.withoutCard(plus, 0).length, 1)
        compare(Log.counts(plus), { exercises: 2, sets: 5 })
    }

    function test_theBodyCarriesOnlyEachMeasuresFields() {
        const cards = [Log.newCard(1, "weight_reps", "lb"), Log.newCard(6, "time", "lb"), Log.newCard(7, "reps", "lb")]
        cards[0].sets = [lifted(135, 12)]
        cards[1].sets = [{ warmup: false, weight: 5, weightUnit: "lb", reps: 3, seconds: 45, distance: null, distanceUnit: null }]
        cards[2].sets = [{ warmup: false, weight: null, weightUnit: "lb", reps: 15, seconds: null, distance: null, distanceUnit: null }]
        const body = Log.toBody("cid", "2026-11-17", 50, "  ", cards)
        compare(body.clientId, "cid")
        compare(body.routineId, 50)
        compare(body.note, null)
        compare(body.exercises[0].sets[0], { warmup: false, weight: 135, weightUnit: "lb", reps: 12, seconds: null,
                                             distance: null, distanceUnit: null })
        compare(body.exercises[1].sets[0].weight, null)
        compare(body.exercises[1].sets[0].reps, null)
        compare(body.exercises[1].sets[0].seconds, 45)
        // A unit with no weight is not sent: reps with no added weight.
        compare(body.exercises[2].sets[0].weightUnit, null)
        compare(Log.toBody("cid", "2026-11-17", 0, "", []).routineId, null)
    }

    function test_editingAWorkoutMakesItsCards() {
        const cards = Log.fromWorkout({ exercises: [{ exerciseId: 1, itemId: 500, measure: "weight_reps", note: null,
                                                      sets: [lifted(135, 12)] }] })
        compare(cards[0].itemId, 500)
        compare(cards[0].sets[0].reps, 12)
        compare(cards[0].item, null)
    }

    function test_chipsAndLinesReadAsTheMockups() {
        compare(Log.setLabel(lifted(135, 12), "weight_reps"), "135 × 12")
        compare(Log.setLabel(lifted(null, null), "weight_reps"), "— × —")
        compare(Log.setLabel({ reps: 15, weight: null }, "reps"), "15 reps")
        compare(Log.setLabel({ reps: 8, weight: 20, weightUnit: "kg" }, "reps"), "8 reps +20 kg")
        compare(Log.setLabel({ seconds: 90 }, "time"), "1:30")
        compare(Log.setLabel({ distance: 5, distanceUnit: "km", seconds: 1500 }, "distance_time"), "5 km · 25:00")
        compare(Log.setLabel({ distance: null, seconds: null }, "distance_time"), "—")
        compare(Log.setsLine([lifted(95, 10, true), lifted(135, 12), lifted(135, 12), lifted(135, 11)], "weight_reps"),
                "135 × 12, 12, 11")
        compare(Log.setsLine([lifted(135, 12), lifted(140, 10)], "weight_reps"), "135 × 12, 140 × 10")
        compare(Log.lastShort({ sets: [lifted(135, 12), lifted(135, 12), lifted(135, 12)] }, "weight_reps"), "3×12")
        compare(Log.lastShort({ sets: [lifted(135, 12), lifted(135, 11)] }, "weight_reps"), "12, 11")
        compare(Log.lastShort(null, "weight_reps"), "")
        compare(Log.proposal({ weight: 140, unit: "lb" }), "140 lb")
        compare(Log.proposal({ weight: null, repsMin: 10, repsMax: 14 }), "10–14 reps")
        compare(Log.proposal({ weight: null, repsMin: null, seconds: 40 }), "0:40")
    }

    function test_recordsReadAsEntered() {
        const set = { weight: 135, weightUnit: "lb", reps: 12, seconds: null, distance: null, distanceUnit: null,
                      estimate: null, estimateUnit: null }
        compare(Log.recordText(Object.assign({ kind: "heaviest" }, set)), "135 lb × 12")
        compare(Log.recordText(Object.assign({ kind: "e1rm" }, set, { estimate: 189, estimateUnit: "lb" })), "est. 1RM 189 lb")
        compare(Log.recordText({ kind: "reps", reps: 18 }), "18 reps")
        compare(Log.recordText({ kind: "time", seconds: 90 }), "1:30")
        compare(Log.recordText({ kind: "distance", distance: 5, distanceUnit: "km" }), "5 km")
        compare(Log.recordText({ kind: "pace", distance: 5, distanceUnit: "km", seconds: 1500 }), "5:00 /km")
        compare(Log.recordText({ kind: "pace", distance: 400, distanceUnit: "m", seconds: 90 }), "3:45 /km")
    }
}
