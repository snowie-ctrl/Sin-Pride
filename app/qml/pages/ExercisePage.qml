import QtQuick
import QtQuick.Controls
import "../logic/words.mjs" as Words

// One exercise (spec §6): its pictures, the muscles it works, its equipment and steps, and the credit its source asks
// for. The person's history and records, and "Add to a routine…", join in milestones 2 and 3. An exercise that has
// left the catalog still opens (history names it) and says so.
Rectangle {
    id: root
    objectName: "exercisePage"

    color: Preferences.backgroundPrimary

    signal backRequested()

    readonly property var exercise: Catalog.current
    readonly property bool found: root.exercise !== undefined && root.exercise.id !== undefined
    readonly property var pictures: root.found ? (root.exercise.pictures || []) : []
    property int pictureIndex: 0
    onExerciseChanged: root.pictureIndex = 0

    ActionButton {
        id: back
        objectName: "exerciseBack"
        anchors { left: parent.left; top: parent.top; margins: Preferences.spacingLarge }
        text: Words.back
        onClicked: root.backRequested()
    }

    Text {
        objectName: "exerciseMissing"
        anchors.centerIn: parent
        visible: !root.found
        text: Words.exerciseMissing
        color: Preferences.textSecondary
        font.family: Preferences.appFont
        font.pixelSize: Preferences.fontSizeBody
    }

    Flickable {
        id: flick
        visible: root.found
        anchors {
            left: parent.left
            right: parent.right
            top: back.bottom
            bottom: parent.bottom
            margins: Preferences.spacingLarge
        }
        contentHeight: Math.max(picturesColumn.implicitHeight, details.implicitHeight)
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar {}

        Column {
            id: picturesColumn
            width: Math.min(flick.width * 0.46, 640)
            spacing: Preferences.spacingSmall

            PictureFrame {
                objectName: "exercisePicture"
                width: parent.width
                height: width * 0.75
                fillMode: Image.PreserveAspectFit
                name: root.pictures.length > 0 ? root.pictures[Math.min(root.pictureIndex, root.pictures.length - 1)] : ""
            }

            Row {
                spacing: 6
                visible: root.pictures.length > 1
                Repeater {
                    model: root.pictures.length
                    delegate: Chip {
                        required property int index
                        objectName: "pictureChip" + index
                        text: Words.pictureCount(index, root.pictures.length)
                        chosen: index === root.pictureIndex
                        onToggled: root.pictureIndex = index
                    }
                }
            }
        }

        Column {
            id: details
            anchors { left: picturesColumn.right; leftMargin: Preferences.spacingLarge }
            width: flick.width - picturesColumn.width - Preferences.spacingLarge
            spacing: Preferences.spacingMedium

            Text {
                objectName: "exerciseName"
                width: parent.width
                wrapMode: Text.Wrap
                text: root.found ? root.exercise.name : ""
                color: Preferences.textPrimary
                font.family: Preferences.headingFont
                font.pixelSize: Preferences.fontSizeDisplay
            }

            Text {
                objectName: "exerciseGone"
                width: parent.width
                wrapMode: Text.Wrap
                visible: root.found && root.exercise.removed === true
                text: Words.exerciseGone
                color: Preferences.textSecondary
                font.family: Preferences.appFont
                font.pixelSize: Preferences.fontSizeBody
                font.italic: true
            }

            Text {
                width: parent.width
                wrapMode: Text.Wrap
                text: root.found ? [Words.valueLabel("level", root.exercise.level),
                                    Words.valueLabel("measure", root.exercise.measure),
                                    Words.valueLabel("region", root.exercise.region)].filter(t => t).join(" · ") : ""
                color: Preferences.textMuted
                font.family: Preferences.appFont
                font.pixelSize: Preferences.fontSizeLabel
            }

            Section {
                title: Words.works
                Text {
                    objectName: "exercisePrimary"
                    width: parent.width
                    wrapMode: Text.Wrap
                    text: root.found ? Words.listLabel("muscle", root.exercise.primary) : ""
                    color: Preferences.textPrimary
                    font.family: Preferences.appFont
                    font.pixelSize: Preferences.fontSizeBody
                }
            }

            Section {
                title: Words.alsoWorks
                visible: root.found && (root.exercise.secondary || []).length > 0
                Text {
                    objectName: "exerciseSecondary"
                    width: parent.width
                    wrapMode: Text.Wrap
                    text: root.found ? Words.listLabel("muscle", root.exercise.secondary) : ""
                    color: Preferences.textSecondary
                    font.family: Preferences.appFont
                    font.pixelSize: Preferences.fontSizeBody
                }
            }

            Section {
                title: Words.equipmentTitle
                Text {
                    objectName: "exerciseEquipment"
                    width: parent.width
                    wrapMode: Text.Wrap
                    text: root.found ? Words.listLabel("equipment", root.exercise.equipment) : ""
                    color: Preferences.textPrimary
                    font.family: Preferences.appFont
                    font.pixelSize: Preferences.fontSizeBody
                }
            }

            Section {
                title: Words.stepsTitle
                Repeater {
                    model: root.found ? (root.exercise.steps || []) : []
                    delegate: Text {
                        required property string modelData
                        required property int index
                        objectName: "exerciseStep"
                        width: details.width
                        wrapMode: Text.Wrap
                        text: (index + 1) + ".  " + modelData
                        color: Preferences.textPrimary
                        font.family: Preferences.appFont
                        font.pixelSize: Preferences.fontSizeBody
                        lineHeight: 1.25
                    }
                }
                Text {
                    objectName: "exerciseNoSteps"
                    visible: root.found && (root.exercise.steps || []).length === 0
                    text: Words.noSteps
                    color: Preferences.textMuted
                    font.family: Preferences.appFont
                    font.pixelSize: Preferences.fontSizeBody
                }
            }

            Text {
                objectName: "exerciseCredit"
                width: parent.width
                wrapMode: Text.Wrap
                text: root.found ? Words.creditLine(root.exercise.source, root.exercise.licence) : ""
                color: Preferences.textMuted
                font.family: Preferences.appFont
                font.pixelSize: Preferences.fontSizeCaption
            }
        }
    }

    // A titled block of the details column.
    component Section: Column {
        property string title: ""
        default property alias content: body.data
        // An inline component has a scope of its own, so it sizes itself from its parent (the details column).
        width: parent ? parent.width : 0
        spacing: Preferences.spacingSmall

        Text {
            text: parent.title
            color: Preferences.textSecondary
            font.family: Preferences.appFont
            font.pixelSize: Preferences.fontSizeLabel
            font.bold: true
        }
        Column {
            id: body
            width: parent.width
            spacing: Preferences.spacingSmall
        }
    }
}
