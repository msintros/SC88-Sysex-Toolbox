#pragma once

#include "ui/ValueCell.h"

#include <memory>

namespace sc88::ui {

// One editor page in the lower panel: optional selector cells in a header
// row and a grid of value cells.
class Page : public juce::Component {
public:
    Page(AppState&, juce::String title, int columns);

    // Title used on the LCD and in export file names, e.g. "A01 Basic".
    virtual juce::String exportLabel() const { return title; }
    const juce::String& getTitle() const { return title; }

    // Everything on the page, for SEND / COPY / PAGE MIDI.
    virtual std::vector<Message> pageMessages() const;
    virtual juce::String copyText() const;

    void refresh();
    void paint(juce::Graphics&) override;
    void resized() override;

    ValueCell& addHeaderCell(CellBinding, int width);
    ValueCell& addCell(CellBinding);

protected:
    AppState& state;
    juce::String title;
    int columns;

    juce::Rectangle<int> bodyArea() const;

    juce::OwnedArray<ValueCell> headerCells, cells;
    std::vector<int> headerWidths;
};

std::unique_ptr<Page> makeParameterPage(AppState&, const std::string& pageId);
std::unique_ptr<Page> makePartPage(AppState&, const std::string& category, const juce::String& title);
std::unique_ptr<Page> makeAftertouchPage(AppState&);
std::unique_ptr<Page> makeScaleTuningPage(AppState&);
std::unique_ptr<Page> makeEfxAssignPage(AppState&);
std::unique_ptr<Page> makeSystemPage(AppState&);
std::unique_ptr<Page> makeEfxTypePage(AppState&);
std::unique_ptr<Page> makeResetPage(AppState&);
std::unique_ptr<Page> makeSettingsPage(AppState&);

} // namespace sc88::ui
