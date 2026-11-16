import QtQuick
import "../logic/words.mjs" as Words

// The week (spec §6 Today, plan decision 22): seven cells, done days filled, planned days ringed with a dashed line,
// today outlined. A past day with no workout is just a day: Pride never marks a miss.
Row {
    id: strip
    objectName: "weekStrip"

    property var days: []            // GET /today's week
    property string todayIso: ""

    spacing: Preferences.spacingSmall

    Repeater {
        model: strip.days
        Rectangle {
            id: cell
            required property var modelData
            objectName: "dayCell-" + modelData.weekday
            readonly property bool done: modelData.done
            readonly property bool planned: modelData.planned
            readonly property bool isToday: modelData.date === strip.todayIso

            width: (strip.width - strip.spacing * 6) / 7
            height: 96
            radius: Preferences.controlRadius
            color: Preferences.backgroundTertiary
            border.width: cell.isToday ? 1 : 0
            border.color: Preferences.accentColor

            Column {
                anchors.centerIn: parent
                spacing: 6
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: Words.weekdayShort(cell.modelData.weekday).toUpperCase()
                    color: cell.isToday ? Preferences.textPrimary : Preferences.textMuted
                    font.family: Preferences.appFont
                    font.pixelSize: Preferences.fontSizeCaption
                    font.letterSpacing: 1
                }
                Item {
                    objectName: "dayMarker"
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: 28
                    height: 28
                    visible: cell.done || cell.planned
                    Rectangle {
                        anchors.fill: parent
                        radius: width / 2
                        visible: cell.done
                        color: Preferences.accentColor
                        Text { anchors.centerIn: parent; text: "✓"; color: Preferences.textPrimary; font.pixelSize: 14; font.bold: true }
                    }
                    Canvas {
                        anchors.fill: parent
                        visible: cell.planned
                        onPaint: {
                            const ctx = getContext("2d")
                            ctx.reset()
                            ctx.setLineDash([3, 3])
                            ctx.lineWidth = 2
                            ctx.strokeStyle = Preferences.accentColor
                            ctx.beginPath()
                            ctx.arc(width / 2, height / 2, width / 2 - 1, 0, 2 * Math.PI)
                            ctx.stroke()
                        }
                    }
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: cell.isToday ? Words.today : cell.done ? Words.dayDone : cell.planned ? Words.dayPlanned : " "
                    color: cell.isToday ? Preferences.textPrimary : Preferences.textMuted
                    font.family: Preferences.appFont
                    font.pixelSize: Preferences.fontSizeCaption
                }
            }
        }
    }
}
