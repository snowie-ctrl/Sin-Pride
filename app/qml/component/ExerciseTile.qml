import QtQuick
import "../logic/words.mjs" as Words

// One exercise in the catalog's grid: its first picture, its name, and what it works and how it is measured.
Rectangle {
    id: tile
    objectName: "exerciseTile"

    // A Catalog tile: {id, name, measure, level, region, primary, equipment, picture}.
    property var exercise: ({})
    signal opened(int id)

    width: Preferences.tileWidth
    height: Preferences.tileWidth * 0.75 + 80
    radius: Preferences.cornerRadius
    color: mouse.containsMouse ? Preferences.backgroundTertiary : Preferences.backgroundSecondary
    border.color: Preferences.borderColor

    PictureFrame {
        id: frame
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: Preferences.spacingSmall }
        height: width * 0.75
        name: tile.exercise.picture || ""
    }

    Text {
        id: title
        anchors { left: parent.left; right: parent.right; top: frame.bottom; margins: 10 }
        text: tile.exercise.name || ""
        wrapMode: Text.Wrap
        maximumLineCount: 2
        elide: Text.ElideRight
        color: Preferences.textPrimary
        font.family: Preferences.appFont
        font.pixelSize: Preferences.fontSizeLabel
        font.bold: true
    }

    Text {
        anchors { left: parent.left; right: parent.right; top: title.bottom; leftMargin: 10; rightMargin: 10; topMargin: 4 }
        text: Words.tileCaption(tile.exercise.primary, tile.exercise.measure)
        elide: Text.ElideRight
        color: Preferences.textMuted
        font.family: Preferences.appFont
        font.pixelSize: Preferences.fontSizeCaption
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: tile.opened(tile.exercise.id)
    }
}
