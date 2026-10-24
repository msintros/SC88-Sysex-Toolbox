#pragma once

#include <JuceHeader.h>

namespace sc88::ui {

// Dot-matrix LCD drawn from the 5x7 Roland glyph table. Each character cell
// shows its unlit dots faintly, like the SC-88 Pro and 88emu displays.
class Lcd : public juce::Component {
public:
    Lcd();

    void setLines(const juce::StringArray& newLines);
    void setText(const juce::String& text) { setLines(juce::StringArray(text)); }
    const juce::StringArray& getLines() const { return lines; }

    // Size of one dot step in logical pixels. A character cell is 6 x 8 steps.
    void setDotPitch(float pitch) { dotPitch = pitch; repaint(); }
    float getDotPitch() const { return dotPitch; }

    // Draw a faint frame of unlit cells across the whole display (main LCD)
    // or only behind the text (value fields).
    void setFillWithCells(bool shouldFill) { fillWithCells = shouldFill; repaint(); }

    void paint(juce::Graphics&) override;

    static void drawText(juce::Graphics& g, juce::Point<float> topLeft, const juce::String& text,
                         float pitch, int columns, juce::Colour lit, juce::Colour unlit);
    static void drawBackground(juce::Graphics& g, juce::Rectangle<float> area);

private:
    juce::StringArray lines;
    float dotPitch = 2.2f;
    bool fillWithCells = true;
};

} // namespace sc88::ui
