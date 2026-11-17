import QtQuick

// A suggestion or a crown on a card (spec §7: gold only for crowns and suggestions): gold words with a small crown on
// a faint gold ground.
Rectangle {
    id: chip

    property string text: ""
    readonly property color gold: Preferences.goldColor

    implicitWidth: row.implicitWidth + 24
    implicitHeight: 28
    radius: height / 2
    color: Qt.rgba(gold.r, gold.g, gold.b, 0.13)
    border.width: 1
    border.color: Qt.rgba(gold.r, gold.g, gold.b, 0.35)

    Row {
        id: row
        anchors.centerIn: parent
        spacing: 6
        TintedIcon { anchors.verticalCenter: parent.verticalCenter; source: "qrc:/images/crown.svg"; size: 14; color: chip.gold }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: chip.text
            color: chip.gold
            font.family: Preferences.appFont
            font.pixelSize: Preferences.fontSizeLabel
        }
    }
}
