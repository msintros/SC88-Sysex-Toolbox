#pragma once

#include <array>
#include <cstdint>
#include <string>
#include <vector>

namespace sc88 {

using Bytes = std::vector<uint8_t>;
using Address = std::array<uint8_t, 3>;

// Roland DT1 (data set 1) message for the SC-88 Pro: F0 41 10 42 12 <addr> <data> <sum> F7.
// The checksum covers address and data bytes.
Bytes makeDT1(const Address& address, const Bytes& data);

// Payload without the enclosing F0/F7, which is what MIDI APIs usually expect.
Bytes withoutFraming(const Bytes& message);

uint8_t rolandChecksum(const Address& address, const Bytes& data);

// "F0 41 10 42 12 40 00 7F 00 41 F7"
std::string toHex(const Bytes& bytes);

Bytes gsReset();
Bytes gmSystemOn();

} // namespace sc88
