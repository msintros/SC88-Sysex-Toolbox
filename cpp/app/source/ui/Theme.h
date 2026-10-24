#pragma once

#include <JuceHeader.h>

namespace sc88::ui {

// Colours and fonts for the 88emu-style front panel.
namespace Theme {
    // Panels
    inline const juce::Colour panelTop { 0xff434b5b };
    inline const juce::Colour panelBottom { 0xff343b48 };
    inline const juce::Colour lowerPanelTop { 0xff3a4250 };
    inline const juce::Colour lowerPanelBottom { 0xff2c323d };
    inline const juce::Colour bevelLight { 0xff5d6779 };
    inline const juce::Colour bevelDark { 0xff1a1e25 };
    inline const juce::Colour well { 0xff1d2129 };

    // Keys and buttons
    inline const juce::Colour keyTop { 0xffeceef1 };
    inline const juce::Colour keyBottom { 0xffa7acb5 };
    inline const juce::Colour keyPressedTop { 0xffb4b9c2 };
    inline const juce::Colour keyPressedBottom { 0xff8a909a };
    inline const juce::Colour keyBorder { 0xff4c525c };
    inline const juce::Colour keyGlyph { 0xff2a2f38 };

    // Text and accents
    inline const juce::Colour label { 0xffe8ebf0 };
    inline const juce::Colour labelDim { 0xffaab2c0 };
    inline const juce::Colour accent { 0xfff26a1b };
    inline const juce::Colour accentText { 0xff2a1608 };
    inline const juce::Colour ledOn { 0xffff7a1f };
    inline const juce::Colour ledOff { 0xff4a3a30 };

    // LCD: the same orange as the Python app's value fields.
    inline const juce::Colour lcdBack { 0xffff6a00 };
    inline const juce::Colour lcdLit { 0xff1e0c00 };
    inline const juce::Colour lcdUnlit { 0x1f000000 };
    inline const juce::Colour lcdBezel { 0xff16191f };

    juce::Font labelFont(float height);
    juce::Font boldFont(float height);
}

} // namespace sc88::ui
