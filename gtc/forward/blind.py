"""Blind theorycraft test (the project's success test): evaluate a team with NO access to its own simulations,
then reveal the reference.

    1. Action libraries for its members are measured from other teams only (`library.build(exclude=[team])`).
    2. The generator builds candidate rotations; the forward model scores them; the best is the engine's answer:
       rotation, DPS, damage shares, buff contributions, energy, field time, conditions.
    3. Only then the reference is computed: the team's community rotation run with the same house builds (gcsim mean
       and crit-averaged same-trace value), plus the community database DPS for context.
"""
from __future__ import annotations


def theorycraft(lineup: list[str], exclude: list | None = None, builds: dict | None = None,
                profile: str = "neutral") -> dict:
    """`profile`: "neutral" (Favonius, no sets, ER added on top: the calculator baseline) or "standard" (phase G:
    realistic gear chosen by the forward model for this team and rotation, ER paid from the substat budget)."""
    from gtc.forward.generator import best_rotation
    from gtc.forward.library import build

    from gtc.forward.generator import roles

    exclude = (exclude or []) + [lineup]
    from gtc.forward.generator import on_field_dealers

    carry, _ = roles(lineup)
    carries = set(on_field_dealers(lineup)) | {carry}
    libs = {m: build(m, exclude, role="carry" if m in carries else "support") for m in lineup}
    out = best_rotation(lineup, libs, builds)
    if profile == "standard" and builds is None:
        out = _standard(lineup, libs, out)
    out["libraries"] = {m: {"sources": [s.split(" ")[3] if len(s.split(" ")) > 3 else s for s in l.sources],
                            "notes": l.notes} for m, l in libs.items()}
    return out


def _standard(lineup: list[str], libs: dict, first: dict) -> dict:
    """Realistic builds (phase G): optimise gear on the neutral-best rotation, search plans again with those builds,
    re-optimise on the new best, and search once more. Returns best_rotation's result plus "builds" and
    "build_report"."""
    from gtc.forward import data as D
    from gtc.forward.energy import requirements
    from gtc.forward.generator import best_rotation
    from gtc.forward.standard import optimise
    from gtc.forward.trace import ER_BUFFER

    from gtc.forward.build import house_builds
    from gtc.forward.generator import _period, generate
    from gtc.forward.rotation import window_fit

    costs = {m: D.value(m, "burst", "Energy Cost") for m in lineup}
    ample = house_builds(lineup, {m: 3.0 for m in lineup})        # everyone on Favonius R1, energy never short
    from gtc.forward.standard import ER_CAP, describe, er_targets, refit, relax_er
    from gtc.forward.trace import _burst_times, _late_bursts

    from gtc.forward.generator import on_field_dealers, roles as _roles
    from gtc.forward.standard import cached_choice, remember

    carry, _ = _roles(lineup)
    role = {m: ("carry" if m in set(on_field_dealers(lineup)) | {carry} else "support") for m in lineup}
    warm = {m: cached_choice(m, role[m]) for m in lineup}
    choices = {m: c for m, c in warm.items() if c is not None} or None
    out = first
    for passes in ((1, 1) if choices and len(choices) == len(lineup) else (2, 1)):
        plan = out["plan"]
        period = _period(plan, libs, window_fit(lineup)["period"])
        rot = generate(lineup, libs, ample, plan, period)
        builds, report = optimise(lineup, rot, None, choices, passes=passes, costs=costs)
        # Energy is a choice made on value: generate the plan with these builds; raise the ER of whoever's Bursts slip
        # only when the team gains from it, and try relaxing each member's ER (damage stats instead, a later Burst):
        # +20% ER can lower paper damage yet raise team DPS by enabling a Burst, or the reverse
        from gtc.forward.model import evaluate as _ev

        def plan_dps(bs):
            return _ev(generate(lineup, libs, bs, plan, period), bs).dps

        targets = er_targets(rot, builds, costs)
        shape = _burst_times(rot)
        cur = plan_dps(builds)
        for _ in range(8):
            late = _late_bursts(shape, _burst_times(generate(lineup, libs, builds, plan, period)))
            if not late:
                break
            raised = dict(targets)
            for n in late:
                raised[n] = min(ER_CAP, max(targets.get(n) or 0.0, builds[n].total("er")) + 0.2)
            cand = refit(builds, raised)
            d = plan_dps(cand)
            if d <= cur:
                break
            builds, targets, cur = cand, raised, d
            for n in late:
                report[n] = {**report.get(n, {}), "er": round(builds[n].total("er"), 3), "er_raised_for_shape": True}
        for n in sorted(lineup, key=lambda x: -builds[x].total("er")):
            relaxed = relax_er(n, builds[n])
            if relaxed is None:
                continue
            cand = {**builds, n: relaxed}
            d = plan_dps(cand)
            if d > cur:
                builds, cur = cand, d
                targets[n] = None
                report[n] = {**report.get(n, {}), **describe(relaxed), "er_relaxed": True}
        choices = {m: b.choice for m, b in builds.items()}
        out = best_rotation(lineup, libs, builds)
    out["builds"], out["build_report"] = builds, report
    remember(builds, role)
    return out


def reveal(lineup: list[str]) -> dict | None:
    from gtc.forward.trace import house_trace
    from gtc.synergy import table

    tr = house_trace(lineup)
    community = (table().by_lineup.get(frozenset(lineup)) or {}).get("dps")
    if tr is None:
        return {"gcsim_mean": None, "community_dps": community}
    rot, info = tr
    gc = info.get("gcsim_char_dps") or {}
    tot = sum(gc.values()) or 1.0
    return {"gcsim_mean": info.get("gcsim_dps"), "gcsim_same_trace": sum(h.gcsim_expected for h in rot.hits) / rot.duration,
            "gcsim_shares": {k: v / tot for k, v in gc.items()}, "community_dps": community,
            "reference_rotation_s": rot.duration, "config": info.get("config")}
