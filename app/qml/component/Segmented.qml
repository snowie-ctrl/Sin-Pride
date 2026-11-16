import QtQuick

// A row of choices, one chosen (spec §6 Settings and the intro): each a Chip, named prefix-value for the page tests.
Row {
    id: root

    property var options: []        // [{value, label}]
    property var current
    property string prefix: ""
    signal picked(var value)

    spacing: Preferences.spacingSmall

    Repeater {
        model: root.options
        Chip {
            objectName: root.prefix + "-" + modelData.value
            text: modelData.label
            chosen: modelData.value === root.current
            onToggled: if (!chosen) root.picked(modelData.value)
        }
    }
}
