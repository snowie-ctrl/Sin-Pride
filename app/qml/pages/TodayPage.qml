import QtQuick
import QtQuick.Controls
import "../logic/words.mjs" as Words
import "../logic/units.mjs" as Units
import "../logic/logbook.mjs" as Log

// Today (spec §6, layout T1 "Throne"): the Next up card across the page with the routine's exercises and their
// targets, then the week. Each visit asks the server again. Each row carries last time's sets and its open suggestion
// (a gold chip with Take it and Not yet, or a stall's tip with Noted); Log this workout sits at the card's foot; the
// recent crowns follow the week.
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
    // A line under the card's title: "Earned it" after a step-up is taken, a refusal, or a change made elsewhere.
    property string notice: ""
    // The suggestion being decided, with its exercise's name, for the words once the answer comes.
    property var deciding: ({})

    function decide(suggestion, exercise, take) {
        root.notice = ""
        root.deciding = { id: suggestion.id, name: exercise.name || Words.unknownExercise, proposal: Log.proposal(suggestion) }
        if (take)
            Progress.accept(suggestion.id)
        else
            Progress.dismiss(suggestion.id)
    }

    // A loss on another device may have been met elsewhere while Today was not on screen; the service keeps it until
    // a page has said so (milestone 1's carried item: Today says so too, not only Programs).
    function takeGoneNotice() {
        if (Programs.goneNotice.length === 0)
            return
        root.notice = Words.goneElsewhere
        Programs.clearGoneNotice()
    }

    // An exercise the catalog does not know, or has taken out, is named when it can be and marked as gone.
    // The catalog can arrive after Today does, and an own exercise can change, so the lookup reads their revisions
    // to run again when either does. The rows wait for the catalog's first answer, so none is drawn nameless.
    function exerciseOf(item) {
        return ExerciseStore.revision >= 0 && Catalog.own !== undefined ? Catalog.exercise(item.exerciseId) : ({})
    }
    function isGone(exercise) { return exercise.id === undefined || exercise.removed === true }

    // Each visit asks again, so the week and next up are fresh. A visit after a failed first fetch, or after a start
    // with no server (where none was made), asks again too, so Today never stays blank. A visit that finds nothing
    // held, nothing failed and the server in reach is waiting for signing in's own fetch, so it does not ask twice.
    Component.onCompleted: {
        root.takeGoneNotice()
        if (!Programs.todayLoading && (root.hasToday || Programs.todayError.length > 0 || Session.offline))
            Programs.loadToday()
    }

    Connections {
        target: Programs
        function onGoneNoticeChanged() { root.takeGoneNotice() }
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

    Connections {
        target: Progress
        function onDecided(id, what) {
            if (id === root.deciding.id && what === "accepted")
                root.notice = Words.earnedIt(root.deciding.name, root.deciding.proposal)
        }
        function onFailed(what, code) {
            if (what === "accept" || what === "dismiss")
                root.notice = Words.saveProblem(code, "")
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
                objectName: "todayNotice"
                visible: text.length > 0
                width: parent.width
                text: root.notice
                wrapMode: Text.WordWrap
                color: Preferences.goldColor
                font.family: Preferences.appFont
                font.pixelSize: Preferences.fontSizeBody
            }

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
                // No answer and nothing on its way (a failed ask, or an offline start where none was made).
                visible: !root.hasToday && (!Programs.todayLoading || Session.offline)
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
                            readonly property var suggestion: modelData.suggestion || null
                            readonly property bool stepUp: suggestion !== null && suggestion.kind === "increase"
                            readonly property bool stall: suggestion !== null && suggestion.kind === "stall"
                            readonly property string measure: modelData.measure || row.exercise.measure || ""
                            objectName: "todayItem"
                            width: cardBody.width
                            height: Math.max(56, info.implicitHeight, side.implicitHeight) + 2 * Preferences.spacingMedium

                            Rectangle {
                                visible: row.index > 0
                                width: parent.width
                                height: 1
                                color: Preferences.borderColor
                            }

                            PictureFrame {
                                id: pic
                                x: 0
                                anchors.verticalCenter: parent.verticalCenter
                                width: 56
                                height: 56
                                name: row.exercise.pictures && row.exercise.pictures.length > 0 ? row.exercise.pictures[0] : ""
                            }
                            Column {
                                id: info
                                anchors { left: pic.right; leftMargin: Preferences.spacingMedium; verticalCenter: parent.verticalCenter }
                                width: row.width - pic.width - side.width - 2 * Preferences.spacingMedium
                                spacing: 2
                                Text {
                                    objectName: "todayItemName"
                                    width: parent.width
                                    elide: Text.ElideRight
                                    text: row.exercise.name || Words.unknownExercise
                                    color: Preferences.textPrimary
                                    font.family: Preferences.appFont
                                    font.pixelSize: Preferences.fontSizeBody
                                    font.weight: Font.DemiBold
                                }
                                Text {
                                    objectName: "todayItemTarget"
                                    text: Units.target(row.modelData, row.measure)
                                    color: Preferences.textSecondary
                                    font.family: Preferences.appFont
                                    font.pixelSize: Preferences.fontSizeLabel
                                }
                                Text {
                                    objectName: "todayItemLast"
                                    visible: text.length > 0
                                    text: row.modelData.last ? Words.lastTime(Log.setsLine(row.modelData.last.sets, row.measure)) : ""
                                    color: Preferences.textMuted
                                    font.family: Preferences.appFont
                                    font.pixelSize: Preferences.fontSizeCaption
                                }
                            }
                            Row {
                                id: side
                                anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                                spacing: Preferences.spacingSmall
                                Text {
                                    objectName: "todayItemGone"
                                    visible: row.gone
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: Words.leftCatalog
                                    color: Preferences.textMuted
                                    font.family: Preferences.appFont
                                    font.pixelSize: Preferences.fontSizeLabel
                                }
                                GoldChip {
                                    objectName: "todayItemSuggestion"
                                    visible: row.stepUp
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: row.stepUp ? Words.suggestionChip(Log.lastShort(row.modelData.last, row.measure),
                                                                            Log.proposal(row.suggestion)) : ""
                                }
                                ActionButton {
                                    objectName: "todayTakeIt"
                                    visible: row.stepUp
                                    anchors.verticalCenter: parent.verticalCenter
                                    compact: true
                                    gold: true
                                    text: Words.takeIt
                                    onClicked: root.decide(row.suggestion, row.exercise, true)
                                }
                                ActionButton {
                                    objectName: "todayNotYet"
                                    visible: row.stepUp
                                    anchors.verticalCenter: parent.verticalCenter
                                    compact: true
                                    text: Words.notYet
                                    onClicked: root.decide(row.suggestion, row.exercise, false)
                                }
                                Text {
                                    objectName: "todayStall"
                                    visible: row.stall
                                    anchors.verticalCenter: parent.verticalCenter
                                    textFormat: Text.StyledText
                                    text: "<b><font color=\"" + Preferences.goldColor + "\">" + Words.holdingSteady + "</font></b> " + Words.stallTip
                                    color: Preferences.textSecondary
                                    font.family: Preferences.appFont
                                    font.pixelSize: Preferences.fontSizeLabel
                                }
                                ActionButton {
                                    objectName: "todayNoted"
                                    visible: row.stall
                                    anchors.verticalCenter: parent.verticalCenter
                                    compact: true
                                    text: Words.noted
                                    onClicked: root.decide(row.suggestion, row.exercise, false)
                                }
                            }
                        }
                    }
                    Item { width: 1; height: Preferences.spacingSmall }
                    Rectangle { width: cardBody.width; height: 1; color: Preferences.borderColor }
                    Item { width: 1; height: Preferences.spacingSmall }
                    ActionButton {
                        objectName: "logThisWorkout"
                        primary: true
                        implicitHeight: 44
                        text: Words.logThisWorkout
                        onClicked: {
                            Workouts.startNew(root.nextUp.routineId)
                            Nav.navigateTo("log-page")
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

            // ---- Recent crowns ----
            Column {
                objectName: "crownsRow"
                width: parent.width
                spacing: Preferences.spacingSmall
                visible: root.hasToday && (root.today.crowns || []).length > 0
                Text {
                    text: Words.recentCrowns.toUpperCase()
                    color: Preferences.textMuted
                    font.family: Preferences.appFont
                    font.pixelSize: Preferences.fontSizeCaption
                    font.letterSpacing: 12 * 0.12
                }
                Flow {
                    width: parent.width
                    spacing: Preferences.spacingMedium
                    Repeater {
                        model: root.hasToday ? (root.today.crowns || []) : []
                        CrownCard {
                            required property var modelData
                            objectName: "crownCard"
                            name: root.exerciseOf(modelData).name || Words.unknownExercise
                            record: Log.recordText(modelData)
                            when: Words.crownWhen(modelData.performedOn, Programs.todayDate)
                        }
                    }
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
