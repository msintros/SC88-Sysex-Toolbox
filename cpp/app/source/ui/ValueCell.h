#pragma once

#include "AppState.h"
#include "Controls.h"
#include "Lcd.h"

namespace sc88::ui {

// What a value cell edits. The functions read and write AppState directly,
// so a cell always shows the current part / effect without being rebuilt.
struct CellBinding {
    std::function<juce::String()> name;
    std::function<juce::String()> display;
    std::function<void(int direction)> step;
    std::function<std::vector<Message>()> messages;
    // Optional. A cell without messages is a selector: it changes what the
    // page shows instead of sending MIDI.
    std::function<bool()> visible;
    std::function<void()> clicked; // the LCD was clicked (e.g. open a menu)
};

// Writes the messages to a MIDI file in the drag cache and starts an
// external drag of it, so it can be dropped into Finder or a DAW.
void dragMidiOut(AppState&, const juce::String& label, const juce::String& scope,
                 const std::vector<Message>& messages, juce::Component* source);

// Label above, LCD value and arrow keys below. Stepping sends the change at
// once; dragging the LCD exports this parameter as a MIDI file.
class ValueCell : public juce::Component {
public:
    ValueCell(AppState&, CellBinding);

    void refresh();
    // Called after the value changed through the arrow keys.
    std::function<void()> onChanged;
    bool isSelector() const { return !binding.messages; }
    const CellBinding& getBinding() const { return binding; }

    void paint(juce::Graphics&) override;
    void resized() override;
    void mouseDown(const juce::MouseEvent&) override;
    void mouseDrag(const juce::MouseEvent&) override;
    void mouseUp(const juce::MouseEvent&) override;
    void mouseMove(const juce::MouseEvent&) override;

private:
    AppState& state;
    CellBinding binding;
    Lcd value;
    ArrowPair arrows;
    bool dragStarted = false;

    juce::Rectangle<int> labelArea() const;
};

} // namespace sc88::ui
