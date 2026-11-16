import QtQuick
import QtQuick.Controls
import "logic/words.mjs" as Words

// The app around its pages: the side rail, the top bar, and the page beside them. The rail holds Today, Programs,
// Catalog and Settings, with Sign out at the foot (Progress joins in milestone 3). Pages are swapped by name, and a
// new shell starts on Nav.currentPage. While the server cannot be reached, a banner under the top bar says so.
Rectangle {
    id: root
    objectName: "navShell"

    color: Preferences.backgroundPrimary

    property string currentPage: ""
    // The last page that is not an exercise, which the Exercise page's Back returns to. A routine counts as a list
    // page, so Back from an exercise opened there returns to it.
    property string lastListPage: "catalog-page"

    // Each page adds its own entry here.
    readonly property var pageComponents: ({ "catalog-page": catalogPage, "exercise-page": exercisePage,
                                         "settings-page": settingsPage })
    readonly property string startPage: root.pageComponents[Nav.currentPage] !== undefined ? Nav.currentPage : "catalog-page"

    Component.onCompleted: {
        root.currentPage = root.startPage
        if (root.startPage !== "exercise-page")
            root.lastListPage = root.startPage
    }

    Connections {
        target: Nav
        function onChangePage(page) {
            if (root.pageComponents[page] === undefined)
                return
            if (page !== "exercise-page")
                root.lastListPage = page
            root.currentPage = page
        }
    }

    Component { id: catalogPage; CatalogPage {} }
    Component { id: settingsPage; SettingsPage {} }
    Component { id: exercisePage; ExercisePage { onBackRequested: Nav.navigateTo(root.lastListPage) } }

    Rectangle {
        id: rail
        anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
        width: 68
        color: Preferences.backgroundSecondary

        Column {
            anchors { top: parent.top; topMargin: 16; horizontalCenter: parent.horizontalCenter }
            spacing: 10

            Image {
                anchors.horizontalCenter: parent.horizontalCenter
                source: "qrc:/icons/prideAppIcon.png"
                sourceSize: Qt.size(40, 40)
                width: 40
                height: 40
                fillMode: Image.PreserveAspectFit
            }
            Item { width: 1; height: 12 }
            RailButton {
                objectName: "railToday"
                label: Words.navToday
                pageTag: "today-page"
                iconSource: "qrc:/images/today.svg"
                onActivated: Nav.navigateTo("today-page")
            }
            RailButton {
                objectName: "railPrograms"
                label: Words.navPrograms
                pageTag: "programs-page"
                alsoOn: "routine-page"
                iconSource: "qrc:/images/programs.svg"
                onActivated: Nav.navigateTo("programs-page")
            }
            RailButton {
                objectName: "railCatalog"
                label: Words.navCatalog
                pageTag: "catalog-page"
                iconSource: "qrc:/images/catalog.svg"
                onActivated: Nav.navigateTo("catalog-page")
            }
            RailButton {
                objectName: "railSettings"
                label: Words.navSettings
                pageTag: "settings-page"
                iconSource: "qrc:/images/settings.svg"
                onActivated: Nav.navigateTo("settings-page")
            }
        }

        RailButton {
            objectName: "railSignOut"
            anchors { bottom: parent.bottom; bottomMargin: 16; horizontalCenter: parent.horizontalCenter }
            label: Words.signOut
            iconSource: "qrc:/images/signout.svg"
            onActivated: Session.logout()
        }
    }

    Rectangle {
        id: topBar
        objectName: "topBar"
        anchors { left: rail.right; right: parent.right; top: parent.top }
        height: 64
        // Above the page, so the search's list (Task 19) lies over it.
        z: 2
        color: Preferences.backgroundPrimary

        QuickSearch {
            x: Preferences.spacingLarge
            anchors.verticalCenter: parent.verticalCenter
            width: 520
            height: 40
        }
    }

    Rectangle {
        id: banner
        objectName: "offlineBanner"
        visible: !Session.online
        anchors { left: rail.right; right: parent.right; top: topBar.bottom }
        height: visible ? 32 : 0
        color: Preferences.accentSubtle

        Text {
            anchors.centerIn: parent
            text: Words.offline
            color: Preferences.textPrimary
            font.family: Preferences.appFont
            font.pixelSize: Preferences.fontSizeLabel
        }
    }

    Loader {
        id: pageLoader
        anchors { left: rail.right; right: parent.right; top: banner.bottom; bottom: parent.bottom }
        sourceComponent: root.pageComponents[root.currentPage] || null
    }

    // An icon with its label as a tooltip: the rail stays narrow so pages get the width. (Gluttony's NavShell at
    // c1ed705.)
    component RailButton: Rectangle {
        id: button

        property string label: ""
        property string pageTag: ""
        // A second page that lights this button too (the routine editor belongs to Programs).
        property string alsoOn: ""
        property url iconSource
        readonly property bool selected: pageTag.length > 0
                                         && (root.currentPage === pageTag || root.currentPage === alsoOn
                                             || (root.currentPage === "exercise-page"
                                                 && (root.lastListPage === pageTag || root.lastListPage === alsoOn)))
        signal activated()

        width: 48
        height: 48
        radius: Preferences.controlRadius
        color: button.selected ? Preferences.accentSubtle
                               : (mouse.containsMouse ? Preferences.backgroundTertiary : "transparent")

        TintedIcon {
            anchors.centerIn: parent
            source: button.iconSource
            size: 24
            color: button.selected ? Preferences.accentColor : Preferences.textSecondary
        }

        ToolTip {
            id: tip
            visible: mouse.containsMouse
            text: button.label
            delay: 400
            x: button.width + 8
            y: (button.height - height) / 2
            contentItem: Text {
                text: tip.text
                color: Preferences.textPrimary
                font.family: Preferences.appFont
                font.pixelSize: Preferences.fontSizeLabel
            }
            background: Rectangle {
                color: Preferences.backgroundTertiary
                border.color: Preferences.borderColor
                radius: Preferences.controlRadius
            }
        }

        MouseArea {
            id: mouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: button.activated()
        }
    }
}
