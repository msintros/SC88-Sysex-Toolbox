#include "MainComponent.h"
#include "Exporter.h"
#include "ui/Theme.h"
#include "ui/ValueCell.h"

namespace sc88 {

using namespace ui;

// ---- ExportButton -------------------------------------------------------------

void ExportButton::mouseDown(const juce::MouseEvent& e)
{
    dragStarted = false;
    RoundButton::mouseDown(e);
}

void ExportButton::mouseDrag(const juce::MouseEvent& e)
{
    RoundButton::mouseDrag(e);
    if (dragStarted || e.getDistanceFromDragStart() < 8) return;
    dragStarted = true;
    if (onDragOut) onDragOut();
}

void ExportButton::clicked()
{
    if (!dragStarted && onSave) onSave();
}

// ---- Layout constants (logical pixels) ------------------------------------------

namespace {
constexpr int topPanelHeight = 238;
const juce::Rectangle<int> keyBlock { 600, 20, 500, 200 };
const juce::Rectangle<int> pageArea { 24, 256, 1072, 450 };
constexpr int keyColumns = 6;

struct Action { const char* label; };
} // namespace

MainComponent::MainComponent(AppState& s) : state(s)
{
    setSize(logicalWidth, logicalHeight);
    addAndMakeVisible(lcd);
    lcd.setDotPitch(3.0f);

    for (auto* b : std::initializer_list<juce::Button*> { &sendButton, &copyButton, &pageMidiButton, &paramMidiButton })
        addAndMakeVisible(b);

    sendButton.onClick = [this] {
        if (page) state.sendPage(page->pageMessages());
    };
    copyButton.onClick = [this] {
        if (!page) return;
        juce::SystemClipboard::copyTextToClipboard(page->copyText());
        state.setStatus("Copied " + page->exportLabel());
    };
    pageMidiButton.onSave = [this] { savePage(); };
    pageMidiButton.onDragOut = [this] {
        if (page) dragMidiOut(state, page->exportLabel(), "Page", page->pageMessages(), &pageMidiButton);
    };
    paramMidiButton.onSave = [this] { saveParameter(); };
    paramMidiButton.onDragOut = [this] {
        auto& p = state.lastEditedParameter();
        dragMidiOut(state, p.label, "Parameter", p ? p.messages() : std::vector<Message> {}, &paramMidiButton);
    };

    auto add = [this](juce::String key, juce::String group, std::function<std::unique_ptr<Page>()> make) {
        entries.push_back({ key, group, std::move(make), std::make_unique<PageKey>(key) });
    };
    add("EFX TYPE", "EFFECTS", [&s] { return makeEfxTypePage(s); });
    add("EFX ASSIGN", "EFFECTS", [&s] { return makeEfxAssignPage(s); });
    add("REVERB", "EFFECTS", [&s] { return makeParameterPage(s, "reverb"); });
    add("CHORUS", "EFFECTS", [&s] { return makeParameterPage(s, "chorus"); });
    add("DELAY", "EFFECTS", [&s] { return makeParameterPage(s, "delay"); });
    add("EQ", "EFFECTS", [&s] { return makeParameterPage(s, "eq"); });
    add("BASIC", "PART", [&s] { return makePartPage(s, "Basic", "Basic"); });
    add("RECEIVE", "PART", [&s] { return makePartPage(s, "Receive", "Receive"); });
    add("TONE", "PART", [&s] { return makePartPage(s, "Tone Modify", "Tone Modify"); });
    add("ROUTING", "PART", [&s] { return makePartPage(s, "Routing", "Routing"); });
    add("MOD", "PART", [&s] { return makePartPage(s, "Mod", "Modulation"); });
    add("TUNING", "PART", [&s] { return makeScaleTuningPage(s); });
    add("BEND", "CONTROL", [&s] { return makePartPage(s, "Bend", "Bend"); });
    add("AFTERTOUCH", "CONTROL", [&s] { return makeAftertouchPage(s); });
    add("CC1", "CONTROL", [&s] { return makePartPage(s, "CC1", "CC1"); });
    add("CC2", "CONTROL", [&s] { return makePartPage(s, "CC2", "CC2"); });
    add("GLOBAL", "SYSTEM", [&s] { return makeParameterPage(s, "global"); });
    add("SYSTEM", "SYSTEM", [&s] { return makeSystemPage(s); });
    add("RESET", "SYSTEM", [&s] { return makeResetPage(s); });
    add("SETTINGS", "SYSTEM", [&s] { return makeSettingsPage(s); });

    for (size_t i = 0; i < entries.size(); ++i) {
        addAndMakeVisible(*entries[i].button);
        entries[i].button->onClick = [this, i] { showPage(int(i)); };
    }

    state.addChangeListener(this);
    Exporter::cleanDragCache();
    resized();
    showPage(0);
    startTimer(250);
}

MainComponent::~MainComponent() { state.removeChangeListener(this); }

void MainComponent::showPage(int index)
{
    if (index == currentPage) return;
    currentPage = index;
    for (size_t i = 0; i < entries.size(); ++i) entries[i].button->setToggleState(int(i) == index, juce::dontSendNotification);
    page = entries[size_t(index)].make();
    addAndMakeVisible(*page);
    page->setBounds(pageArea);
    page->refresh();
    updateLcd();
}

void MainComponent::updateLcd()
{
    auto status = state.status();
    auto out = state.midi.currentOutputName();
    juce::String param = state.lastEditedName.isNotEmpty()
        ? state.lastEditedName.substring(0, 16).paddedRight(' ', 17) + state.lastEditedValue
        : juce::String();
    lcd.setLines({ page ? page->exportLabel() : juce::String(), param, "",
                   status.isNotEmpty() ? status : "MIDI " + (out.isEmpty() ? juce::String("- no output") : out) });
}

void MainComponent::changeListenerCallback(juce::ChangeBroadcaster*)
{
    if (page) page->refresh();
    updateLcd();
}

void MainComponent::timerCallback() { updateLcd(); }

void MainComponent::save(const juce::String& label, const juce::String& scope, const std::vector<Message>& messages)
{
    if (messages.empty()) {
        state.setStatus(scope == "Parameter" ? "Edit a parameter first" : "Nothing to export on this page");
        return;
    }
    auto file = state.settings.midiSaveLocation.getChildFile(Exporter::fileName(label, scope, false));
    if (Exporter::writeMidiFile(file, label, scope, messages, state.settings.sysexDelayMs))
        state.setStatus("Saved " + file.getFileName(), 3000);
    else
        state.setStatus("Could not save " + file.getFileName(), 3000);
}

void MainComponent::savePage()
{
    if (page) save(page->exportLabel(), "Page", page->pageMessages());
}

void MainComponent::saveParameter()
{
    auto& p = state.lastEditedParameter();
    save(p.label, "Parameter", p ? p.messages() : std::vector<Message> {});
}

// ---- Painting and layout --------------------------------------------------------

void MainComponent::paint(juce::Graphics& g)
{
    auto bounds = getLocalBounds().toFloat();
    Draw::panel(g, bounds.removeFromTop(float(topPanelHeight)), Theme::panelTop, Theme::panelBottom);
    Draw::panel(g, bounds, Theme::lowerPanelTop, Theme::lowerPanelBottom);

    // Labels above the LCD, as on the hardware.
    auto lcdR = lcdArea().toFloat();
    Draw::label(g, { lcdR.getX() + 4, 14, 200, 18 }, "SC-88 PRO", juce::Justification::centredLeft, 12.5f);
    g.setColour(Theme::label);
    g.setFont(Theme::boldFont(17.0f).withExtraKerningFactor(0.02f));
    g.drawText("Flashlight", juce::Rectangle<float>(lcdR.getRight() - 220, 10, 220, 24), juce::Justification::centredRight);

    // Round button labels to the left of each button.
    const char* labels[] = { "SEND", "COPY", "PAGE MIDI", "PARAM MIDI" };
    juce::Component* buttons[] = { &sendButton, &copyButton, &pageMidiButton, &paramMidiButton };
    for (int i = 0; i < 4; ++i) {
        auto b = buttons[i]->getBounds().toFloat();
        Draw::label(g, { b.getX() - 84, b.getY(), 80, b.getHeight() }, labels[i], juce::Justification::centredRight, 11.5f);
    }
    Draw::label(g, { lcdR.getX(), 206, lcdR.getWidth(), 16 },
                "Click PAGE / PARAM MIDI to save a .mid file, or drag them (or any value) into Finder or your DAW",
                juce::Justification::centredLeft, 10.0f);

    // Group tags beside each row of page keys.
    juce::String lastGroup;
    for (auto& e : entries) {
        if (e.group == lastGroup) continue;
        lastGroup = e.group;
        auto b = e.button->getBounds();
        Draw::tag(g, juce::Rectangle<float>(float(keyBlock.getX()), float(b.getBottom() - 21), 74.0f, 18.0f), e.group);
    }
}

void MainComponent::resized()
{
    lcd.setBounds(lcdArea());

    auto lcdR = lcdArea();
    const int buttonY = lcdR.getBottom() + 12;
    const int step = lcdR.getWidth() / 4;
    juce::Component* buttons[] = { &sendButton, &copyButton, &pageMidiButton, &paramMidiButton };
    for (int i = 0; i < 4; ++i) buttons[i]->setBounds(lcdR.getX() + step * i + step - 40, buttonY, 34, 34);

    // Page keys: one row per group, after the group's tag.
    const int left = keyBlock.getX() + 84;
    const int keyW = (keyBlock.getRight() - left) / keyColumns;
    int row = -1, col = 0;
    juce::String lastGroup;
    for (auto& e : entries) {
        if (e.group != lastGroup) { lastGroup = e.group; ++row; col = 0; }
        e.button->setBounds(left + col * keyW, keyBlock.getY() + row * 50, keyW, 42);
        ++col;
    }
    if (page) page->setBounds(pageArea);
}

void MainComponent::writeScreenshots(const juce::File& dir, float scale)
{
    dir.createDirectory();
    for (size_t i = 0; i < entries.size(); ++i) {
        showPage(int(i));
        auto image = createComponentSnapshot(getLocalBounds(), true, scale);
        auto file = dir.getChildFile(entries[i].key.replaceCharacter(' ', '_').toLowerCase() + ".png");
        file.deleteFile();
        juce::FileOutputStream out(file);
        juce::PNGImageFormat().writeImageToStream(image, out);
    }
}

// ---- ScaledRoot ----------------------------------------------------------------

void ScaledRoot::resized()
{
    const float scale = juce::jmin(getWidth() / float(MainComponent::logicalWidth),
                                   getHeight() / float(MainComponent::logicalHeight));
    const float x = (getWidth() - MainComponent::logicalWidth * scale) * 0.5f;
    const float y = (getHeight() - MainComponent::logicalHeight * scale) * 0.5f;
    main.setTransform(juce::AffineTransform::scale(scale).translated(x, y));
}

} // namespace sc88
