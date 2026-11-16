import QtQuick
import QtQuick.Controls
import "../logic/words.mjs" as Words

// The catalog picker of the routine editor (plan decision 20): it lists what fits the person's equipment, and one click
// on "Show everything" lists all of it. Choosing a row hands its id to the page, which asks the service to add it.
Popup {
    id: root

    property bool everything: false
    // Catalog.pick reads the store and the person's own exercises; the revisions are named so the list is worked out
    // again when either changes while the picker is open, and the profile's equipment when it changes.
    readonly property var tiles: root.opened && ExerciseStore.revision >= 0 && Catalog.own !== undefined
                                 ? Catalog.pick(field.text, Profile.profile.equipment || [], root.everything, 200) : []
    signal chosen(int exerciseId)

    modal: true
    anchors.centerIn: Overlay.overlay
    width: 640
    height: 600
    padding: Preferences.spacingLarge
    background: Rectangle {
        radius: Preferences.cornerRadius
        color: Preferences.backgroundSecondary
        border.color: Preferences.borderColor
    }

    onAboutToShow: {
        field.text = ""
        root.everything = false
    }
    onOpened: field.forceActiveFocus()

    // The name sits on the content, not on the Popup, so the page tests (which walk the item tree) can find it.
    Column {
        objectName: "exercisePicker"
        anchors.fill: parent
        spacing: Preferences.spacingSmall

        Text {
            text: Words.pickerTitle
            color: Preferences.textPrimary
            font.family: Preferences.headingFont
            font.pixelSize: Preferences.fontSizeHeading
        }
        InputField {
            id: field
            objectName: "pickerField"
            placeholderText: Words.pickerFilter
        }
        Chip {
            objectName: "pickerEverything"
            text: Words.showEverything
            chosen: root.everything
            onToggled: root.everything = !root.everything
        }

        Text {
            objectName: "pickerNothing"
            visible: root.tiles.length === 0
            width: parent.width
            // "Show everything?" is only an offer while everything is not already on.
            text: root.everything ? Words.nothingFound : Words.pickerNothing
            wrapMode: Text.WordWrap
            color: Preferences.textMuted
            font.family: Preferences.appFont
            font.pixelSize: Preferences.fontSizeBody
        }

        ListView {
            id: list
            width: parent.width
            height: parent.height - y
            clip: true
            spacing: Preferences.spacingSmall
            boundsBehavior: Flickable.StopAtBounds
            model: root.tiles
            ScrollBar.vertical: ScrollBar {}

            delegate: Rectangle {
                id: tile
                required property var modelData
                objectName: "pickerRow"
                width: list.width
                height: 56
                radius: Preferences.controlRadius
                color: hover.containsMouse ? Preferences.backgroundTertiary : "transparent"

                PictureFrame {
                    id: pic
                    x: 4
                    anchors.verticalCenter: parent.verticalCenter
                    width: 48
                    height: 48
                    name: tile.modelData.picture || ""
                }
                Column {
                    anchors { left: pic.right; leftMargin: Preferences.spacingSmall; right: parent.right; rightMargin: 8; verticalCenter: parent.verticalCenter }
                    spacing: 2
                    Text {
                        width: parent.width
                        text: tile.modelData.name
                        elide: Text.ElideRight
                        color: Preferences.textPrimary
                        font.family: Preferences.appFont
                        font.pixelSize: Preferences.fontSizeBody
                        font.weight: Font.DemiBold
                    }
                    Text {
                        width: parent.width
                        text: Words.tileCaption(tile.modelData.primary, tile.modelData.measure)
                        elide: Text.ElideRight
                        color: Preferences.textMuted
                        font.family: Preferences.appFont
                        font.pixelSize: Preferences.fontSizeCaption
                    }
                }
                MouseArea {
                    id: hover
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        // Closing empties the list, which destroys this row, so the choice is handed over first.
                        root.chosen(tile.modelData.id)
                        root.close()
                    }
                }
            }
        }
    }
}
