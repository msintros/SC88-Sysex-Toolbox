FetchContent_Declare(Catch2
    GIT_REPOSITORY https://github.com/catchorg/Catch2.git
    GIT_TAG v3.7.1
    GIT_SHALLOW TRUE)
FetchContent_MakeAvailable(Catch2)

add_executable(sc88-core-tests
    test_sysex.cpp
    test_golden.cpp)

target_link_libraries(sc88-core-tests PRIVATE sc88-core nlohmann_json::nlohmann_json Catch2::Catch2WithMain)
target_compile_definitions(sc88-core-tests PRIVATE
    SC88_DATA_ROOT="${SC88_DATA_ROOT}"
    SC88_GOLDEN="${CMAKE_CURRENT_SOURCE_DIR}/golden/golden.json")

include(CTest)
include(Catch)
catch_discover_tests(sc88-core-tests)
