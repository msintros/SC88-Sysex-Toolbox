#!/usr/bin/env python3
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent
src=json.loads((HERE/"efx_source.json").read_text(encoding="utf-8"))

def displays(codec):
    out=[""]*128
    t=codec["type"]
    if t in ("lookup","enum"):
        for raw,val in codec["pairs"]:
            if 0 <= raw < 128: out[raw]=str(val)
    elif t=="linear":
        for raw in range(codec["raw_min"],codec["raw_max"]+1):
            val=codec["display_min"]+(raw-codec["raw_min"])*codec["display_step"]
            if isinstance(val,float) and val.is_integer(): val=int(val)
            out[raw]=f"{val}{codec.get('suffix','')}"
    elif t=="pan":
        for raw in range(128):
            out[raw]=f"L{64-raw}" if raw<64 else ("C" if raw==64 else f"R{raw-64}")
    elif t=="balance":
        for raw in range(128): out[raw]=str(raw)
    return out

legacy={"efx":[]}
for effect in src["effects"]:
    slots=[["",0,""] for _ in range(20)]
    for p in effect["params"]:
        label=("+" if p.get("controller")==1 else "#" if p.get("controller")==2 else "")+p["name"]
        slots[p["address"]-3]=[label,p["default_raw"],displays(src["codecs"][p["codec"]])]
    legacy["efx"].append({"hex":effect["hex"],"name":effect["name"],"params":slots})

(HERE/"efx.json").write_text(json.dumps(legacy,indent=2,ensure_ascii=False),encoding="utf-8")
print(f"Wrote {HERE/'efx.json'} with {len(legacy['efx'])} effects")
