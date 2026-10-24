#pragma once

#include <JuceHeader.h>
#include "sc88/Patch.h"

#include <vector>

namespace sc88 {

// Standard MIDI files and clipboard text for a set of SysEx messages.
namespace Exporter {

// Type 0 SMF at 120 BPM / 480 PPQN, messages spaced by delayMs, with a track
// name of "SC88 Flashlight <scope>: <label>". Matches the Python app's files.
bool writeMidiFile(const juce::File& file, const juce::String& label, const juce::String& scope,
                   const std::vector<Message>& messages, int delayMs);

// SC88_<label>_<scope>_<timestamp>.mid
juce::String fileName(const juce::String& label, const juce::String& scope, bool withMillis);

// Where drag-out files live. DAWs may read them after the drop, so they are
// kept for two days rather than deleted straight away.
juce::File dragCacheDirectory();
void cleanDragCache();

juce::String clipboardText(const juce::String& title, const std::vector<Message>& messages);

} // namespace Exporter
} // namespace sc88
