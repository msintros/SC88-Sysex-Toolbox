#include "Lcd.h"
#include "LcdFontData.h"
#include "Theme.h"

namespace sc88::ui {

namespace {
constexpr int cellColumns = 6; // 5 dots + 1 gap
constexpr int cellRows = 8;    // 7 dots + 1 gap
constexpr float dotFill = 0.84f;
constexpr float padSteps = 1.6f;
} // namespace

Lcd::Lcd() { setInterceptsMouseClicks(false, false); }

void Lcd::setLines(const juce::StringArray& newLines)
{
    if (newLines == lines) return;
    lines = newLines;
    repaint();
}

void Lcd::drawBackground(juce::Graphics& g, juce::Rectangle<float> area)
{
    const float corner = juce::jmin(4.0f, area.getHeight() * 0.18f);
    g.setColour(Theme::lcdBezel);
    g.fillRoundedRectangle(area, corner + 1.0f);

    auto glass = area.reduced(juce::jmax(1.5f, area.getHeight() * 0.06f));
    juce::ColourGradient backlight(Theme::lcdBack.brighter(0.08f), glass.getCentreX(), glass.getY(),
                                   Theme::lcdBack.darker(0.08f), glass.getCentreX(), glass.getBottom(), false);
    g.setGradientFill(backlight);
    g.fillRoundedRectangle(glass, corner * 0.6f);

    // A thin shadow along the top edge reads as glass set into the panel.
    g.setColour(juce::Colours::black.withAlpha(0.18f));
    g.drawHorizontalLine(int(glass.getY()) + 1, glass.getX() + 2, glass.getRight() - 2);
}

void Lcd::drawText(juce::Graphics& g, juce::Point<float> topLeft, const juce::String& text, float pitch,
                   int columns, juce::Colour lit, juce::Colour unlit)
{
    const float dot = pitch * dotFill;
    for (int col = 0; col < columns; ++col) {
        auto ch = col < text.length() ? text[col] : juce::juce_wchar(' ');
        if (ch > 255) ch = '?';
        const auto& glyph = kLcdFont[ch];
        const float x0 = topLeft.x + float(col * cellColumns) * pitch;
        for (int row = 0; row < 7; ++row)
            for (int bit = 0; bit < 5; ++bit) {
                bool on = (glyph[row] >> (4 - bit)) & 1;
                if (!on && unlit.isTransparent()) continue;
                g.setColour(on ? lit : unlit);
                g.fillRect(x0 + float(bit) * pitch, topLeft.y + float(row) * pitch, dot, dot);
            }
    }
}

void Lcd::paint(juce::Graphics& g)
{
    auto area = getLocalBounds().toFloat();
    drawBackground(g, area);

    const float pad = padSteps * dotPitch + juce::jmax(1.5f, area.getHeight() * 0.06f);
    auto inner = area.reduced(pad);
    const int columns = juce::jmax(1, int((inner.getWidth() + dotPitch) / (cellColumns * dotPitch)));
    const int rows = juce::jmax(1, int((inner.getHeight() + dotPitch) / (cellRows * dotPitch)));

    // Centre the character grid inside the glass.
    const float gridW = float(columns * cellColumns - 1) * dotPitch;
    const float gridH = float(rows * cellRows - 1) * dotPitch;
    const float x = inner.getX() + (inner.getWidth() - gridW) * 0.5f;
    float y = inner.getY() + (inner.getHeight() - gridH) * 0.5f;

    for (int r = 0; r < rows; ++r, y += cellRows * dotPitch) {
        auto text = r < lines.size() ? lines[r] : juce::String();
        auto unlit = fillWithCells ? Theme::lcdUnlit : juce::Colours::transparentBlack;
        drawText(g, { x, y }, text, dotPitch, fillWithCells ? columns : juce::jmin(columns, text.length()),
                 Theme::lcdLit, unlit);
    }
}

} // namespace sc88::ui
