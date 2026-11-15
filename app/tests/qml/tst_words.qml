import QtQuick
import QtTest
import "../../qml/logic/words.mjs" as Words

TestCase {
    name: "Words"

    function test_catalogWordsReadAsPridesOwn() {
        compare(Words.valueLabel("measure", "weight_reps"), "Weight × reps")
        compare(Words.valueLabel("measure", "distance_time"), "Distance and time")
        compare(Words.valueLabel("level", "expert"), "Expert")
        compare(Words.valueLabel("region", "full"), "Full body")
        compare(Words.valueLabel("equipment", "pull-up bar"), "Pull-up bar")
        compare(Words.valueLabel("muscle", "middle back"), "Middle back")
        // A word nobody taught the app still shows, as it came.
        compare(Words.valueLabel("measure", "laps"), "laps")
        compare(Words.listLabel("muscle", ["biceps", "lower back"]), "Biceps, Lower back")
        compare(Words.listLabel("muscle", []), "")
    }

    function test_aTileCaptionNeverStartsWithASeparator() {
        compare(Words.tileCaption(["biceps"], "weight_reps"), "Biceps · Weight × reps")
        compare(Words.tileCaption([], "time"), "Time")
        compare(Words.tileCaption(["lats", "biceps"], ""), "Lats, Biceps")
    }

    function test_anUnreadableCatalogHasWords() {
        compare(Words.failure("bad_reply"), "Pride sent a catalog this app can't read. Try again later.")
    }

    function test_counts() {
        compare(Words.countLabel(1), "1 exercise")
        compare(Words.countLabel(873), "873 exercises")
        compare(Words.shownOf(3, 873), "3 of 873 exercises")
        compare(Words.shownOf(873, 873), "873 exercises")
        compare(Words.pictureCount(0, 2), "1 of 2")
    }

    function test_creditNamesTheSourceAndItsLicence() {
        verify(Words.creditLine("free-exercise-db", "Unlicense").indexOf("public domain") > 0)
        verify(Words.creditLine("free-exercise-db", "Unlicense").indexOf("Unlicense") > 0)
        compare(Words.creditLine("wger", "CC-BY-SA 4.0"), "From wger (CC-BY-SA 4.0).")
        compare(Words.creditLine("own", ""), "From own.")
    }

    function test_everySignInCodeHasWords() {
        for (const code of ["invalid_credentials", "invalid_key", "username_taken", "bad_form", "too_many",
                            "network", "bad_reply", "server"])
            verify(Words.signInError(code).length > 0, code)
        compare(Words.signInError("invalid_credentials"), "Wrong username or password")
        compare(Words.signInError("something new"), Words.signInError("server"))
        for (const code of ["not_yours", "this_device", "network", "server"])
            verify(Words.deviceError(code).length > 0, code)
        compare(Words.failure("network"), "Can't reach Pride right now. Nothing was lost; try again.")
    }

    function test_theVoiceNeverShames() {
        const banned = ["missed", "fail", "guilt", "lazy", "should have", "behind", "skip a day", "late", "overdue"]
        // Strings inside the arrays and objects the module exports (weekday names, labels) count too.
        const check = (value, where) => {
            if (typeof value === "string") {
                for (const word of banned)
                    verify(value.toLowerCase().indexOf(word) < 0, where + " says " + word)
            } else if (value !== null && typeof value === "object") {
                for (const inner of Object.keys(value))
                    check(value[inner], where + "." + inner)
            }
        }
        for (const key of Object.keys(Words))
            check(Words[key], key)
    }

    function test_plannedDaysReadAsDays() {
        compare(Words.plannedFor("2026-11-18", "2026-11-18"), "planned for today")
        compare(Words.plannedFor("2026-11-19", "2026-11-18"), "planned for tomorrow")
        compare(Words.plannedFor("2026-11-20", "2026-11-18"), "planned for Friday")
        compare(Words.plannedFor(null, "2026-11-18"), "whenever you're ready")
        compare(Words.weekdayShort(0), "Mon")
        compare(Words.weekdayLong(6), "Sunday")
    }

    function test_everySaveProblemHasWords() {
        compare(Words.saveProblem("invalid", "sets"), Words.fieldProblem("sets"))
        compare(Words.saveProblem("limit", "program"), Words.limitReached("program"))
        compare(Words.saveProblem("network", ""), Words.failure("network"))
        for (const code of ["not_found", "unavailable", "server", "something new"])
            verify(Words.saveProblem(code, "").length > 0, code)
        for (const field of ["title", "note", "sets", "repsMin", "repsMax", "targetWeight", "targetUnit",
                             "targetSeconds", "targetDistance", "distanceUnit", "restSeconds", "name", "measure",
                             "primary", "secondary", "equipment", "steps", "upperIncrement", "lowerIncrement",
                             "daysPerWeek", "days", "exerciseId", "order", "made-up"])
            verify(Words.fieldProblem(field).length > 0, field)
    }
}
