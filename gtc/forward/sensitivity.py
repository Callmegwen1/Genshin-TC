"""One-variable-at-a-time sensitivity sweeps (development diagnostics).

For a team, its selected generated rotation is held fixed and one input moves over a range; the forward model's
response is recorded as a curve. Each sweep declares the expected direction:
    up      the output should not fall as the input rises (stats, talent level, buff amount and duration)
    down    the output should not rise (enemy RES, slower rotation, Burst cost on energy requirement)
    any     informational only
Anomalies flagged per curve:
    reversed       a step against the expected direction (beyond rounding)
    discontinuity  one step larger than 4x the median step and 5% of the base (a jump where the input moved smoothly)
    flat           no response at all over the sweep where the input is relevant to that member's damage
    absurd         a relative change more than 3x the relative change of the input for a linear stat (ATK% etc.)
Writes data/validation/sensitivity.json.
"""
from __future__ import annotations

import json
import statistics
from dataclasses import replace

from gtc import ROOT

OUT = ROOT / "data" / "validation" / "sensitivity.json"


def _setup(team: list[str]):
    from gtc.forward.blind import theorycraft
    from gtc.forward.generator import _period, on_field_dealers, roles
    from gtc.forward.library import build
    from gtc.forward.rotation import window_fit

    r = theorycraft(team)
    builds = r["used_builds"]
    carry, _ = roles(team)
    carries = set(on_field_dealers(team)) | {carry}
    libs = {m: build(m, [team], role="carry" if m in carries else "support") for m in team}
    plan = r["plan"]
    period = _period(plan, libs, window_fit(team)["period"])
    return r, builds, libs, plan, period


def _anomalies(xs, ys, expect, relevant=True, linear_rel=None):
    out = []
    steps = [b - a for a, b in zip(ys, ys[1:])]
    base = abs(ys[0]) or 1.0
    if expect in ("up", "down"):
        bad = [i for i, s in enumerate(steps) if (s < -1e-6 * base if expect == "up" else s > 1e-6 * base)]
        if bad:
            out.append({"kind": "reversed", "at": [xs[i + 1] for i in bad]})
    mags = [abs(s) for s in steps if abs(s) > 0]
    if len(mags) >= 3:
        med = statistics.median(mags)
        jumps = [i for i, s in enumerate(steps) if abs(s) > 4 * med and abs(s) > 0.05 * base]
        if jumps:
            out.append({"kind": "discontinuity", "at": [xs[i + 1] for i in jumps]})
    if relevant and max(ys) - min(ys) <= 1e-9 * base:
        out.append({"kind": "flat"})
    if linear_rel is not None and ys[0]:
        rel_in = linear_rel
        rel_out = abs(ys[-1] / ys[0] - 1)
        if rel_out > 3 * rel_in:
            out.append({"kind": "absurd", "input_change": round(rel_in, 3), "output_change": round(rel_out, 3)})
    return out


def sweep_team(team: list[str]) -> dict:
    from gtc.forward.build import scaling_stat
    from gtc.forward.energy import requirements
    from gtc.forward.generator import generate
    from gtc.forward.model import evaluate
    import gtc.forward.model as M

    r, builds, libs, plan, period = _setup(team)
    rot = r["rotation"]
    base_ev = evaluate(rot, builds)
    curves = []

    def stat_sweep(member, key, values, expect, relevant=True, linear=False):
        ys = []
        for v in values:
            b = dict(builds)
            b[member] = replace(builds[member], stats={**builds[member].stats, key: builds[member].stats.get(key, 0.0) + v})
            ys.append(evaluate(rot, b).dps)
        rel_in = None
        if linear:
            tot0 = builds[member].total(key.replace("_pct", "")) if key.endswith("_pct") else None
            if tot0:
                base_stat = builds[member].stats.get(f"base_{key.replace('_pct', '')}", 0.0)
                rel_in = base_stat * values[-1] / tot0
        curves.append({"variable": f"{member}:{key}", "x": values, "dps": [round(y) for y in ys], "expect": expect,
                       "anomalies": _anomalies(values, ys, expect, relevant, rel_in)})

    share = base_ev.damage_share
    for m in team:
        own = share.get(m, 0.0) > 0.05
        sc = {"atk": "atk_pct", "hp": "hp_pct", "def": "def_pct", "em": "em"}[scaling_stat(m)]
        stat_sweep(m, "cr", [0.0, 0.05, 0.1, 0.15, 0.2, 0.25], "up", relevant=own)
        stat_sweep(m, "cd", [0.0, 0.1, 0.2, 0.3, 0.4], "up", relevant=own)
        if sc != "em":
            stat_sweep(m, sc, [0.0, 0.1, 0.2, 0.3, 0.4], "up", relevant=own, linear=True)
        stat_sweep(m, "em", [0, 50, 100, 150, 200], "up", relevant=False)
        stat_sweep(m, "er", [0.0, 0.2, 0.4, 0.6], "any", relevant=False)
    # enemy RES (all elements)
    ys, xs = [], [-0.2, -0.1, 0.0, 0.1, 0.2, 0.3]
    orig = M.ENEMY_RES
    try:
        for d in xs:
            M.ENEMY_RES = orig + d
            ys.append(evaluate(rot, builds).dps)
    finally:
        M.ENEMY_RES = orig
    curves.append({"variable": "enemy RES", "x": xs, "dps": [round(y) for y in ys], "expect": "down",
                   "anomalies": _anomalies(xs, ys, "down")})
    # talent level of the main dealer (regenerating the same plan)
    main = max(share, key=share.get)
    xs, ys = [6, 7, 8, 9, 10], []
    from gtc.forward.build import house_builds

    ample = house_builds(team, {m: 3.0 for m in team})     # the neutral profile schedules with ample energy
    for lv in xs:
        b, a = dict(builds), dict(ample)
        b[main] = replace(builds[main], talents={k: lv for k in builds[main].talents})
        a[main] = replace(ample[main], talents={k: lv for k in ample[main].talents})
        ys.append(evaluate(generate(team, libs, a, plan, period), b).dps)
    curves.append({"variable": f"{main}:talent level", "x": xs, "dps": [round(y) for y in ys], "expect": "up",
                   "anomalies": _anomalies(xs, ys, "up")})
    # rotation duration (the same actions, slower)
    from gtc.forward.trace import Rotation

    xs, ys = [1.0, 1.05, 1.1, 1.2, 1.3], []
    for s in xs:
        hits = [replace(h, t=h.t * s, action_t=(h.action_t * s if h.action_t is not None else None)) for h in rot.hits]
        acts = [replace(a, t=a.t * s, end=a.end * s) for a in rot.actions]
        r2 = Rotation(rot.lineup, acts, hits, rot.duration * s, rot.energy, [(a * s, b * s, w) for a, b, w in rot.segments],
                      rot.source, list(rot.notes), dict(rot.timeline or {}), dict(rot.reactions or {}),
                      [(t * s, i) for t, i in rot.cycles])
        ys.append(evaluate(r2, builds).dps)
    curves.append({"variable": "rotation time stretch", "x": xs, "dps": [round(y) for y in ys], "expect": "down",
                   "anomalies": _anomalies(xs, ys, "down")})
    # buff amount and duration (each active timed buff, one at a time: amount x0..x2, duration via instance end)
    from gtc.forward.effects import build_timeline

    tl = [e for e in build_timeline(rot, builds) if e.active and e.kind in ("atk_pct", "dmg_bonus", "elemental_dmg_bonus",
                                                                              "crit_rate", "crit_dmg", "atk", "em")]
    for e in tl[:6]:
        xs, ys = [0.0, 0.5, 1.0, 1.5, 2.0], []
        for f in xs:
            ys.append(_with_scaled(rot, builds, e.id, amount=f).dps)
        curves.append({"variable": f"buff amount {e.caster}: {e.source[:30]}", "x": xs, "dps": [round(y) for y in ys],
                       "expect": "up", "anomalies": _anomalies(xs, ys, "up", relevant=False)})
        xs, ys = [0.25, 0.5, 0.75, 1.0], []
        for f in xs:
            ys.append(_with_scaled(rot, builds, e.id, duration=f).dps)
        curves.append({"variable": f"buff duration {e.caster}: {e.source[:30]}", "x": xs, "dps": [round(y) for y in ys],
                       "expect": "up", "anomalies": _anomalies(xs, ys, "up", relevant=False)})
    # Burst cost -> required ER of each member
    from gtc.forward import data as D

    for m in team:
        c0 = D.value(m, "burst", "Energy Cost") or 60
        xs = [c0 - 20, c0 - 10, c0, c0 + 10, c0 + 20]
        ys = [(requirements(rot, {m: c}).get(m) or {}).get("required_er") or 0.0 for c in xs]
        curves.append({"variable": f"{m}: Burst cost -> required ER", "x": xs, "dps": ys, "expect": "up",
                       "anomalies": _anomalies(xs, ys, "up", relevant=False)})
    return {"team": team, "base_dps": round(base_ev.dps), "curves": curves,
            "anomalies": [(c["variable"], a) for c in curves for a in c["anomalies"]]}


def _with_scaled(rot, builds, effect_id, amount: float = 1.0, duration: float = 1.0):
    """Evaluate with one effect's amount scaled, or its instances shortened (duration fraction)."""
    import gtc.forward.effects as E
    from gtc.forward.model import evaluate

    orig = E.build_timeline

    def patched(r, b):
        tl = orig(r, b)
        for e in tl:
            if e.id == effect_id:
                if e.amount is not None:
                    e.amount *= amount
                for i in e.instances:
                    i.end = i.start + (i.end - i.start) * duration
        return tl

    import gtc.forward.model as M

    M.build_timeline = patched
    try:
        return evaluate(rot, builds)
    finally:
        M.build_timeline = orig


def run(teams: list | None = None) -> dict:
    from gtc.forward.reference import REFERENCE

    out = []
    for e in teams or REFERENCE:
        try:
            out.append({"family": e["family"], **sweep_team(e["team"])})
        except Exception as ex:   # noqa: BLE001
            out.append({"family": e["family"], "team": e["team"], "error": f"{type(ex).__name__}: {ex}"})
    summary = {"teams": len(out), "curves": sum(len(x.get("curves", [])) for x in out),
               "anomalies": sum(len(x.get("anomalies", [])) for x in out)}
    res = {"summary": summary, "teams": out}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    return res
