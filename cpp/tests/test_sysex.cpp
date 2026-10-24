#include "sc88/Sysex.h"

#include <catch2/catch_test_macros.hpp>

using namespace sc88;

TEST_CASE("GS reset matches the published message")
{
    CHECK(toHex(gsReset()) == "F0 41 10 42 12 40 00 7F 00 41 F7");
}

TEST_CASE("Checksum wraps to zero")
{
    // 40 + 00 + 40 = 80H, so the checksum is (128 - 0) % 128 = 0.
    CHECK(rolandChecksum({ 0x40, 0x00, 0x40 }, {}) == 0);
}

TEST_CASE("Framing is stripped for MIDI APIs")
{
    CHECK(toHex(withoutFraming(gmSystemOn())) == "7E 7F 09 01");
}
