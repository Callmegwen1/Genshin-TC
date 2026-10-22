"""Freeze a character's action structure into a static kit file (phase C), so blind theorycrafting never runs gcsim.

Source: gcsim-measured behaviour of community rotations of OTHER teams (`library.build`, which never uses any team in
`exclude`; the blind reference set is always excluded). What is kept, and its provenance:

    multipliers   re-linked to the Amber talent tables wherever a measured value equals a table value at talent
                  level 9 (provenance amber: kit-number changes propagate); otherwise literal (provenance gcsim)
    timings       action durations and hit offsets (gcsim-calibrated: the game's frame data as gcsim implements it)
    application   Normal / Charged / Plunge hits use the engine's standard ICD (1U on the 1st of every 3 hits or after
                  2.5 s); Skill / Burst hits keep the measured per-cast gauge pattern (gcsim-calibrated)
    particles     per Skill cast (gcsim-calibrated)
    Swirl         dropped: the reaction model decides Swirl from the auras
    Anemo absorption  hits of an Anemo character in another element become element "absorb" (follows the aura)

Hand-written causal mechanics (states, resources, rules, procs, summons) are layered on top in the same file, under
`causal:`; `freeze()` keeps an existing `causal:` block and every key it does not regenerate.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from gtc import KNOWLEDGE_DIR

ACT_DIR = KNOWLEDGE_DIR / "forward" / "actions"
CHAIN_TYPES = ("normal", "charged", "plunge")


def _table_ref(name: str, mult: float) -> list | None:
    from gtc.forward import data as D

    best = None
    for kind in ("normal", "skill", "burst"):
        for label, vals in D.table(name, kind).items():
            for i, v in enumerate(vals):
                if v and abs(v - mult) <= 1e-3 * max(1.0, abs(v)):
                    if best is None:
                        best = [kind, label, i]
    return best


def _merge(libs: list) -> dict:
    """Union of actions across role libraries: the first library wins a shared action."""
    acts, fillers, follow, first = {}, [], {}, None
    for lib in libs:
        for k, e in lib.actions.items():
            acts.setdefault(k, e)
        for f in lib.fillers:
            if f not in fillers:
                fillers.append(f)
        for k, v in lib.follow.items():
            follow.setdefault(k, v)
        first = first or lib.first
    return {"actions": acts, "fillers": fillers[:4], "follow": follow, "first": first or "skill"}


def freeze(name: str, exclude: list, roles=("carry", "support")) -> dict:
    from gtc.forward.library import build
    from gtc.mechanics import element_of

    libs = []
    sources = set()
    for role in roles:
        lib = build(name, exclude, role=role, measured=True)
        if lib.actions:
            libs.append(lib)
            sources |= set(lib.sources)
    m = _merge(libs)
    own = element_of(name)
    out_actions, n_hits, n_amber = {}, 0, 0
    for k, e in m["actions"].items():
        if k == "wait" and not e.hits:
            continue
        hits = []
        for h in e.hits:
            if h.reaction == "swirl":
                continue
            spec = {"offset": round(h.offset, 3), "type": h.damage_type}
            ref = _table_ref(name, h.mult) if h.mult else None
            n_hits += 1
            if ref:
                spec["table"] = ref
                n_amber += 1
            else:
                spec["mult"] = round(h.mult, 6)
                spec["abil"] = h.abil
                spec["source"] = "gcsim"
            el = h.element
            if own == "Anemo" and el in ("Pyro", "Hydro", "Electro", "Cryo"):
                el = "absorb"
            spec["element"] = el
            if h.scaling != "atk":
                spec["scaling"] = h.scaling
            if h.ignore_def:
                spec["ignore_def"] = True
            if h.damage_type in CHAIN_TYPES:
                spec["icd"] = "standard"
                spec["gauge"] = 1.0
            else:
                spec["gauge"] = round(h.gauge, 2)
            hits.append(spec)
        out_actions[k] = {"duration": round(e.duration, 3), "particles": e.particles, "hits": hits}
    path = ACT_DIR / f"{name}.yaml"
    old = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get(name, {}) if path.exists() else {}
    doc = {**old}
    doc.update({
        "status": {"release_status": "released", "kit_version": "amber-current"},
        "provenance": {"structure": "gcsim-calibrated (behaviour of other teams' community rotations)",
                       "sources": sorted(sources), "excluded_reference_teams": [" / ".join(t) for t in exclude],
                       "multipliers": f"{n_amber} of {n_hits} hits linked to Amber tables; the rest literal (gcsim)",
                       "application": "Normal/Charged/Plunge: engine standard ICD; Skill/Burst: measured per cast"},
        "actions": {**out_actions, **(old.get("actions_override") or {})},
        "fillers": m["fillers"], "follow": m["follow"], "first": m["first"],
    })
    causal = old.get("causal") or {}
    for key in ("resources", "states", "rules", "summons", "procs", "reaction_procs", "specials", "level_bonus", "facts",
                "action_rules"):
        if key in causal:
            doc[key] = causal[key]
    # causal actions replace or remove measured ones (procs moved out of a cast, state variants)
    for k, v in (causal.get("actions") or {}).items():
        if v is None:
            doc["actions"].pop(k, None)
        else:
            doc["actions"][k] = v
    for k, hits_drop in (causal.get("drop_hits") or {}).items():
        if k in doc["actions"]:
            doc["actions"][k]["hits"] = [h for h in doc["actions"][k]["hits"]
                                        if not any(d in (h.get("abil") or str(h.get("table"))) for d in hits_drop)]
    doc["causal"] = causal
    ACT_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# Kit file for the forward model (gtc/forward/kitfreeze.py). Regenerate with freeze(); edit `causal:`.\n"
                    + yaml.safe_dump({name: doc}, sort_keys=False, allow_unicode=True, width=140), encoding="utf-8")
    return {"name": name, "actions": len(out_actions), "hits": n_hits, "amber": n_amber, "sources": len(sources)}
