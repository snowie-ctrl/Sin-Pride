import QtQuick
import QtQuick.Controls
import "../logic/words.mjs" as Words

// The catalog search on every page (spec §6). Ctrl+K puts the cursor here from anywhere. Typing lists up to eight
// exercises by name, those starting with what was typed first. Up and Down choose; Enter or a click opens one;
// Escape clears it.
Item {
    id: search
    objectName: "quickSearch"

    property var matches: []

    function openAt(i) {
        if (i < 0 || i >= search.matches.length)
            return
        const id = search.matches[i].id
        search.close()
        Catalog.open(id)
        Nav.navigateTo("exercise-page")
    }

    // The list is worked out again from what is typed, so a catalog that changes under an open list is followed.
    function recompute() {
        search.matches = Catalog.search(field.text, 8)
        list.currentIndex = 0
    }

    function close() {
        field.text = ""
        search.matches = []
        field.focus = false
    }

    Connections {
        target: ExerciseStore
        function onChanged() {
            if (field.text.length > 0)
                search.recompute()
        }
    }

    Shortcut {
        sequence: "Ctrl+K"
        context: Qt.ApplicationShortcut
        onActivated: {
            field.forceActiveFocus()
            field.selectAll()
        }
    }

    InputField {
        id: field
        objectName: "quickSearchField"
        anchors.fill: parent
        placeholderText: Words.quickSearch
        onTextEdited: search.recompute()
        onAccepted: search.openAt(Math.max(0, list.currentIndex))
        Keys.onDownPressed: list.incrementCurrentIndex()
        Keys.onUpPressed: list.decrementCurrentIndex()
        Keys.onEscapePressed: search.close()
    }

    Rectangle {
        objectName: "quickSearchResults"
        anchors { left: parent.left; right: parent.right; top: field.bottom; topMargin: 4 }
        visible: field.activeFocus && field.text.trim().length > 0
        height: list.count > 0 ? list.contentHeight + 8 : 44
        radius: Preferences.controlRadius
        color: Preferences.backgroundSecondary
        border.color: Preferences.borderColor

        ListView {
            id: list
            anchors.fill: parent
            anchors.margins: 4
            interactive: false
            model: search.matches
            delegate: Rectangle {
                id: row
                objectName: "quickSearchRow"
                required property var modelData
                required property int index
                width: list.width
                height: 36
                radius: Preferences.controlRadius
                color: row.ListView.isCurrentItem || hover.containsMouse ? Preferences.backgroundTertiary : "transparent"

                Text {
                    anchors { left: parent.left; leftMargin: 10; verticalCenter: parent.verticalCenter }
                    text: row.modelData.name
                    color: Preferences.textPrimary
                    font.family: Preferences.appFont
                    font.pixelSize: Preferences.fontSizeBody
                }
                Text {
                    anchors { right: parent.right; rightMargin: 10; verticalCenter: parent.verticalCenter }
                    text: Words.listLabel("muscle", row.modelData.primary)
                    color: Preferences.textMuted
                    font.family: Preferences.appFont
                    font.pixelSize: Preferences.fontSizeCaption
                }
                MouseArea {
                    id: hover
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: search.openAt(row.index)
                }
            }
        }

        Text {
            objectName: "quickSearchNothing"
            anchors.centerIn: parent
            visible: list.count === 0
            text: Words.nothingFound
            color: Preferences.textMuted
            font.family: Preferences.appFont
            font.pixelSize: Preferences.fontSizeLabel
        }
    }
}
