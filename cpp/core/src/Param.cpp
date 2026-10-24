#include "sc88/Param.h"

#include <cstdio>
#include <stdexcept>

namespace sc88 {

namespace {

template <typename... Args>
std::string format(const char* fmt, Args... args)
{
    char buf[64];
    std::snprintf(buf, sizeof buf, fmt, args...);
    return buf;
}

std::string signedWithPlus(int n)
{
    return n > 0 ? format("+%d", n) : format("%d", n);
}

// Roland's Delay Time Center table, raw 01H..73H. Negative means out of range.
double delayTimeCenterMs(int raw)
{
    if (raw >= 0x01 && raw <= 0x14) return raw * 0.1;
    if (raw < 0x01) return -1.0;
    if (raw <= 0x23) return 2.0 + (raw - 0x14) * 0.2;
    if (raw <= 0x2D) return 5.0 + (raw - 0x23) * 0.5;
    if (raw <= 0x37) return 10.0 + (raw - 0x2D) * 1.0;
    if (raw <= 0x46) return 20.0 + (raw - 0x37) * 2.0;
    if (raw <= 0x50) return 50.0 + (raw - 0x46) * 5.0;
    if (raw <= 0x5A) return 100.0 + (raw - 0x50) * 10.0;
    if (raw <= 0x69) return 200.0 + (raw - 0x5A) * 20.0;
    if (raw <= 0x73) return 500.0 + (raw - 0x69) * 50.0;
    return -1.0;
}

std::string formatPan(int raw, const char* centre)
{
    int n = raw - 0x40;
    if (n < 0) return format("L%d", -n);
    if (n > 0) return format("R%d", n);
    return centre;
}

} // namespace

std::string formatValue(const ParamDef& p, int raw)
{
    if (p.isEnum()) {
        if (raw >= 0 && raw < static_cast<int>(p.enumLabels.size()) && !p.enumLabels[raw].empty())
            return p.enumLabels[raw];
        return p.numericEnumFallback ? std::to_string(raw) : "out of range!";
    }

    switch (p.display) {
    case DisplayCodec::Signed64: return signedWithPlus(raw - 64);
    case DisplayCodec::KeyShift: return signedWithPlus(raw - 0x40) + " st";
    case DisplayCodec::BendPitch: return format("%d st", raw - 0x40);
    case DisplayCodec::PartPan: return raw == 0 ? "Random" : formatPan(raw, "Center");
    case DisplayCodec::MasterPan: return formatPan(raw, "0");
    case DisplayCodec::NoteName: {
        static const char* names[] = { "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B" };
        return format("%s%d", names[raw % 12], raw / 12 - 1);
    }
    case DisplayCodec::Program1To128: return std::to_string(raw + 1);
    case DisplayCodec::RxChannel: return raw == 16 ? "Off" : std::to_string(raw + 1);
    case DisplayCodec::FineTune14Bit: {
        double cents = (raw - 0x2000) * (100.0 / 8192.0);
        return format(cents > 0 ? "+%.2f cent" : "%.2f cent", cents);
    }
    case DisplayCodec::MasterTune: {
        double cents = (raw - 0x0400) / 10.0;
        return format(cents > 0 ? "+%.1f cent" : "%.1f cent", cents);
    }
    case DisplayCodec::GainDb: return signedWithPlus(raw - 0x40) + " dB";
    case DisplayCodec::DelayTimeCenter: {
        double ms = delayTimeCenterMs(raw);
        if (ms < 0) return "out of range!";
        if (ms < 10) return format("%.1f ms", ms);
        if (ms == 1000) return "1.0 s";
        return format("%d ms", static_cast<int>(ms));
    }
    case DisplayCodec::DelayRatio: {
        double percent = (raw * 100.0) / 24.0;
        return format("%d%%", static_cast<int>(percent + 0.5));
    }
    case DisplayCodec::Plain: break;
    }
    return p.prefix + std::to_string(raw) + p.suffix;
}

int stepValue(const ParamDef& p, int raw, int direction)
{
    const int count = p.rawMax - p.rawMin + 1;
    if (count <= 0) return raw;
    if (raw < p.rawMin) raw = p.rawMin;
    if (raw > p.rawMax) raw = p.rawMax;
    int pos = ((raw - p.rawMin + direction) % count + count) % count;
    return p.rawMin + pos;
}

Bytes encodeData(const ParamDef& p, int raw)
{
    switch (p.data) {
    case DataCodec::Nibbles4:
        return { uint8_t((raw >> 12) & 0x0F), uint8_t((raw >> 8) & 0x0F),
                 uint8_t((raw >> 4) & 0x0F), uint8_t(raw & 0x0F) };
    case DataCodec::Bits14:
        return { uint8_t((raw >> 7) & 0x7F), uint8_t(raw & 0x7F) };
    case DataCodec::TonePairBank:
    case DataCodec::TonePairProgram:
        throw std::logic_error("Tone pair data is encoded by Patch");
    case DataCodec::Byte: break;
    }
    return { uint8_t(raw & 0x7F) };
}

std::string formatScaleTune(int raw)
{
    return signedWithPlus(raw - 0x40) + " cent";
}

DisplayCodec displayCodecFromName(const std::string& n)
{
    if (n.empty()) return DisplayCodec::Plain;
    if (n == "signed_64") return DisplayCodec::Signed64;
    if (n == "key_shift") return DisplayCodec::KeyShift;
    if (n == "bend_pitch") return DisplayCodec::BendPitch;
    if (n == "part_pan") return DisplayCodec::PartPan;
    if (n == "master_pan") return DisplayCodec::MasterPan;
    if (n == "note_name") return DisplayCodec::NoteName;
    if (n == "program_1_128") return DisplayCodec::Program1To128;
    if (n == "rx_channel") return DisplayCodec::RxChannel;
    if (n == "fine_tune_14bit") return DisplayCodec::FineTune14Bit;
    if (n == "master_tune") return DisplayCodec::MasterTune;
    if (n == "gain_db") return DisplayCodec::GainDb;
    if (n == "delay_time_center") return DisplayCodec::DelayTimeCenter;
    if (n == "delay_ratio") return DisplayCodec::DelayRatio;
    throw std::runtime_error("Unknown display codec: " + n);
}

DataCodec dataCodecFromName(const std::string& n)
{
    if (n.empty()) return DataCodec::Byte;
    if (n == "nibbles4") return DataCodec::Nibbles4;
    if (n == "14bit") return DataCodec::Bits14;
    if (n == "tone_pair_bank") return DataCodec::TonePairBank;
    if (n == "tone_pair_program") return DataCodec::TonePairProgram;
    throw std::runtime_error("Unknown data codec: " + n);
}

} // namespace sc88
