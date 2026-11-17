import QtQuick

// One of Today's recent crowns (spec §6, layout T1): the crown, the exercise and its record, and when.
Rectangle {
    id: card

    property string name: ""
    property string record: ""
    property string when: ""

    implicitWidth: row.implicitWidth + 32
    implicitHeight: row.implicitHeight + 24
    radius: Preferences.cornerRadius
    color: Preferences.backgroundSecondary
    border.width: 1
    border.color: Preferences.borderColor

    Row {
        id: row
        x: 16
        anchors.verticalCenter: parent.verticalCenter
        spacing: 12
        TintedIcon { anchors.verticalCenter: parent.verticalCenter; source: "qrc:/images/crown.svg"; size: 22; color: Preferences.goldColor }
        Column {
            spacing: 2
            Text {
                text: card.name + "  " + card.record
                color: Preferences.textPrimary
                font.family: Preferences.appFont
                font.pixelSize: Preferences.fontSizeBody
                font.weight: Font.DemiBold
            }
            Text {
                text: card.when
                color: Preferences.textMuted
                font.family: Preferences.appFont
                font.pixelSize: Preferences.fontSizeCaption
            }
        }
    }
}
