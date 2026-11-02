#include "Pages.h"
#include "ui/Theme.h"

namespace sc88::ui {

namespace {

constexpr int numberColumnItems = 24; // items per column in a group's submenu

juce::String three(int n) { return juce::String(n).paddedLeft('0', 3); }

// The 16 parts and the sound on each. Every part sends Bank Select (CC0)
// then Program Change on its own MIDI channel.
class ProgramsPage : public Page {
public:
    explicit ProgramsPage(AppState& s) : Page(s, "Programs", 4)
    {
        for (int part = 0; part < ProgramSetup::numParts; ++part) {
            CellBinding b;
            b.name = [part] { return "Part " + juce::String(part + 1).paddedLeft('0', 2); };
            b.display = [&s, part] { return s.programs.programText(part); };
            // Arrows walk the whole list, Off first, then each group in turn.
            b.step = [&s, part](int dir) {
                const int n = s.programList.size() + 1;
                auto& index = s.programs.parts[size_t(part)];
                index = ((index + 1 + dir) % n + n) % n - 1;
            };
            b.messages = [&s, part] { return s.programs.partMessages(part); };
            b.clicked = [this, part] { showMenu(part); };
            addCell(std::move(b)).setMinimumCharacters(13); // longest names in the list
        }
    }

    juce::String exportLabel() const override { return "Programs"; }
    std::vector<Message> pageMessages() const override { return state.programs.allMessages(); }

    void paint(juce::Graphics& g) override
    {
        Page::paint(g);

        // Each part's PC and CC0, right-aligned on its label row.
        g.setFont(Theme::labelFont(10.5f).withExtraKerningFactor(0.04f));
        g.setColour(Theme::labelDim);
        for (int part = 0; part < cells.size(); ++part) {
            const int index = state.programs.parts[size_t(part)];
            if (index < 0) continue;
            const auto& p = state.programList.programs[size_t(index)];
            auto text = juce::String(p.drumSet ? "DRUM SET  " : "") + "PC " + three(p.pc) + "   CC0 " + three(p.cc0);
            g.drawText(text, cells[part]->getBounds().removeFromTop(16).withTrimmedRight(2),
                       juce::Justification::centredRight, false);
        }

        auto note = bodyArea().withTrimmedTop(4 * 60 + 18).removeFromTop(60).toFloat();
        g.setColour(Theme::labelDim);
        g.setFont(Theme::labelFont(11.5f));
        g.drawFittedText("Click a part's display to choose a sound by group, or step through the list with the "
                         "arrows. Each part sends Bank Select (CC0) and then Program Change on its own MIDI channel "
                         "(Part 1 on channel 1 ... Part 16 on channel 16). Parts set to Off are not sent. "
                         "Use SAVE and LOAD in the Programs row to keep setups as files.",
                         note.toNearestInt(), juce::Justification::topLeft, 4, 1.0f);
    }

private:
    void showMenu(int part)
    {
        const auto& list = state.programList;
        const int current = state.programs.parts[size_t(part)];

        juce::PopupMenu menu;
        menu.addItem(1, "Off (not sent)", true, current < 0);
        menu.addSeparator();

        for (size_t c = 0; c < list.categories.size(); ++c) {
            const auto& cat = list.categories[c];
            const int end = cat.first + cat.count;
            if (cat.count > 0 && list.programs[size_t(cat.first)].drumSet) menu.addSeparator();

            // One submenu per group. Columns break between program numbers, so
            // the variations of one PC stay together.
            auto sub = std::make_unique<juce::PopupMenu>();
            int inColumn = 0;
            for (int i = cat.first; i < end;) {
                int j = i;
                while (j < end && list.programs[size_t(j)].pc == list.programs[size_t(i)].pc) ++j;
                if (inColumn > 0 && inColumn + (j - i) > numberColumnItems) {
                    sub->addColumnBreak();
                    inColumn = 0;
                }
                for (int k = i; k < j; ++k) {
                    const auto& p = list.programs[size_t(k)];
                    juce::PopupMenu::Item item(p.name);
                    item.itemID = k + 2;
                    item.isTicked = k == current;
                    item.shortcutKeyDescription = three(p.pc) + " / " + three(p.cc0);
                    sub->addItem(std::move(item));
                }
                inColumn += j - i;
                i = j;
            }

            juce::PopupMenu::Item group(cat.name);
            group.subMenu = std::move(sub);
            group.isTicked = current >= cat.first && current < end;
            menu.addItem(std::move(group));
        }

        juce::Component::SafePointer<ProgramsPage> safe(this);
        menu.showMenuAsync(juce::PopupMenu::Options().withTargetComponent(cells[part]), [safe, part](int result) {
            if (result <= 0 || safe == nullptr) return;
            auto& page = *safe;
            page.state.programs.parts[size_t(part)] = result == 1 ? ProgramSetup::off : result - 2;
            const auto& binding = page.cells[part]->getBinding();
            page.state.lastEditedName = binding.name();
            page.state.lastEditedValue = binding.display();
            page.state.parameterEdited({ binding.name(), binding.messages });
            page.refresh();
        });
    }
};

} // namespace

std::unique_ptr<Page> makeProgramsPage(AppState& s) { return std::make_unique<ProgramsPage>(s); }

} // namespace sc88::ui
