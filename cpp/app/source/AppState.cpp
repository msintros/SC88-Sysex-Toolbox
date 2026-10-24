#include "AppState.h"
#include "BinaryData.h"

namespace sc88 {

static std::string binaryText(const char* data, int size) { return std::string(data, size_t(size)); }

AppState::AppState()
    : tables(Tables::fromJson(binaryText(BinaryData::parameter_pages_json, BinaryData::parameter_pages_jsonSize),
                              binaryText(BinaryData::part_params_json, BinaryData::part_params_jsonSize),
                              binaryText(BinaryData::efx_json, BinaryData::efx_jsonSize))),
      patch(tables),
      settings(Settings::load())
{
    midi.openPreferred(settings.midiOutput);
    midi.onDevicesChanged = [this] { sendChangeMessage(); };
}

void AppState::parameterEdited(const Exportable& parameter)
{
    lastEdited = parameter;
    for (auto& m : parameter.messages()) midi.sendNow(m.bytes);
    sendChangeMessage();
}

void AppState::sendPage(const std::vector<Message>& messages)
{
    if (midi.currentOutputName().isEmpty()) {
        setStatus("No MIDI output selected");
        return;
    }
    std::vector<Bytes> bytes;
    for (auto& m : messages) bytes.push_back(m.bytes);
    midi.sendPaced(bytes, settings.sysexDelayMs);
    setStatus("Sent " + juce::String(int(messages.size())) + " messages");
}

void AppState::setStatus(const juce::String& text, int durationMs)
{
    statusText = text;
    statusUntil = juce::Time::getMillisecondCounter() + juce::uint32(durationMs);
    sendChangeMessage();
}

juce::String AppState::status() const
{
    return juce::Time::getMillisecondCounter() < statusUntil ? statusText : juce::String();
}

} // namespace sc88
