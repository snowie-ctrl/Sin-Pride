import QtQuick
import QtQuick.Controls
import "logic/words.mjs" as Words

ApplicationWindow {
    id: window

    width: 1600
    height: 1000
    minimumWidth: 1100
    minimumHeight: 700
    visible: true

    title: Words.appName
    color: Preferences.backgroundPrimary
    font.family: Preferences.appFont

    // Which top-level page is showing, by name.
    property string topPage: "login-page"

    Component { id: loginPage; LoginPage {} }
    Component { id: navShell; NavShell {} }
    Component { id: introPage; IntroPage {} }

    StackView {
        id: primaryStack
        anchors.fill: parent
        initialItem: loginPage
        replaceEnter: Transition {}
        replaceExit: Transition {}
    }

    Connections {
        target: Nav
        function onChangePage(page) {
            // Pages inside the shell are the shell's business.
            if (page !== "login-page" && page !== "nav-shell" && page !== "intro-page")
                return
            if (window.topPage === page)
                return
            primaryStack.replace(page === "login-page" ? loginPage : (page === "intro-page" ? introPage : navShell))
            window.topPage = page
        }
    }

    // A profile that says pending brings the intro up whenever it is loaded or saved (plan decision 6), so closing the
    // app mid-intro never loses it.
    Connections {
        target: Profile
        function onIntroPending() { Nav.navigateTo("intro-page") }
    }

    Connections {
        target: Session
        function onLoginSucceeded() { Nav.navigateTo(Nav.startPage) }
        // No server, but this account signed in here before: the shell opens on the catalog this device keeps.
        function onStartedOffline() { Nav.navigateTo(Nav.startPage) }
        function onSignedOut() { Nav.navigateTo("login-page") }
    }
}
