// Copied from Gluttony app/qml/component/InputField.qml at c1ed705; as it is.
import QtQuick
import QtQuick.Controls

// The app's text box: a field on the tertiary ground that shows the accent as an outline while it has the focus.
TextField {
    id: field

    width: parent ? parent.width : 300
    height: 40
    leftPadding: 12
    color: Preferences.textPrimary
    placeholderTextColor: Preferences.textMuted
    font.family: Preferences.appFont
    font.pixelSize: Preferences.fontSizeBody
    selectByMouse: true

    background: Rectangle {
        radius: Preferences.controlRadius
        color: Preferences.backgroundTertiary
        border.width: field.activeFocus ? 1 : 0
        border.color: Preferences.accentColor
    }
}
