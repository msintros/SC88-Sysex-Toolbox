import pygame
import math
import random
import os
import time
import json
from pathlib import Path
import sysex_generator
import mido

import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    APP_DIR = Path(sys._MEIPASS)
else:
    APP_DIR = Path(__file__).resolve().parent

os.chdir(APP_DIR)

# Always resolve efx.json and gui_resources relative to this script,
# regardless of the shell's current working directory.
APP_DIR = Path(__file__).resolve().parent
os.chdir(APP_DIR)

APP_VERSION = "a7"
if os.name == "posix" and Path.home().joinpath("Library").exists():
    SETTINGS_DIR = Path.home() / "Library" / "Application Support" / "SC88 Flashlight"
else:
    SETTINGS_DIR = Path.home() / ".sc88_flashlight"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"

DEFAULT_SETTINGS = {
    "midi_output": None,
    "sysex_delay_ms": 10,
    "repeat_interval_ms": 95,
    "midi_save_location": str(Path.home() / "Downloads" / "SC88 Flashlight MIDI"),
}

def load_settings():
    settings = DEFAULT_SETTINGS.copy()
    try:
        if SETTINGS_FILE.exists():
            loaded = json.loads(SETTINGS_FILE.read_text())
            if isinstance(loaded, dict):
                settings.update(loaded)
    except Exception as exc:
        print(f"Could not load settings: {exc}")

    # Clamp numeric settings in case the file was hand-edited.
    settings["sysex_delay_ms"] = max(0, min(250, int(settings.get("sysex_delay_ms", 10))))
    settings["repeat_interval_ms"] = max(25, min(250, int(settings.get("repeat_interval_ms", 95))))
    if not settings.get("midi_save_location"):
        settings["midi_save_location"] = str(Path.home() / "Downloads" / "SC88 Flashlight MIDI")
    return settings

def save_settings():
    try:
        SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps(appSettings, indent=2))
    except Exception as exc:
        print(f"Could not save settings: {exc}")

appSettings = load_settings()

outport = None
currentMidiOutputName = None
midiOutputNames = []
midiDropdownOpen = False
midiDropdownScroll = 0
midiScrollbarDragging = False
midiScrollbarDragOffset = 0

# Pop-up menus are modal input layers: while one is open, controls behind it
# still render but cannot receive clicks. Pop-up controls opt back in explicitly.
popupModalOpen = False
mouseWheelY = 0

# MIDI-file export state.  "Parameter" means the most recently edited value
# on the current page; "Page" means the complete state represented by that page.
lastEditedParameter = None
exportStatus = ""
exportStatusUntil = 0
parameterDragTargets = []
EXPORT_DIR = Path(appSettings["midi_save_location"]).expanduser()
DRAG_DIR = (
    Path.home() / "Library" / "Caches" / "SC88 Flashlight" / "Drag MIDI"
    if os.name == "posix" and Path.home().joinpath("Library").exists()
    else Path.home() / ".cache" / "sc88_flashlight" / "drag_midi"
)

# a5: optional native macOS drag source.  The editor still runs normally when
# PyObjC is absent; clicking PARAM MIDI / PAGE MIDI continues to save files.
NATIVE_DRAG_AVAILABLE = False
nativeDragError = ""
_nativeDragSource = None
try:
    import objc
    from AppKit import (
        NSApplication,
        NSDraggingItem,
        NSWorkspace,
        NSOpenPanel,
        NSModalResponseOK,
        NSDragOperationCopy,
        NSEvent,
        NSEventTypeLeftMouseDragged,
    )
    from Foundation import NSObject, NSURL, NSMakeRect

    class FlashlightDragSource(NSObject):
        def draggingSession_sourceOperationMaskForDraggingContext_(self, session, context):
            return NSDragOperationCopy

        def ignoreModifierKeysForDraggingSession_(self, session):
            return True

    _nativeDragSource = FlashlightDragSource.alloc().init()
    NATIVE_DRAG_AVAILABLE = True
except Exception as exc:
    nativeDragError = str(exc)
    print("Native macOS MIDI drag unavailable (PyObjC not loaded):", exc)


def cleanup_drag_midi_cache(max_age_days=2):
    """Keep drag payloads alive long enough for DAWs, but avoid cache buildup."""
    try:
        if not DRAG_DIR.exists():
            return
        cutoff = time.time() - max_age_days * 86400
        for path in DRAG_DIR.glob("*.mid"):
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink()
            except Exception:
                pass
    except Exception:
        pass


cleanup_drag_midi_cache()


def refresh_midi_outputs():
    global midiOutputNames
    try:
        midiOutputNames = list(mido.get_output_names())
    except Exception:
        midiOutputNames = []
    return midiOutputNames


def select_midi_output(name):
    global outport, currentMidiOutputName

    if name == currentMidiOutputName and outport is not None:
        return True

    try:
        new_port = mido.open_output(name)
    except Exception as exc:
        print(f"Could not open MIDI output '{name}': {exc}")
        return False

    if outport is not None:
        try:
            outport.close()
        except Exception:
            pass

    outport = new_port
    currentMidiOutputName = name
    appSettings["midi_output"] = name
    save_settings()
    print(f"MIDI output: {name}")
    return True


pageSendPacingActive = False
lastMidiSendTime = 0.0

def send_midi(message):
    global lastMidiSendTime
    if outport is None:
        return

    if pageSendPacingActive and appSettings["sysex_delay_ms"] > 0 and lastMidiSendTime:
        minimum_gap = appSettings["sysex_delay_ms"] / 1000.0
        remaining = minimum_gap - (time.monotonic() - lastMidiSendTime)
        if remaining > 0:
            time.sleep(remaining)

    outport.send(message)
    lastMidiSendTime = time.monotonic()


# Prefer the project's original IAC destination when it exists; otherwise
# pick the first available MIDI output.  If none exist, the UI still opens.
refresh_midi_outputs()
if midiOutputNames:
    saved_output = appSettings.get("midi_output")
    preferred = (
        saved_output if saved_output in midiOutputNames
        else 'IAC Driver Bus 1' if 'IAC Driver Bus 1' in midiOutputNames
        else midiOutputNames[0]
    )
    select_midi_output(preferred)
# pygame setup
pygame.init()

awesomeWindowWidth=1040
awesomeWindowHeight=670

screen = pygame.display.set_mode((awesomeWindowWidth, awesomeWindowHeight))
pygame.display.set_caption(f"SC88 Flashlight {APP_VERSION}")
pygame.scrap.init()
clock = pygame.time.Clock()
running = True

buttonLeftImg=pygame.image.load('gui_resources/button_left.png')
buttonMidImg=pygame.image.load('gui_resources/button_middle.png')
buttonRightImg=pygame.image.load('gui_resources/button_right.png')

ButtonFont = pygame.font.SysFont("Helvetica Neue", 14, bold=False)
PanelFont = pygame.font.SysFont("Helvetica Neue", 16, bold=False)
SmallFont = pygame.font.SysFont("Helvetica Neue", 12, bold=False)
DropdownFont = pygame.font.SysFont("Helvetica Neue", 12, bold=False)

screenNWImg=pygame.image.load('gui_resources/screen_NW.png')
screenNImg=pygame.image.load('gui_resources/screen_N.png')
screenNEImg=pygame.image.load('gui_resources/screen_NE.png')
screenEImg=pygame.image.load('gui_resources/screen_E.png')
screenSEImg=pygame.image.load('gui_resources/screen_SE.png')
screenSImg=pygame.image.load('gui_resources/screen_S.png')
screenSWImg=pygame.image.load('gui_resources/screen_SW.png')
screenWImg=pygame.image.load('gui_resources/screen_W.png')

buttonNWImg=pygame.image.load('gui_resources/button_NW.png')
buttonNImg=pygame.image.load('gui_resources/button_N.png')
buttonNEImg=pygame.image.load('gui_resources/button_NE.png')
buttonEImg=pygame.image.load('gui_resources/button_E.png')
buttonSEImg=pygame.image.load('gui_resources/button_SE.png')
buttonSImg=pygame.image.load('gui_resources/button_S.png')
buttonSWImg=pygame.image.load('gui_resources/button_SW.png')
buttonWImg=pygame.image.load('gui_resources/button_W.png')
import pyperclip
import json
buttons=['EFX TYPE',
         'EFX ASSIGN',
         'EQ',
         'CHORUS',
         'DELAY',
         'REVERB',
         'GLOBAL',
         'SYSTEM',
         'TUNING',
         'BASIC',
         'RECEIVE',
         'TONE',
         'ROUTING',
         'MOD',
         'BEND',
         'AFTERTOUCH',
         'CC1',
         'CC2']

efxParams=[]
with open('efx.json','r') as f:
    efxtypes=json.load(f)


alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-=!@#$%^&*()_+~`{}|[]\\:";\'<>?,./ '

rolandFont=pygame.image.load('gui_resources/RolandFontBG.png')

def update_fps():
    fps = str(int(clock.get_fps()))+' FPS'
    fps_text = ButtonFont.render(fps, 1, pygame.Color("coral"))
    return fps_text

def shorten_midi_name(name, max_chars=27):
    if not name:
        return "NO MIDI OUTPUT"
    if len(name) <= max_chars:
        return name
    return name[:max_chars - 3] + "..."


def render_midi_picker(x, y, width=230, draw_popup=True, draw_button=True):
    global midiDropdownOpen, midiDropdownScroll
    global midiScrollbarDragging, midiScrollbarDragOffset

    display_name = shorten_midi_name(currentMidiOutputName)
    if draw_button and renderButton(x, y, width, "MIDI: " + display_name, popup=True):
        midiDropdownOpen = not midiDropdownOpen
        if midiDropdownOpen:
            refresh_midi_outputs()
            midiDropdownScroll = 0
        else:
            midiScrollbarDragging = False

    if not midiDropdownOpen or not draw_popup:
        return

    row_height = 22
    scrollbar_width = 12
    popup_gap = 4
    screen_margin = 10
    # Leave the bottom action bar visually clear even when opening downward.
    bottom_reserved = 22
    names = midiOutputNames[:] if midiOutputNames else ["<No MIDI outputs found>"]

    # Keep the popup entirely inside the window. Choose whichever side of the
    # picker has more room, and show only as many rows as fit there.
    available_above = max(0, y - screen_margin - popup_gap)
    available_below = max(0, awesomeWindowHeight - screen_margin - bottom_reserved - (y + 28) - popup_gap)
    open_below = available_below >= available_above
    available = available_below if open_below else available_above
    visible_rows = max(1, min(len(names), int(available // row_height)))
    menu_height = visible_rows * row_height
    menu_y = y + 28 + popup_gap if open_below else y - popup_gap - menu_height

    max_scroll = max(0, len(names) - visible_rows)
    midiDropdownScroll = max(0, min(midiDropdownScroll, max_scroll))

    mousex, mousey = pygame.mouse.get_pos()
    popup_rect = pygame.Rect(x, menu_y, width, menu_height)

    # Mouse wheel scrolls only while the pointer is over the popup.
    if mouseWheelY and popup_rect.collidepoint(mousex, mousey) and max_scroll > 0:
        midiDropdownScroll = max(
            0, min(max_scroll, midiDropdownScroll - mouseWheelY)
        )

    scrollable = len(names) > visible_rows
    list_width = width - scrollbar_width if scrollable else width

    pygame.draw.rect(screen, '#222222', (x - 3, menu_y - 3, width + 6, menu_height + 6))

    first = midiDropdownScroll
    last = min(len(names), first + visible_rows)
    for visible_index, name_index in enumerate(range(first, last)):
        name = names[name_index]
        row_y = menu_y + visible_index * row_height
        pygame.draw.rect(screen, '#444444', (x, row_y, list_width, row_height))
        pygame.draw.rect(screen, '#777777', (x, row_y, list_width, row_height), 1)

        shown = shorten_midi_name(name, 31)
        img = DropdownFont.render(shown, True, '#ffffff')
        screen.blit(img, (x + 6, row_y + 3))

        if name == currentMidiOutputName:
            pygame.draw.rect(screen, '#dddddd', (x + 2, row_y + 2, 3, row_height - 4))

        if newMouse[0] and not oldMouse[0]:
            if x <= mousex <= x + list_width and row_y <= mousey <= row_y + row_height:
                if midiOutputNames:
                    select_midi_output(name)
                midiDropdownOpen = False
                midiScrollbarDragging = False
                break

    if scrollable and midiDropdownOpen:
        track_x = x + width - scrollbar_width
        track_rect = pygame.Rect(track_x, menu_y, scrollbar_width, menu_height)
        pygame.draw.rect(screen, '#2b2b2b', track_rect)
        pygame.draw.rect(screen, '#666666', track_rect, 1)

        thumb_height = max(24, int(menu_height * visible_rows / len(names)))
        travel = max(1, menu_height - thumb_height)
        thumb_y = menu_y + int(travel * midiDropdownScroll / max_scroll)
        thumb_rect = pygame.Rect(track_x + 2, thumb_y, scrollbar_width - 4, thumb_height)
        pygame.draw.rect(screen, '#999999', thumb_rect)

        just_pressed = bool(newMouse[0]) and not oldMouse[0]
        if just_pressed and thumb_rect.collidepoint(mousex, mousey):
            midiScrollbarDragging = True
            midiScrollbarDragOffset = mousey - thumb_y
        elif just_pressed and track_rect.collidepoint(mousex, mousey):
            # Clicking the track jumps the thumb toward that position.
            target = mousey - menu_y - thumb_height / 2
            ratio = max(0.0, min(1.0, target / travel))
            midiDropdownScroll = int(round(ratio * max_scroll))

        if midiScrollbarDragging:
            if newMouse[0]:
                target_y = mousey - midiScrollbarDragOffset
                ratio = max(0.0, min(1.0, (target_y - menu_y) / travel))
                midiDropdownScroll = int(round(ratio * max_scroll))
            else:
                midiScrollbarDragging = False


def effect_display_name(text):
    """
    Normalize effect names for display.

    The source data contains an arrow glyph in the Chorus->Flanger name
    that is not consistently supported by every font/rendering path.
    """
    name = str(text)
    for arrow in ("→", "⇒", "►", "▶", "›", "➜", "➝"):
        name = name.replace(arrow, ">")

    # Be deliberately defensive about this one known label in case the
    # source contains an unrecognized symbol between the two words.
    if name.startswith("Cho") and "Flanger" in name:
        name = "Cho > Flanger"

    return name


def roland_safe_text(text):
    return effect_display_name(text)


def renderRolandText(x,y,text):
    for _i in range(len(text)):
        chn=int(ord(text[_i]))
        char = pygame.Surface((5, 7))
        char.blit(rolandFont, (0, 0), (5*(chn % 16), 7*math.floor(chn/16), 5, 7))
        char=pygame.transform.scale(char,(10,14))
        screen.blit(char, (x+(11*_i),y))

def renderButton(x,y,width,text,popup=False):
    screen.blit(buttonLeftImg, (x,y))
    for _i in range(width-6):
        screen.blit(buttonMidImg, (x+3+_i,y))
    screen.blit(buttonRightImg, (x+width-3,y))

    # Center from the actual rendered glyph bounds instead of estimating
    # character widths.  This fixes alignment for all standard buttons:
    # main panel, SysEx buttons, A/B selectors, Port A/B, etc.
    img = PanelFont.render(text.upper(), True, '#ffffff')
    text_rect = img.get_rect(center=(round(x + width / 2), round(y + 14)))
    screen.blit(img, text_rect)

    clicked=False
    if popupModalOpen and not popup:
        return False
    if newMouse[0] and newMouse[0]!=oldMouse[0]:
        mousex,mousey=pygame.mouse.get_pos()
        if mousex>=x and mousex<=x+width:
            if mousey>=y and mousey<=y+28:
                clicked=True
    #print(clicked)
    return clicked

# Press-and-hold repeat state for compact increment buttons.
heldRepeatKey = None
heldRepeatStarted = 0
heldRepeatLast = 0
HOLD_REPEAT_DELAY_MS = 420
HOLD_REPEAT_INTERVAL_MS = appSettings["repeat_interval_ms"]

def renderButtonBetter(x,y,width,height,text,popup=False):
    global heldRepeatKey, heldRepeatStarted, heldRepeatLast

    pygame.draw.rect(screen, '#444444', (x+2,y+2,width-4,height-4))
    screen.blit(buttonNWImg, (x,y))

    for _i in range(round(width)-4):
        screen.blit(buttonNImg, (x+2+_i,y))
    screen.blit(buttonNEImg, (x+width-1,y))

    for _i in range(round(height)-5):
        screen.blit(buttonWImg, (x,y+2+_i))
        screen.blit(buttonEImg, (x+width-2,y+2+_i))

    screen.blit(buttonSWImg, (x,y+height-3))
    for _i in range(round(width)-6):
        screen.blit(buttonSImg, (x+3+_i,y+height-3))
    screen.blit(buttonSEImg, (x+width-3,y+height-3))

    mousex, mousey = pygame.mouse.get_pos()
    inside = (x <= mousex <= x + width and y <= mousey <= y + height)
    pressed = bool(newMouse[0])
    just_pressed = pressed and not oldMouse[0]
    key = (round(x), round(y), round(width), round(height))
    now = pygame.time.get_ticks()

    clicked = False

    if popupModalOpen and not popup:
        return False

    if just_pressed and inside:
        clicked = True
        heldRepeatKey = key
        heldRepeatStarted = now
        heldRepeatLast = now

    elif pressed and inside and heldRepeatKey == key:
        if now - heldRepeatStarted >= HOLD_REPEAT_DELAY_MS:
            if now - heldRepeatLast >= HOLD_REPEAT_INTERVAL_MS:
                clicked = True
                heldRepeatLast = now

    if not pressed and heldRepeatKey is not None:
        heldRepeatKey = None
        heldRepeatStarted = 0
        heldRepeatLast = 0

    return clicked

def set_export_status(text, duration_ms=1800):
    global exportStatus, exportStatusUntil
    exportStatus = str(text)
    exportStatusUntil = pygame.time.get_ticks() + duration_ms if duration_ms else 0


def clear_expired_export_status():
    global exportStatus, exportStatusUntil
    if exportStatus and exportStatusUntil and pygame.time.get_ticks() >= exportStatusUntil:
        exportStatus = ""
        exportStatusUntil = 0


def shorten_path(path, max_chars=38):
    text = str(path)
    home = str(Path.home())
    if text.startswith(home):
        text = "~" + text[len(home):]
    if len(text) <= max_chars:
        return text
    return "..." + text[-(max_chars - 3):]


def choose_midi_save_location():
    global EXPORT_DIR
    if not NATIVE_DRAG_AVAILABLE:
        set_export_status("Folder chooser requires PyObjC")
        return False
    try:
        panel = NSOpenPanel.openPanel()
        panel.setCanChooseFiles_(False)
        panel.setCanChooseDirectories_(True)
        panel.setAllowsMultipleSelection_(False)
        panel.setCanCreateDirectories_(True)
        try:
            panel.setDirectoryURL_(NSURL.fileURLWithPath_(str(EXPORT_DIR)))
        except Exception:
            pass
        if panel.runModal() == NSModalResponseOK:
            selected = Path(str(panel.URL().path())).expanduser()
            EXPORT_DIR = selected
            appSettings["midi_save_location"] = str(selected)
            save_settings()
            set_export_status(f"MIDI saves: {shorten_path(selected, 48)}", 2200)
            return True
    except Exception as exc:
        set_export_status(f"Folder chooser failed: {exc}", 3000)
        print("Folder chooser failed:", repr(exc))
    return False


def register_parameter_drag_target(rect, item):
    rect = pygame.Rect(rect)
    parameterDragTargets.append((rect, item))
    mouse = pygame.mouse.get_pos()
    # The most recently edited value is the PARAM MIDI scope. Hovering any
    # value also makes its direct-drag affordance visible without clutter.
    if item == lastEditedParameter:
        pygame.draw.rect(screen, '#dddddd', rect, 1)
    elif rect.collidepoint(mouse):
        pygame.draw.rect(screen, '#aaaaaa', rect, 1)


def parameter_drag_target_at_pos(pos):
    # Last drawn wins if fields ever overlap.
    for rect, item in reversed(parameterDragTargets):
        if rect.collidepoint(pos):
            return item
    return None


def messages_for_parameter_item(item):
    global lastEditedParameter
    previous = lastEditedParameter
    try:
        lastEditedParameter = item
        return current_parameter_midi_messages()
    finally:
        lastEditedParameter = previous


def render_settings_page():
    global HOLD_REPEAT_INTERVAL_MS
    global midiDropdownOpen, midiDropdownScroll, midiScrollbarDragging

    title = f"SC88 Flashlight {APP_VERSION} Settings"
    titleWidth = max(24, len(title) + 2) * 11
    titleX = (awesomeWindowWidth - titleWidth) / 2
    renderScreen(titleX, 262, titleWidth, 20)
    renderRolandText(titleX + 3, 265, title)

    labelX = 205
    labelWidth = 245
    valueX = labelX + labelWidth + 2
    valueWidth = 300
    arrowX = valueX + valueWidth + 4

    # MIDI output and save location use the same compact picker treatment:
    # an orange Roland-style value field plus a simple white text affordance.
    pickerHintX = arrowX + 8
    pickerHint = SmallFont.render("click to choose", True, '#ffffff')

    midiY = 305
    renderScreen(labelX, midiY, labelWidth, 20)
    renderRolandText(labelX + 4, midiY + 3, "MIDI Output")
    renderScreen(valueX, midiY, valueWidth, 20)
    renderRolandText(valueX + 4, midiY + 3, shorten_midi_name(currentMidiOutputName, 26))
    screen.blit(pickerHint, (pickerHintX, midiY + 3))
    midiPickerRect = pygame.Rect(valueX, midiY, valueWidth, 20)
    midiHintRect = pygame.Rect(pickerHintX, midiY, pickerHint.get_width(), 20)
    if newMouse[0] and not oldMouse[0] and (midiPickerRect.collidepoint(pygame.mouse.get_pos()) or midiHintRect.collidepoint(pygame.mouse.get_pos())):
        midiDropdownOpen = not midiDropdownOpen
        if midiDropdownOpen:
            refresh_midi_outputs()
            midiDropdownScroll = 0
        else:
            midiScrollbarDragging = False

    saveY = midiY + 34
    renderScreen(labelX, saveY, labelWidth, 20)
    renderRolandText(labelX + 4, saveY + 3, "MIDI Save Location")
    renderScreen(valueX, saveY, valueWidth, 20)
    renderRolandText(valueX + 4, saveY + 3, shorten_path(EXPORT_DIR, 26))
    screen.blit(pickerHint, (pickerHintX, saveY + 3))
    savePickerRect = pygame.Rect(valueX, saveY, valueWidth, 20)
    saveHintRect = pygame.Rect(pickerHintX, saveY, pickerHint.get_width(), 20)
    if newMouse[0] and not oldMouse[0] and not midiDropdownOpen and (savePickerRect.collidepoint(pygame.mouse.get_pos()) or saveHintRect.collidepoint(pygame.mouse.get_pos())):
        choose_midi_save_location()

    dragY = midiY + 68
    renderScreen(labelX, dragY, labelWidth, 20)
    renderRolandText(labelX + 4, dragY + 3, "DAW Drag")
    renderScreen(valueX, dragY, valueWidth, 20)
    drag_state = "READY" if NATIVE_DRAG_AVAILABLE else "PYOBJC REQUIRED"
    renderRolandText(valueX + 4, dragY + 3, drag_state)

    # Delay inserted only between messages in an automatically generated
    # multi-message page send. Single-parameter live edits are not delayed.
    sysexY = 407
    renderScreen(labelX, sysexY, labelWidth, 20)
    renderRolandText(labelX + 4, sysexY + 3, "SysEx Message Delay")
    renderScreen(valueX, sysexY, valueWidth, 20)
    renderRolandText(valueX + 5, sysexY + 3, f"{appSettings['sysex_delay_ms']} ms")
    upDelay = renderButtonBetter(arrowX, sysexY, 20, 10, "up")
    downDelay = renderButtonBetter(arrowX, sysexY + 11, 20, 10, "down")
    if upDelay:
        appSettings["sysex_delay_ms"] = min(250, appSettings["sysex_delay_ms"] + 1)
        save_settings()
    if downDelay:
        appSettings["sysex_delay_ms"] = max(0, appSettings["sysex_delay_ms"] - 1)
        save_settings()

    repeatY = 450
    renderScreen(labelX, repeatY, labelWidth, 20)
    renderRolandText(labelX + 4, repeatY + 3, "Button Repeat Interval")
    renderScreen(valueX, repeatY, valueWidth, 20)
    renderRolandText(valueX + 5, repeatY + 3, f"{appSettings['repeat_interval_ms']} ms")
    upRepeat = renderButtonBetter(arrowX, repeatY, 20, 10, "up")
    downRepeat = renderButtonBetter(arrowX, repeatY + 11, 20, 10, "down")
    if upRepeat:
        appSettings["repeat_interval_ms"] = min(250, appSettings["repeat_interval_ms"] + 5)
        HOLD_REPEAT_INTERVAL_MS = appSettings["repeat_interval_ms"]
        save_settings()
    if downRepeat:
        appSettings["repeat_interval_ms"] = max(25, appSettings["repeat_interval_ms"] - 5)
        HOLD_REPEAT_INTERVAL_MS = appSettings["repeat_interval_ms"]
        save_settings()

    # A smaller interval means faster held-button stepping.
    renderScreen(labelX, 474, labelWidth + valueWidth + 2, 20)
    renderRolandText(labelX + 4, 477, "Lower repeat interval = faster value changes")

def step_efx_value(param, direction):
    current = param[1]
    vals = param[2]

    if isinstance(vals, list):
        valid = [raw for raw, shown in enumerate(vals) if shown != ""]
        if not valid:
            return current

        if current not in valid:
            current = min(valid, key=lambda x: abs(x - current))

        pos = valid.index(current)
        return valid[(pos + direction) % len(valid)]

    return (current + direction) % 128


# ----------------------------------------------------------------------
# Generic parameter-page framework
#
# A page definition contains a title and a list of parameters.
# Each parameter knows its SysEx address, default raw value, and either:
#   - an enum list, or
#   - a raw_min/raw_max numeric range.
#
# The UI renderer, value stepping, display formatting, and SysEx code are
# shared so Reverb/Chorus/Delay/System/etc. don't each need their own
# hand-written +/- machinery.
# ----------------------------------------------------------------------


# ----------------------------------------------------------------------
# Per-Part Insertion EFX assignment
#
# PART EFX ASSIGN is at 40 4x 22 for Group A when sending via Port A.
# The SC-88 Pro manual specifies that Group B can be addressed from the
# same port by using 50 ** ** instead of 40 ** **.
#
# Roland block numbering is slightly unusual:
# Part 1..9  -> block 1..9
# Part 10    -> block 0
# Part 11..16-> block A..F
# ----------------------------------------------------------------------

efxPartEnabled = {
    "A": [False] * 16,
    "B": [False] * 16,
}


# MIDI-addressable System Parameters only.
# SYSTEM MODE SET: 00 = Mode 1 (Single), 01 = Mode 2 (Double)
systemModeValue = 0

# CHANNEL MSG RX PORT, blocks 00-1F:
# factory defaults are Port A for 00-0F and Port B for 10-1F.
systemBlockPorts = [0] * 16 + [1] * 16


# ----------------------------------------------------------------------
# Per-Part Scale Tuning
#
# Address 40 1x 40-4B for Group A via Port A.
# Group B from the same port uses the parallel 50 ** ** address space.
# Raw 00-7F = -64..+63 cents; 40H = 0 cents.
# ----------------------------------------------------------------------

scaleTuneNotes = ["C", "C#", "D", "D#", "E", "F",
                  "F#", "G", "G#", "A", "A#", "B"]
scaleTuneGroup = "A"
scaleTunePart = 1
scaleTuneValues = {
    "A": [[0x40] * 12 for _ in range(16)],
    "B": [[0x40] * 12 for _ in range(16)],
}


def scale_tune_address(group, part_number, note_index):
    first = "40" if group == "A" else "50"
    block = part_to_block(part_number)
    return [first, "1" + block, format(0x40 + note_index, "02x")]


def send_scale_tune(group, part_number, note_index, raw_value):
    sysex = sysex_generator.generate_sysex(
        scale_tune_address(group, part_number, note_index),
        [format(raw_value, "02x")],
        True,
    )
    send_midi(mido.Message("sysex", data=sysex))


def scale_tune_sysex_text(group, part_number, note_index, raw_value):
    return sysex_generator.generate_sysex(
        scale_tune_address(group, part_number, note_index),
        [format(raw_value, "02x")],
        False,
    )


def format_scale_tune(raw_value):
    cents = raw_value - 0x40
    if cents > 0:
        return f"+{cents} cent"
    return f"{cents} cent"


def render_scale_tuning_page():
    global scaleTuneGroup, scaleTunePart

    changed = None

    titleWidth = 18 * 13
    titleX = (awesomeWindowWidth - titleWidth) / 2
    renderScreen(titleX, 262, titleWidth, 20)
    renderRolandText(titleX + 3, 265, "Scale Tuning")

    selectorY = 290
    renderScreen(105, selectorY, 80, 20)
    renderRolandText(109, selectorY + 3, "Part")

    renderScreen(190, selectorY, 42, 20)
    renderRolandText(199, selectorY + 3, scaleTuneGroup)
    upGroup = renderButtonBetter(237, selectorY, 20, 10, "up")
    downGroup = renderButtonBetter(237, selectorY + 11, 20, 10, "down")
    if upGroup or downGroup:
        scaleTuneGroup = "B" if scaleTuneGroup == "A" else "A"

    renderScreen(266, selectorY, 76, 20)
    renderRolandText(272, selectorY + 3, f"{scaleTuneGroup}{scaleTunePart:02d}")

    upPart = renderButtonBetter(347, selectorY, 20, 10, "up")
    downPart = renderButtonBetter(347, selectorY + 11, 20, 10, "down")

    if upPart:
        scaleTunePart = 1 if scaleTunePart == 16 else scaleTunePart + 1
    if downPart:
        scaleTunePart = 16 if scaleTunePart == 1 else scaleTunePart - 1

    values = scaleTuneValues[scaleTuneGroup][scaleTunePart - 1]

    columns = 2
    rows = 6
    fieldWidth = 165
    valueWidth = 210
    arrowWidth = 20
    columnGap = 30
    rowGap = 4

    fullColumnWidth = fieldWidth + valueWidth + arrowWidth + 4
    totalWidth = (fullColumnWidth * columns) + columnGap
    startX = (awesomeWindowWidth - totalWidth) / 2
    startY = 320

    for note_index, note_name in enumerate(scaleTuneNotes):
        column = note_index // rows
        row = note_index % rows

        x = startX + column * (fullColumnWidth + columnGap)
        y = startY + row * (20 + rowGap)

        renderScreen(x, y, fieldWidth, 20)
        renderScreen(x + fieldWidth + 2, y, valueWidth, 20)
        register_parameter_drag_target(
            (x + fieldWidth + 2, y, valueWidth, 20),
            (screener, "scale", note_index),
        )

        renderRolandText(x + 3, y + 3, note_name)
        renderRolandText(
            x + fieldWidth + 5,
            y + 3,
            format_scale_tune(values[note_index]),
        )

        upClicked = renderButtonBetter(
            x + fieldWidth + valueWidth + 4,
            y,
            arrowWidth,
            10,
            "up",
        )
        downClicked = renderButtonBetter(
            x + fieldWidth + valueWidth + 4,
            y + 11,
            arrowWidth,
            10,
            "down",
        )

        if upClicked:
            values[note_index] = (
                0x00 if values[note_index] == 0x7F
                else values[note_index] + 1
            )
            changed = note_index

        if downClicked:
            values[note_index] = (
                0x7F if values[note_index] == 0x00
                else values[note_index] - 1
            )
            changed = note_index

    return changed


def part_to_block(part_number):
    if 1 <= part_number <= 9:
        return format(part_number, "X")
    if part_number == 10:
        return "0"
    if 11 <= part_number <= 16:
        return format(part_number - 1, "X")
    raise ValueError("Part number must be 1..16")


def efx_part_address(group, part_number):
    first = "40" if group == "A" else "50"
    block = part_to_block(part_number)
    return [first, "4" + block, "22"]


def send_part_efx(group, part_number, enabled):
    address = efx_part_address(group, part_number)
    value = ["01" if enabled else "00"]
    sysex = sysex_generator.generate_sysex(address, value, True)
    send_midi(mido.Message("sysex", data=sysex))


def part_efx_sysex_text(group, part_number, enabled):
    address = efx_part_address(group, part_number)
    value = ["01" if enabled else "00"]
    return sysex_generator.generate_sysex(address, value, False)


def render_efx_part_assign_page():
    """Draw 32 Part EFX assignments in a compact parameter-grid layout."""
    title = "Insertion EFX Assign"
    titleWidth = 22 * 11
    titleX = (awesomeWindowWidth - titleWidth) / 2
    renderScreen(titleX, 262, titleWidth, 20)
    renderRolandText(titleX + 3, 265, title)

    changed = None

    # Four compact columns of eight Parts.
    startX = 48
    startY = 300
    fieldWidth = 62
    valueWidth = 110
    arrowWidth = 20
    columnGap = 24
    rowGap = 3
    fullColumnWidth = fieldWidth + valueWidth + arrowWidth + 4

    column_specs = [
        ("A", 1, 8),
        ("A", 9, 16),
        ("B", 1, 8),
        ("B", 9, 16),
    ]

    for col, (group, first_part, last_part) in enumerate(column_specs):
        x = startX + col * (fullColumnWidth + columnGap)

        for row, part_number in enumerate(range(first_part, last_part + 1)):
            y = startY + row * (20 + rowGap)
            state = efxPartEnabled[group][part_number - 1]

            renderScreen(x, y, fieldWidth, 20)
            renderRolandText(x + 3, y + 3, f"{group}{part_number:02d}")

            renderScreen(x + fieldWidth + 2, y, valueWidth, 20)
            register_parameter_drag_target(
                (x + fieldWidth + 2, y, valueWidth, 20),
                (screener, "efx_assign", group, part_number),
            )
            renderRolandText(
                x + fieldWidth + 5,
                y + 3,
                "EFX" if state else "BYPASS",
            )

            upClicked = renderButtonBetter(
                x + fieldWidth + valueWidth + 4,
                y,
                arrowWidth,
                10,
                "up",
            )
            downClicked = renderButtonBetter(
                x + fieldWidth + valueWidth + 4,
                y + 11,
                arrowWidth,
                10,
                "down",
            )

            if upClicked or downClicked:
                state = not state
                efxPartEnabled[group][part_number - 1] = state
                changed = (group, part_number, state)

    return changed


def send_system_mode(raw_value):
    sysex = sysex_generator.generate_sysex(
        ["00", "00", "7F"],
        [format(raw_value, "02x")],
        True,
    )
    send_midi(mido.Message("sysex", data=sysex))


def system_mode_sysex_text(raw_value):
    return sysex_generator.generate_sysex(
        ["00", "00", "7F"],
        [format(raw_value, "02x")],
        False,
    )


def send_system_block_port(block_number, port_value):
    sysex = sysex_generator.generate_sysex(
        ["00", "01", format(block_number, "02x")],
        [format(port_value, "02x")],
        True,
    )
    send_midi(mido.Message("sysex", data=sysex))


def system_block_port_sysex_text(block_number, port_value):
    return sysex_generator.generate_sysex(
        ["00", "01", format(block_number, "02x")],
        [format(port_value, "02x")],
        False,
    )


def render_system_parameter_page():
    """
    Render only the System Parameters that have explicit SysEx addresses
    in the SC-88 Pro MIDI implementation.

    Returns:
      ("mode", new_value) or ("block", block_number, new_port) or None
    """
    global systemModeValue

    titleWidth = 22 * 13
    titleX = (awesomeWindowWidth - titleWidth) / 2
    renderScreen(titleX, 262, titleWidth, 20)
    renderRolandText(titleX + 3, 265, "System Parameters")

    changed = None

    # System Mode
    labelX = 92
    modeY = 295
    renderScreen(labelX, modeY, 190, 20)
    renderRolandText(labelX + 4, modeY + 3, "System Mode")

    modeText = "MODE 1 / SINGLE" if systemModeValue == 0 else "MODE 2 / DOUBLE"
    modeValueX = labelX + 195
    renderScreen(modeValueX, modeY, 170, 20)
    register_parameter_drag_target(
        (modeValueX, modeY, 170, 20),
        (screener, "system_mode"),
    )
    renderRolandText(modeValueX + 4, modeY + 3, modeText)
    modeUp = renderButtonBetter(modeValueX + 175, modeY, 20, 10, "up")
    modeDown = renderButtonBetter(modeValueX + 175, modeY + 11, 20, 10, "down")
    if modeUp or modeDown:
        systemModeValue = 1 - systemModeValue
        changed = ("mode", systemModeValue)

    # Channel-message receive ports, blocks 00-1F.
    startX = 92
    startY = 335
    colWidth = 200
    colGap = 35
    rowGap = 23

    for block_number in range(32):
        column = block_number // 8
        row = block_number % 8
        x = startX + column * (colWidth + colGap)
        y = startY + row * rowGap

        label = f"BLOCK {block_number:02X}"
        renderScreen(x, y, 95, 20)
        renderRolandText(x + 4, y + 3, label)

        port_value = systemBlockPorts[block_number]
        port_text = "PORT A" if port_value == 0 else "PORT B"

        portX = x + 100
        renderScreen(portX, y, 75, 20)
        register_parameter_drag_target(
            (portX, y, 75, 20),
            (screener, "system_block", block_number),
        )
        renderRolandText(portX + 4, y + 3, port_text)
        portUp = renderButtonBetter(portX + 80, y, 20, 10, "up")
        portDown = renderButtonBetter(portX + 80, y + 11, 20, 10, "down")
        if portUp or portDown:
            port_value = 1 - port_value
            systemBlockPorts[block_number] = port_value
            changed = ("block", block_number, port_value)

    return changed


# ----------------------------------------------------------------------
# Part Parameters
#
# Only parameters with explicit SysEx addresses in the SC-88 Pro MIDI
# implementation are included here.  The editor is split into categories
# so the very large Part parameter map remains usable in the current UI.
#
# Group A from Port A uses 40 ** **; Group B from the same port uses
# 50 ** **, matching the addressing convention already used elsewhere.
# ----------------------------------------------------------------------

partParamGroup = "A"
partParamPart = 1
partParamCategoryIndex = 0

# Main-panel pages that directly expose Part Parameter categories.
PART_PARAM_PAGE_MAP = {
    "part_basic": "Basic",
    "part_receive": "Receive",
    "part_tone": "Tone Modify",
    "part_routing": "Routing",
    "part_mod": "Mod",
    "part_bend": "Bend",
    "part_cc1": "CC1",
    "part_cc2": "CC2",
}
aftertouchCategory = "CAf"

PART_PARAM_CATEGORIES = [
    "Basic",
    "Receive",
    "Tone Modify",
    "Routing",
    "Mod",
    "Bend",
    "CAf",
    "PAf",
    "CC1",
    "CC2",
]


def _pp(name, area, offset, default, raw_min=0, raw_max=127,
        enum=None, codec=None, suffix="", data_codec=None):
    p = {
        "name": name,
        "area": area,
        "offset": offset,
        "default": default,
        "raw_min": raw_min,
        "raw_max": raw_max,
    }
    if enum is not None:
        p["enum"] = enum
    if codec is not None:
        p["display_codec"] = codec
    if suffix:
        p["suffix"] = suffix
    if data_codec is not None:
        p["data_codec"] = data_codec
    return p


PART_PARAM_DEFS = {
    "Basic": [
        # Tone number is a two-byte structure at 1x00.  The editor keeps
        # its two components separate but sends them together.
        _pp("Tone Bank MSB", "1", 0x00, 0, 0, 127, data_codec="tone_pair_bank"),
        _pp("Program", "1", 0x01, 0, 0, 127, codec="program_1_128", data_codec="tone_pair_program"),
        _pp("Rx Channel", "1", 0x02, 0, 0, 16, codec="rx_channel"),
        _pp("Mono / Poly", "1", 0x13, 1, 0, 1, enum=["Mono", "Poly"]),
        _pp("Assign Mode", "1", 0x14, 1, 0, 2,
            enum=["Single", "Limited-Multi", "Full-Multi"]),
        _pp("Rhythm Part", "1", 0x15, 0, 0, 2,
            enum=["Off", "Map 1", "Map 2"]),
        _pp("Key Shift", "1", 0x16, 0x40, 0x28, 0x58, codec="key_shift"),
        _pp("Part Level", "1", 0x19, 100, 0, 127),
        _pp("Velocity Depth", "1", 0x1A, 64, 0, 127),
        _pp("Velocity Offset", "1", 0x1B, 64, 0, 127),
        _pp("Part Pan", "1", 0x1C, 0x40, 0, 127, codec="part_pan"),
        _pp("Keyboard Low", "1", 0x1D, 0, 0, 127, codec="note_name"),
        _pp("Keyboard High", "1", 0x1E, 127, 0, 127, codec="note_name"),
        _pp("CC1 Number", "1", 0x1F, 16, 0, 95),
        _pp("CC2 Number", "1", 0x20, 17, 0, 95),
        _pp("Chorus Send", "1", 0x21, 0, 0, 127),
        _pp("Reverb Send", "1", 0x22, 40, 0, 127),
        _pp("Delay Send", "1", 0x2C, 0, 0, 127),
        _pp("Rx Bank Select", "1", 0x23, 1, 0, 1, enum=["Off", "On"]),
        _pp("Rx Bank LSB", "1", 0x24, 1, 0, 1, enum=["Off", "On"]),
        # RPN #1 style 14-bit value, transmitted MSB/LSB at 1x2A/2B.
        _pp("Pitch Fine Tune", "1", 0x2A, 0x2000, 0, 0x3FFF,
            codec="fine_tune_14bit", data_codec="14bit"),
    ],

    "Receive": [
        _pp("Rx Pitch Bend", "1", 0x03, 1, 0, 1, enum=["Off", "On"]),
        _pp("Rx Ch Pressure", "1", 0x04, 1, 0, 1, enum=["Off", "On"]),
        _pp("Rx Program Change", "1", 0x05, 1, 0, 1, enum=["Off", "On"]),
        _pp("Rx Control Change", "1", 0x06, 1, 0, 1, enum=["Off", "On"]),
        _pp("Rx Poly Pressure", "1", 0x07, 1, 0, 1, enum=["Off", "On"]),
        _pp("Rx Note Message", "1", 0x08, 1, 0, 1, enum=["Off", "On"]),
        _pp("Rx RPN", "1", 0x09, 1, 0, 1, enum=["Off", "On"]),
        _pp("Rx NRPN", "1", 0x0A, 0, 0, 1, enum=["Off", "On"]),
        _pp("Rx Modulation", "1", 0x0B, 1, 0, 1, enum=["Off", "On"]),
        _pp("Rx Volume", "1", 0x0C, 1, 0, 1, enum=["Off", "On"]),
        _pp("Rx Panpot", "1", 0x0D, 1, 0, 1, enum=["Off", "On"]),
        _pp("Rx Expression", "1", 0x0E, 1, 0, 1, enum=["Off", "On"]),
        _pp("Rx Hold 1", "1", 0x0F, 1, 0, 1, enum=["Off", "On"]),
        _pp("Rx Portamento", "1", 0x10, 1, 0, 1, enum=["Off", "On"]),
        _pp("Rx Sostenuto", "1", 0x11, 1, 0, 1, enum=["Off", "On"]),
        _pp("Rx Soft", "1", 0x12, 1, 0, 1, enum=["Off", "On"]),
    ],

    "Tone Modify": [
        _pp("Vibrato Rate", "1", 0x30, 0x40, 0, 127, codec="signed_64"),
        _pp("Vibrato Depth", "1", 0x31, 0x40, 0, 127, codec="signed_64"),
        _pp("TVF Cutoff", "1", 0x32, 0x40, 0, 127, codec="signed_64"),
        _pp("TVF Resonance", "1", 0x33, 0x40, 0, 127, codec="signed_64"),
        _pp("Env Attack", "1", 0x34, 0x40, 0, 127, codec="signed_64"),
        _pp("Env Decay", "1", 0x35, 0x40, 0, 127, codec="signed_64"),
        _pp("Env Release", "1", 0x36, 0x40, 0, 127, codec="signed_64"),
        _pp("Vibrato Delay", "1", 0x37, 0x40, 0, 127, codec="signed_64"),
    ],

    "Routing": [
        _pp("Tone Map Number", "4", 0x00, 0, 0, 3,
            enum=["Selected", "SC-55", "SC-88", "Native"]),
        _pp("Tone Map-0 Number", "4", 0x01, 3, 1, 3,
            enum=["", "SC-55", "SC-88", "Native"]),
        _pp("EQ", "4", 0x20, 1, 0, 1, enum=["Off", "On"]),
        _pp("Output Assign", "4", 0x21, 0, 0, 3,
            enum=["Output-1", "Output-2", "Output-2L", "Output-2R"]),
        _pp("Part EFX", "4", 0x22, 0, 0, 1, enum=["Bypass", "EFX"]),
    ],
}


def _controller_group(prefix, base, bend=False):
    """Build one 11-parameter controller-response category."""
    pitch_min = 0x40 if bend else 0x28
    pitch_default = 0x42 if bend else 0x40
    pitch_codec = "bend_pitch" if bend else "key_shift"
    return [
        _pp(f"{prefix} Pitch", "2", base + 0x00, pitch_default, pitch_min, 0x58, codec=pitch_codec),
        _pp(f"{prefix} TVF Cutoff", "2", base + 0x01, 0x40, 0, 127, codec="signed_64"),
        _pp(f"{prefix} Amplitude", "2", base + 0x02, 0x40, 0, 127, codec="signed_64"),
        _pp(f"{prefix} LFO1 Rate", "2", base + 0x03, 0x40, 0, 127, codec="signed_64"),
        _pp(f"{prefix} LFO1 Pitch", "2", base + 0x04, 0, 0, 127),
        _pp(f"{prefix} LFO1 TVF", "2", base + 0x05, 0, 0, 127),
        _pp(f"{prefix} LFO1 TVA", "2", base + 0x06, 0, 0, 127),
        _pp(f"{prefix} LFO2 Rate", "2", base + 0x07, 0x40, 0, 127, codec="signed_64"),
        _pp(f"{prefix} LFO2 Pitch", "2", base + 0x08, 0, 0, 127),
        _pp(f"{prefix} LFO2 TVF", "2", base + 0x09, 0, 0, 127),
        _pp(f"{prefix} LFO2 TVA", "2", base + 0x0A, 0, 0, 127),
    ]


PART_PARAM_DEFS["Mod"]  = _controller_group("Mod",  0x00)
PART_PARAM_DEFS["Bend"] = _controller_group("Bend", 0x10, bend=True)
PART_PARAM_DEFS["CAf"]  = _controller_group("CAf",  0x20)
PART_PARAM_DEFS["PAf"]  = _controller_group("PAf",  0x30)
PART_PARAM_DEFS["CC1"]  = _controller_group("CC1",  0x40)
PART_PARAM_DEFS["CC2"]  = _controller_group("CC2",  0x50)


def default_part_param_value(param, part_number):
    # Defaults whose MIDI implementation depends on Part/Block.
    if param["name"] == "Rx Channel":
        return part_number - 1
    if param["name"] == "Assign Mode":
        return 0 if part_number == 10 else 1
    if param["name"] == "Rhythm Part":
        return 1 if part_number == 10 else 0
    return param["default"]


partParamValues = {"A": [], "B": []}
for _group in ("A", "B"):
    for _part in range(1, 17):
        _cats = {}
        for _cat in PART_PARAM_CATEGORIES:
            _cats[_cat] = [
                default_part_param_value(p, _part)
                for p in PART_PARAM_DEFS[_cat]
            ]
        partParamValues[_group].append(_cats)


def part_param_address(group, part_number, param):
    first = "40" if group == "A" else "50"
    block = part_to_block(part_number)
    second = param["area"] + block
    third = format(param["offset"], "02x")
    return [first, second, third]


def format_midi_note(raw_value):
    names = ["C", "C#", "D", "D#", "E", "F",
             "F#", "G", "G#", "A", "A#", "B"]
    octave = (raw_value // 12) - 1
    return f"{names[raw_value % 12]}{octave}"


def format_part_param_value(param, raw_value):
    if "enum" in param:
        enum = param["enum"]
        if 0 <= raw_value < len(enum) and enum[raw_value] != "":
            return enum[raw_value]
        return str(raw_value)

    codec = param.get("display_codec")
    if codec == "signed_64":
        return format_signed_64(raw_value)
    if codec == "key_shift":
        n = raw_value - 0x40
        return f"{n:+d} st" if n else "0 st"
    if codec == "bend_pitch":
        return f"{raw_value - 0x40} st"
    if codec == "part_pan":
        if raw_value == 0:
            return "Random"
        n = raw_value - 0x40
        if n < 0:
            return f"L{-n}"
        if n > 0:
            return f"R{n}"
        return "Center"
    if codec == "note_name":
        return format_midi_note(raw_value)
    if codec == "program_1_128":
        return str(raw_value + 1)
    if codec == "rx_channel":
        return "Off" if raw_value == 16 else str(raw_value + 1)
    if codec == "fine_tune_14bit":
        cents = (raw_value - 0x2000) * (100.0 / 8192.0)
        sign = "+" if cents > 0 else ""
        return f"{sign}{cents:.2f} cent"

    return str(raw_value) + param.get("suffix", "")


def encode_part_param_data(param, raw_value, group, part_number, category):
    codec = param.get("data_codec")

    if codec in ("tone_pair_bank", "tone_pair_program"):
        basic = partParamValues[group][part_number - 1]["Basic"]
        bank = basic[0]
        program = basic[1]
        return [format(bank, "02x"), format(program, "02x")]

    if codec == "14bit":
        return [
            format((raw_value >> 7) & 0x7F, "02x"),
            format(raw_value & 0x7F, "02x"),
        ]

    return [format(raw_value, "02x")]


def actual_part_param_address(group, part_number, param):
    # Both halves of TONE NUMBER must be sent beginning at 1x00.
    if param.get("data_codec") in ("tone_pair_bank", "tone_pair_program"):
        p = dict(param)
        p["offset"] = 0x00
        return part_param_address(group, part_number, p)
    return part_param_address(group, part_number, param)


def send_part_param(group, part_number, category, param_index):
    param = PART_PARAM_DEFS[category][param_index]
    raw = partParamValues[group][part_number - 1][category][param_index]
    address = actual_part_param_address(group, part_number, param)
    data = encode_part_param_data(param, raw, group, part_number, category)
    sysex = sysex_generator.generate_sysex(address, data, True)
    send_midi(mido.Message("sysex", data=sysex))


def part_param_sysex_text(group, part_number, category, param_index):
    param = PART_PARAM_DEFS[category][param_index]
    raw = partParamValues[group][part_number - 1][category][param_index]
    address = actual_part_param_address(group, part_number, param)
    data = encode_part_param_data(param, raw, group, part_number, category)
    return sysex_generator.generate_sysex(address, data, False)


def step_part_param(param, current, direction):
    if "enum" in param:
        legal = list(range(param["raw_min"], param["raw_max"] + 1))
    else:
        legal = list(range(param["raw_min"], param["raw_max"] + 1))
    pos = legal.index(current) if current in legal else 0
    return legal[(pos + direction) % len(legal)]


def render_part_category_page(category, page_title=None, allow_aftertouch_switch=False):
    global partParamGroup, partParamPart, aftertouchCategory

    changed = None

    if allow_aftertouch_switch:
        category = aftertouchCategory
        if page_title is None:
            page_title = "Aftertouch"
    elif page_title is None:
        page_title = category

    titleWidth = max(18, len(page_title) + 2) * 11
    titleX = (awesomeWindowWidth - titleWidth) / 2
    renderScreen(titleX, 262, titleWidth, 20)
    renderRolandText(titleX + 3, 265, page_title)

    # Part selector shared by every Part Parameter page.
    selectorY = 290
    renderScreen(70, selectorY, 70, 20)
    renderRolandText(74, selectorY + 3, "Part")

    renderScreen(145, selectorY, 42, 20)
    renderRolandText(154, selectorY + 3, partParamGroup)
    upGroup = renderButtonBetter(192, selectorY, 20, 10, "up")
    downGroup = renderButtonBetter(192, selectorY + 11, 20, 10, "down")
    if upGroup or downGroup:
        partParamGroup = "B" if partParamGroup == "A" else "A"

    renderScreen(221, selectorY, 76, 20)
    renderRolandText(227, selectorY + 3, f"{partParamGroup}{partParamPart:02d}")

    upPart = renderButtonBetter(302, selectorY, 20, 10, "up")
    downPart = renderButtonBetter(302, selectorY + 11, 20, 10, "down")

    if upPart:
        partParamPart = 1 if partParamPart == 16 else partParamPart + 1
    if downPart:
        partParamPart = 16 if partParamPart == 1 else partParamPart - 1

    # CAf and PAf live together under AFTERTOUCH.
    if allow_aftertouch_switch:
        renderScreen(390, selectorY, 110, 20)
        renderRolandText(394, selectorY + 3, "Category")

        renderScreen(505, selectorY, 120, 20)
        renderRolandText(511, selectorY + 3,
                         "Channel" if category == "CAf" else "Poly")

        upCategory = renderButtonBetter(630, selectorY, 20, 10, "up")
        downCategory = renderButtonBetter(630, selectorY + 11, 20, 10, "down")

        if upCategory or downCategory:
            aftertouchCategory = "PAf" if aftertouchCategory == "CAf" else "CAf"
            category = aftertouchCategory

    params = PART_PARAM_DEFS[category]
    values = partParamValues[partParamGroup][partParamPart - 1][category]

    # Same two-column layout as before, but shift the internal label/value
    # boundary 30px to the right while preserving total column width.
    columns = 2
    rows = math.ceil(len(params) / columns)
    fieldWidth = 215       # was 185
    valueWidth = 175       # was 205
    arrowWidth = 20
    columnGap = 28
    rowGap = 2
    fullColumnWidth = fieldWidth + valueWidth + arrowWidth + 4
    totalWidth = fullColumnWidth * columns + columnGap
    startX = (awesomeWindowWidth - totalWidth) / 2
    startY = 320

    for index, param in enumerate(params):
        column = index // rows
        row = index % rows
        x = startX + column * (fullColumnWidth + columnGap)
        y = startY + row * (20 + rowGap)

        renderScreen(x, y, fieldWidth, 20)
        renderScreen(x + fieldWidth + 2, y, valueWidth, 20)
        register_parameter_drag_target(
            (x + fieldWidth + 2, y, valueWidth, 20),
            (screener, "part", category, index),
        )

        renderRolandText(x + 3, y + 3, param["name"])
        renderRolandText(
            x + fieldWidth + 5,
            y + 3,
            format_part_param_value(param, values[index]),
        )

        upClicked = renderButtonBetter(
            x + fieldWidth + valueWidth + 4, y,
            arrowWidth, 10, "up"
        )
        downClicked = renderButtonBetter(
            x + fieldWidth + valueWidth + 4, y + 11,
            arrowWidth, 10, "down"
        )

        if upClicked:
            values[index] = step_part_param(param, values[index], +1)
            changed = (category, index)

        if downClicked:
            values[index] = step_part_param(param, values[index], -1)
            changed = (category, index)

    return changed


PARAMETER_PAGES = {
    "reverb": {
        "title": "Reverb Settings",
        "params": [
            {
                "name": "Macro",
                "address": ["40", "01", "30"],
                "default": 4,
                "enum": [
                    "Room 1",
                    "Room 2",
                    "Room 3",
                    "Hall 1",
                    "Hall 2",
                    "Plate",
                    "Delay",
                    "Panning Delay",
                ],
            },
            {
                "name": "Character",
                "address": ["40", "01", "31"],
                "default": 4,
                "raw_min": 0,
                "raw_max": 7,
            },
            {
                "name": "Pre-LPF",
                "address": ["40", "01", "32"],
                "default": 0,
                "raw_min": 0,
                "raw_max": 7,
            },
            {
                "name": "Level",
                "address": ["40", "01", "33"],
                "default": 64,
                "raw_min": 0,
                "raw_max": 127,
            },
            {
                "name": "Time",
                "address": ["40", "01", "34"],
                "default": 64,
                "raw_min": 0,
                "raw_max": 127,
            },
            {
                "name": "Delay FB",
                "address": ["40", "01", "35"],
                "default": 0,
                "raw_min": 0,
                "raw_max": 127,
            },
            {
                "name": "Predelay",
                "address": ["40", "01", "37"],
                "default": 0,
                "raw_min": 0,
                "raw_max": 127,
                "suffix": " ms",
            },
        ],
    },

    "chorus": {
        "title": "Chorus Settings",
        "params": [
            {
                "name": "Macro",
                "address": ["40", "01", "38"],
                "default": 2,
                "enum": [
                    "Chorus 1",
                    "Chorus 2",
                    "Chorus 3",
                    "Chorus 4",
                    "Feedback Chorus",
                    "Flanger",
                    "Short Delay",
                    "Short Delay (FB)",
                ],
            },
            {
                "name": "Pre-LPF",
                "address": ["40", "01", "39"],
                "default": 0,
                "raw_min": 0,
                "raw_max": 7,
            },
            {
                "name": "Level",
                "address": ["40", "01", "3A"],
                "default": 64,
                "raw_min": 0,
                "raw_max": 127,
            },
            {
                "name": "Feedback",
                "address": ["40", "01", "3B"],
                "default": 8,
                "raw_min": 0,
                "raw_max": 127,
            },
            {
                "name": "Delay",
                "address": ["40", "01", "3C"],
                "default": 80,
                "raw_min": 0,
                "raw_max": 127,
            },
            {
                "name": "Rate",
                "address": ["40", "01", "3D"],
                "default": 3,
                "raw_min": 0,
                "raw_max": 127,
            },
            {
                "name": "Depth",
                "address": ["40", "01", "3E"],
                "default": 19,
                "raw_min": 0,
                "raw_max": 127,
            },
            {
                "name": "Send -> Reverb",
                "address": ["40", "01", "3F"],
                "default": 0,
                "raw_min": 0,
                "raw_max": 127,
            },
            {
                "name": "Send -> Delay",
                "address": ["40", "01", "40"],
                "default": 0,
                "raw_min": 0,
                "raw_max": 127,
            },
        ],
    },

    "delay": {
        "title": "Delay Settings",
        "params": [
            {
                "name": "Macro",
                "address": ["40", "01", "50"],
                "default": 0,
                "enum": [
                    "Delay 1",
                    "Delay 2",
                    "Delay 3",
                    "Delay 4",
                    "Pan Delay 1",
                    "Pan Delay 2",
                    "Pan Delay 3",
                    "Pan Delay 4",
                    "Delay to Reverb",
                    "Pan Repeat",
                ],
            },
            {
                "name": "Pre-LPF",
                "address": ["40", "01", "51"],
                "default": 0,
                "raw_min": 0,
                "raw_max": 7,
            },
            {
                "name": "Time Center",
                "address": ["40", "01", "52"],
                "default": 0x61,
                "raw_min": 0x01,
                "raw_max": 0x73,
                "display_codec": "delay_time_center",
            },
            {
                "name": "Time Ratio L",
                "address": ["40", "01", "53"],
                "default": 0x01,
                "raw_min": 0x01,
                "raw_max": 0x78,
                "display_codec": "delay_ratio",
            },
            {
                "name": "Time Ratio R",
                "address": ["40", "01", "54"],
                "default": 0x01,
                "raw_min": 0x01,
                "raw_max": 0x78,
                "display_codec": "delay_ratio",
            },
            {
                "name": "Level Center",
                "address": ["40", "01", "55"],
                "default": 127,
                "raw_min": 0,
                "raw_max": 127,
            },
            {
                "name": "Level Left",
                "address": ["40", "01", "56"],
                "default": 0,
                "raw_min": 0,
                "raw_max": 127,
            },
            {
                "name": "Level Right",
                "address": ["40", "01", "57"],
                "default": 0,
                "raw_min": 0,
                "raw_max": 127,
            },
            {
                "name": "Level",
                "address": ["40", "01", "58"],
                "default": 64,
                "raw_min": 0,
                "raw_max": 127,
            },
            {
                "name": "Feedback",
                "address": ["40", "01", "59"],
                "default": 0x50,
                "raw_min": 0,
                "raw_max": 127,
                "display_codec": "signed_64",
            },
            {
                "name": "Send -> Reverb",
                "address": ["40", "01", "5A"],
                "default": 0,
                "raw_min": 0,
                "raw_max": 127,
            },
        ],
    },
    "eq": {
        "title": "EQ Settings",
        "params": [
            {
                "name": "Low Freq",
                "address": ["40", "02", "00"],
                "default": 0,
                "enum": ["200 Hz", "400 Hz"],
            },
            {
                "name": "Low Gain",
                "address": ["40", "02", "01"],
                "default": 0x40,
                "raw_min": 0x34,
                "raw_max": 0x4C,
                "display_codec": "gain_db",
            },
            {
                "name": "High Freq",
                "address": ["40", "02", "02"],
                "default": 0,
                "enum": ["3 kHz", "6 kHz"],
            },
            {
                "name": "High Gain",
                "address": ["40", "02", "03"],
                "default": 0x40,
                "raw_min": 0x34,
                "raw_max": 0x4C,
                "display_codec": "gain_db",
            },
        ],
    },


    "global": {
        "title": "Adjust Global Values",
        "params": [
            {
                "name": "Master Tune",
                "address": ["40", "00", "00"],
                "default": 0x0400,
                "raw_min": 0x0018,
                "raw_max": 0x07E8,
                "display_codec": "master_tune",
                "data_codec": "nibbles4",
            },
            {
                "name": "Master Level",
                "address": ["40", "00", "04"],
                "default": 127,
                "raw_min": 0,
                "raw_max": 127,
            },
            {
                "name": "Master Key Shift",
                "address": ["40", "00", "05"],
                "default": 0x40,
                "raw_min": 0x28,
                "raw_max": 0x58,
                "display_codec": "key_shift",
            },
            {
                "name": "Master Pan",
                "address": ["40", "00", "06"],
                "default": 0x40,
                "raw_min": 0x01,
                "raw_max": 0x7F,
                "display_codec": "master_pan",
            },
        ],
    },

}

parameterPageValues = {
    page_name: [param["default"] for param in page["params"]]
    for page_name, page in PARAMETER_PAGES.items()
}


def step_parameter_value(param, current, direction):
    """Step to the next legal raw value, wrapping at either end."""
    if "enum" in param:
        legal = list(range(len(param["enum"])))
    else:
        legal = list(range(param.get("raw_min", 0), param.get("raw_max", 127) + 1))

    if current not in legal:
        current = min(legal, key=lambda value: abs(value - current))

    position = legal.index(current)
    return legal[(position + direction) % len(legal)]


def delay_time_center_ms(raw_value):
    """
    SC-88 Pro Delay Time Center lookup defined by the MIDI implementation.

    Raw 01H..73H covers 0.1 ms..1000 ms with progressively coarser
    resolution as the delay gets longer.
    """
    if 0x01 <= raw_value <= 0x14:
        return raw_value * 0.1
    if raw_value <= 0x23:
        return 2.0 + (raw_value - 0x14) * 0.2
    if raw_value <= 0x2D:
        return 5.0 + (raw_value - 0x23) * 0.5
    if raw_value <= 0x37:
        return 10.0 + (raw_value - 0x2D) * 1.0
    if raw_value <= 0x46:
        return 20.0 + (raw_value - 0x37) * 2.0
    if raw_value <= 0x50:
        return 50.0 + (raw_value - 0x46) * 5.0
    if raw_value <= 0x5A:
        return 100.0 + (raw_value - 0x50) * 10.0
    if raw_value <= 0x69:
        return 200.0 + (raw_value - 0x5A) * 20.0
    if raw_value <= 0x73:
        return 500.0 + (raw_value - 0x69) * 50.0
    return None


def format_delay_time_center(raw_value):
    milliseconds = delay_time_center_ms(raw_value)
    if milliseconds is None:
        return "out of range!"

    if milliseconds < 10:
        return f"{milliseconds:.1f} ms"

    if milliseconds == 1000:
        return "1.0 s"

    # Every value from 10 ms upward is integral in Roland's table.
    return f"{int(milliseconds)} ms"


def format_delay_ratio(raw_value):
    # Roland specifies resolution as 100/24 percent per raw step.
    # The manual presents the user-facing range as 4..500%, so display
    # the percentage rounded to the nearest integer.
    percent = (raw_value * 100.0) / 24.0
    rounded = int(percent + 0.5)
    return f"{rounded}%"


def format_signed_64(raw_value):
    signed = raw_value - 64
    if signed > 0:
        return f"+{signed}"
    return str(signed)


def format_parameter_value(param, raw_value):
    """Convert a raw MIDI value to the text shown in the editor."""
    if "enum" in param:
        if 0 <= raw_value < len(param["enum"]):
            return param["enum"][raw_value]
        return "out of range!"

    codec = param.get("display_codec")
    if codec == "delay_time_center":
        return format_delay_time_center(raw_value)
    if codec == "delay_ratio":
        return format_delay_ratio(raw_value)
    if codec == "signed_64":
        return format_signed_64(raw_value)
    if codec == "gain_db":
        gain = raw_value - 0x40
        if gain > 0:
            return f"+{gain} dB"
        return f"{gain} dB"
    if codec == "master_tune":
        cents = (raw_value - 0x0400) / 10.0
        sign = "+" if cents > 0 else ""
        return f"{sign}{cents:.1f} cent"
    if codec == "key_shift":
        semitones = raw_value - 0x40
        sign = "+" if semitones > 0 else ""
        return f"{sign}{semitones} st"
    if codec == "master_pan":
        offset = raw_value - 0x40
        if offset < 0:
            return f"L{-offset}"
        if offset > 0:
            return f"R{offset}"
        return "0"

    prefix = param.get("prefix", "")
    suffix = param.get("suffix", "")
    return prefix + str(raw_value) + suffix


def encode_parameter_data(param, raw_value):
    """Convert a UI value into the one or more Roland data bytes it requires."""
    if param.get("data_codec") == "nibbles4":
        # Roland MASTER TUNE is a 16-bit value transmitted as four 4-bit bytes:
        # 0aaa 0bbb 0ccc 0ddd.
        return [
            format((raw_value >> 12) & 0x0F, "02x"),
            format((raw_value >> 8) & 0x0F, "02x"),
            format((raw_value >> 4) & 0x0F, "02x"),
            format(raw_value & 0x0F, "02x"),
        ]
    return [format(raw_value, "02x")]


def send_parameter_sysex(param, raw_value):
    """Send one generic SC-88 Pro parameter."""
    data = encode_parameter_data(param, raw_value)
    sysex = sysex_generator.generate_sysex(param["address"], data, True)
    send_midi(mido.Message("sysex", data=sysex))


def parameter_sysex_text(param, raw_value):
    """Generate the printable/copyable form of one parameter SysEx message."""
    data = encode_parameter_data(param, raw_value)
    return sysex_generator.generate_sysex(param["address"], data, False)


def _sysex_message(address, data):
    payload = sysex_generator.generate_sysex(address, data, True)
    return mido.Message("sysex", data=payload)


def _generic_parameter_message(param, raw_value):
    return _sysex_message(param["address"], encode_parameter_data(param, raw_value))


def _part_parameter_message(group, part_number, category, param_index):
    param = PART_PARAM_DEFS[category][param_index]
    raw = partParamValues[group][part_number - 1][category][param_index]
    address = actual_part_param_address(group, part_number, param)
    data = encode_part_param_data(param, raw, group, part_number, category)
    return _sysex_message(address, data)


def _scale_tune_message(group, part_number, note_index):
    raw = scaleTuneValues[group][part_number - 1][note_index]
    return _sysex_message(scale_tune_address(group, part_number, note_index), [format(raw, "02x")])


def _efx_assign_message(group, part_number):
    enabled = efxPartEnabled[group][part_number - 1]
    return _sysex_message(efx_part_address(group, part_number), ["01" if enabled else "00"])


def _system_mode_message():
    return _sysex_message(["00", "00", "7F"], [format(systemModeValue, "02x")])


def _system_block_message(block_number):
    return _sysex_message(
        ["00", "01", format(block_number, "02x")],
        [format(systemBlockPorts[block_number], "02x")],
    )


def _efx_type_message():
    h1 = efxtypes['efx'][efxtype]['hex'][0:2]
    h2 = efxtypes['efx'][efxtype]['hex'][2:4]
    return _sysex_message(['40', '03', '00'], [h1, h2])


def _efx_parameter_message(index):
    raw = efxParams[index][1]
    return _sysex_message(
        ['40', '03', format(3 + index, 'x').zfill(2)],
        [format(raw, 'x').zfill(2)],
    )


def current_page_midi_messages():
    """Return (label, messages) for the complete state represented on screen."""
    if screener in PARAMETER_PAGES:
        page = PARAMETER_PAGES[screener]
        return page["title"], [
            _generic_parameter_message(param, parameterPageValues[screener][i])
            for i, param in enumerate(page["params"])
        ]

    category = None
    if screener in PART_PARAM_PAGE_MAP:
        category = PART_PARAM_PAGE_MAP[screener]
    elif screener == "part_aftertouch":
        category = aftertouchCategory
    if category is not None:
        messages = []
        sent_tone_pair = False
        for i, param in enumerate(PART_PARAM_DEFS[category]):
            pair = param.get("data_codec") in ("tone_pair_bank", "tone_pair_program")
            if pair and sent_tone_pair:
                continue
            messages.append(_part_parameter_message(partParamGroup, partParamPart, category, i))
            if pair:
                sent_tone_pair = True
        return f"{partParamGroup}{partParamPart:02d} {category}", messages

    if screener == "scaletuning":
        return f"{scaleTuneGroup}{scaleTunePart:02d} Scale Tuning", [
            _scale_tune_message(scaleTuneGroup, scaleTunePart, i) for i in range(12)
        ]

    if screener == "efx":
        return "Insertion EFX Assign", [
            _efx_assign_message(group, part)
            for group in ("A", "B") for part in range(1, 17)
        ]

    if screener == "sysparam":
        return "System Parameters", [_system_mode_message()] + [
            _system_block_message(i) for i in range(32)
        ]

    if screener == "efxtype":
        messages = [_efx_type_message()]
        messages += [
            _efx_parameter_message(i) for i in range(20) if efxParams[i][0] != ''
        ]
        return f"EFX {effect_display_name(efxtypes['efx'][efxtype]['name'])}", messages

    return None, []


def current_parameter_midi_messages():
    """Return the most recently edited parameter, but only on its current page."""
    item = lastEditedParameter
    if not item or item[0] != screener:
        return None, []

    kind = item[1]
    if kind == "generic":
        i = item[2]
        param = PARAMETER_PAGES[screener]["params"][i]
        return param["name"], [_generic_parameter_message(param, parameterPageValues[screener][i])]
    if kind == "part":
        category, i = item[2], item[3]
        return PART_PARAM_DEFS[category][i]["name"], [_part_parameter_message(partParamGroup, partParamPart, category, i)]
    if kind == "scale":
        i = item[2]
        return f"{scaleTuneNotes[i]} Scale Tuning", [_scale_tune_message(scaleTuneGroup, scaleTunePart, i)]
    if kind == "efx_assign":
        group, part = item[2], item[3]
        return f"{group}{part:02d} EFX Assign", [_efx_assign_message(group, part)]
    if kind == "system_mode":
        return "System Mode", [_system_mode_message()]
    if kind == "system_block":
        block = item[2]
        return f"System Block {block:02X}", [_system_block_message(block)]
    if kind == "efx_param":
        i = item[2]
        return efxParams[i][0] or f"EFX Parameter {i}", [_efx_parameter_message(i)]
    if kind == "efx_type":
        return "EFX Type", [_efx_type_message()]
    return None, []


def safe_export_name(text):
    cleaned = ''.join(ch if ch.isalnum() or ch in ' -_.' else '_' for ch in str(text))
    return ' '.join(cleaned.split()).strip(' .') or 'SC88 Flashlight'


def write_midi_clip(path, label, messages, scope):
    """Write one Flashlight SysEx SMF to an explicit path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    ppqn = 480
    tempo = 500000  # 120 BPM; makes millisecond pacing deterministic in the file.
    gap_ticks = max(
        0,
        int(round(mido.second2tick(
            appSettings["sysex_delay_ms"] / 1000.0,
            ppqn,
            tempo,
        ))),
    )

    midi = mido.MidiFile(type=0, ticks_per_beat=ppqn)
    track = mido.MidiTrack()
    midi.tracks.append(track)
    track.append(mido.MetaMessage(
        'track_name',
        name=f"SC88 Flashlight {scope}: {label}",
        time=0,
    ))
    track.append(mido.MetaMessage('set_tempo', tempo=tempo, time=0))
    for i, message in enumerate(messages):
        track.append(message.copy(time=0 if i == 0 else gap_ticks))
    track.append(mido.MetaMessage('end_of_track', time=0))
    midi.save(path)
    return path


def save_midi_clip(label, messages, scope):
    """Save a click-exported MIDI clip in the user's configured folder."""
    global exportStatus
    if not messages:
        set_export_status(
            "No parameter selected for MIDI export"
            if scope == "Parameter"
            else "Nothing to export on this page"
        )
        return None

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = f"SC88_{safe_export_name(label)}_{scope}_{timestamp}.mid"
    path = write_midi_clip(EXPORT_DIR / filename, label, messages, scope)
    set_export_status(f"Saved {filename}", 2200)
    print(f"MIDI export: {path}")
    return path


def make_drag_midi_clip(label, messages, scope):
    """Create a persistent cache file suitable for an inter-application drag."""
    global exportStatus
    if not messages:
        set_export_status(
            "Edit a parameter before dragging PARAM MIDI"
            if scope == "Parameter"
            else "Nothing to drag from this page"
        )
        return None

    # Milliseconds avoid collisions when several clips are dragged quickly.
    stamp = time.strftime("%Y%m%d-%H%M%S") + f"-{int((time.time() % 1) * 1000):03d}"
    filename = f"SC88_{safe_export_name(label)}_{scope}_{stamp}.mid"
    return write_midi_clip(DRAG_DIR / filename, label, messages, scope)


def begin_native_file_drag(path):
    """Begin a Cocoa file drag using the current AppKit mouse-drag event."""
    global exportStatus

    if not NATIVE_DRAG_AVAILABLE:
        set_export_status("Drag requires PyObjC (pyobjc-framework-Cocoa)", 3000)
        if nativeDragError:
            print("Native drag unavailable:", nativeDragError)
        return False

    try:
        app = NSApplication.sharedApplication()
        window = app.keyWindow() or app.mainWindow()
        if window is None:
            set_export_status("Could not acquire the macOS window", 3000)
            return False

        # SDL/Pygame has usually already consumed the Cocoa event by the time
        # we see its MOUSEMOTION.  Build a fresh AppKit drag event at the
        # current pointer location instead of relying on NSApp.currentEvent().
        previous_event = app.currentEvent()
        timestamp = previous_event.timestamp() if previous_event is not None else 0.0
        location = window.mouseLocationOutsideOfEventStream()
        event = NSEvent.mouseEventWithType_location_modifierFlags_timestamp_windowNumber_context_eventNumber_clickCount_pressure_(
            NSEventTypeLeftMouseDragged,
            location,
            0,
            timestamp,
            window.windowNumber(),
            None,
            0,
            1,
            1.0,
        )
        if event is None:
            set_export_status("Could not create the macOS drag event", 3000)
            return False

        file_url = NSURL.fileURLWithPath_(str(Path(path)))
        drag_item = NSDraggingItem.alloc().initWithPasteboardWriter_(file_url)

        icon = NSWorkspace.sharedWorkspace().iconForFile_(str(Path(path)))
        try:
            icon.setSize_((32.0, 32.0))
        except Exception:
            pass
        frame = NSMakeRect(location.x - 16.0, location.y - 16.0, 32.0, 32.0)
        drag_item.setDraggingFrame_contents_(frame, icon)

        session = window.beginDraggingSessionWithItems_event_source_(
            [drag_item], event, _nativeDragSource
        )
        if session is None:
            set_export_status("macOS refused to start the drag", 3000)
            return False
        session.setAnimatesToStartingPositionsOnCancelOrFail_(True)
        set_export_status(f"Dragging {Path(path).name}", 900)
        return True
    except Exception as exc:
        set_export_status(f"Native drag failed: {exc}", 3000)
        print("Native drag failed:", repr(exc))
        return False


def midi_action_layout():
    """Return the bottom action-button rectangles used for click/drag hit tests."""
    buttonwidth = 135
    buttonpaddingx = 4
    count = 4
    totalbuttonwidth = (buttonwidth + buttonpaddingx) * count
    groupx = (awesomeWindowWidth / 2) - (totalbuttonwidth / 2)
    y = awesomeWindowHeight - 50
    labels = ['Copy SysEx', 'Send SysEx', 'Param MIDI', 'Page MIDI']
    return [
        (labels[i], pygame.Rect(
            round(groupx + ((buttonwidth + buttonpaddingx) * i)),
            round(y),
            buttonwidth,
            28,
        ))
        for i in range(count)
    ]


def export_scope_at_pos(pos):
    for label, rect in midi_action_layout():
        if rect.collidepoint(pos):
            if label == 'Param MIDI':
                return 'Parameter'
            if label == 'Page MIDI':
                return 'Page'
    return None


def messages_for_export_scope(scope):
    if scope == 'Parameter':
        return current_parameter_midi_messages()
    return current_page_midi_messages()


# Click-vs-drag state for PARAM MIDI and PAGE MIDI.  A short click preserves
# a4's save-to-Downloads behavior; moving 8 px starts a native file drag.
midiDragCandidate = None
midiDragStartPos = None
midiDragStarted = False
midiActionClick = None
directDragCandidate = None
directDragStartPos = None
DRAG_THRESHOLD_PX = 8

def render_parameter_page(page_name):
    """
    Draw a generic parameter editor.

    Returns the index of the parameter changed this frame, or None.
    The caller can then send just that one SysEx value immediately.
    """
    page = PARAMETER_PAGES[page_name]
    values = parameterPageValues[page_name]
    params = page["params"]

    buttonheight = 20
    columns = 2
    rows = math.ceil(len(params) / columns)

    fieldWidth = 165
    valueWidth = 210

    # Global has longer parameter labels. Move only the boundary between
    # the label and value fields 60 px right, while keeping the overall
    # two-column layout centered in the same place.
    if page_name == "global":
        fieldWidth += 60
        valueWidth -= 60

    arrowWidth = 20
    columnGap = 30
    rowGap = 4

    fullColumnWidth = fieldWidth + valueWidth + arrowWidth + 4
    totalWidth = (fullColumnWidth * columns) + columnGap

    startX = (awesomeWindowWidth - totalWidth) / 2
    startY = 290

    # Page title
    titleWidth = 22 * 11
    titleX = (awesomeWindowWidth - titleWidth) / 2
    renderScreen(titleX, 262, titleWidth, buttonheight)
    renderRolandText(titleX + 3, 265, page["title"])

    changed_index = None

    for index, param in enumerate(params):
        column = index // rows
        row = index % rows

        x = startX + column * (fullColumnWidth + columnGap)
        y = startY + row * (buttonheight + rowGap)

        renderScreen(x, y, fieldWidth, buttonheight)
        renderScreen(x + fieldWidth + 2, y, valueWidth, buttonheight)
        register_parameter_drag_target(
            (x + fieldWidth + 2, y, valueWidth, buttonheight),
            (screener, "generic", index),
        )

        shown = format_parameter_value(param, values[index])
        renderRolandText(x + 3, y + 3, param["name"])
        renderRolandText(x + fieldWidth + 5, y + 3, shown)

        upClicked = renderButtonBetter(
            x + fieldWidth + valueWidth + 4,
            y,
            arrowWidth,
            buttonheight / 2,
            "up",
        )
        downClicked = renderButtonBetter(
            x + fieldWidth + valueWidth + 4,
            y + buttonheight / 2 + 1,
            arrowWidth,
            buttonheight / 2,
            "down",
        )

        if upClicked:
            values[index] = step_parameter_value(param, values[index], +1)
            changed_index = index

        if downClicked:
            values[index] = step_parameter_value(param, values[index], -1)
            changed_index = index

    return changed_index


efxtype = 1
efxDropdownOpen = False
def renderScreen(x,y,width,height):
    pygame.draw.rect(screen, '#FF6A00', (x,y,width,height))
    screen.blit(screenNWImg, (x,y))
    
    for _i in range(round(width)-6):
        screen.blit(screenNImg, (x+3+_i,y))
    screen.blit(screenNEImg, (x+width-3,y))
    
    for _i in range(round(height)-6):
        screen.blit(screenWImg, (x,y+3+_i))
        screen.blit(screenEImg, (x+width-3,y+3+_i))

    screen.blit(screenSWImg, (x,y+height-3))
    for _i in range(round(width)-6):
        screen.blit(screenSImg, (x+3+_i,y+height-3))
    screen.blit(screenSEImg, (x+width-3,y+height-3))
    return False
oldMouse=pygame.mouse.get_pressed()
screener='mainmenu' #its only called screener because screen was taken idk
efxChange=True
send=''
while running:
    if efxChange:
        #initialize defaults for efx
        efxParams=[]
        for i in efxtypes['efx'][efxtype]['params']:
            #print(i)
            efxParams.append([i[0],i[1],i[2]])
            #if i[2]=='LCR':
                #efxParams[-1][1]=64 #set pan to center
            #if i[2]=='-12.12':
                #efxParams[-1][1]=12 #They have their own defaults
            #if i[2]=='0.127':
                #if i[1]==127: efxParams[-1][1]=127
            if i[2]=='Balance':
                pass # this is a placeholder for the future D> 0E - D=E - D 0<E balance visual
        efxChange=False
    newMouse=pygame.mouse.get_pressed()
    mouseWheelY = 0
    # poll for events
    # pygame.QUIT event means the user clicked X to close your window
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            efxDropdownOpen = False
            midiDropdownOpen = False
            midiScrollbarDragging = False
        if event.type == pygame.MOUSEWHEEL:
            mouseWheelY += event.y

        # PARAM MIDI / PAGE MIDI are dual-purpose controls in a5:
        # click = save to Downloads, drag = hand a temporary .mid to macOS.
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            scope = export_scope_at_pos(event.pos)
            if scope is not None and not (efxDropdownOpen or midiDropdownOpen):
                midiDragCandidate = scope
                midiDragStartPos = event.pos
                midiDragStarted = False
            elif not (efxDropdownOpen or midiDropdownOpen):
                item = parameter_drag_target_at_pos(event.pos)
                if item is not None:
                    directDragCandidate = item
                    directDragStartPos = event.pos

        if event.type == pygame.MOUSEMOTION and midiDragCandidate and midiDragStartPos:
            if event.buttons[0] and not midiDragStarted:
                dx = event.pos[0] - midiDragStartPos[0]
                dy = event.pos[1] - midiDragStartPos[1]
                if (dx * dx + dy * dy) ** 0.5 >= DRAG_THRESHOLD_PX:
                    label, messages = messages_for_export_scope(midiDragCandidate)
                    drag_path = make_drag_midi_clip(label, messages, midiDragCandidate)
                    if drag_path is not None:
                        midiDragStarted = begin_native_file_drag(drag_path)
                    # Whether native dragging succeeded or failed, this gesture
                    # is no longer a click-save.
                    midiDragCandidate = None
                    midiDragStartPos = None

        if event.type == pygame.MOUSEMOTION and directDragCandidate and directDragStartPos:
            if event.buttons[0]:
                dx = event.pos[0] - directDragStartPos[0]
                dy = event.pos[1] - directDragStartPos[1]
                if (dx * dx + dy * dy) ** 0.5 >= DRAG_THRESHOLD_PX:
                    label, messages = messages_for_parameter_item(directDragCandidate)
                    drag_path = make_drag_midi_clip(label, messages, "Parameter")
                    if drag_path is not None:
                        begin_native_file_drag(drag_path)
                    directDragCandidate = None
                    directDragStartPos = None

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if midiDragCandidate and not midiDragStarted:
                # Only count it as a click when released on the same control.
                released_scope = export_scope_at_pos(event.pos)
                if released_scope == midiDragCandidate:
                    midiActionClick = midiDragCandidate
            midiDragCandidate = None
            midiDragStartPos = None
            midiDragStarted = False
            directDragCandidate = None
            directDragStartPos = None

    # If a popup was already open when this frame began, it owns the mouse.
    # Background controls remain visible but cannot react to the same click.
    popupModalOpen = bool(efxDropdownOpen or midiDropdownOpen)

    # Rebuild direct-drag hit targets from the UI drawn this frame.
    parameterDragTargets.clear()
    clear_expired_export_status()

    # fill the screen with a color to wipe away anything from last frame
    screen.fill("#333333")
    screen.blit(update_fps(), (10,0))
    # RENDER YOUR GAME HERE
    #Render Main Menu at top
    buttoncolumns=3
    buttonwidth=150
    buttonpaddingx=8
    buttonpaddingy=4
    totalbuttonwidth=(buttonwidth+buttonpaddingx)*buttoncolumns
    totalbuttonheight=(28+buttonpaddingy)*math.ceil(len(buttons)/buttoncolumns)
    buttongroupx=(awesomeWindowWidth/2)-(totalbuttonwidth/2)
    buttongroupy=30
    #print(oldMouse)
    #print(newMouse)
    for i in range(len(buttons)):
        buttonclicked=renderButton(buttongroupx+((buttonwidth+buttonpaddingx)*(i%buttoncolumns)),buttongroupy+((28+buttonpaddingy)*math.floor(i/buttoncolumns)),buttonwidth,buttons[i])
        if buttonclicked:
            if i==0: screener='efxtype'
            if i==1: screener='efx'
            if i==2: screener='eq'
            if i==3: screener='chorus'
            if i==4: screener='delay'
            if i==5: screener='reverb'
            if i==6: screener='global'
            if i==7: screener='sysparam'
            if i==8: screener='scaletuning'
            if i==9: screener='part_basic'
            if i==10: screener='part_receive'
            if i==11: screener='part_tone'
            if i==12: screener='part_routing'
            if i==13: screener='part_mod'
            if i==14: screener='part_bend'
            if i==15: screener='part_aftertouch'
            if i==16: screener='part_cc1'
            if i==17: screener='part_cc2'


    if screener=='mainmenu':
        pass #i dont need this if statemtn
    if screener=='settings':
        render_settings_page()
    if screener=='efx':
        efxPartChanged = render_efx_part_assign_page()
        if efxPartChanged is not None:
            group, part_number, enabled = efxPartChanged
            lastEditedParameter = (screener, "efx_assign", group, part_number)
            send_part_efx(group, part_number, enabled)

    if screener=='sysparam':
        systemParamChanged = render_system_parameter_page()
        if systemParamChanged is not None:
            if systemParamChanged[0] == "mode":
                lastEditedParameter = (screener, "system_mode")
                send_system_mode(systemParamChanged[1])
            elif systemParamChanged[0] == "block":
                lastEditedParameter = (screener, "system_block", systemParamChanged[1])
                send_system_block_port(systemParamChanged[1], systemParamChanged[2])

    if screener=='scaletuning':
        scaleTuneChanged = render_scale_tuning_page()
        if scaleTuneChanged is not None:
            lastEditedParameter = (screener, "scale", scaleTuneChanged)
            raw_value = scaleTuneValues[scaleTuneGroup][scaleTunePart - 1][scaleTuneChanged]
            send_scale_tune(scaleTuneGroup, scaleTunePart, scaleTuneChanged, raw_value)

    if screener in PART_PARAM_PAGE_MAP:
        category = PART_PARAM_PAGE_MAP[screener]
        partParamChanged = render_part_category_page(category)
        if partParamChanged is not None:
            changed_category, param_index = partParamChanged
            lastEditedParameter = (screener, "part", changed_category, param_index)
            send_part_param(
                partParamGroup, partParamPart, changed_category, param_index
            )

    if screener=='part_aftertouch':
        partParamChanged = render_part_category_page(
            aftertouchCategory,
            page_title="Aftertouch",
            allow_aftertouch_switch=True,
        )
        if partParamChanged is not None:
            changed_category, param_index = partParamChanged
            lastEditedParameter = (screener, "part", changed_category, param_index)
            send_part_param(
                partParamGroup, partParamPart, changed_category, param_index
            )

    if screener in PARAMETER_PAGES:
        genericParamChanged = render_parameter_page(screener)
        if genericParamChanged is not None:
            lastEditedParameter = (screener, "generic", genericParamChanged)
            param = PARAMETER_PAGES[screener]["params"][genericParamChanged]
            raw_value = parameterPageValues[screener][genericParamChanged]
            send_parameter_sysex(param, raw_value)

    willSend=False
    willSendLite=False
    doingStuff=False
    genericParamChanged = None
    efxPartChanged = None
    systemParamChanged = None
    scaleTuneChanged = None
    partParamChanged = None
    dropdownJustOpened = False
    if screener=='efxtype':
    
        buttoncolumns=4
        buttonwidth=135
        valueWidth=85
        arrowWidth=20
        buttonheight=20
        efxColumnGap=10
        buttonpaddingy=4

        # Actual row width = label + 2px gap + value + 4px gap + arrows.
        efxColumnWidth = buttonwidth + 2 + valueWidth + 4 + arrowWidth
        totalbuttonwidth = (
            efxColumnWidth * buttoncolumns
            + efxColumnGap * (buttoncolumns - 1)
        )
        totalbuttonheight=(28+buttonpaddingy)*math.ceil(len(buttons)/buttoncolumns)
        buttongroupx=(awesomeWindowWidth/2)-(totalbuttonwidth/2)
        buttongroupy=290
        for i in range(len(efxParams)):
            _x=buttongroupx+((efxColumnWidth+efxColumnGap)*(i%buttoncolumns))
            _y=buttongroupy+((buttonheight+buttonpaddingy)*math.floor(i/buttoncolumns))
            #renderButtonBetter(_x,_y,buttonwidth,buttonheight,'sacks')
            renderScreen(_x,_y,buttonwidth,buttonheight)
            renderScreen(_x+buttonwidth+2,_y,valueWidth,buttonheight)
            if efxParams[i][0] != '':
                register_parameter_drag_target(
                    (_x + buttonwidth + 2, _y, valueWidth, buttonheight),
                    (screener, "efx_param", i),
                )
            upClicked=renderButtonBetter(_x+buttonwidth+valueWidth+4,_y,20,buttonheight/2,'sacks')
            downClicked=renderButtonBetter(_x+buttonwidth+valueWidth+4,_y+buttonheight/2+1,20,buttonheight/2,'sacks')
            if upClicked and not efxDropdownOpen:
                efxParams[i][1] = step_efx_value(efxParams[i], +1)
                willSendLite = True
                changed = i
                lastEditedParameter = (screener, "efx_param", i)
                doingStuff = True

            if downClicked and not efxDropdownOpen:
                efxParams[i][1] = step_efx_value(efxParams[i], -1)
                willSendLite = True
                changed = i
                lastEditedParameter = (screener, "efx_param", i)
                doingStuff = True

            shownValue=str(efxParams[i][1])
            vals=efxParams[i][2]
            #print(efxParams[i])
            
            if type(vals)==str:
                if vals=='':
                    shownValue=''
                if vals=='0.127':
                    pass #ideally this shouldnt be here but i felt  like it
                if vals=='0.15':
                    pass #ideally this shouldnt be here but i felt  like it
                if vals=='-12.12':
                    vals=['-12',
                          '-11',
                          '-10',
                          '- 9',
                          '- 8',
                          '- 7',
                          '- 6',
                          '- 5',
                          '- 4',
                          '- 3',
                          '- 2',
                          '- 1',
                          '` 0',
                          '+ 1',
                          '+ 2',
                          '+ 3',
                          '+ 4',
                          '+ 5',
                          '+ 6',
                          '+ 7',
                          '+ 8',
                          '+ 9',
                          '+10',
                          '+11',
                          '+12']
                if vals=='LCR':
                    #im so sorry
                    vals=[]
                    for num in range(-63,0):
                        #print(num)
                        to_append=num
                        if len(str(num))==2:
                            to_append='L '+str(num)[1]
                        vals.append('L'+str(num)[1:3])
                    vals.append('C 0')
                    for num in range(1,64):
                        #print(num)
                        to_append=num
                        if len(str(num))==1:
                            to_append='R '+str(num)
                        vals.append('R'+str(num))
                    #print(vals)
                #if '#' in efxParams[i][0] or '+' in efxParams[i][0]:
                    #shownValue='[X]'
                    #vals='0'
            if type(vals)==list:
                #print(vals)
                try:
                    if vals[0]=='L63':
                        shownValue=str(vals[efxParams[i][1]-1]) #idk why its offset it just is i guess
                    else:
                        shownValue=str(vals[efxParams[i][1]])
                except:
                    shownValue='out of range!'
            
            renderRolandText(_x+3,_y+3,efxParams[i][0])
            renderRolandText(_x+buttonwidth+5,_y+3,shownValue)
        drap = 16 * 11
        effectBoxX = (awesomeWindowWidth / 2) - (drap / 2)
        effectBoxY = 262

        renderScreen(effectBoxX, effectBoxY, drap, buttonheight)
        renderRolandText(
            effectBoxX + 3,
            effectBoxY + 3,
            roland_safe_text(efxtypes['efx'][efxtype]['name'])
        )

        # Clicking the effect-name display opens/closes the effect list.
        # dropdownJustOpened prevents this same mouse click from also selecting
        # an item underneath the cursor in the newly-opened popup.
        if newMouse[0] and newMouse[0] != oldMouse[0]:
            mousex, mousey = pygame.mouse.get_pos()

            if (effectBoxX <= mousex <= effectBoxX + drap and
                effectBoxY <= mousey <= effectBoxY + buttonheight):
                efxDropdownOpen = not efxDropdownOpen
                if efxDropdownOpen:
                    dropdownJustOpened = True

        upClicked = renderButtonBetter(
            effectBoxX + drap, effectBoxY, 20, buttonheight / 2, 'sacks'
        )
        downClicked = renderButtonBetter(
            effectBoxX + drap, effectBoxY + 11, 20, buttonheight / 2, 'sacks'
        )

        if upClicked and not efxDropdownOpen:
            efxChange = True
            efxtype = (efxtype + 1) % len(efxtypes['efx'])
            lastEditedParameter = (screener, "efx_type")

        if downClicked and not efxDropdownOpen:
            efxChange = True
            efxtype = (efxtype - 1) % len(efxtypes['efx'])
            lastEditedParameter = (screener, "efx_type")

        if efxDropdownOpen:
            dropdownColumns = 4
            dropdownRows = math.ceil(len(efxtypes['efx']) / dropdownColumns)

            itemWidth = 235
            itemHeight = 19
            gapX = 5
            gapY = 1

            dropdownWidth = (
                dropdownColumns * itemWidth
                + (dropdownColumns - 1) * gapX
            )
            dropdownHeight = dropdownRows * (itemHeight + gapY)

            dropdownX = (awesomeWindowWidth - dropdownWidth) / 2
            dropdownY = 50

            pygame.draw.rect(
                screen,
                '#222222',
                (
                    dropdownX - 5,
                    dropdownY - 5,
                    dropdownWidth + 10,
                    dropdownHeight + 10
                )
            )

            for effectIndex, effect in enumerate(efxtypes['efx']):
                column = effectIndex // dropdownRows
                row = effectIndex % dropdownRows

                x = dropdownX + column * (itemWidth + gapX)
                y = dropdownY + row * (itemHeight + gapY)

                if effectIndex == efxtype:
                    label = '> ' + str(effectIndex) + '  ' + effect_display_name(effect['name'])
                else:
                    label = '  ' + str(effectIndex) + '  ' + effect_display_name(effect['name'])

                clicked = renderButtonBetter(
                    x,
                    y,
                    itemWidth,
                    itemHeight,
                    label,
                    popup=True
                )

                img = DropdownFont.render(label, False, '#ffffff')
                screen.blit(img, (x + 5, y + 2))

                if clicked and not dropdownJustOpened:
                    efxtype = effectIndex
                    efxChange = True
                    lastEditedParameter = (screener, "efx_type")
                    efxDropdownOpen = False

    buttoncolumns=4
    buttonwidth=135
    buttonheight=28
    buttonpaddingx=4
    buttonpaddingy=4
    totalbuttonwidth=(buttonwidth+buttonpaddingx)*buttoncolumns
    totalbuttonheight=28
    buttongroupx=(awesomeWindowWidth/2)-(totalbuttonwidth/2)
    buttongroupy=awesomeWindowHeight-50
    btns=['Copy SysEx','Send SysEx','Param MIDI','Page MIDI']
    willGenerate=False
    
    for i in range(len(btns)):
        buttonclicked=renderButton(
            buttongroupx+((buttonwidth+buttonpaddingx)*i),
            buttongroupy,
            buttonwidth,
            btns[i]
        )
        if buttonclicked:
            if btns[i]=='Copy SysEx':
                willGenerate=True
                doingStuff=True
            elif btns[i]=='Send SysEx':
                willSend=True
                doingStuff=True
            # PARAM MIDI / PAGE MIDI deliberately ignore renderButton's
            # mouse-down click; their click-vs-drag action is resolved from
            # the event stream above.

    if midiActionClick is not None:
        label, messages = messages_for_export_scope(midiActionClick)
        save_midi_clip(label, messages, midiActionClick)
        midiActionClick = None

    # Hover help is rendered once, at the end of the frame, and only when
    # no higher-priority status message is active.

    # Page-level sends are deliberately paced; immediate parameter edits remain
    # one-message operations and bypass this delay.
    pageSendPacingActive = bool(willSend)
    if pageSendPacingActive:
        lastMidiSendTime = 0.0

    # Settings replaces the always-visible MIDI picker. MIDI output selection
    # now lives on the Settings page with the other persistent preferences.
    settingsButtonWidth = 120
    if renderButton(30, buttongroupy, settingsButtonWidth, "SETTINGS"):
        screener = "settings"

    # Dedicated Reset page button, aligned vertically with SysEx controls.
    resetButtonWidth = 120
    resetButtonX = awesomeWindowWidth - 30 - resetButtonWidth
    if renderButton(resetButtonX, buttongroupy, resetButtonWidth, "RESET"):
        screener = "sysreset"

    #if willGenerate:
        #print('wip')

    # Direct Part Parameter pages: Copy / Send the category shown.
    part_page_category = None
    if screener in PART_PARAM_PAGE_MAP:
        part_page_category = PART_PARAM_PAGE_MAP[screener]
    elif screener == "part_aftertouch":
        part_page_category = aftertouchCategory

    if part_page_category is not None and (willGenerate or willSend):
        category = part_page_category
        params = PART_PARAM_DEFS[category]
        values = partParamValues[partParamGroup][partParamPart - 1][category]

        if willGenerate:
            toCopy = (
                f"Part Parameters {partParamGroup}{partParamPart:02d} "
                f"- {category}:"
            )

        sent_tone_pair = False
        for param_index, param in enumerate(params):
            is_tone_pair = param.get("data_codec") in (
                "tone_pair_bank", "tone_pair_program"
            )

            if willSend:
                if not is_tone_pair or not sent_tone_pair:
                    send_part_param(
                        partParamGroup, partParamPart, category, param_index
                    )
                    if is_tone_pair:
                        sent_tone_pair = True

            if willGenerate:
                shown = format_part_param_value(param, values[param_index])
                sysex = part_param_sysex_text(
                    partParamGroup, partParamPart, category, param_index
                )
                toCopy += (
                    f"\n\n{param['name']} = {shown}:\r\n{sysex}"
                )

        if willGenerate:
            pyperclip.copy(toCopy)

    # Scale Tuning: Copy SysEx / Send SysEx operate on all 12 notes
    # for the currently selected Part.
    if screener == "scaletuning" and (willGenerate or willSend):
        current_values = scaleTuneValues[scaleTuneGroup][scaleTunePart - 1]

        if willGenerate:
            toCopy = f"Scale Tuning {scaleTuneGroup}{scaleTunePart:02d}:"

        for note_index, raw_value in enumerate(current_values):
            if willSend:
                send_scale_tune(
                    scaleTuneGroup, scaleTunePart, note_index, raw_value
                )

            if willGenerate:
                toCopy += (
                    f"\n\n{scaleTuneNotes[note_index]} = "
                    f"{format_scale_tune(raw_value)}:\r\n"
                    + str(
                        scale_tune_sysex_text(
                            scaleTuneGroup,
                            scaleTunePart,
                            note_index,
                            raw_value,
                        )
                    )
                )

        if willGenerate:
            pyperclip.copy(toCopy)

    # System Parameters: Copy SysEx / Send SysEx operate on all explicit
    # MIDI-addressable system parameters.
    if screener == "sysparam" and (willGenerate or willSend):
        if willGenerate:
            toCopy = "System Parameters:"

        if willSend:
            send_system_mode(systemModeValue)
        if willGenerate:
            shown_mode = "Mode 1 / Single" if systemModeValue == 0 else "Mode 2 / Double"
            toCopy += (
                "\n\nSystem Mode = "
                + shown_mode
                + ":\r\n"
                + str(system_mode_sysex_text(systemModeValue))
            )

        for block_number, port_value in enumerate(systemBlockPorts):
            if willSend:
                send_system_block_port(block_number, port_value)

            if willGenerate:
                port_text = "Port A" if port_value == 0 else "Port B"
                toCopy += (
                    f"\n\nBlock {block_number:02X} = {port_text}:\r\n"
                    + str(system_block_port_sysex_text(block_number, port_value))
                )

        if willGenerate:
            pyperclip.copy(toCopy)

    # Generic parameter pages: Copy SysEx / Send SysEx operate on the whole page.
    if screener in PARAMETER_PAGES and (willGenerate or willSend):
        page = PARAMETER_PAGES[screener]
        values = parameterPageValues[screener]

        if willGenerate:
            toCopy = page["title"] + ":"
        else:
            toCopy = ""

        for param_index, param in enumerate(page["params"]):
            raw_value = values[param_index]

            if willSend:
                send_parameter_sysex(param, raw_value)

            if willGenerate:
                shown = format_parameter_value(param, raw_value)
                sysex = parameter_sysex_text(param, raw_value)
                toCopy += (
                    "\n\n"
                    + param["name"]
                    + " = "
                    + shown
                    + ":\r\n"
                    + str(sysex)
                )

        if willGenerate:
            pyperclip.copy(toCopy)

    # Per-Part Insertion EFX page: Copy / Send all 32 assignments.
    if screener == 'efx' and (willGenerate or willSend):
        if willGenerate:
            toCopy = "Insertion EFX Assign:"
        else:
            toCopy = ""

        for group in ("A", "B"):
            for part_number in range(1, 17):
                enabled = efxPartEnabled[group][part_number - 1]

                if willSend:
                    send_part_efx(group, part_number, enabled)

                if willGenerate:
                    state_text = "EFX" if enabled else "BYPASS"
                    sysex = part_efx_sysex_text(
                        group, part_number, enabled
                    )
                    toCopy += (
                        "\n\n"
                        + f"{group}{part_number:02d} = {state_text}:\r\n"
                        + str(sysex)
                    )

        if willGenerate:
            pyperclip.copy(toCopy)

    if screener=='sysreset':
        # Reset/initialization messages with clear MIDI implementation:
        #   GM System On: F0 7E 7F 09 01 F7 (Universal Non-Realtime)
        #   GS Reset:     Roland DT1 at 40 00 7F = 00
        #
        # The old "SC-88 Reset" button actually sent System Mode Set -> Mode 1,
        # so it has been removed here. System Mode belongs on System Parameters.
        buttoncolumns=2
        buttonwidth=180
        buttonheight=20
        buttonpaddingx=8
        buttonpaddingy=4
        sysbuttons=['GM System On','GS Reset']

        totalbuttonwidth=(buttonwidth+buttonpaddingx)*buttoncolumns
        totalbuttonheight=(28+buttonpaddingy)*math.ceil(len(sysbuttons)/buttoncolumns)
        buttongroupx=(awesomeWindowWidth/2)-(totalbuttonwidth/2)
        buttongroupy=(awesomeWindowHeight/4)+(totalbuttonheight/2)+110

        for i in range(len(sysbuttons)):
            btx=buttongroupx+((buttonwidth+buttonpaddingx)*(i%buttoncolumns))
            bty=buttongroupy+((28+buttonpaddingy)*math.floor(i/buttoncolumns))
            buttonclicked=renderButton(btx,bty,buttonwidth,sysbuttons[i])
            if buttonclicked:
                if i==0:
                    send='GM'
                elif i==1:
                    send='GS'

        display_text=''
        if send=='GM':
            display_text='GM System On'
        elif send=='GS':
            display_text='GS Reset'

        drap=18*11
        renderScreen((awesomeWindowWidth/2)-(drap/2),370,drap,buttonheight)
        renderRolandText((awesomeWindowWidth/2)-(drap/2)+3,370+3,display_text)

        if doingStuff and send in ('GM','GS'):
            toCopy=''

            if send=='GM':
                # mido's sysex payload excludes the enclosing F0/F7 bytes.
                if willSend:
                    send_midi(
                        mido.Message('sysex', data=[0x7E,0x7F,0x09,0x01])
                    )
                if willGenerate:
                    toCopy='F0 7E 7F 09 01 F7'

            elif send=='GS':
                addr_=['40','00','7F']
                valu_=['00']
                if willSend:
                    sysex=sysex_generator.generate_sysex(addr_,valu_,True)
                    send_midi(mido.Message('sysex',data=sysex))
                if willGenerate:
                    sysex=sysex_generator.generate_sysex(addr_,valu_,False)
                    toCopy=str(sysex)

            if willGenerate:
                pyperclip.copy(toCopy)

    if screener=='efxtype':
        if doingStuff:
            h1=efxtypes['efx'][efxtype]['hex'][0:2]
            h2=efxtypes['efx'][efxtype]['hex'][2:4]
            #print(h1)
            #print(h2)
            toCopy='Set EFX Type:'
            if willSend:
                sysex=sysex_generator.generate_sysex(['40','03','00'],[h1,h2],True)
                send_midi(mido.Message('sysex',data=sysex))
            if willGenerate:
                sysex=sysex_generator.generate_sysex(['40','03','00'],[h1,h2],False)
                toCopy+='\r\n'+str(sysex)
                #print(toCopy)
            #print(len(efxParams))
            for i in range(20):
                toSend=efxParams[i][1]
                #print(efxParams[i][1])
                #print(efxParams[i][0])
                isCringy=False
                #if '#' in efxParams[i][0] or '+' in efxParams[i][0]: isCringy=True
                if efxParams[i][0]=='': isCringy=True
                #print(efxParams[i][2])
                #print(isCringy)
                if not isCringy:
                    #blah
                    if willSend:
                        sysex=sysex_generator.generate_sysex(['40','03',format(3+i,'x').zfill(2)],[format(toSend,'x').zfill(2)],True)
                        send_midi(mido.Message('sysex',data=sysex))
                    if willSendLite:
                        if changed==i:
                            sysex=sysex_generator.generate_sysex(['40','03',format(3+i,'x').zfill(2)],[format(toSend,'x').zfill(2)],True)
                            send_midi(mido.Message('sysex',data=sysex))
                    if willGenerate:
                        sysex=sysex_generator.generate_sysex(['40','03',format(3+i,'x').zfill(2)],[format(toSend,'x').zfill(2)],False)
                        toCopy+='\n\nSet EFX Parameter #'+str(i)+' ('+efxParams[i][0]+') to '+str(efxParams[i][1])+':\r\n'+str(sysex)

            #print(toCopy)
            pyperclip.copy(toCopy)
            #else:
                #print('fish moment')
                
        
            
    # Page-send pacing applies only to this frame's explicit Send SysEx action.
    pageSendPacingActive = False

    # One mutually-exclusive help/status line: operation status wins, then
    # contextual hover help. This prevents a completed drag message and hover
    # hint from painting over one another.
    help_text = exportStatus
    if not help_text:
        mouse_pos = pygame.mouse.get_pos()
        hovered_item = parameter_drag_target_at_pos(mouse_pos)
        if hovered_item is not None:
            help_text = "Drag this value into DAW"
        else:
            for _label, _rect in midi_action_layout():
                if _rect.collidepoint(mouse_pos):
                    if _label == 'Param MIDI':
                        help_text = "Click to save current parameter  |  Drag into DAW"
                    elif _label == 'Page MIDI':
                        help_text = "Click to save current page  |  Drag into DAW"
                    break
    if help_text:
        status = SmallFont.render(help_text, True, '#dddddd')
        screen.blit(status, ((awesomeWindowWidth - status.get_width()) / 2, awesomeWindowHeight - 72))

    # Popups are composited last so they are visually modal as well as input-modal.
    # The Settings page rendered only the picker button earlier in the frame.
    if screener == 'settings' and midiDropdownOpen:
        labelX = 205
        labelWidth = 245
        valueX = labelX + labelWidth + 2
        render_midi_picker(valueX, 305, 300, draw_popup=True, draw_button=False)

    # flip() the display to put your work on screen
    pygame.display.flip()
    oldMouse=newMouse
    clock.tick(60)  # limits FPS to 60

if outport is not None:
    try:
        outport.close()
    except Exception:
        pass

pygame.quit()
