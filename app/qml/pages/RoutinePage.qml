import QtQuick
import QtQuick.Controls
import "../logic/words.mjs" as Words
import "../logic/forms.mjs" as Forms
import "../logic/units.mjs" as Units

// The Routine editor (spec §6): the routine's name and each exercise's targets for the way it is measured. A row saves
// when a field is finished (Enter or leaving it): the whole row is checked with forms.mjs first, a refusal is worded
// under the row and nothing is sent, and the fields keep what was typed, because rows are rebuilt only when the
// service brings a new program, which a refusal never does.
Rectangle {
    id: root
    objectName: "routinePage"

    color: Preferences.backgroundPrimary

    // Every target the server's full replace takes (server/prideChecks.py itemTargets).
    readonly property var targetFields: ["sets", "repsMin", "repsMax", "targetWeight", "targetUnit", "targetSeconds",
                                         "targetDistance", "distanceUnit", "restSeconds", "note"]

    readonly property bool hasRoutine: Programs.currentRoutineId > 0
    readonly property var routine: Programs.currentRoutine
    readonly property var items: hasRoutine && routine.items !== undefined ? routine.items : []
    readonly property string programTitle: Programs.current.title !== undefined ? Programs.current.title : ""

    property string problem: ""
    // The routine's title last sent as a rename; Enter and then leaving the field both finish editing, and must send once.
    property string sentTitle: ""
    // The item a row last sent, so a refusal is worded under that row and under no other.
    property int editingItem: 0
    // The item whose row gets the focus back after a move rebuilt the rows, so Alt+arrows can be pressed again.
    property int refocusId: 0
    // The drag of a grip: which row, how far the pointer has moved, the place it would land in, and the room it needs.
    property int dragFrom: -1
    property real dragDelta: 0
    property int dragTarget: -1
    property real dragStep: 0

    // The catalog can arrive after the page does, and an own exercise can change, so the lookup reads their revisions.
    function exerciseOf(item) {
        return ExerciseStore.revision >= 0 && Catalog.own !== undefined ? Catalog.exercise(item.exerciseId) : ({})
    }

    function renameRoutine(text) {
        if (!root.hasRoutine)
            return
        const title = text.trim()
        if (title === root.routine.title || (root.sentTitle.length > 0 && title === root.sentTitle))
            return
        const bad = Forms.titleProblem(title)
        if (bad.length > 0) {
            root.problem = bad
            nameField.text = root.routine.title
            return
        }
        root.problem = ""
        root.sentTitle = title
        Programs.renameRoutine(Programs.currentRoutineId, title)
    }

    // Sends the whole new order, or nothing when the row stays where it was.
    function moveItem(from, to) {
        const ids = root.items.map(i => i.id)
        const place = Math.max(0, Math.min(ids.length - 1, to))
        if (from < 0 || from >= ids.length || place === from)
            return
        root.refocusId = ids[from]
        ids.splice(place, 0, ids.splice(from, 1)[0])
        Programs.reorderItems(Programs.currentRoutineId, ids)
    }

    function endDrag() {
        root.dragFrom = -1
        root.dragDelta = 0
        root.dragTarget = -1
    }

    // The row under the pointer is where the dragged one would land (rows differ in height when one shows a refusal).
    function rowAt(y) {
        let found = root.items.length - 1
        for (let i = 0; i < root.items.length; ++i) {
            const r = itemRepeater.itemAt(i)
            if (r && y < r.y + r.height) {
                found = i
                break
            }
        }
        return Math.max(0, found)
    }

    Connections {
        target: Programs
        function onSaved(what) {
            root.problem = ""
            root.sentTitle = ""
            root.editingItem = 0
        }
        function onFailed(what, code, field) {
            root.sentTitle = ""
            root.refocusId = 0
            // A refused row save is worded under its row; the rest, here. The rows' own handlers run in the same
            // emission, so the marker is cleared only after them.
            if (!(what === "item" && root.editingItem > 0))
                root.problem = Words.saveProblem(code, field)
            if (root.hasRoutine)
                nameField.text = root.routine.title
            Qt.callLater(() => { root.editingItem = 0 })
        }
        function onGone() {
            root.editingItem = 0
            root.refocusId = 0
            Nav.navigateTo("programs-page")
        }
    }

    ExercisePicker {
        id: picker
        onChosen: id => Programs.addItem(Programs.currentRoutineId, id)
    }

    // ---- Header ----
    Item {
        id: header
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: Preferences.spacingLarge }
        height: backButton.height

        ActionButton {
            id: backButton
            objectName: "routineBack"
            text: Words.backTo(root.programTitle)
            onClicked: Nav.navigateTo("programs-page")
        }
    }

    // ---- No routine open (after a reload) ----
    Column {
        anchors { left: parent.left; top: header.bottom; margins: Preferences.spacingLarge }
        visible: !root.hasRoutine
        spacing: Preferences.spacingMedium
        Text {
            objectName: "routineMissing"
            text: Words.routineMissing
            color: Preferences.textSecondary
            font.family: Preferences.appFont
            font.pixelSize: Preferences.fontSizeBody
        }
        ActionButton {
            objectName: "routineMissingBack"
            text: Words.backToPrograms
            onClicked: Nav.navigateTo("programs-page")
        }
    }

    Flickable {
        id: flick
        visible: root.hasRoutine
        anchors { left: parent.left; right: parent.right; top: header.bottom; bottom: parent.bottom; margins: Preferences.spacingLarge }
        anchors.topMargin: Preferences.spacingMedium
        contentWidth: width
        contentHeight: body.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar {}

        Column {
            id: body
            width: Math.min(flick.width, 880)
            spacing: Preferences.spacingMedium

            InputField {
                id: nameField
                objectName: "routineNameField"
                maximumLength: 120
                onAccepted: root.renameRoutine(text)
                onEditingFinished: root.renameRoutine(text)
            }
            // A Binding, not a `text:` binding: putting the saved title back by assignment (a refused rename) would
            // destroy a plain binding, and the field would then stop following the open routine.
            Binding {
                target: nameField
                property: "text"
                value: root.hasRoutine ? (root.routine.title || "") : ""
            }
            Text {
                objectName: "routineProgram"
                width: parent.width
                text: root.programTitle
                elide: Text.ElideRight
                color: Preferences.textMuted
                font.family: Preferences.appFont
                font.pixelSize: Preferences.fontSizeLabel
            }

            Problem { objectName: "routineError"; text: root.problem }

            Column {
                id: itemList
                width: parent.width
                spacing: Preferences.spacingSmall

                Repeater {
                    id: itemRepeater
                    model: root.items

                    Rectangle {
                        id: row
                        required property var modelData
                        required property int index

                        readonly property var exercise: root.exerciseOf(modelData)
                        readonly property bool known: exercise.id !== undefined
                        readonly property bool gone: !known || exercise.removed === true
                        readonly property string measure: known ? exercise.measure : ""
                        readonly property bool hasReps: measure === "weight_reps" || measure === "reps"
                        // The units a row starts from: its own, else the person's. Picking one assigns it; nothing
                        // else depends on the initial binding, which the assignment may therefore end.
                        property string weightUnit: modelData.targetUnit || (Profile.profile.units === "kg" ? "kg" : "lb")
                        property string distUnit: modelData.distanceUnit || (Profile.profile.units === "kg" ? "km" : "mi")
                        property string error: ""
                        // The targets last sent (as JSON), so Enter and then leaving a field send once.
                        property string sent: ""
                        readonly property bool dragging: root.dragFrom === row.index
                        // While another row is dragged, the rows it passes make room for it.
                        readonly property real shift: {
                            if (root.dragFrom < 0 || row.dragging)
                                return 0
                            if (root.dragFrom < row.index && row.index <= root.dragTarget)
                                return -root.dragStep
                            if (root.dragTarget <= row.index && row.index < root.dragFrom)
                                return root.dragStep
                            return 0
                        }

                        function number(value) { return value === null || value === undefined ? "" : Units.number(value) }
                        function seconds(value) { return value === null || value === undefined ? "" : Units.duration(value) }
                        function optional(text, parse) { return text.trim().length === 0 ? null : parse(text) }

                        // Reads every field of the row, checks it, and sends it when it differs from what is saved.
                        // A field that does not parse becomes NaN, which Forms.itemProblem refuses in words.
                        function commit() {
                            if (!row.known)
                                return
                            const targets = { sets: Forms.parseNumber(setsField.text), repsMin: null, repsMax: null,
                                              targetWeight: null, targetUnit: null, targetSeconds: null,
                                              targetDistance: null, distanceUnit: null,
                                              restSeconds: row.optional(restField.text, Units.parseDuration),
                                              note: noteField.text.length > 0 ? noteField.text : null }
                            if (row.hasReps) {
                                targets.repsMin = Forms.parseNumber(repsMinField.text)
                                targets.repsMax = Forms.parseNumber(repsMaxField.text)
                                targets.targetWeight = row.optional(weightField.text, Forms.parseNumber)
                                targets.targetUnit = targets.targetWeight === null ? null : row.weightUnit
                            } else if (row.measure === "time") {
                                targets.targetSeconds = Units.parseDuration(secondsField.text)
                            } else {
                                targets.targetDistance = row.optional(distanceField.text, Forms.parseNumber)
                                targets.distanceUnit = targets.targetDistance === null ? null : row.distUnit
                                targets.targetSeconds = row.optional(distanceSecondsField.text, Units.parseDuration)
                            }
                            const bad = Forms.itemProblem(row.measure, targets)
                            if (bad.field.length > 0) {
                                row.error = bad.words
                                return
                            }
                            row.error = ""
                            const changed = root.targetFields.some(k => targets[k] !== (row.modelData[k] === undefined ? null : row.modelData[k]))
                            const json = JSON.stringify(targets)
                            if (!changed || json === row.sent)
                                return
                            row.sent = json
                            root.editingItem = row.modelData.id
                            Programs.updateItem(row.modelData.id, targets)
                        }

                        objectName: "itemRow"
                        width: itemList.width
                        height: rowBody.implicitHeight + 2 * Preferences.spacingSmall + 4
                        z: dragging ? 10 : 0
                        radius: Preferences.controlRadius
                        color: Preferences.backgroundSecondary
                        border.width: 1
                        border.color: row.activeFocus || row.dragging ? Preferences.accentColor : Preferences.borderColor
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
                                root.moveItem(row.index, row.index - 1)
                                event.accepted = true
                            } else if (event.key === Qt.Key_Down) {
                                root.moveItem(row.index, row.index + 1)
                                event.accepted = true
                            }
                        }

                        Connections {
                            target: Programs
                            function onFailed(what, code, field) {
                                if (what === "item" && root.editingItem === row.modelData.id) {
                                    row.sent = ""
                                    row.error = Words.saveProblem(code, field)
                                }
                            }
                        }

                        // A click anywhere on the row gives it the focus, which Alt+Up and Alt+Down act on.
                        MouseArea {
                            anchors.fill: parent
                            onPressed: mouse => { row.forceActiveFocus(); mouse.accepted = true }
                        }

                        MouseArea {
                            id: grip
                            objectName: "itemGrip"
                            x: 8
                            y: 12
                            width: 32
                            height: 32
                            cursorShape: Qt.SizeVerCursor
                            preventStealing: true
                            property real startY: 0

                            function pointerY(mouse) { return grip.mapToItem(itemList, mouse.x, mouse.y).y }

                            onPressed: mouse => {
                                row.forceActiveFocus()
                                grip.startY = grip.pointerY(mouse)
                                root.dragStep = row.height + itemList.spacing
                                root.dragDelta = 0
                                root.dragTarget = row.index
                                root.dragFrom = row.index
                            }
                            onPositionChanged: mouse => {
                                if (!grip.pressed)
                                    return
                                root.dragDelta = grip.pointerY(mouse) - grip.startY
                                // Rows keep their layout places while dragged, so the dragged row's middle finds its place.
                                root.dragTarget = root.rowAt(row.y + row.height / 2 + root.dragDelta)
                            }
                            onReleased: {
                                const from = root.dragFrom
                                const to = root.dragTarget
                                root.endDrag()
                                root.moveItem(from, to)
                            }
                            onCanceled: root.endDrag()

                            TintedIcon {
                                anchors.centerIn: parent
                                source: "qrc:/images/grip.svg"
                                size: 20
                                color: Preferences.textMuted
                            }
                        }

                        Column {
                            id: rowBody
                            anchors { left: grip.right; leftMargin: 8; right: parent.right; rightMargin: Preferences.spacingSmall
                                      top: parent.top; topMargin: Preferences.spacingSmall + 2 }
                            spacing: Preferences.spacingSmall

                            Item {
                                width: parent.width
                                height: 48

                                PictureFrame {
                                    id: pic
                                    width: 48
                                    height: 48
                                    name: row.exercise.pictures && row.exercise.pictures.length > 0 ? row.exercise.pictures[0] : ""
                                }
                                Column {
                                    anchors { left: pic.right; leftMargin: Preferences.spacingSmall; right: removeButton.left
                                              rightMargin: Preferences.spacingSmall; verticalCenter: parent.verticalCenter }
                                    spacing: 2
                                    Text {
                                        objectName: "itemName"
                                        width: parent.width
                                        text: row.exercise.name || Words.unknownExercise
                                        elide: Text.ElideRight
                                        color: Preferences.textPrimary
                                        font.family: Preferences.appFont
                                        font.pixelSize: Preferences.fontSizeBody
                                        font.weight: Font.DemiBold
                                    }
                                    Text {
                                        visible: row.known
                                        width: parent.width
                                        text: row.known ? Words.valueLabel("measure", row.measure) : ""
                                        elide: Text.ElideRight
                                        color: Preferences.textMuted
                                        font.family: Preferences.appFont
                                        font.pixelSize: Preferences.fontSizeCaption
                                    }
                                    Text {
                                        objectName: "itemGone"
                                        visible: row.gone
                                        text: Words.leftCatalog
                                        color: Preferences.textMuted
                                        font.family: Preferences.appFont
                                        font.pixelSize: Preferences.fontSizeCaption
                                    }
                                }
                                ActionButton {
                                    id: removeButton
                                    objectName: "itemDelete"
                                    anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                                    danger: true
                                    text: Words.remove
                                    onClicked: Programs.removeItem(row.modelData.id)
                                }
                            }

                            Flow {
                                visible: row.known
                                width: parent.width
                                spacing: Preferences.spacingSmall + 4

                                Labeled {
                                    label: Words.setsLabel
                                    NumberField {
                                        id: setsField
                                        objectName: "itemSets"
                                        text: row.number(row.modelData.sets)
                                        onEditingFinished: row.commit()
                                    }
                                }
                                Labeled {
                                    visible: row.hasReps
                                    label: Words.repsLabel
                                    Row {
                                        spacing: 6
                                        NumberField {
                                            id: repsMinField
                                            objectName: "itemRepsMin"
                                            text: row.number(row.modelData.repsMin)
                                            onEditingFinished: row.commit()
                                        }
                                        Text {
                                            anchors.verticalCenter: parent.verticalCenter
                                            text: "–"
                                            color: Preferences.textMuted
                                            font.family: Preferences.appFont
                                            font.pixelSize: Preferences.fontSizeBody
                                        }
                                        NumberField {
                                            id: repsMaxField
                                            objectName: "itemRepsMax"
                                            text: row.number(row.modelData.repsMax)
                                            onEditingFinished: row.commit()
                                        }
                                    }
                                }
                                Labeled {
                                    visible: row.hasReps
                                    label: Words.weightLabel
                                    Row {
                                        spacing: 8
                                        NumberField {
                                            id: weightField
                                            objectName: "itemWeight"
                                            text: row.number(row.modelData.targetWeight)
                                            onEditingFinished: row.commit()
                                        }
                                        Segmented {
                                            anchors.verticalCenter: parent.verticalCenter
                                            prefix: "itemUnit"
                                            options: [{ value: "lb", label: "lb" }, { value: "kg", label: "kg" }]
                                            current: row.weightUnit
                                            onPicked: value => { row.weightUnit = value; row.commit() }
                                        }
                                    }
                                }
                                Labeled {
                                    visible: row.measure === "time"
                                    label: Words.timeLabel
                                    NumberField {
                                        id: secondsField
                                        objectName: "itemSeconds"
                                        text: row.seconds(row.modelData.targetSeconds)
                                        onEditingFinished: row.commit()
                                    }
                                }
                                Labeled {
                                    visible: row.measure === "distance_time"
                                    label: Words.distanceLabel
                                    Row {
                                        spacing: 8
                                        NumberField {
                                            id: distanceField
                                            objectName: "itemDistance"
                                            text: row.number(row.modelData.targetDistance)
                                            onEditingFinished: row.commit()
                                        }
                                        Segmented {
                                            anchors.verticalCenter: parent.verticalCenter
                                            prefix: "itemDistanceUnit"
                                            options: [{ value: "km", label: "km" }, { value: "mi", label: "mi" }, { value: "m", label: "m" }]
                                            current: row.distUnit
                                            onPicked: value => { row.distUnit = value; row.commit() }
                                        }
                                    }
                                }
                                // A time row's seconds are its target (above); a distance + time row's are optional.
                                Labeled {
                                    visible: row.measure === "distance_time"
                                    label: Words.timeLabel
                                    NumberField {
                                        id: distanceSecondsField
                                        objectName: "itemDistanceSeconds"
                                        text: row.seconds(row.modelData.targetSeconds)
                                        onEditingFinished: row.commit()
                                    }
                                }
                                Labeled {
                                    label: Words.restLabel
                                    NumberField {
                                        id: restField
                                        objectName: "itemRest"
                                        text: row.seconds(row.modelData.restSeconds)
                                        onEditingFinished: row.commit()
                                    }
                                }
                                Labeled {
                                    label: Words.noteLabel
                                    InputField {
                                        id: noteField
                                        objectName: "itemNote"
                                        width: 280
                                        maximumLength: 1100
                                        text: row.modelData.note || ""
                                        onEditingFinished: row.commit()
                                    }
                                }
                            }

                            Problem { objectName: "itemError"; text: row.error }
                        }
                    }
                }
            }

            ActionButton {
                objectName: "addExercise"
                primary: true
                text: Words.addExercise
                onClicked: picker.open()
            }
        }
    }

    component Labeled: Column {
        id: labeled
        property string label: ""
        spacing: 4
        Text {
            text: labeled.label
            color: Preferences.textMuted
            font.family: Preferences.appFont
            font.pixelSize: Preferences.fontSizeCaption
        }
    }
}
