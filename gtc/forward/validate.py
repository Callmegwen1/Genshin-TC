"""Forward model validation (FM-12): for teams with a community gcsim rotation, compare

    forward          this model, on the community rotation run with house builds
    gcsim (same)     gcsim's crit-averaged damage on exactly the same traced events: isolates the damage model
                     (stats, buffs, conditions, formulas) from rotation variance
    gcsim (mean)     gcsim's mean DPS over its iterations with house builds: includes energy and RNG variance
    community        the community database's DPS for the lineup (community builds: context, never a target)
    legacy           the pair model's normalised estimate (the current production route)

Two sets: CALIBRATION (teams whose diagnostics shaped the model: tuning only here) and LOCKED (never inspected while
building; validation only). Results: data/validation/forward_<set>.json (personal-use).
"""
from __future__ import annotations

import json
import time

from gtc import ROOT

CALIBRATION = [
    ["Kamisato Ayaka", "Shenhe", "Kaedehara Kazuha", "Mona"],
    ["Kamisato Ayaka", "Shenhe", "Kaedehara Kazuha", "Furina"],
    ["Flins", "Aino", "Ineffa", "Sucrose"],
]
LOCKED = [
    ["Raiden Shogun", "Xingqiu", "Xiangling", "Bennett"],
    ["Razor", "Fischl", "Bennett", "Chevreuse"],
    ["Kamisato Ayaka", "Shenhe", "Escoffier", "Furina"],
    ["Hu Tao", "Xingqiu", "Yelan", "Zhongli"],
    ["Neuvillette", "Furina", "Kaedehara Kazuha", "Baizhu"],
]
OUT = ROOT / "data" / "validation"


def run_team(lineup: list[str]) -> dict:
    from gtc.forward.model import contributions
    from gtc.forward.rotation import window_fit
    from gtc.forward.trace import house_trace
    from gtc.synergy import table

    t0 = time.time()
    tr = house_trace(lineup)
    if tr is None:
        return {"lineup": lineup, "error": "no community rotation"}
    rot, info = tr
    t1 = time.time()
    ev, contrib = contributions(rot, info=info)
    t2 = time.time()
    same = sum(h.gcsim_expected for h in rot.hits) / rot.duration
    community = ((table().by_lineup.get(frozenset(lineup)) or {}).get("dps"))
    try:
        from gtc.pairmodel import load

        pm = load()
        legacy = pm.predict(lineup) if pm else None
    except Exception:  # the legacy route is context only
        legacy = None
    gc_chars = info.get("gcsim_char_dps") or {}
    return {"lineup": lineup, "config": info.get("config"), "forward_dps": round(ev.dps), "gcsim_same_rotation": round(same),
            "gcsim_mean": round(info.get("gcsim_dps") or 0), "community_dps": round(community) if community else None,
            "legacy_estimate": round(legacy, 1) if legacy is not None else None,
            "error_vs_same": round(ev.dps / same - 1, 3) if same else None,
            "error_vs_mean": round(ev.dps / info["gcsim_dps"] - 1, 3) if info.get("gcsim_dps") else None,
            "forward_shares": {k: round(v, 3) for k, v in ev.damage_share.items()},
            "gcsim_shares": {k: round(v / sum(gc_chars.values()), 3) for k, v in gc_chars.items()} if gc_chars else {},
            "coverage": ev.coverage, "uncertainty": ev.uncertainty, "unknown": ev.unknown,
            "top_buffs": dict(list(contrib.items())[:6]), "energy": info.get("energy"), "er_added": info.get("er_added"),
            "field_time": ev.field_time, "window_fit": window_fit(lineup),
            "per_reaction": {k: round(v / ev.rotation_duration) for k, v in ev.per_reaction.items()},
            "seconds": {"trace": round(t1 - t0, 1), "forward_with_contributions": round(t2 - t1, 2)}}


def run(which: str = "calibration") -> list[dict]:
    teams = CALIBRATION if which == "calibration" else LOCKED
    rows = [run_team(t) for t in teams]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"forward_{which}.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    return rows
