cmake_minimum_required(VERSION 3.16)

project(Pride VERSION 0.1 LANGUAGES CXX)

set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(Qt6 REQUIRED COMPONENTS Quick QuickControls2 Network)

qt_standard_project_setup(REQUIRES 6.8)

# The app itself (appPride and its QML module) joins once the owner has chosen its look; until then this builds the
# tests of the C++ underneath.

option(PRIDE_BUILD_TESTS "Build the C++ tests" OFF)
if(PRIDE_BUILD_TESTS)
    enable_testing()
    add_subdirectory(tests)
endif()
