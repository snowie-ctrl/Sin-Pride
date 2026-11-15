import QtQuick

// A word that is on or off, such as a filter. Fully round (spec §7's shapes); chosen, it takes the accent's subtle
// ground and outline.
Rectangle {
    id: chip

    property string text: ""
    // How many exercises the word names; -1 shows no count.
    property int count: -1
    property bool chosen: false
    signal toggled()

    implicitWidth: label.implicitWidth + Preferences.spacingLarge
    implicitHeight: 30
    radius: height / 2
    color: chip.chosen ? Preferences.accentSubtle : (mouse.containsMouse ? Preferences.backgroundTertiary : "transparent")
    border.color: chip.chosen ? Preferences.accentColor : Preferences.borderColor

    Text {
        id: label
        anchors.centerIn: parent
        textFormat: Text.StyledText
        text: chip.count >= 0 ? chip.text + "  <font color=\"" + Preferences.textMuted + "\">" + chip.count + "</font>"
                              : chip.text
        color: chip.chosen ? Preferences.textPrimary : Preferences.textSecondary
        font.family: Preferences.appFont
        font.pixelSize: Preferences.fontSizeLabel
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: chip.toggled()
    }
}
