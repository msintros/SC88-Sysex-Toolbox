#include "sc88/Patch.h"

#include <cstdio>

namespace sc88 {

static const char* kNoteNames[12] = { "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B" };

std::string groupPartLabel(Group g, int partNumber)
{
    char buf[8];
    std::snprintf(buf, sizeof buf, "%c%02d", g == Group::A ? 'A' : 'B', partNumber);
    return buf;
}

Patch::Patch(const Tables& tables) : t(tables)
{
    for (const auto& page : t.pages) {
        std::vector<int> values;
        for (const auto& p : page.params) values.push_back(p.defaultValue);
        pageValues.push_back(std::move(values));
    }

    for (auto& group : partValues)
        for (int part = 1; part <= 16; ++part) {
            auto& cats = group[pi(part)];
            cats.resize(t.partCategories.size());
            for (size_t c = 0; c < t.partCategories.size(); ++c)
                for (size_t i = 0; i < t.partCategories[c].params.size(); ++i)
                    cats[c].push_back(t.partDefault(int(c), int(i), part));
        }

    for (auto& group : scaleValues)
        for (auto& part : group) part.fill(0x40);

    for (size_t b = 16; b < 32; ++b) blockPorts[b] = 1;

    if (efxTypeIndex < int(t.efxTypes.size())) setEfxType(efxTypeIndex);
}

// ---- System-wide pages ----------------------------------------------------

int Patch::pageValue(int page, int param) const
{
    return pageValues.at(size_t(page)).at(size_t(param));
}

void Patch::setPageValue(int page, int param, int raw)
{
    pageValues.at(size_t(page)).at(size_t(param)) = raw;
}

Message Patch::pageParamMessage(int page, int param) const
{
    const auto& p = t.pages.at(size_t(page)).params.at(size_t(param));
    return { p.name, makeDT1(p.address, encodeData(p, pageValue(page, param))) };
}

std::vector<Message> Patch::pageMessages(int page) const
{
    std::vector<Message> out;
    for (size_t i = 0; i < t.pages.at(size_t(page)).params.size(); ++i) out.push_back(pageParamMessage(page, int(i)));
    return out;
}

// ---- Part parameters ------------------------------------------------------

int Patch::partValue(Group g, int partNumber, int category, int param) const
{
    return partValues[gi(g)].at(pi(partNumber)).at(size_t(category)).at(size_t(param));
}

void Patch::setPartValue(Group g, int partNumber, int category, int param, int raw)
{
    partValues[gi(g)].at(pi(partNumber)).at(size_t(category)).at(size_t(param)) = raw;
}

Message Patch::partParamMessage(Group g, int partNumber, int category, int param) const
{
    const auto& p = t.partCategories.at(size_t(category)).params.at(size_t(param));
    Bytes data;
    if (p.isTonePair()) {
        // The tone number's bank and program live in the first two Basic slots.
        const auto& cat = t.partCategories.at(size_t(category)).params;
        int bank = 0, program = 0;
        for (size_t i = 0; i < cat.size(); ++i) {
            if (cat[i].data == DataCodec::TonePairBank) bank = partValue(g, partNumber, category, int(i));
            if (cat[i].data == DataCodec::TonePairProgram) program = partValue(g, partNumber, category, int(i));
        }
        data = { uint8_t(bank & 0x7F), uint8_t(program & 0x7F) };
    } else {
        data = encodeData(p, partValue(g, partNumber, category, param));
    }
    return { p.name, makeDT1(partParamAddress(g, partNumber, p), data) };
}

std::vector<Message> Patch::partCategoryMessages(Group g, int partNumber, int category) const
{
    std::vector<Message> out;
    bool sentTonePair = false;
    const auto& params = t.partCategories.at(size_t(category)).params;
    for (size_t i = 0; i < params.size(); ++i) {
        if (params[i].isTonePair()) {
            if (sentTonePair) continue;
            sentTonePair = true;
        }
        out.push_back(partParamMessage(g, partNumber, category, int(i)));
    }
    return out;
}

// ---- Scale tuning -----------------------------------------------------------

int Patch::scaleTune(Group g, int partNumber, int note) const
{
    return scaleValues[gi(g)].at(pi(partNumber)).at(size_t(note));
}

void Patch::setScaleTune(Group g, int partNumber, int note, int raw)
{
    scaleValues[gi(g)].at(pi(partNumber)).at(size_t(note)) = raw;
}

Message Patch::scaleTuneMessage(Group g, int partNumber, int note) const
{
    return { std::string(kNoteNames[note]) + " Scale Tuning",
             makeDT1(scaleTuneAddress(g, partNumber, note), { uint8_t(scaleTune(g, partNumber, note)) }) };
}

std::vector<Message> Patch::scaleTuneMessages(Group g, int partNumber) const
{
    std::vector<Message> out;
    for (int n = 0; n < 12; ++n) out.push_back(scaleTuneMessage(g, partNumber, n));
    return out;
}

// ---- EFX assign -------------------------------------------------------------

bool Patch::efxAssigned(Group g, int partNumber) const { return efxOn[gi(g)].at(pi(partNumber)); }

void Patch::setEfxAssigned(Group g, int partNumber, bool on) { efxOn[gi(g)].at(pi(partNumber)) = on; }

Message Patch::efxAssignMessage(Group g, int partNumber) const
{
    return { groupPartLabel(g, partNumber) + " EFX Assign",
             makeDT1(efxAssignAddress(g, partNumber), { uint8_t(efxAssigned(g, partNumber) ? 1 : 0) }) };
}

std::vector<Message> Patch::efxAssignMessages() const
{
    std::vector<Message> out;
    for (Group g : { Group::A, Group::B })
        for (int part = 1; part <= 16; ++part) out.push_back(efxAssignMessage(g, part));
    return out;
}

// ---- System -----------------------------------------------------------------

Message Patch::systemModeMessage() const
{
    return { "System Mode", makeDT1({ 0x00, 0x00, 0x7F }, { uint8_t(mode) }) };
}

Message Patch::blockPortMessage(int block) const
{
    char label[24];
    std::snprintf(label, sizeof label, "System Block %02X", block);
    return { label, makeDT1({ 0x00, 0x01, uint8_t(block) }, { uint8_t(blockPort(block)) }) };
}

std::vector<Message> Patch::systemMessages() const
{
    std::vector<Message> out { systemModeMessage() };
    for (int b = 0; b < 32; ++b) out.push_back(blockPortMessage(b));
    return out;
}

// ---- Insertion EFX ----------------------------------------------------------

void Patch::setEfxType(int typeIndex)
{
    efxTypeIndex = typeIndex;
    const auto& type = t.efxTypes.at(size_t(typeIndex));
    for (size_t i = 0; i < efxParams.size(); ++i) efxParams[i] = type.params[i].defaultValue;
}

std::string Patch::efxParamDisplay(int index) const
{
    const auto& p = t.efxTypes.at(size_t(efxTypeIndex)).params.at(size_t(index));
    if (!p.used()) return {};
    int raw = efxParam(index);
    if (raw < 0 || raw >= int(p.labels.size()) || p.labels[size_t(raw)].empty()) return "out of range!";
    return p.labels[size_t(raw)];
}

Message Patch::efxTypeMessage() const
{
    const auto& type = t.efxTypes.at(size_t(efxTypeIndex));
    return { "EFX Type", makeDT1({ 0x40, 0x03, 0x00 }, { type.typeMsb, type.typeLsb }) };
}

Message Patch::efxParamMessage(int index) const
{
    const auto& p = t.efxTypes.at(size_t(efxTypeIndex)).params.at(size_t(index));
    return { p.name.empty() ? "EFX Parameter " + std::to_string(index) : p.name,
             makeDT1({ 0x40, 0x03, uint8_t(0x03 + index) }, { uint8_t(efxParam(index) & 0x7F) }) };
}

std::vector<Message> Patch::efxMessages() const
{
    std::vector<Message> out { efxTypeMessage() };
    const auto& type = t.efxTypes.at(size_t(efxTypeIndex));
    for (int i = 0; i < 20; ++i)
        if (type.params[size_t(i)].used()) out.push_back(efxParamMessage(i));
    return out;
}

} // namespace sc88
