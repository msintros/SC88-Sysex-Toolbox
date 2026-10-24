cmake_minimum_required(VERSION 3.22)
project(SC88SysexToolbox VERSION 0.1.0 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

option(SC88_BUILD_TESTS "Build the sc88-core unit tests" ON)
option(SC88_BUILD_APP "Build the JUCE desktop app" ON)

include(FetchContent)
FetchContent_Declare(nlohmann_json
    URL https://github.com/nlohmann/json/releases/download/v3.11.3/json.tar.xz
    URL_HASH SHA256=d6c65aca6b1ed68e7a182f4757257b107ae403032760ed6ef121c9d55e81757d
    DOWNLOAD_EXTRACT_TIMESTAMP TRUE)
FetchContent_MakeAvailable(nlohmann_json)

# Repository root, where efx.json and data/ live.
set(SC88_DATA_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/..")

add_subdirectory(core)

if(SC88_BUILD_APP)
    add_subdirectory(app)
endif()

if(SC88_BUILD_TESTS)
    enable_testing()
    add_subdirectory(tests)
endif()
