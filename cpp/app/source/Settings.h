#pragma once

#include <JuceHeader.h>

namespace sc88 {

// Preferences, stored as settings.json in the same place and format as the
// Python app, so both versions share them.
struct Settings {
    juce::String midiOutput;          // device name, empty for none
    int sysexDelayMs = 10;            // gap between messages of a page send / export
    int repeatIntervalMs = 95;        // hold-to-repeat speed of the arrow keys
    juce::File midiSaveLocation;

    static juce::File settingsFile();
    static Settings load();
    void save() const;
};

} // namespace sc88
