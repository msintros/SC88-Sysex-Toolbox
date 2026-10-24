#include "Exporter.h"
#include "MidiService.h"

namespace sc88::Exporter {

static juce::String safeName(const juce::String& text)
{
    juce::String cleaned;
    for (auto c : text)
        cleaned += (juce::CharacterFunctions::isLetterOrDigit(c) || juce::String(" -_.").containsChar(c)) ? c : '_';
    cleaned = cleaned.trim().trimCharactersAtEnd(".");
    // Collapse runs of whitespace.
    auto parts = juce::StringArray::fromTokens(cleaned, " ", "");
    parts.removeEmptyStrings();
    auto joined = parts.joinIntoString(" ");
    return joined.isEmpty() ? juce::String("SC88 Sysex Toolbox") : joined;
}

juce::String fileName(const juce::String& label, const juce::String& scope, bool withMillis)
{
    auto now = juce::Time::getCurrentTime();
    auto stamp = now.formatted("%Y%m%d-%H%M%S");
    if (withMillis) stamp << "-" << juce::String(now.getMilliseconds()).paddedLeft('0', 3);
    return "SC88_" + safeName(label) + "_" + scope + "_" + stamp + ".mid";
}

bool writeMidiFile(const juce::File& file, const juce::String& label, const juce::String& scope,
                   const std::vector<Message>& messages, int delayMs)
{
    constexpr int ppqn = 480;
    constexpr double secondsPerTick = 0.5 / ppqn; // 120 BPM
    const double gapTicks = std::round(delayMs / 1000.0 / secondsPerTick);

    juce::MidiMessageSequence track;
    auto name = juce::MidiMessage::textMetaEvent(3, "SC88 Sysex Toolbox " + scope + ": " + label);
    name.setTimeStamp(0);
    track.addEvent(name);
    auto tempo = juce::MidiMessage::tempoMetaEvent(500000);
    tempo.setTimeStamp(0);
    track.addEvent(tempo);

    double t = 0;
    for (size_t i = 0; i < messages.size(); ++i) {
        if (i) t += gapTicks;
        auto m = toMidiMessage(messages[i].bytes);
        m.setTimeStamp(t);
        track.addEvent(m);
    }
    auto end = juce::MidiMessage::endOfTrack();
    end.setTimeStamp(t);
    track.addEvent(end);

    juce::MidiFile midi;
    midi.setTicksPerQuarterNote(ppqn);
    midi.addTrack(track);

    file.getParentDirectory().createDirectory();
    file.deleteFile();
    juce::FileOutputStream out(file);
    return out.openedOk() && midi.writeTo(out, 0);
}

juce::File dragCacheDirectory()
{
#if JUCE_MAC
    return juce::File::getSpecialLocation(juce::File::userHomeDirectory)
        .getChildFile("Library/Caches/SC88 Sysex Toolbox/Drag MIDI");
#else
    return juce::File::getSpecialLocation(juce::File::tempDirectory).getChildFile("SC88 Sysex Toolbox Drag MIDI");
#endif
}

void cleanDragCache()
{
    auto cutoff = juce::Time::getCurrentTime() - juce::RelativeTime::days(2);
    for (auto& f : dragCacheDirectory().findChildFiles(juce::File::findFiles, false, "*.mid"))
        if (f.getLastModificationTime() < cutoff) f.deleteFile();
}

juce::String clipboardText(const juce::String& title, const std::vector<Message>& messages)
{
    juce::String text = title + ":";
    for (auto& m : messages) text << "\n\n" << juce::String(m.label) << ":\n" << juce::String(toHex(m.bytes));
    return text;
}

} // namespace sc88::Exporter
