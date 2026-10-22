"""Uncertainty from model knowledge (phase L): what the model does not know, not how far it is from a simulation.

Each source contributes a relative standard deviation; they combine in quadrature:

    unknown kit mechanics     effects whose trigger, amount or condition is unknown (no credit given): 2.5% each,
                              3% when the effect would reach the main damage dealer; capped at 15%
    unknown gear effects      weapon / set sentences the compiler could not read or whose condition is not modelled:
                              1% each, capped at 6%
    per-hit unknowns          effects that depend on a state or resource whose value is unknown at the hit: 1% each
    assumed kit facts         facts a kit file marks as assumed (timings, application, particles), weighted by that
                              member's damage share: 1% per fact, capped at 8% overall
    provisional data          prerelease / beta kit versions: 12% x the member's damage share
    reaction approximation    damage that rides on the aura simulation: amplifying and additive reactions 10%,
                              transformative 15%, Lunar 15%, x their share of team damage
    uncovered damage          damage with no modelled formula: 25% x its share
    rotation                  a generated rotation: 5%, plus 10% x the unrealised share of the carry's states, plus
                              idle time; members whose energy is marginal (+5%) or unsustainable (+10%)

Confidence: High (< 10%, no unknown mechanic on the main damage dealer), Medium (< 20%), Low otherwise.
"""
from __future__ import annotations

import math
from functools import lru_cache

REACTION_SD = {"melt": 0.10, "vaporize": 0.10, "aggravate": 0.10, "spread": 0.10, "lunarcharged": 0.15,
               "lunarbloom": 0.15, "lunarcrystallize": 0.15}
NOT_DAMAGE = ("heal", "shield", "interruption", "infusion", "other", "cooldown", "energy", "er")


@lru_cache(maxsize=256)
def _kit_meta(m: str) -> tuple[dict, dict]:
    """(facts, status) of a kit file, parsed once per process (evaluate calls this for every candidate)."""
    from gtc.forward.library import load_hand

    lib = load_hand(m)
    return ((lib.facts if lib else {}) or {}), ((getattr(lib, "status", None) or {}) if lib else {})


def _status(m: str) -> dict:
    return _kit_meta(m)[1]


def _unknown_facts(m: str) -> list:
    return list(_kit_meta(m)[0].get("unknown") or [])


def _assumed(m: str) -> list:
    return list(_kit_meta(m)[0].get("assumed") or [])


def assess(rot, ev, realisation: dict | None = None, generated: bool | None = None) -> dict:
    comps: list[dict] = []
    share = ev.damage_share or {}
    main = max(share, key=share.get) if share else None

    def add(source, sd, detail):
        if sd > 1e-4:
            comps.append({"source": source, "sd": round(sd, 4), "detail": detail})

    kit_unknown = [c for c in ev.condition_states if c["state"] == "unknown" and c["kind"] not in NOT_DAMAGE
                   and ":gear:" not in c["effect"]]
    on_main = [c for c in kit_unknown if c["caster"] == main]
    facts_unknown = [(m, f) for m in rot.lineup for f in _unknown_facts(m)]
    fu_main = [x for x in facts_unknown if x[0] == main]
    sd = min(0.15, 0.03 * (len(on_main) + len(fu_main)) + 0.025 * (len(kit_unknown) - len(on_main))
             + 0.015 * (len(facts_unknown) - len(fu_main)))
    on_main = on_main + [{"caster": m, "source": f} for m, f in fu_main]
    add("unknown kit mechanics", sd, ([f"{c['caster']}: {c['source']}" for c in kit_unknown]
                                      + [f"{m}: {str(f)[:80]}" for m, f in facts_unknown])[:6])
    gear_unknown = [c for c in ev.condition_states if c["state"] == "unknown" and ":gear:" in c["effect"]]
    add("unknown gear effects", min(0.06, 0.01 * len(gear_unknown)), [f"{c['caster']}: {c['source']}" for c in gear_unknown][:6])
    dyn = [u for u in ev.unknown if "depends on a state or resource" in u]
    add("per-hit unknowns", min(0.05, 0.01 * len(dyn)), dyn[:4])
    assumed = 0.0
    adet = []
    for m in rot.lineup:
        a = _assumed(m)
        if a:
            assumed += 0.01 * len(a) * min(1.0, 2 * share.get(m, 0.0))
            adet.append(f"{m}: {len(a)} assumed fact(s)")
    add("assumed kit facts", min(0.08, assumed), adet)
    prov = 0.0
    pdet = []
    for m in rot.lineup:
        st = _status(m)
        if st.get("release_status") == "prerelease" or str(st.get("kit_version", "")).startswith("beta"):
            prov += 0.12 * share.get(m, 0.0)
            pdet.append(f"{m}: {st.get('release_status')} {st.get('kit_version')}")
    add("provisional data", prov, pdet)
    tot = ev.total_damage or 1.0
    rsd, rdet = 0.0, []
    for k, v in (ev.per_reaction or {}).items():
        fam = k.split("-")[0]
        w = REACTION_SD.get(fam, 0.15)
        rsd += w * v / tot
        rdet.append(f"{k}: {v / tot:.0%} of damage")
    add("reaction approximation", rsd, rdet)
    add("uncovered damage", 0.25 * (1 - (ev.coverage or 0.0)), [f"coverage {ev.coverage:.0%}"])
    if generated is None:
        generated = not str(getattr(rot, "source", "")).startswith("gcsim")
    if generated:
        rs = 0.05
        det = ["generated rotation"]
        if realisation:
            st = realisation.get("state_realisation") or {}
            if st:
                unreal = 1 - sum(st.values()) / len(st)
                rs += 0.10 * unreal
                det.append(f"state realisation {1 - unreal:.0%}")
            idle = realisation.get("idle") or ""
            try:
                secs = float(idle.split()[1])
            except (IndexError, ValueError):
                secs = 0.0
            if secs:
                rs += min(0.10, secs / max(rot.duration, 1.0))
                det.append(idle)
        for m, v in (ev.energy or {}).items():
            if v.get("status") == "marginal":
                rs += 0.05
                det.append(f"{m} energy marginal")
            elif v.get("status") == "unsustainable":
                rs += 0.10
                det.append(f"{m} energy unsustainable")
        add("rotation", rs, det)
    total = math.sqrt(sum(c["sd"] ** 2 for c in comps))
    comps.sort(key=lambda c: -c["sd"])
    if total < 0.10 and not on_main:
        conf, why = "High", "all major mechanics modelled"
    elif total < 0.20:
        conf, why = "Medium", "application, timing or reactions approximated"
    else:
        conf, why = "Low", "an important mechanic is unresolved or approximated"
    if on_main and conf == "High":
        conf = "Medium"
    if on_main and conf != "Low":
        why = f"a mechanic of the main damage dealer is unknown ({str(on_main[0]['source'])[:60]})"
    return {"sd": round(min(total, 0.6), 3), "confidence": conf, "why": why, "components": comps,
            "matters_most": [c["source"] for c in comps[:3]]}
