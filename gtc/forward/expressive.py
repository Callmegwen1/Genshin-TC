"""Strategy expressiveness (development diagnostics): can the generic strategy language represent a reference
rotation at all? The reference is never an input to the search; it is only projected onto the language here.

project(reference trace) -> Plan: the reference's driver, support order, cycle length, Burst cadence, carry opening,
refresh timing, support policy, state protection, quickswap, and the driver's attack string, written in the same
vocabulary the search uses. The projected plan is generated and played in gcsim:
    EXPRESSIBLE              the projection reaches >= 95% of the reference's gcsim DPS
    PARTIALLY_EXPRESSIBLE    85-95%
    NOT_EXPRESSIBLE          below 85%
Missing capabilities are read from where the projection still differs structurally from the reference (support
recasts, attack strings, swaps, Burst cadence, cycle length, idle), as generic capability names.
"""
from __future__ import annotations

import statistics
from collections import Counter

EXPRESSIBLE, PARTIAL = 0.95, 0.85


def _cycles(acts) -> tuple[str | None, list[int]]:
    """The reference's cycle marks: the Burst casts of the member who casts the most Bursts."""
    b = Counter(a.char for a in acts if a.action == "burst")
    if not b:
        return None, []
    top = b.most_common(1)[0][0]
    return top, [i for i, a in enumerate(acts) if a.char == top and a.action == "burst"]


def project(ref, lineup: list[str], libs: dict):
    """The reference rotation written in the strategy language (a Plan)."""
    from gtc.forward.generator import Plan, _has_swap_state

    acts = [a for a in ref.actions if a.action]
    ft = ref.field_time()
    tot = sum(ft.values()) or 1.0
    driver = max(ft, key=ft.get)
    top, marks = _cycles(acts)
    period = statistics.median(acts[j].t - acts[i].t for i, j in zip(marks, marks[1:])) if len(marks) >= 2 else 0.0
    i0, i1 = (marks[1], marks[2]) if len(marks) >= 3 else (0, len(acts))
    cyc = acts[i0:i1]
    n_cycles = max(1, len(marks) - 1)
    bursts = []
    for m in lineup:
        nb = sum(1 for a in acts if a.char == m and a.action == "burst")
        per = nb / n_cycles
        every = 1 if per >= 0.75 else 2 if per >= 0.35 else 0
        if every != 1:
            bursts.append((m, every))
    if ft.get(driver, 0.0) / tot < 0.40:
        order = []
        for a in cyc:
            if a.char not in order:
                order.append(a.char)
        order += [m for m in lineup if m not in order]
        return Plan(tuple(order), "skill", "", ("attack", "attack"), (), period=round(period, 2), bursts=tuple(bursts),
                    family="quickswap")
    sup = []
    for a in cyc:
        if a.char != driver and a.char not in sup:
            sup.append(a.char)
    sup += [m for m in lineup if m != driver and m not in sup]
    own = [a.action for a in cyc if a.char == driver]
    first = next((x for x in own if x in ("skill", "burst")), "skill")
    if not any(a.char == driver and a.action == "burst" for a in acts):
        first = "skill_only"
    # refresh: support actions after the driver's Burst inside the cycle, or in the middle of the driver's window
    di = [k for k, a in enumerate(cyc) if a.char == driver]
    refresh = ""
    if di:
        inside = [a for a in cyc[di[0]: di[-1] + 1] if a.char != driver and a.action in ("skill", "burst")]
        if inside:
            bi = next((k for k in di if cyc[k].action == "burst"), None)
            refresh = "after_burst" if bi is not None and any(k > bi for k in range(di[0], di[-1] + 1)
                                                               if cyc[k].char != driver) else "mid"
    skills = Counter(a.char for a in cyc if a.char != driver and a.action == "skill")
    policy = "recast" if skills and max(skills.values()) >= 2 else "wait"
    # the driver's attack string: the longest run of plain actions between their specials
    runs, cur = [], []
    for a in cyc:
        if a.char == driver and a.action not in ("skill", "burst"):
            cur.append(a.action)
        else:
            if cur:
                runs.append(tuple(cur))
            cur = []
    if cur:
        runs.append(tuple(cur))
    filler = Counter(runs).most_common(1)[0][0][:12] if runs else ()
    return Plan(tuple(sup), first, refresh, filler, (driver,), period=round(period, 2), bursts=tuple(bursts),
                support_policy=policy, protect_state=_has_swap_state(libs.get(driver)))


CAPABILITY = {  # structural metric where the projection still differs -> the generic capability it points to
    "support_casts_pm": "support recast pattern (who recasts, how often, when)",
    "carry_attacks_pm": "attack-string repetition / length",
    "swaps_pm": "mid-window swaps",
    "bursts_pm": "Burst cadence (delayed / skipped / alternating Bursts)",
    "cycle_s": "cycle length",
    "idle_s_pm": "waiting avoided by the reference (event-driven timing)",
    "driver_field_share": "field-time allocation",
}


def assess(team: list[str], ref, ref_dps: float, builds: dict, libs: dict) -> dict:
    """Project the reference, play the projection in gcsim, and classify the language's expressiveness."""
    from gtc.forward import structure as ST
    from gtc.forward.decompose import _label, run_generated
    from gtc.forward.generator import _period, _run_plan
    from gtc.forward import data as D
    from gtc.forward.rotation import window_fit

    from dataclasses import replace

    plan = project(ref, team, libs)
    base = window_fit(team)["period"]
    costs = {m: D.value(m, "burst", "Energy Cost") for m in team}
    # the projection gets the Energy Recharge its own rotation needs (as the reference has for its own), not the
    # builds tuned for another plan. What the trace cannot say for certain (how supports are called in, whether the
    # driver's state is protected) is tried both ways; the encoding the forward model scores best is played
    variants = [plan] if plan.family == "quickswap" else [
        replace(plan, support_policy=pol, protect_state=prot)
        for pol in ("wait", "defer", "recast", "event") for prot in (False, True)]
    runs = [_run_plan(team, libs, None, v, _period(v, libs, base), costs) for v in variants]
    r = max(runs, key=lambda x: x[0])
    plan = r[1]
    g = run_generated(r[2], r[4])
    dps = g.get("gcsim_steady") or g.get("gcsim_dps") or 0.0
    ratio = dps / ref_dps if ref_dps else None
    verdict = ("EXPRESSIBLE" if ratio is not None and ratio >= EXPRESSIBLE else
               "PARTIALLY_EXPRESSIBLE" if ratio is not None and ratio >= PARTIAL else "NOT_EXPRESSIBLE")
    missing = []
    if g.get("trace") is not None:
        d = ST.delta(ST.profile(g["trace"]), ST.profile(ref))
        rp = ST.profile(ref)
        for k, cap in CAPABILITY.items():
            v, base_v = d.get(k), rp.get(k)
            if v is None or base_v in (None, 0):
                continue
            if abs(v) / abs(base_v) > 0.2:
                missing.append(f"{cap}: {k} {v:+.2f}")
    return {"plan": _label(plan), "family": plan.family, "projection_gcsim": round(dps),
            "projection_forward": round(r[0]), "ratio": round(ratio, 3) if ratio else None, "verdict": verdict,
            "missing": missing}
