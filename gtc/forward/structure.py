"""Structural profile of a rotation as gcsim executed it, for comparing our strategies with the community reference
(development diagnostics; the reference is never an input to the generator).

Both sides are measured the same way, on gcsim traces: the reference's own sample and our selected rotation played
in gcsim. Rates are per minute so different cycle lengths compare. Fields:
    driver              the on-field character with the most field time
    driver_field_share  its share of field time
    driver_damage_share its share of team damage
    carry_attacks_pm    Normal / Charged / Plunge actions by the driver
    damaging_actions_pm attack, charge, plunge, skill and burst actions (dash, jump, swap and wait excluded)
    support_casts_pm    Skill / Burst casts by the other characters
    support_field_s_pm  seconds per minute other characters hold the field (setup / refresh time)
    bursts_pm, skills_pm, swaps_pm
    idle_s_pm           seconds per minute gcsim spent refusing an action (cooldown, energy, stamina, swap) or in
                        an explicit wait (gcsim traces); for a generated rotation, gaps beyond the measured transitions
    reactions_pm        reaction events: transformative damage plus amplified (melt, vaporize) and catalysed hits
    cycle_s             median interval between Bursts of the character who casts the most Bursts
    support_recasts_pm  support Skills beyond one per support per cycle
    damage_per_action   team damage per damaging action (the average action value)
"""
from __future__ import annotations

import statistics
from collections import Counter, defaultdict

DAMAGING = {"attack", "charge", "skill", "burst", "high_plunge", "low_plunge", "aim"}
CARRY = {"attack", "charge", "high_plunge", "low_plunge", "aim"}


def _idle(rot) -> float:
    from gtc.forward import frames as FR

    acts = [a for a in rot.actions if a.action]
    idle = 0.0
    run = 0
    for a0, a1 in zip(acts, acts[1:]):
        run = run + 1 if a0.action == "attack" else 0
        gap = a1.t - a0.t
        if a1.char == a0.char:
            need = FR.gap(a0.char, a0.action, run, a1.action) or FR.lock(a0.char, a0.action, a1.action)
        else:
            need = (FR.lock(a0.char, a0.action, "swap") or 0.0) + 0.2
        if need is not None and gap > need + 0.05:
            idle += gap - need
    return idle


def profile(rot) -> dict:
    """The structural profile of a rotation (a gcsim trace, or a generated rotation)."""
    dur = rot.duration or 1.0
    pm = 60.0 / dur
    acts = [a for a in rot.actions if a.action]
    ft = rot.field_time()
    driver = max(ft, key=ft.get) if ft else None
    tot_ft = sum(ft.values()) or 1.0
    dmg = defaultdict(float)
    for h in rot.hits:
        dmg[h.char] += (h.gcsim_expected or 0.0) if getattr(h, "gcsim_expected", 0.0) else 0.0
    tot = sum(dmg.values()) or 1.0
    bursts = Counter(a.char for a in acts if a.action == "burst")
    cyc = None
    if bursts:
        top = bursts.most_common(1)[0][0]
        ts = [a.t for a in acts if a.char == top and a.action == "burst"]
        if len(ts) >= 2:
            cyc = statistics.median(b - a for a, b in zip(ts, ts[1:]))
    swaps = sum(1 for a0, a1 in zip(acts, acts[1:]) if a1.char != a0.char)
    rx = sum(1 for h in rot.hits if h.reaction or h.damage_type == "reaction" or getattr(h, "amp", "") or getattr(h, "cata", ""))
    return {
        "duration_s": round(dur, 1), "driver": driver,
        "driver_field_share": round(ft.get(driver, 0.0) / tot_ft, 3) if driver else None,
        "driver_damage_share": round(dmg.get(driver, 0.0) / tot, 3) if driver and dmg else None,
        "carry_attacks_pm": round(sum(1 for a in acts if a.char == driver and a.action in CARRY) * pm, 2),
        "damaging_actions_pm": round(sum(1 for a in acts if a.action in DAMAGING) * pm, 2),
        "support_casts_pm": round(sum(1 for a in acts if a.char != driver and a.action in ("skill", "burst")) * pm, 2),
        "support_field_s_pm": round((tot_ft - ft.get(driver, 0.0)) / tot_ft * 60.0, 2) if driver else None,
        "bursts_pm": round(sum(bursts.values()) * pm, 2),
        "skills_pm": round(sum(1 for a in acts if a.action == "skill") * pm, 2),
        "swaps_pm": round(swaps * pm, 2),
        # gcsim traces carry the idle gcsim logged (refused actions + waits); a generated rotation its own estimate
        "idle_s_pm": round((rot.idle_s if getattr(rot, "idle_s", None) is not None else _idle(rot)) * pm, 2),
        "reactions_pm": round(rx * pm, 2),
        "cycle_s": round(cyc, 2) if cyc else None,
        # support Skills beyond one per support per cycle (refreshes inside the driver's window)
        "support_recasts_pm": round(max(0.0, sum(1 for a in acts if a.char != driver and a.action == "skill") * pm
                                        - (len(ft) - 1) * (60.0 / cyc if cyc else 0.0)), 2) if driver else None,
        # average value of an action: team damage per damaging action (gcsim's own damage numbers)
        "damage_per_action": round(sum(dmg.values()) / max(1, sum(1 for a in acts if a.action in DAMAGING))),
    }


NUMERIC = ("driver_field_share", "driver_damage_share", "carry_attacks_pm", "damaging_actions_pm", "support_casts_pm",
           "support_field_s_pm", "bursts_pm", "skills_pm", "swaps_pm", "idle_s_pm", "reactions_pm", "cycle_s",
           "support_recasts_pm", "damage_per_action")


def delta(gen: dict, ref: dict) -> dict:
    out = {k: round(gen[k] - ref[k], 3) for k in NUMERIC if gen.get(k) is not None and ref.get(k) is not None}
    out["driver_match"] = gen.get("driver") == ref.get("driver")
    return out


def aggregate(rows: list[dict]) -> dict:
    """Mean and median of each structural delta (generated minus reference) over teams, plus driver agreement."""
    out = {}
    for k in NUMERIC:
        v = [r["delta"][k] for r in rows if k in (r.get("delta") or {})]
        if v:
            out[k] = {"mean": round(statistics.mean(v), 3), "median": round(statistics.median(v), 3),
                      "share_negative": round(sum(1 for x in v if x < 0) / len(v), 2), "n": len(v)}
    m = [r["delta"]["driver_match"] for r in rows if r.get("delta")]
    out["driver_match_rate"] = round(sum(m) / len(m), 2) if m else None
    return out
