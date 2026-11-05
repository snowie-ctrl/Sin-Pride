import QtQuick
import QtQuick.Controls
import "../logic/words.mjs" as Words

// The catalog's filter side panel (spec §6): a section per facet, each word a chip with how many exercises it
// names. Within a facet any chosen word matches; across facets all must (Catalog).
Rectangle {
    id: panel
    objectName: "filterPanel"

    color: Preferences.backgroundSecondary

    // Bumped whenever the results change, so each chip asks Catalog.isChosen again.
    property int choices: 0
    Connections {
        target: Catalog
        function onResultsChanged() { panel.choices++ }
    }

    Flickable {
        anchors.fill: parent
        anchors.margins: Preferences.spacingMedium
        contentHeight: column.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        Column {
            id: column
            width: parent.width
            spacing: Preferences.spacingLarge

            Item {
                width: parent.width
                height: 38
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: Words.filtersTitle
                    color: Preferences.textPrimary
                    font.family: Preferences.headingFont
                    font.pixelSize: Preferences.fontSizeHeading
                }
                ActionButton {
                    objectName: "resetFilters"
                    anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                    visible: Catalog.narrowed
                    text: Words.resetFilters
                    onClicked: Catalog.reset()
                }
            }

            Repeater {
                model: ["muscle", "equipment", "measure", "level"]

                delegate: Column {
                    id: section
                    required property string modelData
                    readonly property string facet: modelData
                    width: column.width
                    spacing: Preferences.spacingSmall
                    visible: (Catalog.options[section.facet] || []).length > 0

                    Text {
                        text: Words.facetTitles[section.facet]
                        color: Preferences.textSecondary
                        font.family: Preferences.appFont
                        font.pixelSize: Preferences.fontSizeLabel
                        font.bold: true
                    }

                    Flow {
                        width: parent.width
                        spacing: 6
                        Repeater {
                            model: Catalog.options[section.facet] || []
                            delegate: Chip {
                                required property var modelData
                                objectName: "chip-" + section.facet + "-" + modelData.value
                                text: Words.valueLabel(section.facet, modelData.value)
                                count: modelData.count
                                chosen: panel.choices >= 0 && Catalog.isChosen(section.facet, modelData.value)
                                onToggled: Catalog.toggle(section.facet, modelData.value)
                            }
                        }
                    }
                }
            }
        }
    }
}
