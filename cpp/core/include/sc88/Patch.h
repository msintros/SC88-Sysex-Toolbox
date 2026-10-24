#pragma once

#include "sc88/Tables.h"

#include <array>
#include <string>
#include <vector>

namespace sc88 {

// One SysEx message plus a human-readable label for copy/export.
struct Message {
    std::string label;
    Bytes bytes;
};

enum class ResetKind { GsReset, GmSystemOn };

// The editor's complete state: every value the user can set, and the
// messages that reproduce it on the SC-88 Pro.
class Patch {
public:
    explicit Patch(const Tables& tables);

    const Tables& tables() const { return t; }

    // Puts every value where the SC-88 Pro puts it on receiving the reset, per
    // the owner's manual parameter map: factory defaults, EFX type Thru, and
    // Rx NRPN / Rx Bank Select on for GS Reset and off for GM System On.
    // System parameters (mode, block ports) and Tone Map-0 Number are not
    // affected by either reset, so they are left alone.
    void reset(ResetKind kind);

    // System-wide parameter pages (Reverb, Chorus, Delay, EQ, Global).
    int pageValue(int page, int param) const;
    void setPageValue(int page, int param, int raw);
    Message pageParamMessage(int page, int param) const;
    std::vector<Message> pageMessages(int page) const;

    // Part parameters. partNumber is 1..16.
    int partValue(Group g, int partNumber, int category, int param) const;
    void setPartValue(Group g, int partNumber, int category, int param, int raw);
    Message partParamMessage(Group g, int partNumber, int category, int param) const;
    std::vector<Message> partCategoryMessages(Group g, int partNumber, int category) const;

    // Scale tuning, 12 notes per part, raw 00H..7FH around 40H.
    int scaleTune(Group g, int partNumber, int note) const;
    void setScaleTune(Group g, int partNumber, int note, int raw);
    Message scaleTuneMessage(Group g, int partNumber, int note) const;
    std::vector<Message> scaleTuneMessages(Group g, int partNumber) const;

    // Insertion EFX on/off per part.
    bool efxAssigned(Group g, int partNumber) const;
    void setEfxAssigned(Group g, int partNumber, bool on);
    Message efxAssignMessage(Group g, int partNumber) const;
    std::vector<Message> efxAssignMessages() const;

    // System mode (0 = Mode 1 / Single, 1 = Mode 2 / Double) and the
    // receive port (0 = A, 1 = B) for each of the 32 blocks.
    int systemMode() const { return mode; }
    void setSystemMode(int value) { mode = value; }
    int blockPort(int block) const { return blockPorts.at(static_cast<size_t>(block)); }
    void setBlockPort(int block, int port) { blockPorts.at(static_cast<size_t>(block)) = port; }
    Message systemModeMessage() const;
    Message blockPortMessage(int block) const;
    std::vector<Message> systemMessages() const;

    // Insertion effect type and its 20 parameters. Changing the type
    // resets the parameters to that type's defaults.
    int efxType() const { return efxTypeIndex; }
    void setEfxType(int typeIndex);
    int efxParam(int index) const { return efxParams.at(static_cast<size_t>(index)); }
    void setEfxParam(int index, int raw) { efxParams.at(static_cast<size_t>(index)) = raw; }
    std::string efxParamDisplay(int index) const;
    Message efxTypeMessage() const;
    Message efxParamMessage(int index) const;
    std::vector<Message> efxMessages() const; // type + every used parameter

private:
    using CategoryValues = std::vector<std::vector<int>>; // [category][param]

    const Tables& t;
    std::vector<std::vector<int>> pageValues;
    std::array<std::array<CategoryValues, 16>, 2> partValues;
    std::array<std::array<std::array<int, 12>, 16>, 2> scaleValues;
    std::array<std::array<bool, 16>, 2> efxOn {};
    int mode = 0;
    std::array<int, 32> blockPorts {};
    int efxTypeIndex = 0; // Thru, the power-on and reset default
    std::array<int, 20> efxParams {};

    void resetPartsAndEffects();

    static size_t gi(Group g) { return g == Group::A ? 0 : 1; }
    static size_t pi(int partNumber) { return static_cast<size_t>(partNumber - 1); }
};

std::string groupPartLabel(Group g, int partNumber); // "A01"

} // namespace sc88
