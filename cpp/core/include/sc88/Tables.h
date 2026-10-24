#pragma once

#include "sc88/Param.h"

#include <array>
#include <filesystem>
#include <string>
#include <vector>

namespace sc88 {

enum class Group { A, B };

// System-wide parameter page (Reverb, Chorus, Delay, EQ, Global).
struct ParameterPage {
    std::string id;
    std::string title;
    std::vector<ParamDef> params;
};

// Part parameter category (Basic, Receive, Tone Modify, ...).
struct PartCategory {
    std::string name;
    std::vector<ParamDef> params;
};

struct EfxParam {
    std::string name;            // empty when the slot is unused
    int defaultValue = 0;
    // Display label per raw byte; an empty label means the byte is not legal.
    std::vector<std::string> labels;

    bool used() const { return !name.empty(); }
};

struct EfxType {
    std::string name;
    std::string displayName;     // arrows normalised to ">" for the LCD font
    uint8_t typeMsb = 0;
    uint8_t typeLsb = 0;
    std::array<EfxParam, 20> params;
};

struct Tables {
    std::vector<ParameterPage> pages;
    std::vector<PartCategory> partCategories;
    std::vector<EfxType> efxTypes;

    // JSON documents as text, so the app can load them from embedded binary data.
    static Tables fromJson(const std::string& parameterPagesJson,
                           const std::string& partParamsJson,
                           const std::string& efxJson);
    static Tables fromFiles(const std::filesystem::path& parameterPages,
                            const std::filesystem::path& partParams,
                            const std::filesystem::path& efx);

    const ParameterPage& page(const std::string& id) const;
    int pageIndex(const std::string& id) const;
    int categoryIndex(const std::string& name) const;

    // Default for a part parameter, including the part-dependent ones
    // (Rx Channel follows the part, part 10 is the rhythm part).
    int partDefault(int category, int index, int partNumber) const;

private:
    struct PartDefaultRule {
        std::string name;
        bool partMinusOne = false;
        std::vector<std::pair<int, int>> overrides; // part number -> value
    };
    std::vector<PartDefaultRule> partDefaultRules;
};

// 1..16 to the SC-88 Pro block nibble: parts 1-9 are 1-9, part 10 is 0, 11-16 are A-F.
uint8_t partToBlock(int partNumber);

Address partParamAddress(Group group, int partNumber, const ParamDef& param);
Address scaleTuneAddress(Group group, int partNumber, int noteIndex);
Address efxAssignAddress(Group group, int partNumber);

std::string effectDisplayName(const std::string& name);

// Next legal raw value for an insertion-effect parameter, wrapping.
int stepEfxValue(const EfxParam& param, int raw, int direction);

} // namespace sc88
