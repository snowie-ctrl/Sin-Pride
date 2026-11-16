import QtQuick

// A refusal in the danger colour; takes no room while there is nothing to say. Its words come from words.mjs.
Text {
    visible: text.length > 0
    height: visible ? implicitHeight : 0
    color: Preferences.dangerColor
    font.family: Preferences.appFont
    font.pixelSize: Preferences.fontSizeLabel
    wrapMode: Text.WordWrap
    width: parent ? parent.width : implicitWidth
}
