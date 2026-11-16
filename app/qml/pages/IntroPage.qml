import QtQuick
import QtQuick.Controls
import "../logic/words.mjs" as Words

// The introduction (spec §6): a welcome, three questions (days a week, equipment, goal) and then a suggested starter
// to use, tweak or replace by building one's own. It is a top-level page like sign-in. Skip is on every step. Opened
// from Settings (a replay) it changes nothing: Skip returns to Settings, and only adopting a starter adds anything.
// Programs and Profile answer asynchronously for everyone, so `pending` names the one thing this page waits for and
// a `saved` or `failed` it did not ask for is ignored.
Rectangle {
    id: root
    objectName: "introPage"

    color: Preferences.backgroundPrimary

    Component.onCompleted: root.replay = Profile.profile.introState !== "pending"

    // 0 welcome, 1 days, 2 equipment, 3 goal, 4 the starter.
    property int step: 0
    // Fixed when the page is made: saving the answers is what turns a pending intro into a done one, so the profile
    // changes under this page and must not flip it into a replay half-way.
    // Assigned once, in Component.onCompleted: a live binding would flip as soon as the answers are saved.
    property bool replay: false
    property int days: Profile.profile.daysPerWeek || 3
    property string goal: Profile.profile.goal || "general"
    property string preset: ""
    property string chosenKey: ""
    // "answers", "adopt-use", "adopt-tweak", "build", "skip-list" (Skip waiting for the list), "skip" or "" for nothing.
    property string pending: ""
    property string problem: ""

    // The equipment words in the server's order (prideCatalog.EQUIPMENT), so a save's body equals what the server
    // would send back.
    readonly property var presetWords: ({
        gym: ["barbell", "dumbbell", "kettlebell", "machine", "cable", "bands", "bodyweight", "bench", "pull-up bar"],
        dumbbells: ["dumbbell", "bodyweight", "bench"],
        bodyweight: ["bands", "bodyweight"]
    })

    // The starter on show: the one picked from the others, else the server's suggestion, else the first.
    readonly property var starter: {
        const list = Programs.starters
        const picked = list.find(s => s.key === root.chosenKey)
        return picked || list.find(s => s.suggested) || list[0] || null
    }
    readonly property bool usable: root.starter !== null
                                   && root.starter.routines.some(r => r.items.length > 0)
    readonly property bool starterLoading: root.pending === "answers" || Programs.startersLoading
    readonly property bool busy: root.pending.length > 0

    function answers() {
        return { daysPerWeek: root.days, equipment: root.presetWords[root.preset], goal: root.goal }
    }

    function goTo(next) {
        root.problem = ""
        root.step = next
        if (next === 4) {
            root.chosenKey = ""
            root.pending = "answers"
            Profile.save(root.answers())
        }
    }

    // Leaves for another page once the intro is over, for good (not in a replay's skip, which saves nothing).
    function finish(page) {
        Profile.save({ introState: "done" })
        Nav.navigateTo(page)
    }

    function adopt(how) {
        root.problem = ""
        root.pending = how
        Programs.adopt(root.starter.key)
    }

    function buildOwn() {
        root.problem = ""
        root.pending = "build"
        Programs.create(Words.myProgram)
    }

    function skip() {
        if (root.replay) {
            Nav.navigateTo("settings-page")
            return
        }
        Profile.save({ introState: "skipped" })
        root.problem = ""
        // Whether the person has a program is known only from a list that answered. Without one (still loading,
        // failed, or never asked) the list is asked for first, so Skip never makes a spare "My program".
        if (Programs.listLoading || Programs.listError.length > 0 || Programs.programs.length === 0) {
            root.pending = "skip-list"
            Programs.loadList()
        } else {
            Nav.navigateTo("programs-page")
        }
    }

    // The list Skip waited for has answered: make the empty program only when it really came back empty.
    function listAnswered() {
        if (root.pending !== "skip-list" || Programs.listLoading)
            return
        if (Programs.listError.length > 0) {
            root.pending = ""
            root.problem = Words.failure(Programs.listError)
        } else if (Programs.programs.length === 0) {
            root.pending = "skip"
            Programs.create(Words.myProgram)
        } else {
            root.pending = ""
            Nav.navigateTo("programs-page")
        }
    }

    // What Programs.saved's `what` this page's pending is waiting for.
    function waitingFor() {
        if (root.pending === "adopt-use" || root.pending === "adopt-tweak")
            return "adopted"
        return root.pending === "build" || root.pending === "skip" ? "program" : ""
    }

    Connections {
        target: Programs
        function onProgramsChanged() { root.listAnswered() }
        function onSaved(what) {
            if (root.pending.length === 0 || what !== root.waitingFor())
                return
            const how = root.pending
            root.pending = ""
            if (how === "adopt-use") {
                root.finish("today-page")
            } else if (how === "adopt-tweak") {
                const routines = Programs.current.routines || []
                if (routines.length > 0)
                    Programs.openRoutine(routines[0].id)
                root.finish("routine-page")
            } else if (how === "build") {
                root.finish("programs-page")
            } else {
                Nav.navigateTo("programs-page")
            }
        }
        function onFailed(what, code, field) {
            if (root.pending.length === 0 || what !== root.waitingFor())
                return
            root.pending = ""
            root.problem = Words.saveProblem(code, field)
        }
    }

    Connections {
        target: Profile
        function onSaved() {
            if (root.pending !== "answers")
                return
            root.pending = ""
            Programs.loadStarters()
        }
        function onFailed(code, field) {
            if (root.pending !== "answers")
                return
            // The starters cannot be picked without the answers, so the last question comes back to try again.
            root.pending = ""
            root.step = 3
            root.problem = Words.saveProblem(code, field)
        }
    }

    Flickable {
        id: flick
        anchors.fill: parent
        contentWidth: width
        contentHeight: Math.max(height, card.height + 2 * Preferences.spacingLarge)
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar {}

        Rectangle {
            id: card
            width: 720
            height: column.implicitHeight + 2 * Preferences.spacingLarge
            x: (flick.width - width) / 2
            y: Math.max(Preferences.spacingLarge, (flick.height - height) / 2)
            radius: Preferences.cornerRadius
            color: Preferences.backgroundSecondary
            border.color: Preferences.borderColor

            Column {
                id: column
                x: Preferences.spacingLarge
                y: Preferences.spacingLarge
                width: card.width - 2 * Preferences.spacingLarge
                spacing: Preferences.spacingMedium

                Image {
                    anchors.horizontalCenter: parent.horizontalCenter
                    source: "qrc:/icons/prideAppIcon.png"
                    sourceSize: Qt.size(56, 56)
                }

                Text {
                    objectName: "introStep"
                    property int step: root.step
                    visible: root.step >= 1
                    height: visible ? implicitHeight : 0
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: Words.introStepOf(root.step)
                    color: Preferences.textMuted
                    font.family: Preferences.appFont
                    font.pixelSize: Preferences.fontSizeLabel
                }

                // The question this step asks.
                Text {
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    text: [Words.introWelcomeTitle, Words.introDaysTitle, Words.introEquipmentTitle,
                           Words.introGoalTitle, Words.introStarterHeading][root.step]
                    color: Preferences.textPrimary
                    font.family: Preferences.headingFont
                    font.pixelSize: Preferences.fontSizeDisplay
                }

                // ---- 0: welcome ----
                Text {
                    visible: root.step === 0
                    height: visible ? implicitHeight : 0
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    text: Words.introWelcomeBody
                    color: Preferences.textSecondary
                    font.family: Preferences.appFont
                    font.pixelSize: Preferences.fontSizeBody
                }

                // ---- 1: days ----
                Segmented {
                    visible: root.step === 1
                    height: visible ? implicitHeight : 0
                    anchors.horizontalCenter: parent.horizontalCenter
                    prefix: "introDays"
                    options: [2, 3, 4, 5, 6].map(d => ({ value: d, label: String(d) }))
                    current: root.days
                    onPicked: value => root.days = value
                }

                // ---- 2: equipment ----
                Segmented {
                    visible: root.step === 2
                    height: visible ? implicitHeight : 0
                    anchors.horizontalCenter: parent.horizontalCenter
                    prefix: "introPreset"
                    options: ["gym", "dumbbells", "bodyweight"].map(p => ({ value: p, label: Words.presetLabel(p) }))
                    current: root.preset
                    onPicked: value => root.preset = value
                }

                // ---- 3: goal, each with its hint ----
                Column {
                    visible: root.step === 3
                    height: visible ? implicitHeight : 0
                    anchors.horizontalCenter: parent.horizontalCenter
                    spacing: Preferences.spacingSmall
                    Repeater {
                        model: ["strength", "muscle", "general"]
                        Row {
                            spacing: Preferences.spacingMedium
                            Chip {
                                objectName: "introGoal-" + modelData
                                text: Words.goalLabel(modelData)
                                chosen: modelData === root.goal
                                onToggled: root.goal = modelData
                            }
                            Caption {
                                anchors.verticalCenter: parent.verticalCenter
                                text: Words.goalHint(modelData)
                                muted: true
                            }
                        }
                    }
                }

                // ---- 4: the starter ----
                Column {
                    visible: root.step === 4
                    height: visible ? implicitHeight : 0
                    width: parent.width
                    spacing: Preferences.spacingMedium

                    Caption {
                        objectName: "introStarterLoading"
                        visible: root.starterLoading
                        height: visible ? implicitHeight : 0
                        text: Words.introLoading
                    }

                    Column {
                        visible: !root.starterLoading && root.starter !== null
                        height: visible ? implicitHeight : 0
                        width: parent.width
                        spacing: Preferences.spacingMedium

                        Text {
                            objectName: "introStarterTitle"
                            width: parent.width
                            wrapMode: Text.WordWrap
                            text: root.starter ? root.starter.title : ""
                            color: Preferences.textPrimary
                            font.family: Preferences.headingFont
                            font.pixelSize: 34
                        }
                        Text {
                            width: parent.width
                            wrapMode: Text.WordWrap
                            text: root.starter ? root.starter.blurb : ""
                            color: Preferences.textSecondary
                            font.family: Preferences.appFont
                            font.pixelSize: Preferences.fontSizeBody
                        }
                        Caption {
                            width: parent.width
                            text: root.starter
                                  ? Words.starterVariant(root.starter.variant) + " · " + Words.introPlanned + " "
                                    + root.starter.days.map(d => Words.weekdayLong(d)).join(", ")
                                  : ""
                        }

                        Repeater {
                            model: root.starter ? root.starter.routines : []
                            Rectangle {
                                objectName: "introPreviewRoutine"
                                width: parent.width
                                height: preview.implicitHeight + 2 * Preferences.spacingMedium
                                radius: Preferences.controlRadius
                                color: Preferences.backgroundTertiary

                                Column {
                                    id: preview
                                    x: Preferences.spacingMedium
                                    y: Preferences.spacingMedium
                                    width: parent.width - 2 * Preferences.spacingMedium
                                    spacing: 4
                                    Text {
                                        width: parent.width
                                        text: modelData.title
                                        color: Preferences.textPrimary
                                        font.family: Preferences.appFont
                                        font.pixelSize: Preferences.fontSizeBody
                                        font.bold: true
                                    }
                                    Caption {
                                        width: parent.width
                                        text: modelData.items.map(i => i.name).join(" · ")
                                    }
                                }
                            }
                        }

                        // Notes, not refusals: nothing went wrong, the catalog just lacks some of the starter's exercises.
                        Caption {
                            objectName: "introMissing"
                            width: parent.width
                            visible: root.starter !== null && root.starter.missing.length > 0
                            height: visible ? implicitHeight : 0
                            text: Words.introMissing
                        }
                        Caption {
                            objectName: "introUnavailable"
                            width: parent.width
                            visible: !root.usable
                            height: visible ? implicitHeight : 0
                            text: Words.introUnavailable
                        }
                    }

                    // A starter list that could not load says so in words.
                    Problem {
                        text: Programs.startersError.length && !root.starterLoading ? Words.failure(Programs.startersError) : ""
                    }

                    Caption {
                        visible: Programs.starters.length > 1
                        height: visible ? implicitHeight : 0
                        text: Words.introOthers
                    }
                    Flow {
                        width: parent.width
                        spacing: Preferences.spacingSmall
                        Repeater {
                            model: Programs.starters.filter(s => !root.starter || s.key !== root.starter.key)
                            Chip {
                                objectName: "introStarter-" + modelData.key
                                text: modelData.title
                                onToggled: root.chosenKey = modelData.key
                            }
                        }
                    }

                    Row {
                        spacing: Preferences.spacingMedium
                        ActionButton {
                            objectName: "introUseThis"
                            primary: true
                            enabled: root.usable && !root.starterLoading && !root.busy
                            text: Words.introUseThis
                            onClicked: root.adopt("adopt-use")
                        }
                        ActionButton {
                            objectName: "introTweak"
                            enabled: root.usable && !root.starterLoading && !root.busy
                            text: Words.introTweak
                            onClicked: root.adopt("adopt-tweak")
                        }
                        ActionButton {
                            objectName: "introBuildOwn"
                            enabled: !root.starterLoading && !root.busy
                            text: Words.introBuildOwn
                            onClicked: root.buildOwn()
                        }
                    }
                }

                Problem { objectName: "introError"; text: root.problem }

                // Back (left) and Skip (right) are quiet; Next, beside Skip, is the step's one main action (the starter
                // step has its own).
                Item {
                    width: parent.width
                    height: 38

                    ActionButton {
                        objectName: "introBack"
                        anchors.left: parent.left
                        visible: root.step > 0
                        enabled: !root.busy
                        text: Words.introBack
                        onClicked: root.goTo(root.step - 1)
                    }
                    ActionButton {
                        id: introSkipButton
                        objectName: "introSkip"
                        anchors.right: parent.right
                        enabled: !root.busy
                        text: Words.introSkip
                        onClicked: root.skip()
                    }
                    ActionButton {
                        objectName: "introNext"
                        anchors.right: introSkipButton.left
                        anchors.rightMargin: Preferences.spacingSmall
                        visible: root.step < 4
                        primary: true
                        enabled: root.step !== 2 || root.preset.length > 0
                        text: Words.introNext
                        onClicked: root.goTo(root.step + 1)
                    }
                }
            }
        }
    }
}
