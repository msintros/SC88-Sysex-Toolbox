#include "Pages.h"
#include "Exporter.h"
#include "ui/Theme.h"

namespace sc88::ui {

// ---- Page -------------------------------------------------------------------

namespace {
constexpr int headerHeight = 48;
constexpr int gapX = 22;
} // namespace

Page::Page(AppState& s, juce::String t, int cols) : state(s), title(std::move(t)), columns(cols) {}

ValueCell& Page::addHeaderCell(CellBinding binding, int width)
{
    auto* cell = headerCells.add(new ValueCell(state, std::move(binding)));
    cell->onChanged = [this] { refresh(); };
    headerWidths.push_back(width);
    addAndMakeVisible(cell);
    return *cell;
}

ValueCell& Page::addCell(CellBinding binding)
{
    auto* cell = cells.add(new ValueCell(state, std::move(binding)));
    addAndMakeVisible(cell);
    return *cell;
}

std::vector<Message> Page::pageMessages() const
{
    std::vector<Message> out;
    for (auto* c : cells)
        if (c->isVisible() && c->getBinding().messages)
            for (auto& m : c->getBinding().messages()) out.push_back(m);
    return out;
}

juce::String Page::copyText() const
{
    std::vector<Message> labelled;
    for (auto* c : headerCells)
        if (!c->isSelector()) labelled.push_back({ (c->getBinding().name() + " = " + c->getBinding().display()).toStdString(), c->getBinding().messages().front().bytes });
    for (auto* c : cells) {
        if (!c->isVisible() || c->isSelector()) continue;
        auto label = c->getBinding().name() + " = " + c->getBinding().display();
        for (auto& m : c->getBinding().messages()) labelled.push_back({ label.toStdString(), m.bytes });
    }
    return Exporter::clipboardText(exportLabel(), labelled);
}

void Page::refresh()
{
    bool layoutChanged = false;
    for (auto* c : cells) {
        bool show = !c->getBinding().visible || c->getBinding().visible();
        if (show != c->isVisible()) { c->setVisible(show); layoutChanged = true; }
        c->refresh();
    }
    for (auto* c : headerCells) c->refresh();
    if (layoutChanged) resized();
    repaint();
}

juce::Rectangle<int> Page::bodyArea() const
{
    return getLocalBounds().withTrimmedTop(headerHeight + 14);
}

void Page::paint(juce::Graphics& g)
{
    auto header = getLocalBounds().removeFromTop(headerHeight);
    auto tagWidth = juce::jmax(140, int(juce::GlyphArrangement::getStringWidth(Theme::boldFont(11.0f), title.toUpperCase())) + 28);
    Draw::tag(g, header.removeFromLeft(tagWidth).withSizeKeepingCentre(tagWidth, 20).translated(0, 8).toFloat(),
              title.toUpperCase());

    // Thin groove under the header, like the orange EFX line on 88emu.
    g.setColour(Theme::accent.withAlpha(0.8f));
    g.fillRect(juce::Rectangle<float>(0, float(headerHeight) + 3.0f, float(getWidth()), 1.5f));
}

void Page::resized()
{
    auto header = getLocalBounds().removeFromTop(headerHeight);
    for (int i = headerCells.size(); --i >= 0;) {
        headerCells[i]->setBounds(header.removeFromRight(headerWidths[size_t(i)]).withTrimmedBottom(2));
        header.removeFromRight(gapX);
    }

    juce::Array<ValueCell*> visible;
    for (auto* c : cells)
        if (c->isVisible()) visible.add(c);
    if (visible.isEmpty()) return;

    auto body = bodyArea();
    const int rows = (visible.size() + columns - 1) / columns;
    const int gap = columns > 4 ? 14 : gapX;
    const int cellW = (body.getWidth() - (columns - 1) * gap) / columns;
    const int pitch = juce::jmin(60, body.getHeight() / juce::jmax(1, rows));
    for (int i = 0; i < visible.size(); ++i) {
        int col = i % columns, row = i / columns;
        visible[i]->setBounds(body.getX() + col * (cellW + gap), body.getY() + row * pitch, cellW, 46);
    }
}

// ---- Shared helpers ---------------------------------------------------------

namespace {

juce::String partLabel(const AppState& s) { return groupPartLabel(s.selGroup, s.selPart); }

// A01..A16, B01..B16 as one wrapping list.
CellBinding partSelector(AppState& s)
{
    CellBinding b;
    b.name = [] { return juce::String("Part"); };
    b.display = [&s] { return partLabel(s); };
    b.step = [&s](int dir) {
        int index = (s.selGroup == Group::A ? 0 : 16) + s.selPart - 1;
        index = (index + dir + 32) % 32;
        s.selGroup = index < 16 ? Group::A : Group::B;
        s.selPart = index % 16 + 1;
        s.clearLastEdited();
    };
    return b;
}

std::vector<Message> one(Message m) { return { std::move(m) }; }

class SimplePage : public Page {
public:
    SimplePage(AppState& s, juce::String t, int cols, std::function<juce::String()> label = {})
        : Page(s, std::move(t), cols), labelFn(std::move(label)) {}
    juce::String exportLabel() const override { return labelFn ? labelFn() : title; }

private:
    std::function<juce::String()> labelFn;
};

} // namespace

// ---- System-wide parameter pages -----------------------------------------------

std::unique_ptr<Page> makeParameterPage(AppState& s, const std::string& pageId)
{
    const int pageIndex = s.tables.pageIndex(pageId);
    const auto& def = s.tables.pages[size_t(pageIndex)];
    auto page = std::make_unique<SimplePage>(s, juce::String(def.title).replace(" Settings", "").replace("Adjust Global Values", "Global"), 3,
                                             [title = juce::String(def.title)] { return title; });
    for (size_t i = 0; i < def.params.size(); ++i) {
        const auto& p = def.params[i];
        const int index = int(i);
        CellBinding b;
        b.name = [&p] { return juce::String(p.name); };
        b.display = [&s, &p, pageIndex, index] { return juce::String(formatValue(p, s.patch.pageValue(pageIndex, index))); };
        b.step = [&s, &p, pageIndex, index](int dir) {
            s.patch.setPageValue(pageIndex, index, stepValue(p, s.patch.pageValue(pageIndex, index), dir));
        };
        b.messages = [&s, pageIndex, index] { return one(s.patch.pageParamMessage(pageIndex, index)); };
        page->addCell(std::move(b));
    }
    return page;
}

// ---- Part parameter pages -----------------------------------------------------

namespace {

class PartPage : public Page {
public:
    PartPage(AppState& s, juce::String t, std::function<int()> category)
        : Page(s, std::move(t), 3), categoryFn(std::move(category))
    {
        addHeaderCell(partSelector(s), 200);
    }

    juce::String exportLabel() const override
    {
        return partLabel(state) + " " + juce::String(state.tables.partCategories[size_t(categoryFn())].name);
    }

    // Whole category, with the two halves of the tone number sent once.
    std::vector<Message> pageMessages() const override
    {
        return state.patch.partCategoryMessages(state.selGroup, state.selPart, categoryFn());
    }

    void addParams()
    {
        // Categories that share a page (CAf / PAf) have the same layout.
        const auto& params = state.tables.partCategories[size_t(categoryFn())].params;
        for (size_t i = 0; i < params.size(); ++i) {
            const int index = int(i);
            auto& s = state;
            auto cat = categoryFn;
            auto param = [&s, cat, index]() -> const ParamDef& {
                return s.tables.partCategories[size_t(cat())].params[size_t(index)];
            };
            CellBinding b;
            b.name = [param] { return juce::String(param().name); };
            b.display = [&s, cat, param, index] {
                return juce::String(formatValue(param(), s.patch.partValue(s.selGroup, s.selPart, cat(), index)));
            };
            b.step = [&s, cat, param, index](int dir) {
                int v = s.patch.partValue(s.selGroup, s.selPart, cat(), index);
                s.patch.setPartValue(s.selGroup, s.selPart, cat(), index, stepValue(param(), v, dir));
            };
            b.messages = [&s, cat, index] { return one(s.patch.partParamMessage(s.selGroup, s.selPart, cat(), index)); };
            addCell(std::move(b));
        }
    }

protected:
    std::function<int()> categoryFn;
};

} // namespace

std::unique_ptr<Page> makePartPage(AppState& s, const std::string& category, const juce::String& title)
{
    const int cat = s.tables.categoryIndex(category);
    auto page = std::make_unique<PartPage>(s, title, [cat] { return cat; });
    page->addParams();
    return page;
}

std::unique_ptr<Page> makeAftertouchPage(AppState& s)
{
    const int caf = s.tables.categoryIndex("CAf"), paf = s.tables.categoryIndex("PAf");
    auto page = std::make_unique<PartPage>(s, "Aftertouch", [&s, caf, paf] { return s.aftertouchPoly ? paf : caf; });

    CellBinding type;
    type.name = [] { return juce::String("Type"); };
    type.display = [&s] { return juce::String(s.aftertouchPoly ? "Polyphonic" : "Channel"); };
    type.step = [&s](int) { s.aftertouchPoly = !s.aftertouchPoly; s.clearLastEdited(); };
    page->addHeaderCell(std::move(type), 230);
    page->addParams();
    return page;
}

// ---- Scale tuning -----------------------------------------------------------------

std::unique_ptr<Page> makeScaleTuningPage(AppState& s)
{
    static const char* notes[] = { "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B" };
    auto page = std::make_unique<SimplePage>(s, "Scale Tuning", 3, [&s] { return partLabel(s) + " Scale Tuning"; });
    page->addHeaderCell(partSelector(s), 200);
    for (int n = 0; n < 12; ++n) {
        CellBinding b;
        b.name = [n] { return juce::String(notes[n]); };
        b.display = [&s, n] { return juce::String(formatScaleTune(s.patch.scaleTune(s.selGroup, s.selPart, n))); };
        b.step = [&s, n](int dir) {
            int v = (s.patch.scaleTune(s.selGroup, s.selPart, n) + dir + 128) % 128;
            s.patch.setScaleTune(s.selGroup, s.selPart, n, v);
        };
        b.messages = [&s, n] { return one(s.patch.scaleTuneMessage(s.selGroup, s.selPart, n)); };
        page->addCell(std::move(b));
    }
    return page;
}

// ---- EFX assign -------------------------------------------------------------------

std::unique_ptr<Page> makeEfxAssignPage(AppState& s)
{
    auto page = std::make_unique<SimplePage>(s, "EFX Assign", 6, [] { return juce::String("Insertion EFX Assign"); });
    for (Group g : { Group::A, Group::B })
        for (int part = 1; part <= 16; ++part) {
            CellBinding b;
            b.name = [g, part] { return groupPartLabel(g, part); };
            b.display = [&s, g, part] { return juce::String(s.patch.efxAssigned(g, part) ? "EFX" : "Bypass"); };
            b.step = [&s, g, part](int) { s.patch.setEfxAssigned(g, part, !s.patch.efxAssigned(g, part)); };
            b.messages = [&s, g, part] { return one(s.patch.efxAssignMessage(g, part)); };
            page->addCell(std::move(b));
        }
    return page;
}

// ---- System -------------------------------------------------------------------------

namespace {

// The mode cell sits in the header, so page messages come from the patch.
class SystemPage : public SimplePage {
public:
    using SimplePage::SimplePage;
    std::vector<Message> pageMessages() const override { return state.patch.systemMessages(); }
};

} // namespace

std::unique_ptr<Page> makeSystemPage(AppState& s)
{
    auto page = std::make_unique<SystemPage>(s, "System", 6, [] { return juce::String("System Parameters"); });

    CellBinding mode;
    mode.name = [] { return juce::String("System Mode"); };
    mode.display = [&s] { return juce::String(s.patch.systemMode() == 0 ? "Mode 1 / Single" : "Mode 2 / Double"); };
    mode.step = [&s](int) { s.patch.setSystemMode(1 - s.patch.systemMode()); };
    mode.messages = [&s] { return one(s.patch.systemModeMessage()); };
    page->addHeaderCell(std::move(mode), 380);

    for (int block = 0; block < 32; ++block) {
        CellBinding b;
        b.name = [block] { return "Block " + juce::String::toHexString(block).paddedLeft('0', 2).toUpperCase(); };
        b.display = [&s, block] { return juce::String(s.patch.blockPort(block) == 0 ? "Port A" : "Port B"); };
        b.step = [&s, block](int) { s.patch.setBlockPort(block, 1 - s.patch.blockPort(block)); };
        b.messages = [&s, block] { return one(s.patch.blockPortMessage(block)); };
        page->addCell(std::move(b));
    }
    return page;
}

// ---- EFX type ---------------------------------------------------------------------

namespace {

class EfxTypePage : public Page {
public:
    explicit EfxTypePage(AppState& s) : Page(s, "EFX Type", 4)
    {
        CellBinding type;
        type.name = [] { return juce::String("Insertion Effect"); };
        type.display = [&s] { return typeText(s, s.patch.efxType()); };
        type.step = [&s](int dir) {
            int n = int(s.tables.efxTypes.size());
            s.patch.setEfxType((s.patch.efxType() + dir + n) % n);
        };
        type.messages = [&s] { return one(s.patch.efxTypeMessage()); };
        type.clicked = [this] { showTypeMenu(); };
        addHeaderCell(std::move(type), 380).onChanged = [this] { refresh(); };

        for (int i = 0; i < 20; ++i) {
            CellBinding b;
            auto param = [&s, i]() -> const EfxParam& { return s.tables.efxTypes[size_t(s.patch.efxType())].params[size_t(i)]; };
            b.name = [param] { return juce::String(param().name); };
            b.display = [&s, i] { return juce::String(s.patch.efxParamDisplay(i)); };
            b.step = [&s, param, i](int dir) { s.patch.setEfxParam(i, stepEfxValue(param(), s.patch.efxParam(i), dir)); };
            b.messages = [&s, i] { return one(s.patch.efxParamMessage(i)); };
            b.visible = [param] { return param().used(); };
            addCell(std::move(b));
        }
        refresh();
    }

    juce::String exportLabel() const override
    {
        return "EFX " + juce::String(state.tables.efxTypes[size_t(state.patch.efxType())].displayName);
    }

    std::vector<Message> pageMessages() const override { return state.patch.efxMessages(); }

private:
    static juce::String typeText(const AppState& s, int index)
    {
        return juce::String(index).paddedLeft('0', 2) + " " + juce::String(s.tables.efxTypes[size_t(index)].displayName);
    }

    void showTypeMenu()
    {
        juce::PopupMenu menu;
        for (size_t i = 0; i < state.tables.efxTypes.size(); ++i)
            menu.addItem(int(i) + 1, typeText(state, int(i)), true, int(i) == state.patch.efxType());
        menu.showMenuAsync(juce::PopupMenu::Options().withTargetComponent(headerCells[0]).withMaximumNumColumns(3),
                           [this](int result) {
                               if (result <= 0) return;
                               state.patch.setEfxType(result - 1);
                               state.lastEditedName = "EFX Type";
                               state.lastEditedValue = state.tables.efxTypes[size_t(result - 1)].displayName;
                               state.parameterEdited({ "EFX Type", [this] { return one(state.patch.efxTypeMessage()); } });
                               refresh();
                           });
    }
};

} // namespace

std::unique_ptr<Page> makeEfxTypePage(AppState& s) { return std::make_unique<EfxTypePage>(s); }

// ---- Reset --------------------------------------------------------------------------

namespace {

class ResetPage : public Page {
public:
    explicit ResetPage(AppState& s) : Page(s, "Reset", 1)
    {
        for (auto* k : { &gm, &gs }) addAndMakeVisible(k);
        gm.onClick = [this] { choose(false); };
        gs.onClick = [this] { choose(true); };
    }

    std::vector<Message> pageMessages() const override
    {
        return { gsChosen ? Message { "GS Reset", gsReset() } : Message { "GM System On", gmSystemOn() } };
    }

    juce::String copyText() const override { return Exporter::clipboardText(exportLabel(), pageMessages()); }
    juce::String exportLabel() const override { return gsChosen ? "GS Reset" : "GM System On"; }

    void paint(juce::Graphics& g) override
    {
        Page::paint(g);
        auto body = bodyArea().withTrimmedTop(70);
        Draw::label(g, body.removeFromTop(20).toFloat(),
                    "Sends a reset to the SC-88 Pro. GS Reset restores GS defaults; GM System On switches to GM mode.",
                    juce::Justification::centred, 12.0f);
    }

    void resized() override
    {
        Page::resized();
        auto row = bodyArea().withTrimmedTop(10).removeFromTop(40).withSizeKeepingCentre(420, 34);
        gm.setBounds(row.removeFromLeft(200));
        gs.setBounds(row.removeFromRight(200));
    }

private:
    KeyButton gm { KeyButton::Glyph::none, "GM SYSTEM ON" }, gs { KeyButton::Glyph::none, "GS RESET" };
    bool gsChosen = true;

    void choose(bool gsReset)
    {
        gsChosen = gsReset;
        state.lastEditedName = exportLabel();
        state.lastEditedValue = {};
        auto chosen = pageMessages();
        state.parameterEdited({ exportLabel(), [chosen] { return chosen; } });
        state.setStatus("Sent " + exportLabel());
    }
};

// ---- Settings -----------------------------------------------------------------------

class SettingsPage : public Page {
public:
    explicit SettingsPage(AppState& s) : Page(s, "Settings", 2)
    {
        CellBinding out;
        out.name = [] { return juce::String("MIDI Output"); };
        out.display = [&s] {
            auto name = s.midi.currentOutputName();
            return name.isEmpty() ? juce::String("None") : name;
        };
        out.step = [&s](int dir) {
            auto devices = s.midi.outputs();
            if (devices.isEmpty()) return;
            int current = -1;
            for (int i = 0; i < devices.size(); ++i)
                if (devices[i].name == s.midi.currentOutputName()) current = i;
            int next = (current + dir + devices.size()) % devices.size();
            selectOutput(s, devices[next].name);
        };
        out.clicked = [this] { showOutputMenu(); };
        addCell(std::move(out));

        CellBinding folder;
        folder.name = [] { return juce::String("MIDI Save Location (click to choose)"); };
        folder.display = [&s] { return shortened(s.settings.midiSaveLocation.getFullPathName(), 30); };
        folder.clicked = [this] { chooseFolder(); };
        addCell(std::move(folder));

        CellBinding delay;
        delay.name = [] { return juce::String("SysEx Message Delay"); };
        delay.display = [&s] { return juce::String(s.settings.sysexDelayMs) + " ms"; };
        delay.step = [&s](int dir) {
            s.settings.sysexDelayMs = juce::jlimit(0, 250, s.settings.sysexDelayMs + dir);
            s.settings.save();
        };
        addCell(std::move(delay));

        CellBinding repeat;
        repeat.name = [] { return juce::String("Button Repeat Interval"); };
        repeat.display = [&s] { return juce::String(s.settings.repeatIntervalMs) + " ms"; };
        repeat.step = [&s](int dir) {
            s.settings.repeatIntervalMs = juce::jlimit(25, 250, s.settings.repeatIntervalMs + dir * 5);
            s.settings.save();
            s.sendChangeMessage();
        };
        addCell(std::move(repeat));
    }

    std::vector<Message> pageMessages() const override { return {}; }

    void paint(juce::Graphics& g) override
    {
        Page::paint(g);
        auto note = bodyArea().withTrimmedTop(140).removeFromTop(40).toFloat();
        g.setColour(Theme::labelDim);
        g.setFont(Theme::labelFont(11.5f));
        g.drawFittedText("SysEx delay spaces the messages of SEND and the MIDI files. A lower repeat interval "
                         "makes held arrow keys step faster (applies after switching pages). Settings are shared "
                         "with the Python version.",
                         note.toNearestInt(), juce::Justification::topLeft, 3);
    }

private:
    std::unique_ptr<juce::FileChooser> chooser;

    static juce::String shortened(const juce::String& text, int maxChars)
    {
        auto home = juce::File::getSpecialLocation(juce::File::userHomeDirectory).getFullPathName();
        auto t = text.startsWith(home) ? "~" + text.substring(home.length()) : text;
        return t.length() <= maxChars ? t : "..." + t.getLastCharacters(maxChars - 3);
    }

    static void selectOutput(AppState& s, const juce::String& name)
    {
        if (s.midi.open(name)) {
            s.settings.midiOutput = name;
            s.settings.save();
            s.setStatus("MIDI out: " + name);
        } else {
            s.setStatus("Could not open " + name);
        }
    }

    void showOutputMenu()
    {
        juce::PopupMenu menu;
        auto devices = state.midi.outputs();
        if (devices.isEmpty()) menu.addItem(-1, "No MIDI outputs found", false);
        for (int i = 0; i < devices.size(); ++i)
            menu.addItem(i + 1, devices[i].name, true, devices[i].name == state.midi.currentOutputName());
        menu.showMenuAsync(juce::PopupMenu::Options().withTargetComponent(cells[0]), [this, devices](int result) {
            if (result > 0) selectOutput(state, devices[result - 1].name);
            refresh();
        });
    }

    void chooseFolder()
    {
        chooser = std::make_unique<juce::FileChooser>("Choose where MIDI files are saved", state.settings.midiSaveLocation);
        chooser->launchAsync(juce::FileBrowserComponent::openMode | juce::FileBrowserComponent::canSelectDirectories,
                             [this](const juce::FileChooser& fc) {
                                 auto dir = fc.getResult();
                                 if (dir == juce::File()) return;
                                 state.settings.midiSaveLocation = dir;
                                 state.settings.save();
                                 refresh();
                             });
    }
};

} // namespace

std::unique_ptr<Page> makeResetPage(AppState& s) { return std::make_unique<ResetPage>(s); }
std::unique_ptr<Page> makeSettingsPage(AppState& s) { return std::make_unique<SettingsPage>(s); }

} // namespace sc88::ui
