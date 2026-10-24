#include "MidiService.h"

namespace sc88 {

juce::MidiMessage toMidiMessage(const Bytes& message)
{
    auto payload = withoutFraming(message);
    return juce::MidiMessage::createSysExMessage(payload.data(), int(payload.size()));
}

MidiService::MidiService()
{
    deviceListConnection = juce::MidiDeviceListConnection::make([this] {
        // Reopen by name if our device came back, or drop it if it went away.
        auto name = currentOutputName();
        bool stillThere = false;
        for (auto& d : outputs())
            if (d.name == name) stillThere = true;
        if (!stillThere) output.reset();
        if (onDevicesChanged) onDevicesChanged();
    });
}

bool MidiService::open(const juce::String& name)
{
    for (auto& d : outputs()) {
        if (d.name != name) continue;
        if (auto out = juce::MidiOutput::openDevice(d.identifier)) {
            if (output) output->stopBackgroundThread();
            output = std::move(out);
            output->startBackgroundThread();
            return true;
        }
    }
    return false;
}

void MidiService::openPreferred(const juce::String& saved)
{
    if (saved.isNotEmpty() && open(saved)) return;
    if (open("IAC Driver Bus 1")) return;
    auto devices = outputs();
    if (!devices.isEmpty()) open(devices[0].name);
}

void MidiService::sendNow(const Bytes& message)
{
    if (output) output->sendMessageNow(toMidiMessage(message));
}

void MidiService::sendPaced(const std::vector<Bytes>& messages, int delayMs)
{
    if (!output || messages.empty()) return;
    // Sample positions are milliseconds: sendBlockOfMessages runs at 1 kHz here.
    juce::MidiBuffer buffer;
    int position = 0;
    for (auto& m : messages) {
        buffer.addEvent(toMidiMessage(m), position);
        position += juce::jmax(1, delayMs);
    }
    output->sendBlockOfMessages(buffer, juce::Time::getMillisecondCounterHiRes(), 1000.0);
}

} // namespace sc88
