#pragma once

#include <JuceHeader.h>
#include "MidiService.h"
#include "Settings.h"
#include "sc88/Patch.h"

#include <functional>
#include <memory>

namespace sc88 {

// Something the user can export as a single MIDI file: a parameter or a page.
struct Exportable {
    juce::String label;
    std::function<std::vector<Message>()> messages;
    explicit operator bool() const { return static_cast<bool>(messages); }
};

// Shared application state. UI components listen for changes and repaint.
class AppState : public juce::ChangeBroadcaster {
public:
    AppState();

    Tables tables;
    Patch patch;
    Settings settings;
    MidiService midi;

    // Send one edited parameter right away and remember it for PARAM MIDI.
    void parameterEdited(const Exportable& parameter);
    const Exportable& lastEditedParameter() const { return lastEdited; }
    void clearLastEdited() { lastEdited = {}; }

    void sendPage(const std::vector<Message>& messages);

    // Status line shown on the main LCD for a few seconds.
    void setStatus(const juce::String& text, int durationMs = 2200);
    juce::String status() const;

    juce::String lastEditedName, lastEditedValue;

    // Part shown on the Part pages and Scale Tuning.
    Group selGroup = Group::A;
    int selPart = 1;
    bool aftertouchPoly = false; // Aftertouch page: CAf or PAf

private:
    Exportable lastEdited;
    juce::String statusText;
    juce::uint32 statusUntil = 0;
};

} // namespace sc88
