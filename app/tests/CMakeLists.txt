find_package(Qt6 REQUIRED COMPONENTS Test Gui Network Qml Quick)

# One test executable: its sources, the libraries beyond Qt Test, and a ctest entry. Console programs, so their
# output reaches ctest; offscreen, so no window reaches the owner's screen. (Gluttony's tests/CMakeLists.txt at
# c1ed705 is the model.)
function(pride_test name)
    cmake_parse_arguments(T "" "" "SOURCES;LIBS" ${ARGN})
    qt_add_executable(${name} ${T_SOURCES})
    target_include_directories(${name} PRIVATE ..)
    target_link_libraries(${name} PRIVATE Qt6::Test ${T_LIBS})
    set_target_properties(${name} PROPERTIES WIN32_EXECUTABLE FALSE MACOSX_BUNDLE FALSE)
    add_test(NAME ${name} COMMAND ${name})
    set_tests_properties(${name} PROPERTIES ENVIRONMENT "QT_QPA_PLATFORM=offscreen")
endfunction()

set(PRIDE_API ../api/Api.h ../api/Api.cpp ../api/AppConfig.h ../api/SessionAuth.h ../api/SessionAuth.cpp)

pride_test(tst_api
    SOURCES tst_api.cpp FakeServer.h ${PRIDE_API}
    LIBS Qt6::Network)

pride_test(tst_sessionauth
    SOURCES tst_sessionauth.cpp FakeServer.h ../api/SessionAuth.h ../api/SessionAuth.cpp ../api/AuthNetworkFactory.h
    LIBS Qt6::Network Qt6::Qml)

pride_test(tst_accountstore
    SOURCES tst_accountstore.cpp ../services/AccountStore.h ../services/AccountStore.cpp)

pride_test(tst_session
    SOURCES tst_session.cpp FakeServer.h ${PRIDE_API}
            ../services/AccountStore.h ../services/AccountStore.cpp
            ../services/Session.h ../services/Session.cpp
    LIBS Qt6::Network)

pride_test(tst_exercisestore
    SOURCES tst_exercisestore.cpp FakeServer.h ${PRIDE_API} ../api/AuthNetworkFactory.h
            ../services/ExerciseStore.h ../services/ExerciseStore.cpp
    LIBS Qt6::Network Qt6::Gui Qt6::Qml)

pride_test(tst_catalog
    SOURCES tst_catalog.cpp FakeServer.h ${PRIDE_API} ../api/AuthNetworkFactory.h
            ../services/ExerciseStore.h ../services/ExerciseStore.cpp
            ../services/Catalog.h ../services/Catalog.cpp
    LIBS Qt6::Network Qt6::Gui Qt6::Qml)
