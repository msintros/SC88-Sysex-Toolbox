#pragma once

#include <JuceHeader.h>
#include "sc88/Sysex.h"

#include <functional>
#include <vector>

namespace sc88 {

// Owns the MIDI output. Single edits go out immediately; page sends are
// spaced by the SysEx delay so the SC-88 Pro's input buffer keeps up.
class MidiService {
public:
    MidiService();

    juce::Array<juce::MidiDeviceInfo> outputs() const { return juce::MidiOutput::getAvailableDevices(); }
    juce::String currentOutputName() const { return output ? output->getName() : juce::String(); }

    // Opens the named device. Returns false if it is not available.
    bool open(const juce::String& name);
    // Saved device if present, else the IAC bus, else the first device.
    void openPreferred(const juce::String& saved);

    void sendNow(const Bytes& message);
    void sendPaced(const std::vector<Bytes>& messages, int delayMs);

    // Called on the message thread when devices are plugged in or removed.
    std::function<void()> onDevicesChanged;

private:
    std::unique_ptr<juce::MidiOutput> output;
    juce::MidiDeviceListConnection deviceListConnection;
};

juce::MidiMessage toMidiMessage(const Bytes& message);

} // namespace sc88
