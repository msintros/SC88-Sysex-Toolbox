"""Generate golden test vectors for the C++ core from the Python app.

Every display string and SysEx message here comes from the Python code itself,
so the C++ tests prove the port produces byte-identical output.

Run from anywhere:  python3 tools/make_golden.py
"""
import json
import sys
from extract_definitions import ROOT, load

sys.path.insert(0, str(ROOT))
import sysex_generator  # noqa: E402

defs = load()
gen = sysex_generator.generate_sysex


def hexmsg(address, data):
    return gen(address, data, False).upper()


def sample(lo, hi):
    """Every value for normal ranges, a stride plus edges for 14-bit ones."""
    if hi - lo <= 255:
        return list(range(lo, hi + 1))
    step = max(1, (hi - lo) // 200)
    return sorted(set(list(range(lo, hi + 1, step)) + [hi, (lo + hi) // 2]))


golden = {"generic": [], "part": [], "part_defaults": [], "scale_tune": [],
          "efx_assign": [], "system": [], "efx": [], "steps": []}

# Generic pages: Reverb, Chorus, Delay, EQ, Global.
for page_id, page in defs["PARAMETER_PAGES"].items():
    for index, p in enumerate(page["params"]):
        lo = 0 if "enum" in p else p.get("raw_min", 0)
        hi = len(p["enum"]) - 1 if "enum" in p else p.get("raw_max", 127)
        for raw in sample(lo, hi):
            golden["generic"].append({
                "page": page_id, "index": index, "raw": raw,
                "display": defs["format_parameter_value"](p, raw),
                "hex": hexmsg(p["address"], defs["encode_parameter_data"](p, raw)),
            })
        for raw in (lo, hi, p["default"]):
            for direction in (1, -1):
                golden["steps"].append({
                    "kind": "generic", "page": page_id, "index": index,
                    "raw": raw, "direction": direction,
                    "result": defs["step_parameter_value"](p, raw, direction),
                })

# Part parameters. The tone pair always sends bank + program from 1x00, so the
# vectors pin the other half of the pair to a known value.
PAIR_OTHER = 5
for group in ("A", "B"):
    for part in (1, 9, 10, 11, 16):
        for cat in defs["PART_PARAM_CATEGORIES"]:
            for index, p in enumerate(defs["PART_PARAM_DEFS"][cat]):
                values = sample(p["raw_min"], p["raw_max"]) if (group, part) == ("A", 1) \
                    else sorted({p["raw_min"], p["raw_max"], p["default"]})
                for raw in values:
                    address = defs["actual_part_param_address"](group, part, p)
                    codec = p.get("data_codec")
                    if codec == "tone_pair_bank":
                        data = [format(raw, "02x"), format(PAIR_OTHER, "02x")]
                    elif codec == "tone_pair_program":
                        data = [format(PAIR_OTHER, "02x"), format(raw, "02x")]
                    elif codec == "14bit":
                        data = [format((raw >> 7) & 0x7F, "02x"), format(raw & 0x7F, "02x")]
                    else:
                        data = [format(raw, "02x")]
                    golden["part"].append({
                        "group": group, "part": part, "category": cat, "index": index,
                        "raw": raw, "pair_other": PAIR_OTHER,
                        "display": defs["format_part_param_value"](p, raw),
                        "hex": hexmsg(address, data),
                    })

for part in range(1, 17):
    golden["part_defaults"].append({
        "part": part,
        "values": {cat: [defs["default_part_param_value"](p, part)
                         for p in defs["PART_PARAM_DEFS"][cat]]
                   for cat in defs["PART_PARAM_CATEGORIES"]},
    })

for group in ("A", "B"):
    for part in range(1, 17):
        for note in range(12):
            for raw in ((0x00, 0x40, 0x7F) if note else range(128)):
                golden["scale_tune"].append({
                    "group": group, "part": part, "note": note, "raw": raw,
                    "display": defs["format_scale_tune"](raw),
                    "hex": hexmsg(defs["scale_tune_address"](group, part, note), [format(raw, "02x")]),
                })
        for enabled in (False, True):
            golden["efx_assign"].append({
                "group": group, "part": part, "enabled": enabled,
                "hex": hexmsg(defs["efx_part_address"](group, part), ["01" if enabled else "00"]),
            })

for mode in (0, 1):
    golden["system"].append({"kind": "mode", "value": mode,
                             "hex": hexmsg(["00", "00", "7F"], [format(mode, "02x")])})
for block in range(32):
    for port in (0, 1):
        golden["system"].append({"kind": "block", "block": block, "value": port,
                                 "hex": hexmsg(["00", "01", format(block, "02x")], [format(port, "02x")])})

with open(ROOT / "efx.json") as f:
    efx = json.load(f)["efx"]
for type_index, effect in enumerate(efx):
    entry = {
        "type": type_index,
        "display_name": defs["effect_display_name"](effect["name"]),
        "type_hex": hexmsg(["40", "03", "00"], [effect["hex"][0:2], effect["hex"][2:4]]),
        "params": [],
    }
    for i, p in enumerate(effect["params"]):
        if p[0] == "":
            continue
        entry["params"].append({
            "index": i, "raw": p[1],
            "hex": hexmsg(["40", "03", format(3 + i, "x").zfill(2)], [format(p[1], "x").zfill(2)]),
            "step_up": defs["step_efx_value"](p, 1),
            "step_down": defs["step_efx_value"](p, -1),
        })
    golden["efx"].append(entry)

golden["gs_reset"] = hexmsg(["40", "00", "7F"], ["00"])

out = ROOT / "cpp" / "tests" / "golden" / "golden.json"
out.write_text(json.dumps(golden, separators=(",", ":"), ensure_ascii=False) + "\n")
print("wrote", out.relative_to(ROOT), {k: len(v) for k, v in golden.items() if isinstance(v, list)})
