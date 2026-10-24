#include "ValueCell.h"
#include "Exporter.h"
#include "Theme.h"

namespace sc88::ui {

void dragMidiOut(AppState& state, const juce::String& label, const juce::String& scope,
                 const std::vector<Message>& messages, juce::Component* source)
{
    if (messages.empty()) {
        state.setStatus(scope == "Parameter" ? "Edit a parameter first" : "Nothing to drag on this page");
        return;
    }
    auto file = Exporter::dragCacheDirectory().getChildFile(Exporter::fileName(label, scope, true));
    if (!Exporter::writeMidiFile(file, label, scope, messages, state.settings.sysexDelayMs)) {
        state.setStatus("Could not write drag file");
        return;
    }
    state.setStatus("Dragging " + file.getFileName(), 1200);
    juce::DragAndDropContainer::performExternalDragDropOfFiles({ file.getFullPathName() }, false, source);
}

ValueCell::ValueCell(AppState& s, CellBinding b) : state(s), binding(std::move(b))
{
    addAndMakeVisible(value);
    addAndMakeVisible(arrows);
    value.setFillWithCells(true);
    arrows.setRepeatInterval(state.settings.repeatIntervalMs);
    arrows.setVisible(static_cast<bool>(binding.step));
    arrows.onStep = [this](int direction) {
        binding.step(direction);
        refresh();
        if (!isSelector()) {
            state.lastEditedName = binding.name();
            state.lastEditedValue = binding.display();
            state.parameterEdited({ binding.name(), binding.messages });
        }
        if (onChanged) onChanged();
    };
    refresh();
}

void ValueCell::refresh()
{
    value.setText(binding.display());
    repaint(labelArea());
}

juce::Rectangle<int> ValueCell::labelArea() const { return getLocalBounds().removeFromTop(16); }

void ValueCell::paint(juce::Graphics& g)
{
    Draw::label(g, labelArea().toFloat().withTrimmedLeft(2), binding.name().toUpperCase(),
                juce::Justification::centredLeft, 11.0f);
}

void ValueCell::resized()
{
    auto r = getLocalBounds();
    r.removeFromTop(18);
    auto row = r.removeFromTop(26);
    if (arrows.isVisible()) {
        arrows.setBounds(row.removeFromRight(getWidth() < 200 ? 58 : 78));
        row.removeFromRight(getWidth() < 200 ? 4 : 6);
    }
    value.setBounds(row);
    // Size the dots so the value LCD shows about 7 dot rows of text.
    value.setDotPitch(juce::jlimit(1.6f, 2.4f, float(row.getHeight()) / 11.0f));
}

void ValueCell::mouseDown(const juce::MouseEvent&) { dragStarted = false; }

void ValueCell::mouseMove(const juce::MouseEvent& e)
{
    bool overValue = value.getBounds().contains(e.getPosition());
    setMouseCursor(!overValue ? juce::MouseCursor::NormalCursor
                   : binding.clicked ? juce::MouseCursor::PointingHandCursor
                   : isSelector() ? juce::MouseCursor::NormalCursor
                                  : juce::MouseCursor::DraggingHandCursor);
}

void ValueCell::mouseUp(const juce::MouseEvent& e)
{
    if (!dragStarted && binding.clicked && e.mouseWasClicked() && value.getBounds().contains(e.getPosition()))
        binding.clicked();
}

void ValueCell::mouseDrag(const juce::MouseEvent& e)
{
    if (isSelector() || dragStarted || e.getDistanceFromDragStart() < 8
        || !value.getBounds().contains(e.getMouseDownPosition()))
        return;
    dragStarted = true;
    dragMidiOut(state, binding.name(), "Parameter", binding.messages(), this);
}

} // namespace sc88::ui
