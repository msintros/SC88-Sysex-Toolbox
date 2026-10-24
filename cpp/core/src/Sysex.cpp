#include "sc88/Sysex.h"

#include <cstdio>

namespace sc88 {

uint8_t rolandChecksum(const Address& address, const Bytes& data)
{
    unsigned sum = 0;
    for (auto b : address) sum += b;
    for (auto b : data) sum += b;
    return static_cast<uint8_t>((128 - (sum % 128)) % 128);
}

Bytes makeDT1(const Address& address, const Bytes& data)
{
    Bytes out { 0xF0, 0x41, 0x10, 0x42, 0x12 };
    out.insert(out.end(), address.begin(), address.end());
    out.insert(out.end(), data.begin(), data.end());
    out.push_back(rolandChecksum(address, data));
    out.push_back(0xF7);
    return out;
}

Bytes withoutFraming(const Bytes& message)
{
    if (message.size() >= 2 && message.front() == 0xF0 && message.back() == 0xF7)
        return Bytes(message.begin() + 1, message.end() - 1);
    return message;
}

std::string toHex(const Bytes& bytes)
{
    std::string out;
    out.reserve(bytes.size() * 3);
    char buf[4];
    for (size_t i = 0; i < bytes.size(); ++i) {
        std::snprintf(buf, sizeof buf, i ? " %02X" : "%02X", bytes[i]);
        out += buf;
    }
    return out;
}

Bytes gsReset() { return makeDT1({ 0x40, 0x00, 0x7F }, { 0x00 }); }

Bytes gmSystemOn() { return { 0xF0, 0x7E, 0x7F, 0x09, 0x01, 0xF7 }; }

} // namespace sc88
