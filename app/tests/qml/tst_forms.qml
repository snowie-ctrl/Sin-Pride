import QtQuick
import QtTest
import "../../qml/logic/forms.mjs" as Forms
import "../../qml/logic/words.mjs" as Words

TestCase {
    name: "Forms"

    function test_signInLengthsMatchTheServer_data() {
        return [
            { tag: "fine", u: "ann", p: "12345678", want: "" },
            { tag: "short username", u: "an", p: "12345678", want: Words.usernameLength },
            { tag: "long username", u: "a".repeat(33), p: "12345678", want: Words.usernameLength },
            { tag: "username at 32", u: "a".repeat(32), p: "12345678", want: "" },
            { tag: "spaces trimmed", u: "  an  ", p: "12345678", want: Words.usernameLength },
            { tag: "short password", u: "ann", p: "1234567", want: Words.passwordLength },
            { tag: "password at 256", u: "ann", p: "p".repeat(256), want: "" },
            { tag: "long password", u: "ann", p: "p".repeat(257), want: Words.passwordLength },
            { tag: "nothing typed", u: "", p: "", want: Words.enterUsernameAndPassword },
        ]
    }

    function test_signInLengthsMatchTheServer(data) {
        compare(Forms.signInProblem(data.u, data.p), data.want)
    }

    function item(changes) {
        const values = { sets: 3, repsMin: 8, repsMax: 12, targetWeight: null, targetUnit: null, targetSeconds: null,
                         targetDistance: null, distanceUnit: null, restSeconds: null, note: "" }
        for (const k in changes) values[k] = changes[k]
        return values
    }

    function test_itemChecksMatchTheServer_data() {
        return [
            { tag: "fine", m: "weight_reps", c: {}, field: "" },
            { tag: "weight and unit", m: "weight_reps", c: { targetWeight: 135, targetUnit: "lb" }, field: "" },
            { tag: "no sets", m: "weight_reps", c: { sets: 0 }, field: "sets" },
            { tag: "21 sets", m: "weight_reps", c: { sets: 21 }, field: "sets" },
            { tag: "half a set", m: "weight_reps", c: { sets: 2.5 }, field: "sets" },
            { tag: "reps reversed", m: "weight_reps", c: { repsMin: 12, repsMax: 8 }, field: "repsMax" },
            { tag: "reps 0", m: "weight_reps", c: { repsMin: 0 }, field: "repsMin" },
            { tag: "reps missing", m: "reps", c: { repsMin: null }, field: "repsMin" },
            { tag: "weight no unit", m: "weight_reps", c: { targetWeight: 50 }, field: "targetUnit" },
            { tag: "weight too much", m: "weight_reps", c: { targetWeight: 2000.5, targetUnit: "lb" }, field: "targetWeight" },
            { tag: "rest too long", m: "weight_reps", c: { restSeconds: 3601 }, field: "restSeconds" },
            { tag: "long note", m: "weight_reps", c: { note: "x".repeat(1001) }, field: "note" },
            { tag: "time needs seconds", m: "time", c: { repsMin: null, repsMax: null }, field: "targetSeconds" },
            { tag: "time fine", m: "time", c: { repsMin: null, repsMax: null, targetSeconds: 30 }, field: "" },
            { tag: "time takes no reps", m: "time", c: { targetSeconds: 30 }, field: "repsMin" },
            { tag: "distance no unit", m: "distance_time", c: { repsMin: null, repsMax: null, targetDistance: 5 }, field: "distanceUnit" },
            { tag: "distance zero", m: "distance_time", c: { repsMin: null, repsMax: null, targetDistance: 0, distanceUnit: "km" }, field: "targetDistance" },
            { tag: "distance nothing set", m: "distance_time", c: { repsMin: null, repsMax: null, sets: 1 }, field: "" },
        ]
    }

    function test_itemChecksMatchTheServer(data) {
        const problem = Forms.itemProblem(data.m, item(data.c))
        compare(problem.field, data.field)
        compare(problem.words, data.field ? Words.fieldProblem(data.field) : "")
    }

    function test_titlesNotesAndIncrements() {
        compare(Forms.titleProblem("Push"), "")
        compare(Forms.titleProblem("   "), Words.fieldProblem("title"))
        compare(Forms.titleProblem("x".repeat(61)), Words.fieldProblem("title"))
        compare(Forms.noteProblem("x".repeat(1000)), "")
        compare(Forms.incrementProblem("2.5"), "")
        compare(Forms.incrementProblem("2,5"), "")
        compare(Forms.incrementProblem("0.3"), Words.fieldProblem("upperIncrement"))
        compare(Forms.incrementProblem("0"), Words.fieldProblem("upperIncrement"))
        compare(Forms.incrementProblem("abc"), Words.fieldProblem("upperIncrement"))
    }

    function test_numbersTypedTheWayPeopleType() {
        compare(Forms.parseNumber("62.5"), 62.5)
        compare(Forms.parseNumber(" 62,5 "), 62.5)
        compare(Forms.parseNumber("135"), 135)
        verify(isNaN(Forms.parseNumber("")))
        verify(isNaN(Forms.parseNumber("1.2.3")))
        verify(isNaN(Forms.parseNumber("-5")))
    }

    function test_ownExerciseChecks() {
        const fine = { name: "Sandbag Carry", measure: "distance_time", primary: ["forearms"], secondary: [],
                       equipment: ["other"], steps: [] }
        compare(Forms.ownExerciseProblem(fine).field, "")
        const noName = Object.assign({}, fine, { name: " " })
        compare(Forms.ownExerciseProblem(noName).field, "name")
        compare(Forms.ownExerciseProblem(Object.assign({}, fine, { primary: [] })).field, "primary")
        compare(Forms.ownExerciseProblem(Object.assign({}, fine, { secondary: ["forearms"] })).field, "secondary")
        compare(Forms.ownExerciseProblem(Object.assign({}, fine, { equipment: [] })).field, "equipment")
        compare(Forms.ownExerciseProblem(Object.assign({}, fine, { measure: "" })).field, "measure")
        compare(Forms.ownExerciseProblem(Object.assign({}, fine, { steps: ["x".repeat(1001)] })).field, "steps")
    }

    function test_aSetIsCheckedAsTheServerChecksIt() {
        compare(Forms.setProblem("weight_reps", { warmup: false, weight: 135, weightUnit: "lb", reps: 12 }).field, "")
        compare(Forms.setProblem("weight_reps", { reps: 8 }).field, "weight")
        compare(Forms.setProblem("weight_reps", { weight: 100, reps: 8 }).field, "weightUnit")
        compare(Forms.setProblem("weight_reps", { weight: 2001, weightUnit: "lb", reps: 8 }).field, "weight")
        compare(Forms.setProblem("weight_reps", { weight: NaN, weightUnit: "lb", reps: 8 }).field, "weight")
        compare(Forms.setProblem("weight_reps", { weight: 100, weightUnit: "lb", reps: 0 }).field, "reps")
        compare(Forms.setProblem("weight_reps", { weight: 100, weightUnit: "lb", reps: 8, seconds: 30 }).field, "seconds")
        compare(Forms.setProblem("reps", { reps: 12 }).field, "")
        compare(Forms.setProblem("time", {}).field, "seconds")
        compare(Forms.setProblem("time", { seconds: 30, reps: 5 }).field, "reps")
        compare(Forms.setProblem("distance_time", {}).field, "distance")
        compare(Forms.setProblem("distance_time", { distance: 5 }).field, "distanceUnit")
        compare(Forms.setProblem("distance_time", { seconds: 1500 }).field, "")
        verify(Forms.setProblem("weight_reps", { reps: 8 }).words.length > 0)
    }

    function test_aWorkoutNamesItsFirstProblemAndWhere() {
        const good = { measure: "weight_reps", sets: [{ warmup: false, weight: 135, weightUnit: "lb", reps: 12 }] }
        const bad = { measure: "weight_reps", sets: [good.sets[0], { warmup: false, weight: null, weightUnit: "lb", reps: 12 }] }
        compare(Forms.workoutProblem("2026-11-17", "2026-11-17", "", [good]).field, "")
        compare(Forms.workoutProblem("2026-11-18", "2026-11-17", "", [good]).field, "performedOn")
        compare(Forms.workoutProblem("2026-11-17", "2026-11-17", "", []).field, "exercises")
        compare(Forms.workoutProblem("2026-11-17", "2026-11-17", "x".repeat(1001), [good]).field, "note")
        compare(Forms.workoutProblem("2026-11-17", "2026-11-17", "", [{ measure: "reps", sets: [] }]).field, "sets")
        const found = Forms.workoutProblem("2026-11-17", "2026-11-17", "", [good, bad])
        compare(found.field, "weight")
        compare(found.card, 1)
        compare(found.set, 1)
    }
}
