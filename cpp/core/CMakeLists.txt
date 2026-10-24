add_library(sc88-core STATIC
    src/Sysex.cpp
    src/Param.cpp
    src/Tables.cpp
    src/Patch.cpp)

target_include_directories(sc88-core PUBLIC include)
target_link_libraries(sc88-core PRIVATE nlohmann_json::nlohmann_json)

if(MSVC)
    target_compile_options(sc88-core PRIVATE /W4)
else()
    target_compile_options(sc88-core PRIVATE -Wall -Wextra -Wpedantic)
endif()
