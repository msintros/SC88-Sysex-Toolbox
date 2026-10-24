#pragma once

#include <JuceHeader.h>

#include <functional>

namespace sc88::ui {

// Shared drawing for the front-panel parts.
namespace Draw {
    void panel(juce::Graphics&, juce::Rectangle<float>, juce::Colour top, juce::Colour bottom);
    // Rounded trough that holds keys, as on the 88emu panel.
    void well(juce::Graphics&, juce::Rectangle<float>);
    // Orange section tag with dark text.
    void tag(juce::Graphics&, juce::Rectangle<float>, const juce::String& text);
    void label(juce::Graphics&, juce::Rectangle<float>, const juce::String& text,
               juce::Justification = juce::Justification::centred, float height = 11.0f);
    void led(juce::Graphics&, juce::Point<float> centre, float radius, bool on);
}

// Light grey rectangular key with an optional triangle glyph or caption.
class KeyButton : public juce::Button {
public:
    enum class Glyph { none, left, right };

    explicit KeyButton(Glyph glyph = Glyph::none, const juce::String& caption = {});
    void paintButton(juce::Graphics&, bool highlighted, bool down) override;

    static void drawKey(juce::Graphics&, juce::Rectangle<float>, bool highlighted, bool down, bool enabled,
                        Glyph glyph = Glyph::none, const juce::String& caption = {});

private:
    Glyph glyph;
    juce::String caption;
};

// Two keys in a well: step down / step up, repeating while held.
class ArrowPair : public juce::Component {
public:
    ArrowPair();
    std::function<void(int direction)> onStep;
    void setRepeatInterval(int ms);
    void paint(juce::Graphics&) override;
    void resized() override;

private:
    KeyButton down { KeyButton::Glyph::left }, up { KeyButton::Glyph::right };
};

// Domed round button in a dark bezel (ALL / MUTE on the hardware panel).
class RoundButton : public juce::Button {
public:
    RoundButton() : juce::Button({}) {}
    void paintButton(juce::Graphics&, bool highlighted, bool down) override;
};

// Page selector key: label above, key below, LED lit while the page is shown.
class PageKey : public juce::Button {
public:
    explicit PageKey(const juce::String& label);
    void paintButton(juce::Graphics&, bool highlighted, bool down) override;
};

} // namespace sc88::ui
