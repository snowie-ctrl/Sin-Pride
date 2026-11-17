cmake_minimum_required(VERSION 3.16)

project(Pride VERSION 0.1 LANGUAGES CXX)

set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(Qt6 REQUIRED COMPONENTS Quick QuickControls2 Network)

qt_standard_project_setup(REQUIRES 6.8)

qt_add_executable(appPride
    main.cpp
    LinkSuppressor.h

    assets/resources.qrc
    assets/Preferences.h
    assets/Preferences.cpp

    api/AppConfig.h
    api/Api.h
    api/Api.cpp
    api/SessionAuth.h
    api/SessionAuth.cpp
    api/AuthNetworkFactory.h

    services/Nav.h
    services/AccountStore.h
    services/AccountStore.cpp
    services/Session.h
    services/Session.cpp
    services/ExerciseStore.h
    services/ExerciseStore.cpp
    services/Catalog.h
    services/Catalog.cpp
    services/Profile.h
    services/Profile.cpp
    services/Programs.h
    services/Programs.cpp
    services/Workouts.h
    services/Workouts.cpp
    services/Progress.h
    services/Progress.cpp
    services/Wiring.h
    services/Wiring.cpp
)

if(WIN32)
    # The crown as the .exe's own icon (Explorer, the taskbar before the window opens). Written with the icon's full
    # path, so the resource compiler never has to guess where it is.
    file(WRITE ${CMAKE_CURRENT_BINARY_DIR}/pride.rc
         "IDI_ICON1 ICON \"${CMAKE_CURRENT_SOURCE_DIR}/assets/icons/pride.ico\"\n")
    target_sources(appPride PRIVATE ${CMAKE_CURRENT_BINARY_DIR}/pride.rc)
endif()

# The QML lives in a static library of its own, so the page tests (tests/tst_pages.cpp) load the real pages.
qt_add_library(pride_ui STATIC)
qt_add_qml_module(pride_ui
    URI Pride
    VERSION 1.0
    QML_FILES
        qml/Main.qml
        qml/NavShell.qml
        qml/pages/LoginPage.qml
        qml/pages/CatalogPage.qml
        qml/pages/ExercisePage.qml
        qml/pages/SettingsPage.qml
        qml/pages/IntroPage.qml
        qml/pages/TodayPage.qml
        qml/pages/ProgramsPage.qml
        qml/pages/RoutinePage.qml
        qml/component/QuickSearch.qml
        qml/component/TintedIcon.qml
        qml/component/ActionButton.qml
        qml/component/InputField.qml
        qml/component/NumberField.qml
        qml/component/ExercisePicker.qml
        qml/component/Chip.qml
        qml/component/Segmented.qml
        qml/component/Caption.qml
        qml/component/Problem.qml
        qml/component/PictureFrame.qml
        qml/component/ExerciseTile.qml
        qml/component/FilterPanel.qml
        qml/component/WeekStrip.qml
        qml/component/DayChips.qml
        qml/component/ConfirmDialog.qml
        qml/component/OwnExerciseForm.qml
        qml/component/AddToRoutine.qml
        qml/component/GoldChip.qml
        qml/component/CrownCard.qml
        qml/logic/words.mjs
        qml/logic/forms.mjs
        qml/logic/units.mjs
        qml/logic/logbook.mjs
        qml/logic/charts.mjs
)
target_link_libraries(pride_ui PRIVATE Qt6::Quick Qt6::QuickControls2)

set_target_properties(appPride PROPERTIES WIN32_EXECUTABLE TRUE MACOSX_BUNDLE TRUE)

# The sources include each other from the project root ("api/Api.h").
target_include_directories(appPride PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})

target_link_libraries(appPride PRIVATE pride_uiplugin Qt6::Quick Qt6::QuickControls2 Qt6::Network)

# A dev build finds config/secrets.json in the source tree; a Release build never falls back to it.
target_compile_definitions(appPride PRIVATE
    $<$<NOT:$<CONFIG:Release>>:PRIDE_SOURCE_DIR="${CMAKE_CURRENT_SOURCE_DIR}">
)

add_custom_command(TARGET appPride POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E make_directory $<TARGET_FILE_DIR:appPride>/config
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
            ${CMAKE_CURRENT_SOURCE_DIR}/config/secrets.example.json
            $<TARGET_FILE_DIR:appPride>/config/secrets.example.json
)
if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/config/secrets.json)
    add_custom_command(TARGET appPride POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy_if_different
                ${CMAKE_CURRENT_SOURCE_DIR}/config/secrets.json
                $<TARGET_FILE_DIR:appPride>/config/secrets.json
    )
endif()

option(PRIDE_BUILD_TESTS "Build the C++ tests" OFF)
if(PRIDE_BUILD_TESTS)
    enable_testing()
    add_subdirectory(tests)
endif()
