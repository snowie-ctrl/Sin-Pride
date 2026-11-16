import QtQuick

// A small box for one number or a time (the routine editor's targets): narrow, centred, and asking a touch keyboard
// for digits. Parsing and checking are forms.mjs's and units.mjs's; this only looks and sounds like a number field.
InputField {
    width: 72
    horizontalAlignment: Text.AlignHCenter
    inputMethodHints: Qt.ImhFormattedNumbersOnly
}
