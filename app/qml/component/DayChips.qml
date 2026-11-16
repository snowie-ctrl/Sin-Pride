import QtQuick
import "../logic/words.mjs" as Words

// The planned weekdays (spec §6): seven chips in the person's week order; a click sends the whole new set.
Row {
    id: chips

    property var days: []            // weekdays 0 = Monday
    property string weekStart: "mon"
    signal changed(var days)

    readonly property var order: chips.weekStart === "sun" ? [6, 0, 1, 2, 3, 4, 5] : [0, 1, 2, 3, 4, 5, 6]

    spacing: Preferences.spacingSmall

    Repeater {
        model: chips.order
        Chip {
            objectName: "day-" + modelData
            text: Words.weekdayShort(modelData)
            chosen: chips.days.indexOf(modelData) >= 0
            onToggled: {
                const next = chosen ? chips.days.filter(d => d !== modelData) : chips.days.concat([modelData])
                chips.changed(next.sort((a, b) => a - b))
            }
        }
    }
}
