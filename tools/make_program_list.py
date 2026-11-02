"""Builds data/programs.json, the SC-88 Pro Native map instrument and drum set
lists, from a text export of the owner's manual (Instrument list pp. 154-161,
Drum set list p. 163).

    python3 tools/make_program_list.py SC-88_Pro_Manual.txt data/programs.json

Each row of the instrument list is "[PC] CC00 <Native name> <voices>" followed by
the SC-88 map and SC-55 map columns. Only the Native map (the power-on map) is
kept. Names may end in digits ("Piano 1 1"), so the row is split by trying each
place the Native column could end and keeping the one whose remainder parses as
two more columns.
"""

import json
import re
import sys

CATEGORIES = [
    "Piano", "Chromatic percussion", "Organ", "Guitar", "Bass", "Strings/orchestra",
    "Ensemble", "Brass", "Reed", "Pipe", "Synth lead", "Synth pad, etc", "Synth SFX",
    "Ethnic, etc", "Percussive", "SFX",
]
# Display names for the menu.
TITLES = {
    "Chromatic percussion": "Chromatic Percussion", "Strings/orchestra": "Strings / Orchestra",
    "Synth lead": "Synth Lead", "Synth pad, etc": "Synth Pad", "Synth SFX": "Synth SFX",
    "Ethnic, etc": "Ethnic",
}

# Rows the text export mangled, by (PC, CC00): the Native map name.
FIXES = {
    (40, 9): "Dly Bass",
    (40, 10): "X Wire Bass",
}


def is_voice(tok):
    return tok in ("1", "2")


def parse_column(tokens, i, first):
    """Yields every index just past one map column starting at tokens[i]."""
    if i < len(tokens) and tokens[i] == "-----":
        if not first:
            yield i + 1
        return
    j = i
    if not first:
        while j < len(tokens) and tokens[j] in ("#", "*", "X"):
            j += 1
    while j < len(tokens) and tokens[j] == "+":
        j += 1
    # Name tokens, then a voice count, then an optional "+".
    for k in range(j + 1, len(tokens)):
        if is_voice(tokens[k]) and not is_voice(tokens[j]):
            end = k + 1
            while end < len(tokens) and tokens[end] in ("+", "#", "*"):
                if tokens[end] == "+":
                    end += 1
                else:
                    break
            yield end


def native_name(tokens):
    """Name in the Native column of a row's tokens (after PC/CC00)."""
    candidates = []
    for end in parse_column(tokens, 0, True):
        for end2 in parse_column(tokens, end, False):
            for end3 in parse_column(tokens, end2, False):
                if end3 == len(tokens):
                    candidates.append(end)
    if not candidates:
        return None, 0
    # Voice count sits just before the end (possibly followed by "+").
    end = candidates[0]
    k = end - 1
    while tokens[k] == "+":
        k -= 1
    return " ".join(tokens[:k]), len(set(candidates))


def clean(name):
    # A trailing ":" is the manual's legato mark. It is kept, as it is the only
    # thing telling "Trumpet" (057/000) from "Trumpet :" (057/002).
    return name.strip()


def parse_instruments(lines):
    start = next(i for i, l in enumerate(lines) if l.strip() == "Piano" and "PC CC00" in lines[i + 1])
    end = next(i for i, l in enumerate(lines) if i > start and l.strip() == "CM-64")
    categories, current, pc = [], None, None
    for raw in lines[start:end]:
        line = raw.strip()
        if line in CATEGORIES:
            current = {"name": TITLES.get(line, line), "programs": []}
            categories.append(current)
            continue
        m = re.match(r"^(\d{3}) (\d{3}) (.*)$", line)
        # "017 303 Sqr Bs": a CC00 row whose name starts with digits.
        if m and int(m.group(2)) > 127:
            m = None
        if m:
            pc, cc0, rest = int(m.group(1)), int(m.group(2)), m.group(3)
        else:
            m = re.match(r"^(\d{3}) (.*)$", line)
            if not m or pc is None or current is None:
                continue
            cc0, rest = int(m.group(1)), m.group(2)
            # Page numbers and similar lines never have a voice count.
            if not re.search(r"\b[12]\b", rest):
                continue
        name = FIXES.get((pc, cc0))
        if name is None:
            name, ways = native_name(rest.split())
            if name is None:
                raise SystemExit(f"could not parse {pc:03}/{cc0:03}: {line}")
            if ways > 1:
                print(f"ambiguous {pc:03}/{cc0:03}: {line} -> {name}", file=sys.stderr)
        current["programs"].append({"pc": pc, "cc0": cc0, "name": clean(name)})
    return categories


# Drum set list, Native map column (p. 163). Short enough to keep here; the
# text export runs the three map columns together.
DRUM_SETS = [
    (1, "STANDARD 1"), (2, "STANDARD 2"), (3, "STANDARD 3"), (9, "ROOM"), (10, "HIP HOP"),
    (11, "JUNGLE"), (12, "TECHNO"), (17, "POWER"), (25, "ELECTRONIC"), (26, "TR-808"),
    (27, "DANCE"), (28, "CR-78"), (29, "TR-606"), (30, "TR-707"), (31, "TR-909"),
    (33, "JAZZ"), (41, "BRUSH"), (49, "ORCHESTRA"), (50, "ETHNIC"), (51, "KICK & SNARE"),
    (53, "ASIA"), (54, "CYMBAL&CLAPS"), (57, "SFX"), (58, "RHYTHM FX"), (59, "RHYTHM FX 2"),
]


def parse_drums(lines):
    # Check the hand-kept list against the manual's rows.
    start = next(i for i, l in enumerate(lines) if l.startswith("PC Native Map SC-88Map SC-55Map"))
    for (pc, name), line in zip(DRUM_SETS, lines[start + 1:]):
        if not line.startswith(f"{pc:03} {name}"):
            raise SystemExit(f"drum set list mismatch: {line}")
    return [{"pc": pc, "cc0": 0, "name": name} for pc, name in DRUM_SETS]


def main():
    src, dst = sys.argv[1], sys.argv[2]
    lines = open(src, encoding="utf-8").read().splitlines()
    data = {
        "source": "SC-88 Pro owner's manual: Instrument list (Native map) pp. 154-161, Drum set list p. 163",
        "categories": parse_instruments(lines),
        "drumSets": parse_drums(lines),
    }
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        f.write("\n")
    n = sum(len(c["programs"]) for c in data["categories"])
    print(f"{n} instruments in {len(data['categories'])} categories, {len(data['drumSets'])} drum sets")


if __name__ == "__main__":
    main()
