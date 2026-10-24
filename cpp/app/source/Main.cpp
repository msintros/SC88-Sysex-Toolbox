#include "MainComponent.h"
#include "ui/Theme.h"

namespace sc88 {

class Application : public juce::JUCEApplication {
public:
    const juce::String getApplicationName() override { return JUCE_APPLICATION_NAME_STRING; }
    const juce::String getApplicationVersion() override { return JUCE_APPLICATION_VERSION_STRING; }
    bool moreThanOneInstanceAllowed() override { return false; }

    void initialise(const juce::String& commandLine) override
    {
        // Menus and dialogs in the panel's colours and font.
        auto& laf = juce::LookAndFeel::getDefaultLookAndFeel();
        laf.setDefaultSansSerifTypeface(ui::Theme::labelFont(14.0f).getTypefacePtr());
        laf.setColour(juce::PopupMenu::backgroundColourId, ui::Theme::panelBottom);
        laf.setColour(juce::PopupMenu::textColourId, ui::Theme::label);
        laf.setColour(juce::PopupMenu::highlightedBackgroundColourId, ui::Theme::accent);
        laf.setColour(juce::PopupMenu::highlightedTextColourId, ui::Theme::accentText);

        state = std::make_unique<AppState>();

        // --screenshots <dir>: render every page to PNG files and quit.
        auto args = juce::StringArray::fromTokens(commandLine, true);
        if (auto i = args.indexOf("--screenshots"); i >= 0 && i + 1 < args.size()) {
            MainComponent main(*state);
            main.writeScreenshots(juce::File(args[i + 1].unquoted()), 2.0f);
            quit();
            return;
        }

        window = std::make_unique<MainWindow>(getApplicationName(), *state);
    }

    void shutdown() override
    {
        window.reset();
        state.reset();
    }

    void systemRequestedQuit() override { quit(); }

private:
    class MainWindow : public juce::DocumentWindow {
    public:
        MainWindow(const juce::String& name, AppState& state)
            : DocumentWindow(name, ui::Theme::panelBottom, DocumentWindow::allButtons)
        {
            setUsingNativeTitleBar(true);
            setContentOwned(new ScaledRoot(state), false);
            setResizable(true, true);
            // Keep the panel's proportions; vector drawing stays sharp at any size.
            const double aspect = double(MainComponent::logicalWidth) / MainComponent::logicalHeight;
            getConstrainer()->setFixedAspectRatio(aspect);
            setResizeLimits(840, 540, 3360, 2160);
            centreWithSize(MainComponent::logicalWidth, MainComponent::logicalHeight);
            setVisible(true);
        }

        void closeButtonPressed() override { JUCEApplication::getInstance()->systemRequestedQuit(); }
    };

    std::unique_ptr<AppState> state;
    std::unique_ptr<MainWindow> window;
};

} // namespace sc88

START_JUCE_APPLICATION(sc88::Application)
