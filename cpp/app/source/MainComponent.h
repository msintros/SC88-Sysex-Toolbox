#pragma once

#include "AppState.h"
#include "pages/Pages.h"
#include "ui/Controls.h"
#include "ui/Lcd.h"

namespace sc88 {

// Round button that saves on click and starts a file drag when dragged.
class ExportButton : public ui::RoundButton {
public:
    std::function<void()> onSave, onDragOut;
    void mouseDown(const juce::MouseEvent&) override;
    void mouseDrag(const juce::MouseEvent&) override;
    using RoundButton::clicked;
    void clicked() override;

private:
    bool dragStarted = false;
};

// The whole editor, laid out at a fixed logical size. ScaledRoot scales it
// to the window so the panel keeps its proportions at any size.
class MainComponent : public juce::Component, private juce::ChangeListener, private juce::Timer {
public:
    static constexpr int logicalWidth = 1120;
    static constexpr int logicalHeight = 720;

    explicit MainComponent(AppState&);
    ~MainComponent() override;

    void paint(juce::Graphics&) override;
    void resized() override;

    // Renders every page to <dir>/<page>.png at the given scale. Used by
    // --screenshots to check the look without opening a window.
    void writeScreenshots(const juce::File& dir, float scale);

private:
    struct PageEntry {
        juce::String key;
        juce::String group;
        std::function<std::unique_ptr<ui::Page>()> make;
        std::unique_ptr<ui::PageKey> button;
    };

    AppState& state;
    ui::Lcd lcd;
    ui::RoundButton sendButton, copyButton;
    ExportButton pageMidiButton, paramMidiButton;
    std::vector<PageEntry> entries;
    std::unique_ptr<ui::Page> page;
    int currentPage = -1;

    void showPage(int index);
    void updateLcd();
    void changeListenerCallback(juce::ChangeBroadcaster*) override;
    void timerCallback() override;

    void savePage(), saveParameter();
    void save(const juce::String& label, const juce::String& scope, const std::vector<Message>&);

    juce::Rectangle<int> lcdArea() const { return { 24, 38, 540, 118 }; }
};

class ScaledRoot : public juce::Component {
public:
    explicit ScaledRoot(AppState& s) : main(s) { addAndMakeVisible(main); }
    void resized() override;
    MainComponent& getMain() { return main; }

private:
    MainComponent main;
};

} // namespace sc88
