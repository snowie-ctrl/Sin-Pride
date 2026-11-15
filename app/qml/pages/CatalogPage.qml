import QtQuick
import QtQuick.Controls
import "../logic/words.mjs" as Words

// The catalog (spec §6): the filter panel on the left; beside it the title and how many exercises are shown, a field
// that narrows by name, and the tiles. Everything reads the copy on this device, so it works with no server. With no
// copy at all it says so (and, with no server either, that Pride can't be reached), and offers Try again.
Rectangle {
    id: root
    objectName: "catalogPage"

    color: Preferences.backgroundPrimary

    readonly property bool empty: ExerciseStore.count === 0

    FilterPanel {
        id: panel
        anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
        width: 280
        visible: !root.empty
    }

    Item {
        id: main
        anchors {
            left: panel.visible ? panel.right : parent.left
            right: parent.right
            top: parent.top
            bottom: parent.bottom
            margins: Preferences.spacingLarge
        }

        Text {
            id: title
            anchors { left: parent.left; top: parent.top }
            text: Words.catalogTitle
            color: Preferences.textPrimary
            font.family: Preferences.headingFont
            font.pixelSize: Preferences.fontSizeDisplay
        }

        Text {
            objectName: "catalogCount"
            anchors { left: title.right; leftMargin: Preferences.spacingMedium; baseline: title.baseline }
            visible: !root.empty
            text: Words.shownOf(Catalog.results.length, Catalog.shownCount)
            color: Preferences.textMuted
            font.family: Preferences.appFont
            font.pixelSize: Preferences.fontSizeLabel
        }

        InputField {
            id: filterField
            objectName: "catalogFilterField"
            anchors { right: parent.right; verticalCenter: title.verticalCenter }
            width: 320
            visible: !root.empty
            placeholderText: Words.catalogFilter
            text: Catalog.text
            onTextEdited: Catalog.setText(text)
        }

        // Reset (or a grab's start text) changes the catalog's text from outside the field.
        Connections {
            target: Catalog
            function onResultsChanged() {
                if (filterField.text !== Catalog.text)
                    filterField.text = Catalog.text
            }
        }

        GridView {
            id: grid
            objectName: "catalogGrid"
            anchors {
                left: parent.left
                right: parent.right
                top: title.bottom
                topMargin: Preferences.spacingLarge
                bottom: parent.bottom
            }
            visible: !root.empty && count > 0
            clip: true
            cellWidth: Preferences.tileWidth + Preferences.spacingMedium
            cellHeight: Preferences.tileWidth * 0.75 + 80 + Preferences.spacingMedium
            boundsBehavior: Flickable.StopAtBounds
            model: Catalog.results
            delegate: ExerciseTile {
                required property var modelData
                exercise: modelData
                onOpened: id => {
                    Catalog.open(id)
                    Nav.navigateTo("exercise-page")
                }
            }
            ScrollBar.vertical: ScrollBar {}
        }

        Text {
            objectName: "nothingMatches"
            anchors.centerIn: grid
            visible: !root.empty && Catalog.results.length === 0
            text: Words.nothingMatches
            color: Preferences.textMuted
            font.family: Preferences.appFont
            font.pixelSize: Preferences.fontSizeBody
        }

        Text {
            objectName: "catalogLoading"
            anchors.centerIn: parent
            visible: root.empty && ExerciseStore.loading
            text: Words.catalogLoading
            color: Preferences.textMuted
            font.family: Preferences.appFont
            font.pixelSize: Preferences.fontSizeBody
        }

        Column {
            objectName: "catalogUnavailable"
            anchors.centerIn: parent
            width: Math.min(parent.width, 420)
            visible: root.empty && !ExerciseStore.loading
            spacing: Preferences.spacingMedium

            Text {
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.Wrap
                text: Words.catalogUnavailable + (!Session.online || Session.offline ? " " + Words.catalogOffline : "")
                color: Preferences.textSecondary
                font.family: Preferences.appFont
                font.pixelSize: Preferences.fontSizeBody
            }
            ActionButton {
                objectName: "catalogRetry"
                anchors.horizontalCenter: parent.horizontalCenter
                text: Words.tryAgain
                onClicked: Session.offline ? Session.retry() : ExerciseStore.refresh()
            }
        }
    }
}
