#pragma once

#include <JuceHeader.h>

namespace sc88 {

// Preferences, stored as settings.json in the same format as the Python app.
// On first run, settings saved by SC88 Flashlight (the Python app) are picked up.
struct Settings {
    juce::String midiOutput;          // device name, empty for none
    int sysexDelayMs = 10;            // gap between messages of a page send / export
    int repeatIntervalMs = 95;        // hold-to-repeat speed of the arrow keys
    juce::File midiSaveLocation;

    static juce::File settingsFile();
    static juce::File settingsFileFor(const juce::String& appFolder);
    static Settings load();
    void save() const;
};

} // namespace sc88
