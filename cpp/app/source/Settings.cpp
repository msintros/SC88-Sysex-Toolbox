#include "Settings.h"

namespace sc88 {

static juce::File defaultSaveLocation()
{
    return juce::File::getSpecialLocation(juce::File::userHomeDirectory)
        .getChildFile("Downloads")
        .getChildFile("SC88 Sysex Toolbox MIDI");
}

juce::File Settings::settingsFileFor(const juce::String& appFolder)
{
#if JUCE_MAC
    auto dir = juce::File::getSpecialLocation(juce::File::userHomeDirectory)
                   .getChildFile("Library/Application Support").getChildFile(appFolder);
#elif JUCE_WINDOWS
    auto dir = juce::File::getSpecialLocation(juce::File::userApplicationDataDirectory).getChildFile(appFolder);
#else
    auto dir = juce::File::getSpecialLocation(juce::File::userHomeDirectory)
                   .getChildFile("." + appFolder.toLowerCase().replaceCharacter(' ', '_'));
#endif
    return dir.getChildFile("settings.json");
}

juce::File Settings::settingsFile() { return settingsFileFor("SC88 Sysex Toolbox"); }

Settings Settings::load()
{
    Settings s;
    s.midiSaveLocation = defaultSaveLocation();

    auto file = settingsFile();
    if (!file.existsAsFile()) file = settingsFileFor("SC88 Flashlight"); // the Python app's settings
    auto json = juce::JSON::parse(file);
    if (auto* obj = json.getDynamicObject()) {
        auto output = obj->getProperty("midi_output");
        if (output.isString()) s.midiOutput = output.toString();
        if (obj->hasProperty("sysex_delay_ms")) s.sysexDelayMs = int(obj->getProperty("sysex_delay_ms"));
        if (obj->hasProperty("repeat_interval_ms")) s.repeatIntervalMs = int(obj->getProperty("repeat_interval_ms"));
        auto location = obj->getProperty("midi_save_location").toString();
        if (location.isNotEmpty())
            s.midiSaveLocation = juce::File(location.startsWith("~")
                ? juce::File::getSpecialLocation(juce::File::userHomeDirectory).getFullPathName() + location.substring(1)
                : location);
    }

    // Clamp in case the file was hand-edited.
    s.sysexDelayMs = juce::jlimit(0, 250, s.sysexDelayMs);
    s.repeatIntervalMs = juce::jlimit(25, 250, s.repeatIntervalMs);
    return s;
}

void Settings::save() const
{
    auto* obj = new juce::DynamicObject();
    obj->setProperty("midi_output", midiOutput.isEmpty() ? juce::var() : juce::var(midiOutput));
    obj->setProperty("sysex_delay_ms", sysexDelayMs);
    obj->setProperty("repeat_interval_ms", repeatIntervalMs);
    obj->setProperty("midi_save_location", midiSaveLocation.getFullPathName());

    auto file = settingsFile();
    file.getParentDirectory().createDirectory();
    file.replaceWithText(juce::JSON::toString(juce::var(obj)));
}

} // namespace sc88
