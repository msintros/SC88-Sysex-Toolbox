#include "sc88/Tables.h"

#include <nlohmann/json.hpp>

#include <cstdlib>
#include <fstream>
#include <sstream>
#include <stdexcept>

namespace sc88 {

using nlohmann::json;

namespace {

ParamDef paramFromJson(const json& j, bool partParam)
{
    ParamDef p;
    p.name = j.at("name").get<std::string>();
    if (partParam) {
        p.area = j.at("area").get<uint8_t>();
        p.offset = j.at("offset").get<uint8_t>();
        p.numericEnumFallback = true;
    } else {
        auto a = j.at("address");
        p.address = { a.at(0).get<uint8_t>(), a.at(1).get<uint8_t>(), a.at(2).get<uint8_t>() };
    }
    p.defaultValue = j.at("default").get<int>();
    p.rawMin = j.value("raw_min", 0);
    p.rawMax = j.value("raw_max", 127);
    if (j.contains("enum")) p.enumLabels = j.at("enum").get<std::vector<std::string>>();
    p.display = displayCodecFromName(j.value("display_codec", std::string {}));
    p.data = dataCodecFromName(j.value("data_codec", std::string {}));
    p.prefix = j.value("prefix", std::string {});
    p.suffix = j.value("suffix", std::string {});
    return p;
}

std::string readFile(const std::filesystem::path& path)
{
    std::ifstream in(path, std::ios::binary);
    if (!in) throw std::runtime_error("Cannot open " + path.string());
    std::ostringstream ss;
    ss << in.rdbuf();
    return ss.str();
}

uint8_t hexByte(const std::string& s, size_t pos)
{
    return static_cast<uint8_t>(std::strtoul(s.substr(pos, 2).c_str(), nullptr, 16));
}

void replaceAll(std::string& s, const std::string& from, const std::string& to)
{
    for (size_t pos = 0; (pos = s.find(from, pos)) != std::string::npos; pos += to.size())
        s.replace(pos, from.size(), to);
}

} // namespace

Tables Tables::fromJson(const std::string& pagesText, const std::string& partsText, const std::string& efxText)
{
    Tables t;

    // Parse into named documents: a range-for over a temporary's at() would dangle.
    const auto pagesDoc = json::parse(pagesText);
    for (const auto& pj : pagesDoc.at("pages")) {
        ParameterPage page { pj.at("id"), pj.at("title"), {} };
        for (const auto& param : pj.at("params")) page.params.push_back(paramFromJson(param, false));
        t.pages.push_back(std::move(page));
    }

    const auto parts = json::parse(partsText);
    for (const auto& cj : parts.at("categories")) {
        PartCategory cat { cj.at("name"), {} };
        for (const auto& param : cj.at("params")) cat.params.push_back(paramFromJson(param, true));
        t.partCategories.push_back(std::move(cat));
    }
    for (const auto& [name, rule] : parts.at("part_defaults").items()) {
        PartDefaultRule r { name, false, {} };
        if (rule.is_string()) r.partMinusOne = rule.get<std::string>() == "part_number_minus_1";
        else
            for (const auto& [part, value] : rule.items()) r.overrides.emplace_back(std::stoi(part), value.get<int>());
        t.partDefaultRules.push_back(std::move(r));
    }

    const auto efxDoc = json::parse(efxText);
    for (const auto& ej : efxDoc.at("efx")) {
        EfxType type;
        type.name = ej.at("name").get<std::string>();
        type.displayName = effectDisplayName(type.name);
        auto hex = ej.at("hex").get<std::string>();
        type.typeMsb = hexByte(hex, 0);
        type.typeLsb = hexByte(hex, 2);
        const auto& params = ej.at("params");
        for (size_t i = 0; i < type.params.size() && i < params.size(); ++i) {
            auto& p = type.params[i];
            p.name = params[i].at(0).get<std::string>();
            p.defaultValue = params[i].at(1).get<int>();
            if (params[i].at(2).is_array()) p.labels = params[i].at(2).get<std::vector<std::string>>();
        }
        t.efxTypes.push_back(std::move(type));
    }
    return t;
}

Tables Tables::fromFiles(const std::filesystem::path& pages, const std::filesystem::path& parts,
                         const std::filesystem::path& efx)
{
    return fromJson(readFile(pages), readFile(parts), readFile(efx));
}

const ParameterPage& Tables::page(const std::string& id) const
{
    return pages.at(static_cast<size_t>(pageIndex(id)));
}

int Tables::pageIndex(const std::string& id) const
{
    for (size_t i = 0; i < pages.size(); ++i)
        if (pages[i].id == id) return static_cast<int>(i);
    throw std::out_of_range("No parameter page " + id);
}

int Tables::categoryIndex(const std::string& name) const
{
    for (size_t i = 0; i < partCategories.size(); ++i)
        if (partCategories[i].name == name) return static_cast<int>(i);
    throw std::out_of_range("No part category " + name);
}

int Tables::partDefault(int category, int index, int partNumber) const
{
    const auto& p = partCategories.at(static_cast<size_t>(category)).params.at(static_cast<size_t>(index));
    for (const auto& rule : partDefaultRules) {
        if (rule.name != p.name) continue;
        if (rule.partMinusOne) return partNumber - 1;
        for (auto [part, value] : rule.overrides)
            if (part == partNumber) return value;
    }
    return p.defaultValue;
}

uint8_t partToBlock(int partNumber)
{
    if (partNumber >= 1 && partNumber <= 9) return static_cast<uint8_t>(partNumber);
    if (partNumber == 10) return 0;
    if (partNumber >= 11 && partNumber <= 16) return static_cast<uint8_t>(partNumber - 1);
    throw std::out_of_range("Part number must be 1..16");
}

static uint8_t groupByte(Group g) { return g == Group::A ? 0x40 : 0x50; }

Address partParamAddress(Group group, int partNumber, const ParamDef& param)
{
    // Both halves of the tone number are sent together starting at 1x00.
    uint8_t offset = param.isTonePair() ? 0x00 : param.offset;
    return { groupByte(group), uint8_t((param.area << 4) | partToBlock(partNumber)), offset };
}

Address scaleTuneAddress(Group group, int partNumber, int noteIndex)
{
    return { groupByte(group), uint8_t(0x10 | partToBlock(partNumber)), uint8_t(0x40 + noteIndex) };
}

Address efxAssignAddress(Group group, int partNumber)
{
    return { groupByte(group), uint8_t(0x40 | partToBlock(partNumber)), 0x22 };
}

std::string effectDisplayName(const std::string& name)
{
    std::string out = name;
    for (const char* arrow : { "→", "⇒", "►", "▶", "›", "➜", "➝" })
        replaceAll(out, arrow, ">");
    if (out.rfind("Cho", 0) == 0 && out.find("Flanger") != std::string::npos) out = "Cho > Flanger";
    return out;
}

int stepEfxValue(const EfxParam& param, int raw, int direction)
{
    std::vector<int> valid;
    for (size_t i = 0; i < param.labels.size(); ++i)
        if (!param.labels[i].empty()) valid.push_back(static_cast<int>(i));
    if (valid.empty()) return raw;

    // Snap a non-canonical value to the nearest legal one (first on ties).
    size_t pos = 0;
    for (size_t i = 1; i < valid.size(); ++i)
        if (std::abs(valid[i] - raw) < std::abs(valid[pos] - raw)) pos = i;

    const auto n = static_cast<long>(valid.size());
    long next = ((static_cast<long>(pos) + direction) % n + n) % n;
    return valid[static_cast<size_t>(next)];
}

} // namespace sc88
