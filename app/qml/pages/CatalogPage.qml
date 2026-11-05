import QtQuick
import "../logic/words.mjs" as Words

// The catalog (spec §6). This first page only says how much of it this device holds; the filters, the tiles and
// the search follow.
Rectangle {
    id: root
    objectName: "catalogPage"
    color: Preferences.backgroundPrimary

    Column {
        anchors { left: parent.left; top: parent.top; margins: Preferences.spacingLarge }
        spacing: Preferences.spacingSmall
        Text {
            text: Words.catalogTitle
            color: Preferences.textPrimary
            font.family: Preferences.headingFont
            font.pixelSize: Preferences.fontSizeDisplay
        }
        Text {
            objectName: "catalogCount"
            text: Words.countLabel(Catalog.shownCount)
            color: Preferences.textMuted
            font.family: Preferences.appFont
            font.pixelSize: Preferences.fontSizeLabel
        }
    }
}
