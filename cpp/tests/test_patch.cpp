// Reset behaviour, checked against the SC-88 Pro owner's manual parameter map.

#include "sc88/Patch.h"

#include <catch2/catch_test_macros.hpp>

using namespace sc88;

namespace {

const Tables& tables()
{
    static const Tables t = Tables::fromFiles(SC88_DATA_ROOT "/data/parameter_pages.json",
                                              SC88_DATA_ROOT "/data/part_params.json",
                                              SC88_DATA_ROOT "/efx.json");
    return t;
}

int param(const char* category, const char* name)
{
    int cat = tables().categoryIndex(category);
    const auto& params = tables().partCategories[size_t(cat)].params;
    for (size_t i = 0; i < params.size(); ++i)
        if (params[i].name == name) return int(i);
    FAIL("No parameter " << name);
    return -1;
}

} // namespace

TEST_CASE("A new patch starts at the power-on defaults")
{
    Patch patch(tables());
    CHECK(patch.efxType() == 0); // Thru
    CHECK(patch.pageValue(tables().pageIndex("reverb"), 0) == 4); // Hall 2
    CHECK(patch.partValue(Group::A, 1, tables().categoryIndex("Mod"), param("Mod", "Mod LFO1 Pitch")) == 0x0A);
    CHECK(patch.blockPort(0) == 0);
    CHECK(patch.blockPort(16) == 1);
}

TEST_CASE("GS Reset restores factory values")
{
    Patch patch(tables());
    const int basic = tables().categoryIndex("Basic");
    const int routing = tables().categoryIndex("Routing");
    const int reverb = tables().pageIndex("reverb");

    patch.setEfxType(5);
    patch.setEfxParam(0, 3);
    patch.setPageValue(reverb, 0, 0);
    patch.setPartValue(Group::B, 10, basic, param("Basic", "Part Level"), 12);
    patch.setPartValue(Group::A, 3, routing, param("Routing", "Tone Map-0 Number"), 1);
    patch.setScaleTune(Group::A, 1, 0, 0x50);
    patch.setEfxAssigned(Group::A, 2, true);
    patch.setSystemMode(1);
    patch.setBlockPort(3, 1);

    patch.reset(ResetKind::GsReset);

    CHECK(patch.efxType() == 0);
    CHECK(patch.pageValue(reverb, 0) == 4);
    CHECK(patch.partValue(Group::B, 10, basic, param("Basic", "Part Level")) == 100);
    CHECK(patch.partValue(Group::B, 10, basic, param("Basic", "Rhythm Part")) == 1);
    CHECK(patch.scaleTune(Group::A, 1, 0) == 0x40);
    CHECK_FALSE(patch.efxAssigned(Group::A, 2));
    CHECK(patch.partValue(Group::A, 1, basic, param("Basic", "Rx Bank Select")) == 1);
    CHECK(patch.partValue(Group::A, 1, tables().categoryIndex("Receive"), param("Receive", "Rx NRPN")) == 1);

    // Not touched by a reset.
    CHECK(patch.partValue(Group::A, 3, routing, param("Routing", "Tone Map-0 Number")) == 1);
    CHECK(patch.systemMode() == 1);
    CHECK(patch.blockPort(3) == 1);
}

TEST_CASE("GM System On turns NRPN and bank select reception off")
{
    Patch patch(tables());
    patch.reset(ResetKind::GmSystemOn);
    CHECK(patch.partValue(Group::A, 5, tables().categoryIndex("Basic"), param("Basic", "Rx Bank Select")) == 0);
    CHECK(patch.partValue(Group::B, 5, tables().categoryIndex("Receive"), param("Receive", "Rx NRPN")) == 0);
    CHECK(patch.efxType() == 0);
}
