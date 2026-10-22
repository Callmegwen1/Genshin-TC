"""Reaction event parity: the same rotation in the forward model and in gcsim, application by application.

gcsim side (sample log): every elemental application with the aura before ("existing") and after, Dendro cores
spawned / expired / triggered, and every reaction damage instance with its owner.
Forward side: the generated hits after the aura simulation (gtc/forward/reactions.py): each applying hit's aura
before (Hit.auras), its gauge, and the reaction hits with their owners.

Applications are aligned per (character, element) in order: the k-th Hydro application by Furina on one side is
compared with the k-th on the other. The first divergence is the first aligned application (in time) whose aura
before differs in which elements are present, or which is missing on one side.
Counters: applications per character and element, reactions per kind and owner, Dendro cores created / consumed by
Hyperbloom or Burgeon / expired as Bloom, Quicken uptime, Electro-on-Quicken hits (Aggravate-eligible) and actual
Aggravates.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

FPS = 60.0
ELE = {"pyro": "Pyro", "hydro": "Hydro", "electro": "Electro", "cryo": "Cryo", "anemo": "Anemo", "geo": "Geo",
       "dendro": "Dendro", "quicken": "Quicken", "frozen": "Frozen", "burning": "Burning"}


def _auras(lst) -> frozenset:
    out = set()
    for s in lst or []:
        k = str(s).split(":")[0].strip().lower()
        if k in ELE:
            out.add(ELE[k])
    return frozenset(out)


def compare(rot, builds: dict, sample: dict | None = None) -> dict:
    from gtc.forward.decompose import char_keys, to_gcsim
    from gtc.synergy import run_sample

    keys = char_keys(rot.lineup)
    if sample is None:
        sample = run_sample(to_gcsim(rot, builds, keys), keep=True)
    inv = {v: k for k, v in keys.items()}
    inv.update({re.sub(r"[^a-z0-9]", "", k.lower()): k for k in keys})
    order = [inv.get(c.get("name"), c.get("name")) for c in sample.get("character_details") or []]
    # ---- gcsim ----
    g_apps, g_rx, g_cores = [], Counter(), Counter()
    g_owner = defaultdict(Counter)
    quick_g = []
    for l in sample.get("logs") or []:
        ev, msg, fr, lg = l.get("event"), str(l.get("msg") or ""), l.get("frame", 0), l.get("logs") or {}
        ci = l.get("char_index", -1)
        who = order[ci] if 0 <= ci < len(order) else None
        if ev == "element" and msg == "application":
            before, after = _auras(lg.get("existing")), _auras(lg.get("after"))
            g_apps.append({"t": fr / FPS, "char": who, "abil": lg.get("abil"), "ele": ELE.get(str(lg.get("applied_ele")).lower()),
                           "units": (lg.get("dur") or 0) / 25.0, "before": before, "after": after})
            quick_g.append((fr / FPS, "Quicken" in after))
        elif ev == "element" and "dendro core" in msg:
            g_cores[msg.replace("dendro core ", "")] += 1
        elif ev == "element" and msg.endswith("triggered"):
            g_cores[msg] += 1
        elif ev == "damage":
            name = msg.lower()
            for k in ("hyperbloom", "burgeon", "bloom", "electrocharged", "lunarcharged", "overload", "superconduct",
                      "swirl", "shatter", "melt", "vaporize", "aggravate", "spread"):
                if name.startswith(k) and "self damage" not in name:
                    g_rx[k] += 1
                    g_owner[k][who] += 1
                    break
            amp = str(lg.get("amp") or "")
            cata = str(lg.get("cata") or "")
            for k in (amp, cata):
                if k:
                    g_rx[k] += 1
                    g_owner[k][who] += 1
    # ---- forward ----
    f_apps = []
    f_rx, f_owner = Counter(), defaultdict(Counter)
    for h in sorted(rot.hits, key=lambda x: x.t):
        k = h.reaction or h.amp or h.cata
        if k:
            fam = k.split("-")[0]
            fam = "overload" if fam in ("overloaded", "overload") else fam
            f_rx[fam] += 1
            f_owner[fam][h.char] += 1
        if h.gauge and not h.reaction and h.element not in ("", "Physical"):
            f_apps.append({"t": h.t, "char": h.char, "abil": h.abil, "ele": h.element, "units": h.gauge,
                           "before": frozenset(h.auras or ())})
    # align applications structurally: each application belongs to its character's latest action (same action index
    # on both sides: the same ordered actions), then the k-th application of an element within it. This separates
    # hit-structure differences from timeline drift.
    g_exec = [(l.get("frame", 0) / FPS, order[l["char_index"]] if 0 <= l.get("char_index", -1) < len(order) else None)
              for l in sample.get("logs") or [] if l.get("event") == "action"
              and str(l.get("msg", "")).startswith("executed ") and str(l.get("msg")) not in ("executed swap", "executed wait")]
    f_exec = [(a.t, a.char) for a in rot.actions]

    def owner_action(execs, char, t):
        idx = None
        for i, (tt, c) in enumerate(execs):
            if tt > t + 1e-6:
                break
            if c == char:
                idx = i
        return idx

    fq, gq = defaultdict(list), defaultdict(list)
    for a in f_apps:
        fq[(a["char"], owner_action(f_exec, a["char"], a["t"]), a["ele"])].append(a)
    for a in g_apps:
        gq[(a["char"], owner_action(g_exec, a["char"], a["t"]), a["ele"])].append(a)
    diffs = []
    for key in set(fq) | set(gq):
        for i in range(max(len(fq[key]), len(gq[key]))):
            a = fq[key][i] if i < len(fq[key]) else None
            b = gq[key][i] if i < len(gq[key]) else None
            if a is None or b is None:
                diffs.append((min(x["t"] for x in (a, b) if x), key, i, "missing on " + ("forward" if a is None else "gcsim"),
                              a, b))
            elif a["before"] - {"Frozen"} != b["before"] - {"Frozen"} or abs(a["units"] - b["units"]) > 0.26:
                diffs.append((min(a["t"], b["t"]), key, i, f"aura before {sorted(a['before'])} vs {sorted(b['before'])}; "
                              f"units {a['units']} vs {b['units']}", a, b))
    diffs.sort(key=lambda d: d[0])
    first = None
    if diffs:
        t, key, i, why, a, b = diffs[0]
        first = {"t": round(t, 2), "char": key[0], "action_index": key[1], "element": key[2], "k": i, "why": why,
                 "forward": None if a is None else {"t": round(a["t"], 2), "abil": a["abil"]},
                 "gcsim": None if b is None else {"t": round(b["t"], 2), "abil": b["abil"]}}
    # quicken uptime (gcsim from the aura after each application; forward from the simulation)
    dur = rot.duration or 1.0
    q_up = 0.0
    for (t0, q), (t1, _) in zip(quick_g, quick_g[1:]):
        if q:
            q_up += t1 - t0
    f_detail = ((rot.reactions or {}).get("_detail") or {}) if getattr(rot, "reactions", None) else {}
    f_quick = (f_detail.get("aura_uptime") or {}).get("Quicken")
    eligible_f = sum(1 for a in f_apps if a["ele"] == "Electro" and "Quicken" in a["before"])
    eligible_g = sum(1 for a in g_apps if a["ele"] == "Electro" and "Quicken" in a["before"])
    return {
        "applications": {"forward": dict(Counter(f"{a['char']}:{a['ele']}" for a in f_apps)),
                         "gcsim": dict(Counter(f"{a['char']}:{a['ele']}" for a in g_apps))},
        "reactions": {"forward": dict(f_rx), "gcsim": dict(g_rx)},
        "owners": {"forward": {k: dict(v) for k, v in f_owner.items()}, "gcsim": {k: dict(v) for k, v in g_owner.items()}},
        "cores_gcsim": dict(g_cores),
        "quicken_uptime": {"forward": f_quick, "gcsim": round(q_up / dur, 3)},
        "aggravate_eligible_electro_applications": {"forward": eligible_f, "gcsim": eligible_g},
        "first_divergence": first, "divergences": len(diffs),
        "divergence_examples": [(round(d[0], 2), d[1], d[2], d[3]) for d in diffs[:8]],
    }
