import QtQuick
import QtQuick.Controls
import "../logic/words.mjs" as Words
import "../logic/forms.mjs" as Forms

// Add or edit one of the person's own exercises (spec §6; plan decisions 3 and 19). The words are the catalog's, in
// the order the filter panel shows them. A refusal, before sending or from the server, leaves every field as it was.
Popup {
    id: root

    // The muscle and equipment words in Catalog's order (server/prideCatalog.py holds the same words).
    readonly property var muscleWords: ["abdominals", "abductors", "adductors", "biceps", "calves", "chest", "forearms",
                                        "glutes", "hamstrings", "lats", "lower back", "middle back", "neck",
                                        "quadriceps", "shoulders", "traps", "triceps"]
    readonly property var equipmentWords: ["bodyweight", "dumbbell", "barbell", "kettlebell", "bands", "cable",
                                           "machine", "bench", "pull-up bar", "other"]
    readonly property var measureOptions: ["weight_reps", "reps", "time", "distance_time"].map(
        m => ({ value: m, label: Words.valueLabel("measure", m) }))

    // 0 while adding a new one.
    property int editingId: 0
    property string measure: ""
    property var primary: []
    property var secondary: []
    property var equipment: []
    property bool saving: false
    // What the last save attempt was refused for; declared, as every Problem on a page is, so its height settles.
    property string problem: ""
    // A page listens to follow a new exercise to its own page.
    signal created(int id)

    modal: true
    anchors.centerIn: Overlay.overlay
    width: 560
    height: Math.min(680, Overlay.overlay ? Overlay.overlay.height - 2 * Preferences.spacingLarge : 680)
    padding: Preferences.spacingLarge
    background: Rectangle {
        radius: Preferences.cornerRadius
        color: Preferences.backgroundSecondary
        border.color: Preferences.borderColor
    }

    // Empty, to add a new one.
    function openNew() {
        root.fill(undefined)
        root.open()
    }

    // Starting from an exercise's own values, to change it.
    function openFor(exercise) {
        root.fill(exercise)
        root.open()
    }

    function fill(exercise) {
        const e = exercise || {}
        root.editingId = e.id || 0
        nameField.text = e.name || ""
        root.measure = e.measure || ""
        root.primary = (e.primary || []).slice()
        root.secondary = (e.secondary || []).slice()
        root.equipment = (e.equipment || []).slice()
        stepsArea.text = (e.steps || []).join("\n")
        root.problem = ""
        root.saving = false
    }

    // A word on or off in a list, kept in the catalog's order.
    function flipped(list, all, word) {
        const on = list.indexOf(word) >= 0
        return all.filter(w => w === word ? !on : list.indexOf(w) >= 0)
    }

    function save() {
        const steps = stepsArea.text.split("\n").map(s => s.trim()).filter(s => s.length > 0)
        const exercise = { name: nameField.text.trim(), measure: root.measure, primary: root.primary,
                           secondary: root.secondary, equipment: root.equipment, steps: steps }
        const found = Forms.ownExerciseProblem(exercise)
        if (found.words.length > 0) {
            root.problem = found.words
            return
        }
        root.problem = ""
        root.saving = true
        if (root.editingId > 0)
            exercise.id = root.editingId
        Catalog.saveOwn(exercise)
    }

    Connections {
        target: Catalog
        function onOwnSaved(id) {
            if (!root.saving)
                return
            root.saving = false
            const wasNew = root.editingId === 0
            root.close()
            if (wasNew)
                root.created(id)
        }
        function onOwnFailed(code, field) {
            if (!root.saving)
                return
            root.saving = false
            root.problem = Words.saveProblem(code, field)
        }
    }

    // The name sits on the content, not on the Popup, so the page tests (which walk the item tree) can find it.
    Flickable {
        objectName: "ownForm"
        anchors { left: parent.left; right: parent.right; top: parent.top; bottom: footer.top
                  bottomMargin: Preferences.spacingSmall }
        contentHeight: column.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar {}

        Column {
            id: column
            width: parent.width - Preferences.spacingMedium
            spacing: Preferences.spacingSmall

            Text {
                text: root.editingId > 0 ? Words.ownEditTitle : Words.ownFormTitle
                color: Preferences.textPrimary
                font.family: Preferences.headingFont
                font.pixelSize: Preferences.fontSizeHeading
            }

            Caption { width: parent.width; text: Words.ownName }
            InputField { id: nameField; objectName: "ownName" }

            Caption { width: parent.width; text: Words.ownMeasure }
            Segmented {
                prefix: "ownMeasure"
                options: root.measureOptions
                current: root.measure
                onPicked: value => root.measure = value
            }

            Caption { width: parent.width; text: Words.ownPrimary }
            Flow {
                width: parent.width
                spacing: 6
                Repeater {
                    model: root.muscleWords
                    delegate: Chip {
                        required property string modelData
                        objectName: "ownPrimary-" + modelData
                        text: Words.valueLabel("muscle", modelData)
                        chosen: root.primary.indexOf(modelData) >= 0
                        onToggled: root.primary = root.flipped(root.primary, root.muscleWords, modelData)
                    }
                }
            }

            Caption { width: parent.width; text: Words.ownSecondary }
            Flow {
                width: parent.width
                spacing: 6
                Repeater {
                    model: root.muscleWords
                    delegate: Chip {
                        required property string modelData
                        objectName: "ownSecondary-" + modelData
                        text: Words.valueLabel("muscle", modelData)
                        chosen: root.secondary.indexOf(modelData) >= 0
                        onToggled: root.secondary = root.flipped(root.secondary, root.muscleWords, modelData)
                    }
                }
            }

            Caption { width: parent.width; text: Words.ownEquipment }
            Flow {
                width: parent.width
                spacing: 6
                Repeater {
                    model: root.equipmentWords
                    delegate: Chip {
                        required property string modelData
                        objectName: "ownEquipment-" + modelData
                        text: Words.valueLabel("equipment", modelData)
                        chosen: root.equipment.indexOf(modelData) >= 0
                        onToggled: root.equipment = root.flipped(root.equipment, root.equipmentWords, modelData)
                    }
                }
            }

            Caption { width: parent.width; text: Words.ownSteps }
            Rectangle {
                width: parent.width
                height: 110
                radius: Preferences.controlRadius
                color: Preferences.backgroundTertiary
                border.width: stepsArea.activeFocus ? 1 : 0
                border.color: Preferences.accentColor
                TextArea {
                    id: stepsArea
                    objectName: "ownSteps"
                    anchors.fill: parent
                    wrapMode: TextArea.Wrap
                    color: Preferences.textPrimary
                    selectByMouse: true
                    font.family: Preferences.appFont
                    font.pixelSize: Preferences.fontSizeBody
                    background: null
                }
            }
        }
    }

    // Outside the scrolling form, so the refusal and Save and Cancel are always in view, however long the form is.
    Column {
        id: footer
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        spacing: Preferences.spacingSmall

        // Not a Problem: its height binding loops when it grows inside a column of this popup, and a Column skips
        // an invisible child anyway, so visibility alone is enough here.
        Text {
            objectName: "ownError"
            width: parent.width
            visible: text.length > 0
            text: root.problem
            wrapMode: Text.WordWrap
            color: Preferences.dangerColor
            font.family: Preferences.appFont
            font.pixelSize: Preferences.fontSizeLabel
        }

        Row {
            anchors.right: parent.right
            spacing: Preferences.spacingSmall
            ActionButton { objectName: "ownCancel"; text: Words.cancel; onClicked: root.close() }
            ActionButton {
                objectName: "ownSave"
                primary: true
                enabled: !root.saving
                text: Words.save
                onClicked: root.save()
            }
        }
    }
}
