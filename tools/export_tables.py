"""Export the Python app's parameter tables to data/*.json for the C++ app.

Run from anywhere:  python3 tools/export_tables.py
"""
import json
from extract_definitions import ROOT, load

defs = load()


def generic_param(p):
    out = {
        "name": p["name"],
        "address": [int(b, 16) for b in p["address"]],
        "default": p["default"],
    }
    if "enum" in p:
        out["enum"] = p["enum"]
        out["raw_min"], out["raw_max"] = 0, len(p["enum"]) - 1
    else:
        out["raw_min"] = p.get("raw_min", 0)
        out["raw_max"] = p.get("raw_max", 127)
    for key in ("display_codec", "data_codec", "prefix", "suffix"):
        if key in p:
            out[key] = p[key]
    return out


def part_param(p):
    out = {
        "name": p["name"],
        "area": int(p["area"], 16),
        "offset": p["offset"],
        "default": p["default"],
        "raw_min": p["raw_min"],
        "raw_max": p["raw_max"],
    }
    for key in ("enum", "display_codec", "data_codec", "suffix"):
        if key in p:
            out[key] = p[key]
    return out


pages = {
    "pages": [
        {"id": page_id, "title": page["title"],
         "params": [generic_param(p) for p in page["params"]]}
        for page_id, page in defs["PARAMETER_PAGES"].items()
    ]
}

parts = {
    "categories": [
        {"name": cat, "params": [part_param(p) for p in defs["PART_PARAM_DEFS"][cat]]}
        for cat in defs["PART_PARAM_CATEGORIES"]
    ],
    # Defaults that depend on the part number (see default_part_param_value).
    "part_defaults": {
        "Rx Channel": "part_number_minus_1",
        "Assign Mode": {"10": 0},
        "Rhythm Part": {"10": 1},
    },
}

for name, data in (("parameter_pages.json", pages), ("part_params.json", parts)):
    path = ROOT / "data" / name
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print("wrote", path.relative_to(ROOT))
