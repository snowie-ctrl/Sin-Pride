import QtQuick
import QtQuick.Controls
import "../logic/words.mjs" as Words
import "../logic/forms.mjs" as Forms

// Settings (spec §6): the account and the devices that sign in by themselves, the training profile (each pick saves
// at once), the introduction's replay, and the look. Every word of a refusal comes from Words.saveProblem, so the
// page never words an error itself.
Rectangle {
    id: root
    objectName: "settingsPage"

    color: Preferences.backgroundPrimary

    // The equipment words in the server's order (prideCatalog.EQUIPMENT): a save sends the whole list in this order.
    readonly property var equipmentWords: ["barbell", "dumbbell", "kettlebell", "machine", "cable", "bands",
                                           "bodyweight", "bench", "pull-up bar", "other"]
    readonly property var profile: Profile.profile
    // Why something about a device failed, in words; set by a failure, cleared once the list is fresh.
    property string accountProblem: ""
    property string profileProblem: ""

    function show(value) { return value === undefined ? "" : String(value) }

    // The increment box whose value was last sent, so only its typed text is let go once the save is answered.
    property var sentBox: null

    // `box` keeps what was typed until the server has it: another save (units, equipment) changes the profile too,
    // and must not put the old value back over an increment that was typed but not saved (spec §8).
    function saveIncrement(field, text, current, box) {
        const problem = Forms.incrementProblem(text)
        if (problem.length) {
            root.profileProblem = problem
            return
        }
        const value = Forms.parseNumber(text)
        root.profileProblem = ""
        // Leaving a field alone must not send anything.
        if (value !== current) {
            const changes = {}
            changes[field] = value
            root.sentBox = box
            Profile.save(changes)
        } else {
            box.dirty = false
        }
    }

    function toggleEquipment(word) {
        const have = root.profile.equipment || []
        const next = root.equipmentWords.filter(w => w === word ? have.indexOf(w) < 0 : have.indexOf(w) >= 0)
        Profile.save({ equipment: next })
    }

    function signInDate(iso) {
        return iso ? Words.lastSignIn + " " + Qt.formatDate(new Date(iso), "d MMM yyyy") : Words.neverSignedIn
    }

    Component.onCompleted: Session.loadDevices()

    Connections {
        target: Session
        function onAccountFailed(what, code) { root.accountProblem = Words.deviceError(code) }
        function onDevicesChanged() {
            if (Session.devicesError.length === 0 && !Session.devicesLoading)
                root.accountProblem = ""
        }
    }

    Connections {
        target: Profile
        function onFailed(code, field) {
            root.profileProblem = Words.saveProblem(code, field)
            root.sentBox = null
            savedNote.visible = false
        }
        function onSaved() {
            if (root.sentBox)
                root.sentBox.dirty = false
            root.sentBox = null
            root.profileProblem = ""
            savedNote.visible = true
            savedTimer.restart()
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
            width: Math.min(flick.width, 760)
            spacing: Preferences.spacingLarge

            Text {
                text: Words.settingsTitle
                color: Preferences.textPrimary
                font.family: Preferences.headingFont
                font.pixelSize: Preferences.fontSizeDisplay
            }

            // ---- Account ----
            Card {
                title: Words.accountTitle

                Text {
                    text: Words.signedInAs + " " + Session.username
                    color: Preferences.textPrimary
                    font.family: Preferences.appFont
                    font.pixelSize: Preferences.fontSizeBody
                }
                Caption { text: Words.devicesTitle }

                Repeater {
                    model: Session.devices
                    Rectangle {
                        objectName: "deviceRow"
                        width: parent.width
                        height: 44
                        radius: Preferences.controlRadius
                        color: Preferences.backgroundTertiary

                        Text {
                            id: deviceLabel
                            anchors { left: parent.left; leftMargin: 12; verticalCenter: parent.verticalCenter }
                            text: modelData.label
                            color: Preferences.textPrimary
                            font.family: Preferences.appFont
                            font.pixelSize: Preferences.fontSizeBody
                        }
                        Text {
                            anchors { left: deviceLabel.right; leftMargin: 12; verticalCenter: parent.verticalCenter }
                            text: modelData.current ? Words.thisDevice : root.signInDate(modelData.lastSignIn)
                            color: Preferences.textSecondary
                            font.family: Preferences.appFont
                            font.pixelSize: Preferences.fontSizeLabel
                        }
                        // Never on this device's own row: signing it out is Sign out's job. A Loader, so that row
                        // has no such button at all.
                        Loader {
                            active: !modelData.current
                            anchors { right: parent.right; rightMargin: 6; verticalCenter: parent.verticalCenter }
                            sourceComponent: ActionButton {
                                objectName: "removeDevice"
                                text: Words.removeDevice
                                danger: true
                                onClicked: Session.removeDevice(modelData.id)
                            }
                        }
                    }
                }

                Problem {
                    objectName: "devicesError"
                    text: root.accountProblem.length ? root.accountProblem
                          : (Session.devicesError.length ? Words.deviceError(Session.devicesError) : "")
                }
            }

            // ---- Training ----
            Card {
                title: Words.trainingTitle

                Text {
                    visible: !Profile.loaded
                    text: Profile.error.length ? Words.profileUnavailable : "…"
                    color: Preferences.textSecondary
                    font.family: Preferences.appFont
                    font.pixelSize: Preferences.fontSizeBody
                }
                ActionButton {
                    visible: !Profile.loaded && Profile.error.length > 0
                    text: Words.tryAgain
                    onClicked: Profile.load()
                }

                Column {
                    width: parent.width
                    spacing: Preferences.spacingMedium
                    visible: Profile.loaded

                    Caption { text: Words.unitsTitle }
                    Segmented {
                        prefix: "units"
                        options: [{ value: "lb", label: Words.unitsLabel("lb") }, { value: "kg", label: Words.unitsLabel("kg") }]
                        current: root.profile.units
                        onPicked: value => Profile.save({ units: value })
                    }

                    Caption { text: Words.incrementsTitle }
                    Row {
                        spacing: Preferences.spacingLarge
                        Column {
                            spacing: 4
                            Caption { text: Words.upperIncrement }
                            InputField {
                                id: upperBox
                                objectName: "upperIncrementField"
                                width: 120
                                // True from the first keystroke until the server has the value.
                                property bool dirty: false
                                onTextEdited: dirty = true
                                onEditingFinished: root.saveIncrement("upperIncrement", text, root.profile.upperIncrement, upperBox)
                            }
                            // A Binding, not a `text:` binding, and idle while the box holds something unsaved.
                            Binding {
                                target: upperBox
                                property: "text"
                                value: root.show(root.profile.upperIncrement)
                                when: !upperBox.dirty
                            }
                        }
                        Column {
                            spacing: 4
                            Caption { text: Words.lowerIncrement }
                            InputField {
                                id: lowerBox
                                objectName: "lowerIncrementField"
                                width: 120
                                // True from the first keystroke until the server has the value.
                                property bool dirty: false
                                onTextEdited: dirty = true
                                onEditingFinished: root.saveIncrement("lowerIncrement", text, root.profile.lowerIncrement, lowerBox)
                            }
                            // A Binding, not a `text:` binding, and idle while the box holds something unsaved.
                            Binding {
                                target: lowerBox
                                property: "text"
                                value: root.show(root.profile.lowerIncrement)
                                when: !lowerBox.dirty
                            }
                        }
                    }
                    Caption { text: Words.incrementsHint; muted: true }

                    Caption { text: Words.goalTitle }
                    Segmented {
                        prefix: "goal"
                        options: ["strength", "muscle", "general"].map(g => ({ value: g, label: Words.goalLabel(g) }))
                        current: root.profile.goal
                        onPicked: value => Profile.save({ goal: value })
                    }

                    Caption { text: Words.daysPerWeekTitle }
                    Segmented {
                        prefix: "days"
                        options: [2, 3, 4, 5, 6].map(d => ({ value: d, label: String(d) }))
                        current: root.profile.daysPerWeek
                        onPicked: value => Profile.save({ daysPerWeek: value })
                    }

                    Caption { text: Words.weekStartTitle }
                    Segmented {
                        prefix: "weekStart"
                        options: [{ value: "mon", label: Words.weekdayLong(0) }, { value: "sun", label: Words.weekdayLong(6) }]
                        current: root.profile.weekStart
                        onPicked: value => Profile.save({ weekStart: value })
                    }

                    Caption { text: Words.equipmentTitleSettings }
                    Flow {
                        width: parent.width
                        spacing: Preferences.spacingSmall
                        Repeater {
                            model: root.equipmentWords
                            Chip {
                                objectName: "equipment-" + modelData
                                text: Words.valueLabel("equipment", modelData)
                                chosen: (root.profile.equipment || []).indexOf(modelData) >= 0
                                onToggled: root.toggleEquipment(modelData)
                            }
                        }
                    }
                }

                Problem { objectName: "settingsError"; text: root.profileProblem }

                Text {
                    id: savedNote
                    objectName: "settingsSaved"
                    visible: false
                    text: Words.settingsSaved
                    color: Preferences.successColor
                    font.family: Preferences.appFont
                    font.pixelSize: Preferences.fontSizeLabel
                    Timer { id: savedTimer; interval: 2500; onTriggered: savedNote.visible = false }
                }
            }

            // ---- Introduction ----
            Card {
                title: Words.introTitleSettings

                ActionButton {
                    objectName: "replayIntro"
                    text: Words.replayIntro
                    onClicked: Nav.navigateTo("intro-page")
                }
                Caption { text: Words.replayHint; muted: true }
            }

            // ---- Look ----
            Card {
                title: Words.lookTitle

                ActionButton {
                    objectName: "resetLook"
                    text: Words.resetLook
                    onClicked: Preferences.resetAll()
                }
            }
        }
    }

    // A section: a card with its heading, holding whatever the section puts inside.
    component Card: Rectangle {
        id: card

        property string title: ""
        default property alias content: body.data

        width: parent ? parent.width : 0
        height: body.implicitHeight + 2 * Preferences.spacingLarge
        radius: Preferences.cornerRadius
        color: Preferences.backgroundSecondary

        Column {
            id: body
            x: Preferences.spacingLarge
            y: Preferences.spacingLarge
            width: card.width - 2 * Preferences.spacingLarge
            spacing: Preferences.spacingMedium

            Text {
                text: card.title
                color: Preferences.textPrimary
                font.family: Preferences.headingFont
                font.pixelSize: Preferences.fontSizeHeading
            }
        }
    }
}
