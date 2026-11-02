#pragma once

#include <JuceHeader.h>
#include "sc88/Patch.h"

#include <array>
#include <vector>

namespace sc88 {

// One sound the SC-88 Pro can be switched to with Bank Select (CC0) and
// Program Change. Program numbers are 1-128, as printed in the manual.
struct Program {
    juce::String name;
    int pc = 1;
    int cc0 = 0;
    bool drumSet = false;
    int category = 0;
};

struct ProgramCategory {
    juce::String name;
    int first = 0, count = 0; // range in ProgramList::programs
};

// Native map instrument list (manual pp. 154-161) and drum sets (p. 163),
// from data/programs.json. Drum sets are the last category.
class ProgramList {
public:
    static ProgramList fromJson(const juce::String& json);

    std::vector<Program> programs;
    std::vector<ProgramCategory> categories;

    // Index of the program with these numbers, or -1.
    int find(int pc, int cc0, bool drumSet) const;
    int size() const { return int(programs.size()); }
};

// Which program each of the 16 parts plays. Part n is addressed on MIDI
// channel n. A part set to -1 is left alone when sending.
class ProgramSetup {
public:
    static constexpr int numParts = 16;
    static constexpr int off = -1;

    explicit ProgramSetup(const ProgramList&);

    const ProgramList& list;
    std::array<int, numParts> parts {};

    // What the SC-88 Pro sets on GS Reset / GM System On: Piano 1 on every
    // part, STANDARD 1 on part 10.
    void reset();

    // CC0 then Program Change on the part's channel. Empty when the part is off.
    std::vector<Message> partMessages(int part) const;
    std::vector<Message> allMessages() const;

    juce::String programText(int part) const;

    // Saved setup files: JSON with each part's PC, CC0 and name.
    juce::var toVar(const juce::String& title) const;
    // Returns how many parts named a sound not in the list (those are set off).
    int fromVar(const juce::var&);
};

} // namespace sc88
