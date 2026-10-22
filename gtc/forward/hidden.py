"""Hidden validation set (first real out-of-sample test). Personal-use diagnostics; production untouched.

Protocol (the first result is the result; it is never overwritten):
    1. freeze()  - with the engine frozen, run the blind theorycraft on every hidden team and store what it predicts:
                   the selected strategy, the forward DPS, the top finalists (for search regret), the rotations and
                   builds, and a fingerprint of the kits, frame data and engine version. No reference rotation, DPS,
                   damage share or reaction count is read at this stage.
    2. reveal()  - only after freeze(), once: play the frozen rotations in gcsim, run each community reference, and
                   write data/validation/hidden_first_result.json (refused if it exists) plus a `hidden` run in the
                   results store.

The hidden lineups were chosen from community configs that are not development teams, were never a kit source
(gtc/forward/kitfreeze provenance), and had no gcsim log in data/sims when chosen (so no frame data came from them).
They are excluded from frame measurement like the development teams.
"""
from __future__ import annotations

import hashlib
import json
import pickle
import time

from gtc import KNOWLEDGE_DIR, ROOT

OUT = ROOT / "data" / "validation"
FROZEN = OUT / "hidden_frozen.pkl"
FROZEN_JSON = OUT / "hidden_frozen.json"
FIRST = OUT / "hidden_first_result.json"

HIDDEN = [
    {"cohort": "Freeze", "team": ["Kamisato Ayaka", "Shenhe", "Kaedehara Kazuha", "Yelan"]},
    {"cohort": "Melt", "team": ["Kamisato Ayaka", "Bennett", "Xiangling", "Sucrose"]},
    {"cohort": "Vaporize", "team": ["Hu Tao", "Xingqiu", "Yelan", "Xiangling"]},
    {"cohort": "Vaporize + HP state (Furina)", "team": ["Hu Tao", "Furina", "Yelan", "Zhongli"]},
    {"cohort": "Hypercarry + Pyro (Neuvillette)", "team": ["Neuvillette", "Xiangling", "Bennett", "Kaedehara Kazuha"]},
    {"cohort": "Overloaded", "team": ["Raiden Shogun", "Chevreuse", "Bennett", "Xiangling"]},
    {"cohort": "Overloaded dual-window", "team": ["Razor", "Chevreuse", "Bennett", "Xiangling"]},
    {"cohort": "National-like", "team": ["Xiangling", "Xingqiu", "Bennett", "Furina"]},
    {"cohort": "Quicken (Aggravate)", "team": ["Yae Miko", "Fischl", "Nahida", "Kaedehara Kazuha"]},
    {"cohort": "Hyperbloom / Quicken", "team": ["Nahida", "Kuki Shinobu", "Fischl", "Yelan"]},
    {"cohort": "Direct hypercarry", "team": ["Neuvillette", "Furina", "Kaedehara Kazuha", "Zhongli"]},
    {"cohort": "Summon-heavy", "team": ["Yae Miko", "Fischl", "Furina", "Baizhu"]},
    {"cohort": "Raiden + Dendro (dual-window)", "team": ["Raiden Shogun", "Nahida", "Xingqiu", "Yelan"]},
    {"cohort": "Lunar", "team": ["Flins", "Ineffa", "Furina", "Sucrose"]},
    {"cohort": "Lunar (Razor)", "team": ["Razor", "Ineffa", "Aino", "Sucrose"]},
    {"cohort": "Quickswap candidate", "team": ["Raiden Shogun", "Nahida", "Fischl", "Zhongli"]},
    {"cohort": "Electro-Charged / Freeze", "team": ["Raiden Shogun", "Escoffier", "Furina", "Yelan"]},
]


def lineups() -> set[frozenset]:
    return {frozenset(e["team"]) for e in HIDDEN}


def fingerprint() -> dict:
    """What the frozen prediction was made with: engine version, and hashes of the kit files and frame data."""
    from gtc.forward import FORWARD_VERSION

    h = hashlib.sha256()
    for p in sorted((KNOWLEDGE_DIR / "forward" / "actions").glob("*.yaml")):
        h.update(p.read_bytes())
    frames = (KNOWLEDGE_DIR / "forward" / "frames.json").read_bytes()
    return {"version": FORWARD_VERSION, "kits_sha256": h.hexdigest(), "frames_sha256": hashlib.sha256(frames).hexdigest()}


def freeze(profile: str = "neutral", top: int = 6) -> dict:
    """Blind predictions for every hidden team (no reference is read). Refuses to overwrite a freeze."""
    if FROZEN.exists():
        raise RuntimeError(f"{FROZEN} exists: the hidden predictions are already frozen")
    from gtc.forward.blind import theorycraft
    from gtc.forward.decompose import _label, all_candidates, finalists
    from gtc.forward.generator import on_field_dealers, roles
    from gtc.forward.library import build

    out, store = [], {}
    for e in HIDDEN:
        team = e["team"]
        t0 = time.time()
        r = theorycraft(team, profile=profile)
        builds = r.get("builds") or r.get("used_builds")
        carry, _ = roles(team)
        carries = set(on_field_dealers(team)) | {carry}
        libs = {m: build(m, [team], role="carry" if m in carries else "support") for m in team}
        cands = all_candidates(team, libs, None if profile == "neutral" else builds)
        fin = finalists(cands, top)
        sel = cands[0]
        store[" / ".join(team)] = {"selected": (sel[1], sel[2], getattr(sel[2], "builds", None) or builds),
                                   "finalists": [(f[0], f[1], f[2], getattr(f[2], "builds", None) or builds) for f in fin]}
        out.append({"cohort": e["cohort"], "team": team, "selected": _label(sel[1]), "forward_dps": round(sel[0]),
                    "finalists": [{"strategy": _label(f[1]), "forward_dps": round(f[0])} for f in fin],
                    "seconds": round(time.time() - t0, 1)})
    OUT.mkdir(parents=True, exist_ok=True)
    meta = {"frozen_at": time.strftime("%Y-%m-%d %H:%M:%S"), "profile": profile, **fingerprint(), "teams": out}
    with open(FROZEN, "wb") as f:
        pickle.dump({"meta": meta, "store": store}, f)
    FROZEN_JSON.write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return meta


def reveal() -> dict:
    """Play the frozen predictions against gcsim and the community references - once. The first result is kept."""
    if FIRST.exists():
        raise RuntimeError(f"{FIRST} exists: the first hidden result is final and is not overwritten")
    if not FROZEN.exists():
        raise RuntimeError("freeze() first")
    from gtc.forward.decompose import run_generated
    from gtc.forward.parity import compare
    from gtc.forward.rxparity import compare as rx_compare
    from gtc.forward.trace import house_trace
    from gtc.forward import structure as ST

    with open(FROZEN, "rb") as f:
        frozen = pickle.load(f)
    meta, store = frozen["meta"], frozen["store"]
    now = fingerprint()
    rows = []
    for t in meta["teams"]:
        team = t["team"]
        st = store[" / ".join(team)]
        plan, rot, b = st["selected"]
        g = run_generated(rot, b)
        same = g.get("gcsim_steady") or g.get("gcsim_dps") or 0.0
        fins = []
        for fdps, fplan, frot, fb in st["finalists"]:
            fg = run_generated(frot, fb)
            fins.append({"forward_dps": round(fdps), "gcsim_dps": round(fg.get("gcsim_steady") or fg.get("gcsim_dps") or 0)})
        best = max(f["gcsim_dps"] for f in fins) if fins else same
        tr = house_trace(team, None)
        ref = tr[1]["gcsim_dps"] if tr else None
        par = compare(rot, b)
        rxp = rx_compare(rot, b)
        fwd = t["forward_dps"]
        # ranking agreement within the finalists: does the forward order match gcsim's?
        from itertools import combinations

        pairs = [(x, y) for x, y in combinations(fins, 2) if x["gcsim_dps"] != y["gcsim_dps"]]
        agree = (sum((x["forward_dps"] > y["forward_dps"]) == (x["gcsim_dps"] > y["gcsim_dps"]) for x, y in pairs)
                 / len(pairs)) if pairs else None
        rf, rg = (rxp.get("reactions") or {}).get("forward") or {}, (rxp.get("reactions") or {}).get("gcsim") or {}
        rx_err = {k: round(rf.get(k, 0) / v - 1, 3) for k, v in rg.items() if v >= 10}
        row = {"set": "hidden", "cohort": t["cohort"], "family": f"HIDDEN {t['cohort']}", "team": team,
               "selected": t["selected"], "forward_dps": fwd, "gcsim_same_rotation": round(same),
               "best_generated_gcsim": round(best), "reference_gcsim": round(ref) if ref else None,
               "calculator_error": round(fwd / same - 1, 3) if same else None,
               "residual": round(fwd / ref - 1, 3) if ref else None,
               "search_regret": round(1 - best / ref, 3) if ref else None,
               "selection_regret": round(1 - same / best, 3) if best else None,
               "duration_error": par.get("duration_error"), "ranking_agreement_finalists": agree,
               "reaction_rate_error": rx_err, "reactions": rxp.get("reactions"), "applications": rxp.get("applications"),
               "reaction_owners": rxp.get("owners"), "finalists": fins,
               "structure": ({"reference": ST.profile(tr[0]), "selected": ST.profile(g["trace"]),
                              "delta_selected": ST.delta(ST.profile(g["trace"]), ST.profile(tr[0]))}
                             if tr and g.get("trace") is not None else {}),
               "profile": meta["profile"]}
        rows.append(row)
    result = {"revealed_at": time.strftime("%Y-%m-%d %H:%M:%S"), "frozen": {k: meta[k] for k in
              ("frozen_at", "version", "kits_sha256", "frames_sha256")}, "engine_unchanged_since_freeze":
              all(now[k] == meta[k] for k in ("version", "kits_sha256", "frames_sha256")), "rows": rows}
    FIRST.write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")
    try:
        from gtc.forward.results import record

        result["run"] = record(rows)
    except Exception as ex:   # noqa: BLE001
        result["record_error"] = f"{type(ex).__name__}: {ex}"
    return result
