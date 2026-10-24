#pragma once

#include "sc88/Sysex.h"

#include <string>
#include <vector>

namespace sc88 {

// How a raw parameter value is shown to the user.
enum class DisplayCodec {
    Plain,           // prefix + raw + suffix
    Signed64,        // raw - 64, with a leading + for positive values
    KeyShift,        // semitones around 40H
    BendPitch,       // semitones above 40H
    PartPan,         // Random, L63..Center..R63
    MasterPan,       // L63..0..R63
    NoteName,        // C-1..G9
    Program1To128,   // raw + 1
    RxChannel,       // 1..16, Off
    FineTune14Bit,   // cents around 2000H
    MasterTune,      // tenths of a cent around 0400H
    GainDb,          // dB around 40H
    DelayTimeCenter, // Roland's delay time lookup, 0.1 ms..1 s
    DelayRatio,      // percent in 100/24 steps
};

// How a raw value becomes the data bytes of a DT1 message.
enum class DataCodec {
    Byte,
    Nibbles4,        // 16-bit value as four 4-bit bytes (Master Tune)
    Bits14,          // 14-bit value as MSB, LSB
    TonePairBank,    // Tone number: bank + program sent together from offset 00H
    TonePairProgram,
};

struct ParamDef {
    std::string name;

    // Fixed address for system-wide parameters (Reverb, Chorus, ...).
    Address address { 0, 0, 0 };
    // Part parameters are addressed as 4g (a|block) offset instead.
    uint8_t area = 0;
    uint8_t offset = 0;

    int defaultValue = 0;
    int rawMin = 0;
    int rawMax = 127;

    std::vector<std::string> enumLabels;
    // Part parameters show an unlabelled enum value as its number rather
    // than "out of range!", matching the Python app.
    bool numericEnumFallback = false;

    DisplayCodec display = DisplayCodec::Plain;
    DataCodec data = DataCodec::Byte;
    std::string prefix;
    std::string suffix;

    bool isEnum() const { return !enumLabels.empty(); }
    bool isTonePair() const { return data == DataCodec::TonePairBank || data == DataCodec::TonePairProgram; }
};

std::string formatValue(const ParamDef& param, int raw);

// Next legal raw value in the given direction, wrapping at either end.
// A value outside the legal range first snaps to the nearest legal one.
int stepValue(const ParamDef& param, int raw, int direction);

// Data bytes for every codec except the tone pair, which needs both halves
// and is encoded by the patch.
Bytes encodeData(const ParamDef& param, int raw);

// Used by the Scale Tuning page: cents around 40H.
std::string formatScaleTune(int raw);

DisplayCodec displayCodecFromName(const std::string& name);
DataCodec dataCodecFromName(const std::string& name);

} // namespace sc88
