import QtQuick
import QtQuick.Controls
import "../logic/words.mjs" as Words
import "../logic/units.mjs" as Units

// Today (spec §6, layout T1 "Throne"): the Next up card across the page with the routine's exercises and their
// targets, then the week. Each visit asks the server again. Milestone 3 adds the suggestion chip on each row and
// "Log this workout" at the card's foot; the crowns row waits for there being any (plan decision 23).
Rectangle {
    id: root
    objectName: "todayPage"

    color: Preferences.backgroundPrimary

    readonly property var today: Programs.today
    readonly property bool hasToday: today !== undefined && today.week !== undefined
    readonly property var program: hasToday ? today.program : null
    readonly property var nextUp: hasToday ? today.nextUp : null
    // Set while this page's own "empty program" is being made, so only that save moves the person on.
    property bool makingEmpty: false

    // An exercise the catalog does not know, or has taken out, is named when it can be and marked as gone.
    // The catalog can arrive after Today does, and an own exercise can change, so the lookup reads their revisions
    // to run again when either does. The rows wait for the catalog's first answer, so none is drawn nameless.
    function exerciseOf(item) {
        return ExerciseStore.revision >= 0 && Catalog.own !== undefined ? Catalog.exercise(item.exerciseId) : ({})
    }
    function isGone(exercise) { return exercise.id === undefined || exercise.removed === true }

    // Each visit asks again, so the week and next up are fresh. The first answer is signing in's to fetch (wiring asks
    // for everything then), so a page with nothing held yet does not ask a second time.
    Component.onCompleted: {
        if (root.hasToday && !Programs.todayLoading)
            Programs.loadToday()
    }

    Connections {
        target: Programs
        function onSaved(what) {
            if (what === "program" && root.makingEmpty) {
                root.makingEmpty = false
                Nav.navigateTo("programs-page")
            }
        }
        function onFailed(what) {
            if (what === "program")
                root.makingEmpty = false
        }
    }

    Flickable {
        id: flick
        anchors.fill: parent
        anchors.margins: Preferences.spacingLarge
        contentWidth: width
        contentHeight: column.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar {}

        Column {
            id: column
            width: flick.width
            spacing: Preferences.spacingLarge

            Text {
                objectName: "todayLoading"
                visible: Programs.todayLoading && !root.hasToday
                text: Words.todayLoadingText
                color: Preferences.textMuted
                font.family: Preferences.appFont
                font.pixelSize: Preferences.fontSizeBody
            }

            Panel {
                objectName: "todayUnavailable"
                visible: Programs.todayError.length > 0 && !root.hasToday
                Text {
                    width: parent.width
                    text: Words.todayUnavailable
                    wrapMode: Text.WordWrap
                    color: Preferences.textPrimary
                    font.family: Preferences.appFont
                    font.pixelSize: Preferences.fontSizeBody
                }
                ActionButton { objectName: "todayRetry"; text: Words.tryAgain; onClicked: Programs.loadToday() }
            }

            Panel {
                objectName: "noProgramCard"
                visible: root.hasToday && root.program === null && Programs.programs.length === 0
                Text {
                    width: parent.width
                    text: Words.noProgram
                    wrapMode: Text.WordWrap
                    color: Preferences.textPrimary
                    font.family: Preferences.appFont
                    font.pixelSize: Preferences.fontSizeBody
                }
                Row {
                    spacing: Preferences.spacingMedium
                    ActionButton {
                        objectName: "todayShowIntro"
                        primary: true
                        text: Words.showIntro
                        onClicked: Nav.navigateTo("intro-page")
                    }
                    ActionButton {
                        objectName: "todayEmptyProgram"
                        text: Words.startEmptyProgram
                        onClicked: {
                            root.makingEmpty = true
                            Programs.create(Words.myProgram)
                        }
                    }
                }
            }

            Panel {
                objectName: "pickProgramCard"
                visible: root.hasToday && root.program === null && Programs.programs.length > 0
                Text {
                    width: parent.width
                    text: Words.pickProgram
                    wrapMode: Text.WordWrap
                    color: Preferences.textPrimary
                    font.family: Preferences.appFont
                    font.pixelSize: Preferences.fontSizeBody
                }
                ActionButton {
                    objectName: "todayPickProgram"
                    primary: true
                    text: Words.openPrograms
                    onClicked: Nav.navigateTo("programs-page")
                }
            }

            Panel {
                objectName: "noRoutinesCard"
                visible: root.hasToday && root.program !== null && root.nextUp === null
                Text {
                    width: parent.width
                    text: root.program ? Words.noRoutinesYet(root.program.title) : ""
                    wrapMode: Text.WordWrap
                    color: Preferences.textPrimary
                    font.family: Preferences.appFont
                    font.pixelSize: Preferences.fontSizeBody
                }
                ActionButton {
                    objectName: "todayOpenPrograms"
                    primary: true
                    text: Words.openPrograms
                    onClicked: {
                        Programs.open(root.program.id)
                        Nav.navigateTo("programs-page")
                    }
                }
            }

            // ---- The Next up card ----
            Rectangle {
                id: card
                objectName: "nextUpCard"
                visible: root.hasToday && root.nextUp !== null
                width: parent.width
                height: visible ? cardBody.implicitHeight + 2 * 32 : 0
                radius: Preferences.cornerRadius
                color: Preferences.backgroundSecondary
                border.width: 1
                border.color: Preferences.borderColor

                Column {
                    id: cardBody
                    x: 32
                    y: 32
                    width: card.width - 64
                    spacing: Preferences.spacingSmall

                    Text {
                        text: Words.nextUp.toUpperCase()
                        color: Preferences.textMuted
                        font.family: Preferences.appFont
                        font.pixelSize: Preferences.fontSizeCaption
                        // 0.12 em of the 12 px size.
                        font.letterSpacing: 12 * 0.12
                    }

                    Row {
                        spacing: Preferences.spacingSmall
                        Text {
                            id: title
                            objectName: "nextUpTitle"
                            text: root.nextUp ? root.nextUp.title : ""
                            color: Preferences.textPrimary
                            font.family: Preferences.headingFont
                            font.pixelSize: 34
                        }
                        Text {
                            objectName: "nextUpWhen"
                            anchors.baseline: title.baseline
                            text: "· " + Words.plannedFor(root.hasToday ? root.today.plannedDay : null, Programs.todayDate)
                            color: Preferences.textSecondary
                            font.family: Preferences.appFont
                            font.pixelSize: Preferences.fontSizeHeading
                        }
                    }

                    Repeater {
                        model: root.nextUp && ExerciseStore.settled ? root.nextUp.items : []
                        Item {
                            id: row
                            required property var modelData
                            required property int index
                            readonly property var exercise: root.exerciseOf(modelData)
                            readonly property bool gone: root.isGone(exercise)
                            objectName: "todayItem"
                            width: cardBody.width
                            height: 56 + 2 * Preferences.spacingMedium

                            Rectangle {
                                visible: row.index > 0
                                width: parent.width
                                height: 1
                                color: Preferences.borderColor
                            }

                            PictureFrame {
                                id: pic
                                x: 0
                                y: Preferences.spacingMedium
                                width: 56
                                height: 56
                                name: row.exercise.pictures && row.exercise.pictures.length > 0 ? row.exercise.pictures[0] : ""
                            }
                            Column {
                                anchors { left: pic.right; leftMargin: Preferences.spacingMedium; verticalCenter: pic.verticalCenter }
                                spacing: 2
                                Text {
                                    objectName: "todayItemName"
                                    text: row.exercise.name || Words.unknownExercise
                                    color: Preferences.textPrimary
                                    font.family: Preferences.appFont
                                    font.pixelSize: Preferences.fontSizeBody
                                    font.weight: Font.DemiBold
                                }
                                Text {
                                    objectName: "todayItemTarget"
                                    text: Units.target(row.modelData, row.exercise.measure)
                                    color: Preferences.textSecondary
                                    font.family: Preferences.appFont
                                    font.pixelSize: Preferences.fontSizeLabel
                                }
                            }
                            Text {
                                objectName: "todayItemGone"
                                visible: row.gone
                                anchors { right: parent.right; verticalCenter: pic.verticalCenter }
                                text: Words.leftCatalog
                                color: Preferences.textMuted
                                font.family: Preferences.appFont
                                font.pixelSize: Preferences.fontSizeLabel
                            }
                        }
                    }
                }
            }

            // ---- The week ----
            Column {
                width: parent.width
                spacing: Preferences.spacingSmall
                visible: root.hasToday
                Text {
                    text: Words.thisWeek.toUpperCase()
                    color: Preferences.textMuted
                    font.family: Preferences.appFont
                    font.pixelSize: Preferences.fontSizeCaption
                    font.letterSpacing: 12 * 0.12
                }
                WeekStrip {
                    width: parent.width
                    days: root.hasToday ? root.today.week : []
                    todayIso: Programs.todayDate
                }
            }
        }
    }

    // A plain card for the states that hold only a sentence and a button or two.
    component Panel: Rectangle {
        id: panel
        default property alias content: body.data
        width: parent ? parent.width : 0
        height: visible ? body.implicitHeight + 2 * Preferences.spacingLarge : 0
        radius: Preferences.cornerRadius
        color: Preferences.backgroundSecondary
        border.width: 1
        border.color: Preferences.borderColor

        Column {
            id: body
            x: Preferences.spacingLarge
            y: Preferences.spacingLarge
            width: panel.width - 2 * Preferences.spacingLarge
            spacing: Preferences.spacingMedium
        }
    }
}
