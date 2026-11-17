// Copied from Gluttony app/qml/component/ActionButton.qml at c1ed705; Superbia's gradient (violet into royal) with
// light text on it.
import QtQuick

// The app's button. Primary is the violet-into-royal gradient, for the one thing a screen is for. Danger is outlined
// in the danger colour and never filled, so it cannot be mistaken for primary. Anything else is a quiet panel colour.
Rectangle {
    id: button

    property string text: ""
    property bool primary: false
    property bool danger: false
    // Smaller, for a row's own buttons (Today's Take it and Not yet, the set editor's).
    property bool compact: false
    // Outlined in gold: a suggestion's own button (spec §7).
    property bool gold: false
    signal clicked()

    implicitWidth: label.implicitWidth + (compact ? 24 : 32)
    implicitHeight: compact ? 28 : 38
    radius: Preferences.controlRadius
    opacity: enabled ? 1 : 0.45
    color: primary || danger || gold ? "transparent"
                                     : (mouse.containsMouse ? Qt.lighter(Preferences.backgroundTertiary, 1.25) : Preferences.backgroundTertiary)
    border.width: danger || gold ? 1 : 0
    border.color: gold ? Preferences.goldColor : Preferences.dangerColor
    gradient: primary ? superbia : null

    Gradient {
        id: superbia
        orientation: Gradient.Horizontal
        GradientStop { position: 0; color: mouse.containsMouse ? Qt.lighter(Preferences.accentDeep, 1.1) : Preferences.accentDeep }
        GradientStop { position: 1; color: Preferences.accentColor }
    }

    Text {
        id: label
        anchors.centerIn: parent
        text: button.text
        color: button.danger ? Preferences.dangerColor : button.gold ? Preferences.goldColor : Preferences.textPrimary
        font.family: Preferences.appFont
        font.pixelSize: button.compact ? Preferences.fontSizeLabel : Preferences.fontSizeBody
        font.bold: button.primary
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        enabled: button.enabled
        cursorShape: Qt.PointingHandCursor
        onClicked: button.clicked()
    }
}
