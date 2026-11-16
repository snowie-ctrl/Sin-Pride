import QtQuick
import QtQuick.Controls
import "../logic/words.mjs" as Words

// Asks before anything that can't be undone (spec §6: delete with a confirmation). Yes is outlined in the danger
// colour, never filled, as every destructive button is.
Popup {
    id: dialog

    property string text: ""
    property string yesText: ""
    signal accepted()

    modal: true
    anchors.centerIn: Overlay.overlay
    width: 420
    padding: Preferences.spacingLarge
    background: Rectangle {
        radius: Preferences.cornerRadius
        color: Preferences.backgroundSecondary
        border.color: Preferences.borderColor
    }

    // The name sits on the content, not on the Popup: a Popup is not an Item, so the page tests (which walk the item
    // tree) could not find it there, and the content is shown only while the dialog is open.
    Column {
        objectName: "confirmDialog"
        width: parent.width
        spacing: Preferences.spacingMedium
        Text {
            width: parent.width
            text: dialog.text
            wrapMode: Text.Wrap
            color: Preferences.textPrimary
            font.family: Preferences.appFont
            font.pixelSize: Preferences.fontSizeBody
        }
        Row {
            anchors.right: parent.right
            spacing: Preferences.spacingSmall
            ActionButton { objectName: "confirmNo"; text: Words.keepIt; onClicked: dialog.close() }
            ActionButton {
                objectName: "confirmYes"
                danger: true
                text: dialog.yesText
                onClicked: { dialog.close(); dialog.accepted() }
            }
        }
    }
}
