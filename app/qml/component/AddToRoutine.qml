import QtQuick
import QtQuick.Controls
import "../logic/words.mjs" as Words

// "Add to a routine…" from any shown exercise (plan decision 19): pick a program (the one followed first), then one of
// its routines, and the exercise is added there with the service's defaults.
Popup {
    id: root

    property int exerciseId: 0
    // The program whose routines are listed; 0 while the programs are.
    property int programId: 0
    property string doneText: ""
    property string problem: ""
    property bool pending: false
    property string chosenRoutineTitle: ""

    // The followed program first, the rest as the service lists them.
    readonly property var ordered: {
        const all = (Programs.programs || []).slice()
        return all.filter(p => p.active).concat(all.filter(p => !p.active))
    }
    readonly property var routines: root.programId > 0 && Programs.currentId === root.programId
                                    ? (Programs.current.routines || []) : []

    modal: true
    anchors.centerIn: Overlay.overlay
    width: 420
    padding: Preferences.spacingLarge
    background: Rectangle {
        radius: Preferences.cornerRadius
        color: Preferences.backgroundSecondary
        border.color: Preferences.borderColor
    }

    function chooseProgram(id) {
        root.problem = ""
        root.programId = id
        Programs.open(id)
    }

    function chooseRoutine(routine) {
        root.pending = true
        root.problem = ""
        root.chosenRoutineTitle = routine.title
        Programs.addItem(routine.id, root.exerciseId)
    }

    function openFor(id) {
        root.exerciseId = id
        root.programId = 0
        root.doneText = ""
        root.problem = ""
        root.pending = false
        Programs.loadList()
        root.open()
    }

    Timer {
        id: closer
        interval: 1400
        onTriggered: root.close()
    }
    onClosed: closer.stop()

    Connections {
        target: Programs
        // A program that can't be opened (offline, or gone elsewhere) sends the person back to the list, with why.
        function onGone(what) {
            if (what !== "program" || root.programId === 0)
                return
            root.programId = 0
            root.problem = Words.goneElsewhere
        }
        function onSaved(what) {
            if (what !== "item" || !root.pending)
                return
            root.pending = false
            root.problem = ""
            root.doneText = Words.addedTo(root.chosenRoutineTitle)
            closer.restart()
        }
        function onFailed(what, code, field) {
            if (what === "program" && root.programId > 0) {
                root.programId = 0
                root.problem = Words.saveProblem(code, field)
                return
            }
            if (what !== "item" || !root.pending)
                return
            root.pending = false
            root.problem = Words.saveProblem(code, field)
        }
    }

    // The name sits on the content, not on the Popup, so the page tests (which walk the item tree) can find it.
    Column {
        objectName: "addToRoutinePopup"
        width: parent.width
        spacing: Preferences.spacingSmall

        Text {
            width: parent.width
            text: Words.addToRoutineTitle
            wrapMode: Text.Wrap
            color: Preferences.textPrimary
            font.family: Preferences.headingFont
            font.pixelSize: Preferences.fontSizeHeading
        }

        Text {
            objectName: "addToRoutineNoPrograms"
            width: parent.width
            visible: root.ordered.length === 0 && !Programs.listLoading && Programs.listError.length === 0
            text: Words.noProgramsForAdd
            wrapMode: Text.Wrap
            color: Preferences.textMuted
            font.family: Preferences.appFont
            font.pixelSize: Preferences.fontSizeBody
        }
        // A list that could not load is not an empty one: say so rather than send the person to make a program.
        Text {
            objectName: "addToRoutineListError"
            width: parent.width
            visible: root.ordered.length === 0 && !Programs.listLoading && Programs.listError.length > 0
            text: Programs.listError.length > 0 ? Words.failure(Programs.listError) : ""
            wrapMode: Text.Wrap
            color: Preferences.dangerColor
            font.family: Preferences.appFont
            font.pixelSize: Preferences.fontSizeBody
        }
        ActionButton {
            objectName: "addToRoutineOpenPrograms"
            visible: root.ordered.length === 0 && !Programs.listLoading && Programs.listError.length === 0
            text: Words.openPrograms
            onClicked: { root.close(); Nav.navigateTo("programs-page") }
        }

        // The programs, until one is chosen.
        Repeater {
            model: root.programId === 0 ? root.ordered : []
            delegate: Rectangle {
                required property var modelData
                objectName: "addProgramRow"
                width: root.availableWidth
                height: 40
                radius: Preferences.controlRadius
                color: rowMouse.containsMouse ? Preferences.backgroundTertiary : "transparent"
                border.color: Preferences.borderColor
                Text {
                    anchors { left: parent.left; leftMargin: Preferences.spacingMedium; verticalCenter: parent.verticalCenter }
                    text: parent.modelData.title + (parent.modelData.active ? "  ·  " + Words.activeBadge : "")
                    color: Preferences.textPrimary
                    font.family: Preferences.appFont
                    font.pixelSize: Preferences.fontSizeBody
                }
                MouseArea {
                    id: rowMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.chooseProgram(parent.modelData.id)
                }
            }
        }

        // The chosen program's routines.
        Repeater {
            model: root.routines
            delegate: Rectangle {
                required property var modelData
                objectName: "addRoutineRow"
                width: root.availableWidth
                height: 40
                radius: Preferences.controlRadius
                color: routineMouse.containsMouse ? Preferences.backgroundTertiary : "transparent"
                border.color: Preferences.borderColor
                Text {
                    anchors { left: parent.left; leftMargin: Preferences.spacingMedium; verticalCenter: parent.verticalCenter }
                    text: parent.modelData.title
                    color: Preferences.textPrimary
                    font.family: Preferences.appFont
                    font.pixelSize: Preferences.fontSizeBody
                }
                MouseArea {
                    id: routineMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    enabled: !root.pending && root.doneText.length === 0
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.chooseRoutine(parent.modelData)
                }
            }
        }

        Text {
            objectName: "addToRoutineNoRoutines"
            width: parent.width
            visible: root.programId > 0 && root.routines.length === 0 && Programs.currentId === root.programId
            text: Words.noRoutines
            wrapMode: Text.Wrap
            color: Preferences.textMuted
            font.family: Preferences.appFont
            font.pixelSize: Preferences.fontSizeBody
        }

        Text {
            objectName: "addToRoutineDone"
            width: parent.width
            visible: root.doneText.length > 0
            text: root.doneText
            wrapMode: Text.Wrap
            color: Preferences.accentColor
            font.family: Preferences.appFont
            font.pixelSize: Preferences.fontSizeBody
            MouseArea { anchors.fill: parent; onClicked: root.close() }
        }

        Problem { objectName: "addToRoutineError"; text: root.problem }

        ActionButton {
            anchors.right: parent.right
            text: root.doneText.length > 0 ? Words.back : Words.cancel
            onClicked: root.close()
        }
    }
}
