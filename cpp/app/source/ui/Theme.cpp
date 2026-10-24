#include "Theme.h"
#include "BinaryData.h"

namespace sc88::ui::Theme {

static juce::Typeface::Ptr medium()
{
    static auto t = juce::Typeface::createSystemTypefaceFor(BinaryData::InterMedium_ttf, BinaryData::InterMedium_ttfSize);
    return t;
}

static juce::Typeface::Ptr semiBold()
{
    static auto t = juce::Typeface::createSystemTypefaceFor(BinaryData::InterSemiBold_ttf, BinaryData::InterSemiBold_ttfSize);
    return t;
}

juce::Font labelFont(float height) { return juce::Font(juce::FontOptions(medium()).withHeight(height)); }
juce::Font boldFont(float height) { return juce::Font(juce::FontOptions(semiBold()).withHeight(height)); }

} // namespace sc88::ui::Theme
