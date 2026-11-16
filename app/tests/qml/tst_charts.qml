import QtQuick
import QtTest
import "../../qml/logic/charts.mjs" as Charts

TestCase {
    name: "Charts"

    function test_pointsSpanTheWidthAndTheValues() {
        const plotted = Charts.plot([100, null, 120, 110], 320, 200, 20)
        compare(plotted.low, 100)
        compare(plotted.high, 120)
        compare(plotted.points.length, 3)              // the workout with no value is left out
        compare(plotted.points[0].x, 20)
        compare(plotted.points[0].y, 180)              // the lowest sits at the bottom
        compare(plotted.points[1].index, 2)
        compare(plotted.points[1].x, 20 + 280 * 2 / 3)
        compare(plotted.points[1].y, 20)               // the highest at the top
        compare(plotted.points[2].x, 300)
    }

    function test_oneValueOrEqualValuesSitInTheMiddle() {
        const one = Charts.plot([50], 320, 200, 20)
        compare(one.points[0].x, 160)
        compare(one.points[0].y, 100)
        compare(Charts.plot([50, 50], 320, 200, 20).points[1].y, 100)
        compare(Charts.plot([null], 320, 200, 20).points.length, 0)
        compare(Charts.plot([], 320, 200, 20).low, null)
    }

    function test_workoutsPerWeekByTheWeekStart() {
        const history = [{ performedOn: "2026-11-17" }, { performedOn: "2026-11-16" }, { performedOn: "2026-11-15" },
                         { performedOn: "2026-11-09" }, { performedOn: "2026-08-01" }]
        const weeks = Charts.weekly(history, "mon", "2026-11-17", 3)
        compare(weeks.map(w => w.start), ["2026-11-02", "2026-11-09", "2026-11-16"])
        compare(weeks.map(w => w.count), [0, 2, 2])
        const sundays = Charts.weekly(history, "sun", "2026-11-17", 2)
        compare(sundays.map(w => w.start), ["2026-11-08", "2026-11-15"])
        compare(sundays.map(w => w.count), [1, 3])
    }
}
