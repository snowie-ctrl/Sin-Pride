import QtQuick
import QtQuick.Controls
import "../logic/words.mjs" as Words
import "../logic/forms.mjs" as Forms

// Programs (spec §6): the list on the left with the one you follow marked, and the open program on the right with its
// name, planned days and routines in rotation. Every change is the service's call; the page only words what it is told
// (Words.saveProblem) and never opens a program again by itself once the service has closed one.
Rectangle {
    id: root
    objectName: "programsPage"

    color: Preferences.backgroundPrimary

    readonly property var current: Programs.current
    readonly property bool hasCurrent: Programs.currentId > 0
    readonly property var routines: hasCurrent && current.routines !== undefined ? current.routines : []
    readonly property string weekStart: Profile.profile.weekStart === "sun" ? "sun" : "mon"
    readonly property var weekOrder: root.weekStart === "sun" ? [6, 0, 1, 2, 3, 4, 5] : [0, 1, 2, 3, 4, 5, 6]

    property string problem: ""
    property string notice: ""
    // Set while a write this page asked for is out, so only its answer clears the matching field.
    property bool creatingProgram: false
    property bool addingRoutine: false
    // The title last sent as a rename; Enter and then leaving the field both finish editing, and must send once.
    property string sentTitle: ""
    // True until the page has opened a program on its own, which it does once, when first shown.
    property bool autoOpen: true
    // The routine whose row gets the focus back after a move rebuilt the rows, so Alt+arrows can be pressed again.
    property int refocusId: 0

    readonly property int rowHeight: 56
    readonly property int rowStep: rowHeight + Preferences.spacingSmall
    // The drag of a grip: which row, how far the pointer has moved, and the place it would land in.
    property int dragFrom: -1
    property real dragDelta: 0
    property int dragTarget: -1

    function daysText(days) {
        return root.weekOrder.filter(d => days.indexOf(d) >= 0).map(Words.weekdayShort).join(", ")
    }

    function rowSubtitle(row) {
        const days = daysText(row.days || [])
        return Words.routineCount(row.routineCount) + (days.length > 0 ? " · " + days : "")
    }

    function tryAutoOpen() {
        if (!root.autoOpen)
            return
        if (root.hasCurrent) {
            root.autoOpen = false
            return
        }
        const list = Programs.programs
        if (list.length === 0)
            return
        root.autoOpen = false
        const active = list.find(p => p.active)
        Programs.open((active || list[0]).id)
    }

    function renameProgram(text) {
        if (!root.hasCurrent)
            return
        const title = text.trim()
        if (title === root.current.title || (root.sentTitle.length > 0 && title === root.sentTitle))
            return
        const bad = Forms.titleProblem(title)
        if (bad.length > 0) {
            root.problem = bad
            titleField.text = root.current.title
            return
        }
        root.problem = ""
        root.sentTitle = title
        Programs.rename(Programs.currentId, title)
    }

    function createProgram() {
        const bad = Forms.titleProblem(newProgramField.text)
        root.problem = bad
        if (bad.length > 0)
            return
        root.creatingProgram = true
        Programs.create(newProgramField.text.trim())
    }

    function createRoutine() {
        const bad = Forms.titleProblem(newRoutineField.text)
        root.problem = bad
        if (bad.length > 0)
            return
        root.addingRoutine = true
        Programs.addRoutine(Programs.currentId, newRoutineField.text.trim())
    }

    // Sends the whole new order, or nothing when the row stays where it was.
    function moveRoutine(from, to) {
        const ids = root.routines.map(r => r.id)
        const place = Math.max(0, Math.min(ids.length - 1, to))
        if (from < 0 || from >= ids.length || place === from)
            return
        root.refocusId = ids[from]
        ids.splice(place, 0, ids.splice(from, 1)[0])
        Programs.reorderRoutines(Programs.currentId, ids)
    }

    // A loss on another device may have been met in the editor, whose Back brought this page into being after the
    // signal was gone; the service keeps it until a page has said so.
    function takeGoneNotice() {
        if (Programs.goneNotice.length === 0)
            return
        root.notice = Words.goneElsewhere
        Programs.clearGoneNotice()
    }

    Component.onCompleted: {
        root.takeGoneNotice()
        Programs.loadList()
        root.tryAutoOpen()
    }

    Connections {
        target: Programs
        function onProgramsChanged() { root.tryAutoOpen() }
        function onGoneNoticeChanged() { root.takeGoneNotice() }
        function onSaved(what) {
            root.problem = ""
            root.notice = ""
            root.sentTitle = ""
            if (what === "program" && root.creatingProgram)
                newProgramField.text = ""
            if (what === "routine" && root.addingRoutine)
                newRoutineField.text = ""
            root.creatingProgram = false
            root.addingRoutine = false
        }
        function onFailed(what, code, field) {
            root.problem = Words.saveProblem(code, field)
            root.sentTitle = ""
            root.refocusId = 0
            root.creatingProgram = false
            root.addingRoutine = false
            if (root.hasCurrent)
                titleField.text = root.current.title
        }
        function onGone() {
            root.notice = Words.goneElsewhere
            root.problem = ""
            root.sentTitle = ""
            root.refocusId = 0
            root.creatingProgram = false
            root.addingRoutine = false
        }
    }

    ConfirmDialog {
        id: confirmProgram
        property int programId: 0
        yesText: Words.deleteWord
        onAccepted: Programs.remove(programId)
    }

    ConfirmDialog {
        id: confirmRoutine
        property int routineId: 0
        yesText: Words.deleteWord
        onAccepted: Programs.removeRoutine(routineId)
    }

    // ---- The list ----
    Rectangle {
        id: listPane
        anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
        width: 320
        color: Preferences.backgroundSecondary

        Flickable {
            id: listFlick
            anchors.fill: parent
            anchors.margins: Preferences.spacingLarge
            contentWidth: width
            contentHeight: listColumn.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds

            Column {
                id: listColumn
                width: listFlick.width
                spacing: Preferences.spacingSmall

                Text {
                    text: Words.programsTitle
                    color: Preferences.textPrimary
                    font.family: Preferences.headingFont
                    font.pixelSize: Preferences.fontSizeHeading
                    bottomPadding: Preferences.spacingSmall
                }

                Text {
                    objectName: "programsEmpty"
                    visible: Programs.programs.length === 0 && !Programs.listLoading
                    width: parent.width
                    text: Words.programsEmpty
                    wrapMode: Text.WordWrap
                    color: Preferences.textMuted
                    font.family: Preferences.appFont
                    font.pixelSize: Preferences.fontSizeBody
                }

                Repeater {
                    model: Programs.programs
                    Rectangle {
                        id: programRow
                        required property var modelData
                        readonly property bool open: Programs.currentId === modelData.id
                        objectName: "programRow"
                        width: listColumn.width
                        height: 60
                        radius: Preferences.controlRadius
                        color: programRow.open ? Preferences.accentSubtle
                                               : (rowMouse.containsMouse ? Preferences.backgroundTertiary : "transparent")

                        MouseArea {
                            id: rowMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: Programs.open(programRow.modelData.id)
                        }

                        Column {
                            anchors { left: parent.left; right: badge.left; leftMargin: 12; rightMargin: 8; verticalCenter: parent.verticalCenter }
                            spacing: 2
                            Text {
                                objectName: "programRowTitle"
                                width: parent.width
                                text: programRow.modelData.title
                                elide: Text.ElideRight
                                color: Preferences.textPrimary
                                font.family: Preferences.appFont
                                font.pixelSize: Preferences.fontSizeBody
                                font.weight: Font.DemiBold
                            }
                            Text {
                                width: parent.width
                                text: root.rowSubtitle(programRow.modelData)
                                elide: Text.ElideRight
                                color: Preferences.textMuted
                                font.family: Preferences.appFont
                                font.pixelSize: Preferences.fontSizeLabel
                            }
                        }

                        Rectangle {
                            id: badge
                            objectName: "programRowActive"
                            visible: programRow.modelData.active === true
                            anchors { right: parent.right; rightMargin: 12; verticalCenter: parent.verticalCenter }
                            width: visible ? badgeText.implicitWidth + 16 : 0
                            height: 22
                            radius: height / 2
                            color: Preferences.accentSubtle
                            Text {
                                id: badgeText
                                anchors.centerIn: parent
                                text: Words.activeBadge
                                color: Preferences.accentColor
                                font.family: Preferences.appFont
                                font.pixelSize: Preferences.fontSizeCaption
                            }
                        }
                    }
                }

                Item { width: 1; height: Preferences.spacingSmall }

                InputField {
                    id: newProgramField
                    objectName: "newProgramField"
                    placeholderText: Words.programName
                    maximumLength: 120
                    onAccepted: root.createProgram()
                }
                ActionButton {
                    objectName: "newProgramButton"
                    text: Words.newProgram
                    onClicked: root.createProgram()
                }
            }
        }
    }

    // ---- The open program ----
    Item {
        id: detail
        anchors { left: listPane.right; right: parent.right; top: parent.top; bottom: parent.bottom }

        // Notice and refusals sit above the program, so they show when there is none open.
        Column {
            id: messages
            x: Preferences.spacingLarge
            y: Preferences.spacingLarge
            width: Math.min(detail.width - 2 * Preferences.spacingLarge, 640)
            spacing: Preferences.spacingSmall

            Text {
                objectName: "programsNotice"
                visible: root.notice.length > 0
                width: parent.width
                text: root.notice
                wrapMode: Text.WordWrap
                color: Preferences.textSecondary
                font.family: Preferences.appFont
                font.pixelSize: Preferences.fontSizeBody
            }
            Problem { objectName: "programsError"; text: root.problem }
        }

        Flickable {
            id: flick
            visible: root.hasCurrent
            anchors { left: parent.left; right: parent.right; top: messages.bottom; bottom: parent.bottom }
            anchors.margins: Preferences.spacingLarge
            anchors.topMargin: Preferences.spacingMedium
            contentWidth: width
            contentHeight: body.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar {}

            Column {
                id: body
                width: Math.min(flick.width, 640)
                spacing: Preferences.spacingMedium

                InputField {
                    id: titleField
                    objectName: "programTitleField"
                    maximumLength: 120
                    onAccepted: root.renameProgram(text)
                    onEditingFinished: root.renameProgram(text)
                }
                // A Binding, not a `text:` binding: putting the saved title back by assignment (a refused rename)
                // would destroy a plain binding, and the field would then stop following the open program.
                Binding {
                    target: titleField
                    property: "text"
                    value: root.hasCurrent ? (root.current.title || "") : ""
                }

                Row {
                    spacing: Preferences.spacingSmall
                    ActionButton {
                        objectName: "programActivate"
                        visible: root.hasCurrent && root.current.active !== true
                        primary: true
                        text: Words.followThis
                        onClicked: Programs.activate(Programs.currentId)
                    }
                    ActionButton {
                        objectName: "programDuplicate"
                        text: Words.duplicate
                        onClicked: Programs.duplicate(Programs.currentId)
                    }
                    ActionButton {
                        objectName: "programDelete"
                        danger: true
                        text: Words.deleteWord
                        onClicked: {
                            confirmProgram.programId = Programs.currentId
                            confirmProgram.text = Words.deleteProgramQuestion(root.current.title)
                            confirmProgram.open()
                        }
                    }
                }

                Caption { width: parent.width; text: Words.plannedDays }
                DayChips {
                    days: root.hasCurrent && root.current.days !== undefined ? root.current.days : []
                    weekStart: root.weekStart
                    onChanged: days => Programs.setDays(Programs.currentId, days)
                }
                Caption { width: parent.width; muted: true; text: Words.plannedDaysHint }

                Caption { width: parent.width; text: Words.routinesTitle }

                Text {
                    objectName: "routinesEmpty"
                    visible: root.routines.length === 0
                    width: parent.width
                    text: Words.noRoutines
                    wrapMode: Text.WordWrap
                    color: Preferences.textMuted
                    font.family: Preferences.appFont
                    font.pixelSize: Preferences.fontSizeBody
                }

                Column {
                    id: routineList
                    width: parent.width
                    spacing: Preferences.spacingSmall

                    Repeater {
                        model: root.routines
                        Rectangle {
                            id: row
                            required property var modelData
                            required property int index
                            readonly property bool dragging: root.dragFrom === row.index
                            // While another row is dragged, the rows it passes make room for it.
                            readonly property real shift: {
                                if (root.dragFrom < 0 || row.dragging)
                                    return 0
                                if (root.dragFrom < row.index && row.index <= root.dragTarget)
                                    return -root.rowStep
                                if (root.dragTarget <= row.index && row.index < root.dragFrom)
                                    return root.rowStep
                                return 0
                            }
                            objectName: "routineRow"
                            width: routineList.width
                            height: root.rowHeight
                            z: dragging ? 10 : 0
                            radius: Preferences.controlRadius
                            color: Preferences.backgroundSecondary
                            border.width: 1
                            border.color: row.activeFocus || row.dragging ? Preferences.accentColor : Preferences.borderColor
                            activeFocusOnTab: true
                            transform: Translate { y: row.dragging ? root.dragDelta : row.shift }

                            Component.onCompleted: {
                                if (root.refocusId === row.modelData.id) {
                                    root.refocusId = 0
                                    row.forceActiveFocus()
                                }
                            }

                            Keys.onPressed: event => {
                                if (!(event.modifiers & Qt.AltModifier))
                                    return
                                if (event.key === Qt.Key_Up) {
                                    root.moveRoutine(row.index, row.index - 1)
                                    event.accepted = true
                                } else if (event.key === Qt.Key_Down) {
                                    root.moveRoutine(row.index, row.index + 1)
                                    event.accepted = true
                                }
                            }

                            // A click anywhere on the row gives it the focus, which Alt+Up and Alt+Down act on.
                            MouseArea {
                                anchors.fill: parent
                                onPressed: mouse => { row.forceActiveFocus(); mouse.accepted = true }
                            }

                            MouseArea {
                                id: grip
                                objectName: "routineGrip"
                                x: 8
                                anchors.verticalCenter: parent.verticalCenter
                                width: 32
                                height: 32
                                cursorShape: Qt.SizeVerCursor
                                preventStealing: true
                                property real startY: 0

                                function pointerY(mouse) { return grip.mapToItem(routineList, mouse.x, mouse.y).y }

                                onPressed: mouse => {
                                    row.forceActiveFocus()
                                    grip.startY = grip.pointerY(mouse)
                                    root.dragDelta = 0
                                    root.dragTarget = row.index
                                    root.dragFrom = row.index
                                }
                                onPositionChanged: mouse => {
                                    if (!grip.pressed)
                                        return
                                    root.dragDelta = grip.pointerY(mouse) - grip.startY
                                    // The row under the middle of the dragged one is where it would land.
                                    const middle = row.index * root.rowStep + root.rowHeight / 2 + root.dragDelta
                                    root.dragTarget = Math.max(0, Math.min(root.routines.length - 1,
                                                                           Math.floor(middle / root.rowStep)))
                                }
                                onReleased: {
                                    const from = root.dragFrom
                                    const to = root.dragTarget
                                    root.dragFrom = -1
                                    root.dragDelta = 0
                                    root.dragTarget = -1
                                    root.moveRoutine(from, to)
                                }
                                onCanceled: {
                                    root.dragFrom = -1
                                    root.dragDelta = 0
                                    root.dragTarget = -1
                                }

                                TintedIcon {
                                    anchors.centerIn: parent
                                    source: "qrc:/images/grip.svg"
                                    size: 20
                                    color: Preferences.textMuted
                                }
                            }

                            Column {
                                anchors { left: grip.right; leftMargin: 8; right: editButton.left; rightMargin: 8; verticalCenter: parent.verticalCenter }
                                spacing: 2
                                Text {
                                    objectName: "routineTitle"
                                    width: parent.width
                                    text: row.modelData.title
                                    elide: Text.ElideRight
                                    color: Preferences.textPrimary
                                    font.family: Preferences.appFont
                                    font.pixelSize: Preferences.fontSizeBody
                                    font.weight: Font.DemiBold
                                }
                                Text {
                                    width: parent.width
                                    text: Words.exerciseCount(row.modelData.items ? row.modelData.items.length : 0)
                                    color: Preferences.textMuted
                                    font.family: Preferences.appFont
                                    font.pixelSize: Preferences.fontSizeLabel
                                }
                            }

                            ActionButton {
                                id: editButton
                                objectName: "routineEdit"
                                anchors { right: deleteButton.left; rightMargin: Preferences.spacingSmall; verticalCenter: parent.verticalCenter }
                                text: Words.edit
                                onClicked: {
                                    Programs.openRoutine(row.modelData.id)
                                    Nav.navigateTo("routine-page")
                                }
                            }
                            ActionButton {
                                id: deleteButton
                                objectName: "routineDelete"
                                anchors { right: parent.right; rightMargin: Preferences.spacingSmall; verticalCenter: parent.verticalCenter }
                                danger: true
                                text: Words.deleteWord
                                onClicked: {
                                    confirmRoutine.routineId = row.modelData.id
                                    confirmRoutine.text = Words.deleteRoutineQuestion(row.modelData.title)
                                    confirmRoutine.open()
                                }
                            }
                        }
                    }
                }

                InputField {
                    id: newRoutineField
                    objectName: "newRoutineField"
                    placeholderText: Words.routineName
                    maximumLength: 120
                    onAccepted: root.createRoutine()
                }
                ActionButton {
                    objectName: "newRoutineButton"
                    text: Words.addRoutine
                    onClicked: root.createRoutine()
                }
            }
        }
    }
}
