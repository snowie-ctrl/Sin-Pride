import QtQuick

// A small caption above a control (Settings and the intro). Muted for a hint rather than a label.
Text {
    property bool muted: false

    color: muted ? Preferences.textMuted : Preferences.textSecondary
    font.family: Preferences.appFont
    font.pixelSize: Preferences.fontSizeLabel
    wrapMode: Text.WordWrap
}
