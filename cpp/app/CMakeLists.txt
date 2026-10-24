# JUCE is fetched at configure time. To use a local checkout instead, pass
# -DFETCHCONTENT_SOURCE_DIR_JUCE=/path/to/JUCE.
FetchContent_Declare(JUCE
    GIT_REPOSITORY https://github.com/juce-framework/JUCE.git
    GIT_TAG 8.0.4
    GIT_SHALLOW TRUE)
FetchContent_MakeAvailable(JUCE)

juce_add_gui_app(SC88SysexToolbox
    PRODUCT_NAME "SC88 Sysex Toolbox"
    COMPANY_NAME "SC88 Sysex Toolbox"
    BUNDLE_ID "com.sc88sysextoolbox.app"
    ICON_BIG resources/icon.png
    VERSION ${PROJECT_VERSION})

juce_generate_juce_header(SC88SysexToolbox)

juce_add_binary_data(SC88SysexToolboxData SOURCES
    ${SC88_DATA_ROOT}/efx.json
    ${SC88_DATA_ROOT}/data/parameter_pages.json
    ${SC88_DATA_ROOT}/data/part_params.json
    resources/fonts/Inter-Medium.ttf
    resources/fonts/Inter-SemiBold.ttf)

target_sources(SC88SysexToolbox PRIVATE
    source/Main.cpp
    source/AppState.cpp
    source/MidiService.cpp
    source/Exporter.cpp
    source/Settings.cpp
    source/MainComponent.cpp
    source/ui/Theme.cpp
    source/ui/Lcd.cpp
    source/ui/Controls.cpp
    source/ui/ValueCell.cpp
    source/pages/Pages.cpp)

target_include_directories(SC88SysexToolbox PRIVATE source)

target_compile_definitions(SC88SysexToolbox PRIVATE
    JUCE_WEB_BROWSER=0
    JUCE_USE_CURL=0
    JUCE_APPLICATION_NAME_STRING="$<TARGET_PROPERTY:SC88SysexToolbox,JUCE_PRODUCT_NAME>"
    JUCE_APPLICATION_VERSION_STRING="$<TARGET_PROPERTY:SC88SysexToolbox,JUCE_VERSION>")

target_link_libraries(SC88SysexToolbox
    PRIVATE
        sc88-core
        SC88SysexToolboxData
        juce::juce_gui_extra
        juce::juce_audio_basics
        juce::juce_audio_devices
    PUBLIC
        juce::juce_recommended_config_flags
        juce::juce_recommended_lto_flags
        juce::juce_recommended_warning_flags)
