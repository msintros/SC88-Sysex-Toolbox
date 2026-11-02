#include "Programs.h"

namespace sc88 {

// ---- ProgramList --------------------------------------------------------------

ProgramList ProgramList::fromJson(const juce::String& json)
{
    ProgramList list;
    auto root = juce::JSON::parse(json);

    auto addCategory = [&list](const juce::String& name, const juce::var& programs, bool drums) {
        ProgramCategory cat { name, list.size(), 0 };
        const int index = int(list.categories.size());
        if (auto* arr = programs.getArray())
            for (auto& p : *arr) {
                list.programs.push_back({ p["name"].toString(), int(p["pc"]), int(p["cc0"]), drums, index });
                ++cat.count;
            }
        list.categories.push_back(cat);
    };

    if (auto* cats = root["categories"].getArray())
        for (auto& c : *cats) addCategory(c["name"].toString(), c["programs"], false);
    addCategory("Drum Sets", root["drumSets"], true);
    return list;
}

int ProgramList::find(int pc, int cc0, bool drumSet) const
{
    for (size_t i = 0; i < programs.size(); ++i)
        if (programs[i].pc == pc && programs[i].cc0 == cc0 && programs[i].drumSet == drumSet) return int(i);
    return -1;
}

// ---- ProgramSetup -------------------------------------------------------------

ProgramSetup::ProgramSetup(const ProgramList& l) : list(l) { reset(); }

void ProgramSetup::reset()
{
    const int piano = list.find(1, 0, false);
    const int standard = list.find(1, 0, true);
    for (int i = 0; i < numParts; ++i) parts[size_t(i)] = i == 9 ? standard : piano;
}

std::vector<Message> ProgramSetup::partMessages(int part) const
{
    const int index = parts[size_t(part)];
    if (index < 0 || index >= list.size()) return {};
    const auto& p = list.programs[size_t(index)];
    const auto channel = uint8_t(part & 0x0f);
    const auto partName = "Part " + juce::String(part + 1).paddedLeft('0', 2);
    return {
        { (partName + " Bank Select CC0 = " + juce::String(p.cc0)).toStdString(),
          { uint8_t(0xb0 | channel), 0x00, uint8_t(p.cc0 & 0x7f) } },
        { (partName + " Program Change = " + juce::String(p.pc) + " " + p.name).toStdString(),
          { uint8_t(0xc0 | channel), uint8_t((p.pc - 1) & 0x7f) } },
    };
}

std::vector<Message> ProgramSetup::allMessages() const
{
    std::vector<Message> out;
    for (int i = 0; i < numParts; ++i)
        for (auto& m : partMessages(i)) out.push_back(m);
    return out;
}

juce::String ProgramSetup::programText(int part) const
{
    const int index = parts[size_t(part)];
    return index < 0 ? juce::String("Off") : list.programs[size_t(index)].name;
}

juce::var ProgramSetup::toVar(const juce::String& title) const
{
    auto* root = new juce::DynamicObject();
    root->setProperty("format", "SC88 Sysex Toolbox Programs");
    root->setProperty("version", 1);
    root->setProperty("name", title);
    juce::Array<juce::var> partList;
    for (int i = 0; i < numParts; ++i) {
        auto* part = new juce::DynamicObject();
        part->setProperty("part", i + 1);
        const int index = parts[size_t(i)];
        if (index < 0) {
            part->setProperty("off", true);
        } else {
            const auto& p = list.programs[size_t(index)];
            part->setProperty("pc", p.pc);
            part->setProperty("cc0", p.cc0);
            part->setProperty("name", p.name);
            if (p.drumSet) part->setProperty("drumSet", true);
        }
        partList.add(juce::var(part));
    }
    root->setProperty("parts", partList);
    return juce::var(root);
}

int ProgramSetup::fromVar(const juce::var& root)
{
    int missing = 0;
    if (auto* arr = root["parts"].getArray())
        for (auto& p : *arr) {
            const int part = int(p["part"]) - 1;
            if (part < 0 || part >= numParts) continue;
            if (bool(p["off"]) || !p.hasProperty("pc")) {
                parts[size_t(part)] = off;
                continue;
            }
            int index = list.find(int(p["pc"]), int(p["cc0"]), bool(p["drumSet"]));
            if (index < 0) ++missing;
            parts[size_t(part)] = index;
        }
    return missing;
}

} // namespace sc88
