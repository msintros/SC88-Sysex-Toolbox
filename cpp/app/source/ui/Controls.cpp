#include "Controls.h"
#include "Theme.h"

namespace sc88::ui {

// ---- Drawing helpers --------------------------------------------------------

void Draw::panel(juce::Graphics& g, juce::Rectangle<float> r, juce::Colour top, juce::Colour bottom)
{
    g.setGradientFill(juce::ColourGradient(top, r.getX(), r.getY(), bottom, r.getX(), r.getBottom(), false));
    g.fillRect(r);
    g.setColour(Theme::bevelLight.withAlpha(0.7f));
    g.fillRect(r.withHeight(1.0f));
    g.setColour(Theme::bevelDark);
    g.fillRect(r.withTop(r.getBottom() - 2.0f));
}

void Draw::well(juce::Graphics& g, juce::Rectangle<float> r)
{
    const float corner = r.getHeight() * 0.5f;
    // Highlight on the lower lip, then the trough with an inner shadow on top.
    g.setColour(Theme::bevelLight.withAlpha(0.55f));
    g.fillRoundedRectangle(r.translated(0, 1.0f), corner);
    g.setColour(Theme::well);
    g.fillRoundedRectangle(r, corner);
    juce::ColourGradient shade(juce::Colours::black.withAlpha(0.45f), r.getX(), r.getY(),
                               juce::Colours::transparentBlack, r.getX(), r.getY() + r.getHeight() * 0.45f, false);
    g.setGradientFill(shade);
    g.fillRoundedRectangle(r, corner);
}

void Draw::tag(juce::Graphics& g, juce::Rectangle<float> r, const juce::String& text)
{
    g.setColour(Theme::accent);
    g.fillRoundedRectangle(r, 3.0f);
    g.setColour(Theme::accentText);
    g.setFont(Theme::boldFont(juce::jmin(11.0f, r.getHeight() * 0.68f)));
    g.drawText(text, r, juce::Justification::centred, false);
}

void Draw::label(juce::Graphics& g, juce::Rectangle<float> r, const juce::String& text, juce::Justification just,
                 float height)
{
    g.setColour(Theme::label);
    g.setFont(Theme::labelFont(height).withExtraKerningFactor(0.04f));
    g.drawFittedText(text, r.toNearestInt(), just, 1, 0.8f);
}

void Draw::led(juce::Graphics& g, juce::Point<float> c, float radius, bool on)
{
    auto r = juce::Rectangle<float>(radius * 2, radius * 2).withCentre(c);
    if (on) {
        g.setColour(Theme::ledOn.withAlpha(0.35f));
        g.fillEllipse(r.expanded(radius * 0.9f));
    }
    g.setColour(on ? Theme::ledOn : Theme::ledOff);
    g.fillEllipse(r);
    g.setColour(juce::Colours::white.withAlpha(on ? 0.5f : 0.12f));
    g.fillEllipse(r.reduced(radius * 0.45f).translated(-radius * 0.2f, -radius * 0.25f));
}

// ---- KeyButton --------------------------------------------------------------

KeyButton::KeyButton(Glyph g, const juce::String& captionText) : juce::Button(captionText), glyph(g), caption(captionText) {}

void KeyButton::paintButton(juce::Graphics& g, bool highlighted, bool down)
{
    drawKey(g, getLocalBounds().toFloat(), highlighted, down, isEnabled(), glyph, caption);
}

void KeyButton::drawKey(juce::Graphics& g, juce::Rectangle<float> bounds, bool highlighted, bool down, bool enabled,
                        Glyph glyph, const juce::String& caption)
{
    auto r = bounds.reduced(1.0f);
    const float corner = juce::jmin(3.0f, r.getHeight() * 0.2f);

    // Drop shadow under the key, gone while pressed.
    if (!down) {
        g.setColour(juce::Colours::black.withAlpha(0.5f));
        g.fillRoundedRectangle(r.translated(0, 1.2f), corner);
    }
    auto face = down ? r.translated(0, 0.8f) : r;
    auto top = down ? Theme::keyPressedTop : Theme::keyTop;
    auto bottom = down ? Theme::keyPressedBottom : Theme::keyBottom;
    if (highlighted && !down) top = top.brighter(0.04f);
    if (!enabled) { top = top.darker(0.5f); bottom = bottom.darker(0.5f); }
    g.setGradientFill(juce::ColourGradient(top, face.getX(), face.getY(), bottom, face.getX(), face.getBottom(), false));
    g.fillRoundedRectangle(face, corner);
    g.setColour(Theme::keyBorder);
    g.drawRoundedRectangle(face, corner, 0.8f);
    g.setColour(juce::Colours::white.withAlpha(0.55f));
    g.drawHorizontalLine(int(face.getY() + 1.5f), face.getX() + corner, face.getRight() - corner);

    g.setColour(Theme::keyGlyph);
    if (glyph != Glyph::none) {
        const float h = juce::jmin(face.getHeight() * 0.42f, 9.0f);
        auto c = face.getCentre();
        juce::Path tri;
        if (glyph == Glyph::left)
            tri.addTriangle(c.x - h * 0.45f, c.y, c.x + h * 0.45f, c.y - h * 0.5f, c.x + h * 0.45f, c.y + h * 0.5f);
        else
            tri.addTriangle(c.x + h * 0.45f, c.y, c.x - h * 0.45f, c.y - h * 0.5f, c.x - h * 0.45f, c.y + h * 0.5f);
        g.fillPath(tri);
    } else if (caption.isNotEmpty()) {
        g.setFont(Theme::boldFont(juce::jmin(11.0f, face.getHeight() * 0.5f)));
        g.drawFittedText(caption, face.toNearestInt().reduced(4, 0), juce::Justification::centred, 1, 0.75f);
    }
}

// ---- ArrowPair --------------------------------------------------------------

ArrowPair::ArrowPair()
{
    for (auto* b : { &down, &up }) {
        addAndMakeVisible(b);
        b->setRepeatSpeed(420, 95);
        b->setWantsKeyboardFocus(false);
    }
    down.onClick = [this] { if (onStep) onStep(-1); };
    up.onClick = [this] { if (onStep) onStep(+1); };
}

void ArrowPair::setRepeatInterval(int ms)
{
    for (auto* b : { &down, &up }) b->setRepeatSpeed(420, ms);
}

void ArrowPair::paint(juce::Graphics& g) { Draw::well(g, getLocalBounds().toFloat()); }

void ArrowPair::resized()
{
    auto r = getLocalBounds().reduced(int(getHeight() * 0.38f), 3);
    auto half = r.getWidth() / 2;
    down.setBounds(r.removeFromLeft(half));
    up.setBounds(r);
}

// ---- RoundButton ------------------------------------------------------------

void RoundButton::paintButton(juce::Graphics& g, bool highlighted, bool down)
{
    auto r = getLocalBounds().toFloat();
    auto size = juce::jmin(r.getWidth(), r.getHeight());
    auto bezel = juce::Rectangle<float>(size, size).withCentre(r.getCentre()).reduced(1.0f);

    g.setColour(Theme::bevelLight.withAlpha(0.5f));
    g.fillEllipse(bezel.translated(0, 1.0f));
    g.setColour(juce::Colour(0xff15181e));
    g.fillEllipse(bezel);

    auto dome = bezel.reduced(size * 0.12f);
    if (down) dome = dome.reduced(0.6f).translated(0, 0.6f);
    auto light = down ? juce::Colour(0xffb8bcc4) : juce::Colour(0xffdcdfe4);
    auto dark = down ? juce::Colour(0xff6f7480) : juce::Colour(0xff8c919b);
    if (highlighted && !down) light = light.brighter(0.05f);
    juce::ColourGradient grad(light, dome.getX() + dome.getWidth() * 0.35f, dome.getY() + dome.getHeight() * 0.25f,
                              dark, dome.getRight(), dome.getBottom(), true);
    g.setGradientFill(grad);
    g.fillEllipse(dome);
    g.setColour(juce::Colours::black.withAlpha(0.35f));
    g.drawEllipse(dome, 0.8f);
}

// ---- PageKey ----------------------------------------------------------------

PageKey::PageKey(const juce::String& label) : juce::Button(label)
{
    setClickingTogglesState(false);
}

void PageKey::paintButton(juce::Graphics& g, bool highlighted, bool down)
{
    auto r = getLocalBounds().toFloat();
    auto labelArea = r.removeFromTop(r.getHeight() * 0.42f);
    g.setColour(getToggleState() ? Theme::label : Theme::labelDim);
    g.setFont(Theme::labelFont(juce::jmin(10.5f, labelArea.getHeight() * 0.8f)).withExtraKerningFactor(0.03f));
    g.drawFittedText(getButtonText(), labelArea.toNearestInt(), juce::Justification::centred, 1, 0.7f);

    // Key face, with an LED in its left end showing the current page.
    auto key = r.reduced(2.0f, 1.0f);
    KeyButton::drawKey(g, key, highlighted, down, isEnabled());
    Draw::led(g, { key.getX() + 9.0f, key.getCentreY() + (down ? 0.8f : 0.0f) }, 2.6f, getToggleState());
}

} // namespace sc88::ui
