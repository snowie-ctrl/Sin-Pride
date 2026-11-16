import QtQuick
import QtTest
import "../../qml/logic/units.mjs" as Units

TestCase {
    name: "Units"

    function test_numbersReadAsEntered() {
        compare(Units.weight(135, "lb"), "135 lb")
        compare(Units.weight(62.5, "kg"), "62.5 kg")
        compare(Units.weight(60.0, "kg"), "60 kg")
        compare(Units.weight(null, "kg"), "")
        compare(Units.distance(5, "km"), "5 km")
        compare(Units.distance(0.25, "mi"), "0.25 mi")
    }

    function test_durations() {
        compare(Units.duration(30), "0:30")
        compare(Units.duration(90), "1:30")
        compare(Units.duration(600), "10:00")
        compare(Units.duration(3600), "1:00:00")
        compare(Units.duration(3725), "1:02:05")
    }

    function test_parseDuration_data() {
        return [
            { tag: "seconds", text: "45", want: 45 }, { tag: "m:ss", text: "1:30", want: 90 },
            { tag: "h:mm:ss", text: "1:00:00", want: 3600 }, { tag: "spaces", text: " 2:05 ", want: 125 },
            { tag: "bad seconds", text: "1:75", want: NaN }, { tag: "letters", text: "1m30", want: NaN },
            { tag: "empty", text: "", want: NaN }, { tag: "four parts", text: "1:2:3:4", want: NaN },
        ]
    }

    function test_parseDuration(data) {
        const got = Units.parseDuration(data.text)
        if (isNaN(data.want))
            verify(isNaN(got), data.tag)
        else
            compare(got, data.want)
    }

    function test_targetsReadLikeTheMockups() {
        compare(Units.target({ sets: 3, repsMin: 8, repsMax: 12, targetWeight: 135, targetUnit: "lb" }, "weight_reps"),
                "3 × 8–12 · 135 lb")
        compare(Units.target({ sets: 3, repsMin: 10, repsMax: 10, targetWeight: null }, "weight_reps"), "3 × 10")
        compare(Units.target({ sets: 3, repsMin: 10, repsMax: 15, targetWeight: 20, targetUnit: "kg" }, "reps"),
                "3 × 10–15 · +20 kg")
        compare(Units.target({ sets: 3, targetSeconds: 30 }, "time"), "3 × 0:30")
        compare(Units.target({ sets: 1, targetDistance: 5, distanceUnit: "km", targetSeconds: 1800 }, "distance_time"),
                "5 km in 30:00")
        compare(Units.target({ sets: 2, targetDistance: 400, distanceUnit: "m", targetSeconds: null }, "distance_time"),
                "2 × 400 m")
        compare(Units.target({ sets: 1, targetDistance: null, targetSeconds: null }, "distance_time"), "1 set")
        compare(Units.target({ sets: 3, targetDistance: null, targetSeconds: null }, "distance_time"), "3 sets")
    }
}
