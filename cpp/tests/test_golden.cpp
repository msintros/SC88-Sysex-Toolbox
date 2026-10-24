// Checks the C++ core against vectors generated from the Python app by
// tools/make_golden.py: every display string and SysEx byte must match.

#include "sc88/Patch.h"

#include <catch2/catch_test_macros.hpp>
#include <nlohmann/json.hpp>

#include <fstream>

using namespace sc88;
using nlohmann::json;

namespace {

const Tables& tables()
{
    static const Tables t = Tables::fromFiles(SC88_DATA_ROOT "/data/parameter_pages.json",
                                              SC88_DATA_ROOT "/data/part_params.json",
                                              SC88_DATA_ROOT "/efx.json");
    return t;
}

const json& golden()
{
    static const json g = [] {
        std::ifstream in(SC88_GOLDEN);
        return json::parse(in);
    }();
    return g;
}

Group group(const json& j) { return j.at("group").get<std::string>() == "A" ? Group::A : Group::B; }

} // namespace

TEST_CASE("System-wide pages match the Python app")
{
    Patch patch(tables());
    for (const auto& v : golden()["generic"]) {
        int page = tables().pageIndex(v["page"]);
        int index = v["index"], raw = v["raw"];
        const auto& p = tables().pages[size_t(page)].params[size_t(index)];
        INFO(v.dump());
        CHECK(formatValue(p, raw) == v["display"].get<std::string>());
        patch.setPageValue(page, index, raw);
        CHECK(toHex(patch.pageParamMessage(page, index).bytes) == v["hex"].get<std::string>());
    }
}

TEST_CASE("Stepping matches the Python app")
{
    for (const auto& v : golden()["steps"]) {
        const auto& p = tables().page(v["page"]).params[v["index"].get<size_t>()];
        INFO(v.dump());
        CHECK(stepValue(p, v["raw"], v["direction"]) == v["result"].get<int>());
    }
}

TEST_CASE("Part parameters match the Python app")
{
    Patch patch(tables());
    for (const auto& v : golden()["part"]) {
        Group g = group(v);
        int part = v["part"], cat = tables().categoryIndex(v["category"]), index = v["index"], raw = v["raw"];
        const auto& params = tables().partCategories[size_t(cat)].params;
        const auto& p = params[size_t(index)];
        INFO(v.dump());
        CHECK(formatValue(p, raw) == v["display"].get<std::string>());

        if (p.isTonePair()) {
            for (size_t i = 0; i < params.size(); ++i)
                if (params[i].isTonePair()) patch.setPartValue(g, part, cat, int(i), v["pair_other"]);
        }
        patch.setPartValue(g, part, cat, index, raw);
        CHECK(toHex(patch.partParamMessage(g, part, cat, index).bytes) == v["hex"].get<std::string>());
    }
}

TEST_CASE("Part defaults match the Python app")
{
    Patch patch(tables());
    for (const auto& v : golden()["part_defaults"]) {
        int part = v["part"];
        for (const auto& [category, values] : v["values"].items()) {
            int cat = tables().categoryIndex(category);
            for (size_t i = 0; i < values.size(); ++i) {
                INFO(category << " part " << part << " param " << i);
                CHECK(patch.partValue(Group::A, part, cat, int(i)) == values[i].get<int>());
            }
        }
    }
}

TEST_CASE("Scale tuning, EFX assign and system match the Python app")
{
    Patch patch(tables());
    for (const auto& v : golden()["scale_tune"]) {
        INFO(v.dump());
        CHECK(formatScaleTune(v["raw"]) == v["display"].get<std::string>());
        patch.setScaleTune(group(v), v["part"], v["note"], v["raw"]);
        CHECK(toHex(patch.scaleTuneMessage(group(v), v["part"], v["note"]).bytes) == v["hex"].get<std::string>());
    }
    for (const auto& v : golden()["efx_assign"]) {
        INFO(v.dump());
        patch.setEfxAssigned(group(v), v["part"], v["enabled"]);
        CHECK(toHex(patch.efxAssignMessage(group(v), v["part"]).bytes) == v["hex"].get<std::string>());
    }
    for (const auto& v : golden()["system"]) {
        INFO(v.dump());
        if (v["kind"] == "mode") {
            patch.setSystemMode(v["value"]);
            CHECK(toHex(patch.systemModeMessage().bytes) == v["hex"].get<std::string>());
        } else {
            patch.setBlockPort(v["block"], v["value"]);
            CHECK(toHex(patch.blockPortMessage(v["block"]).bytes) == v["hex"].get<std::string>());
        }
    }
    CHECK(toHex(gsReset()) == golden()["gs_reset"].get<std::string>());
}

TEST_CASE("Insertion effects match the Python app")
{
    Patch patch(tables());
    REQUIRE(tables().efxTypes.size() == golden()["efx"].size());
    for (const auto& v : golden()["efx"]) {
        int type = v["type"];
        patch.setEfxType(type);
        const auto& def = tables().efxTypes[size_t(type)];
        INFO("EFX type " << type << " " << def.name);
        CHECK(def.displayName == v["display_name"].get<std::string>());
        CHECK(toHex(patch.efxTypeMessage().bytes) == v["type_hex"].get<std::string>());

        auto messages = patch.efxMessages();
        REQUIRE(messages.size() == v["params"].size() + 1);
        size_t m = 1;
        for (const auto& p : v["params"]) {
            int index = p["index"];
            INFO(p.dump());
            CHECK(patch.efxParam(index) == p["raw"].get<int>());
            CHECK(toHex(messages[m++].bytes) == p["hex"].get<std::string>());
            CHECK(stepEfxValue(def.params[size_t(index)], p["raw"], +1) == p["step_up"].get<int>());
            CHECK(stepEfxValue(def.params[size_t(index)], p["raw"], -1) == p["step_down"].get<int>());
        }
    }
}
