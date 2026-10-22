"""Causal swap analysis (phase K): replace one member and explain where the change comes from.

Both teams are theorycrafted from scratch (rotation, builds, reactions, energy, field time): nothing is a generic
synergy score. The delta is then split into its causes, in DPS:

    personal      the outgoing member's own damage lost, the incoming member's own damage gained
    buffs         each effect's contribution (team damage lost when that effect alone is removed) for the effects
                  the outgoing member provided (lost) and the incoming member provides (gained)
    reactions     the change in reaction damage per reaction kind
    carry         the change in the carry's own damage (it moves with buffs, reactions, field time)
    rotation      cycle length, the carry's field share, energy status per member
    system        aura uptime per element; Furina's average Fanfare when she is in either team
    other         what the listed parts do not explain (overlaps between buffs, rotation shape)

Contributions overlap (two buffs on the same hit are not additive), so the parts are explanations, not an exact
accounting; `other` carries the difference.
"""
from __future__ import annotations


def _side(team: list[str], profile: str) -> dict:
    from gtc.forward.blind import theorycraft
    from gtc.forward.model import contributions

    r = theorycraft(team, profile=profile)
    builds = r.get("builds") or r.get("used_builds")
    ev = r["evaluation"]
    _, contrib = contributions(r["rotation"], builds, info={"energy": ev.energy, "er_added": {}})
    r["contrib"] = contrib
    r["builds_used"] = builds
    return r


def _fanfare(r) -> float | None:
    from gtc.forward.effects import build_timeline, fanfare_curve

    rot = r["rotation"]
    if "Furina" not in rot.lineup:
        return None
    curve = fanfare_curve(rot, r["builds_used"], build_timeline(rot, r["builds_used"]))
    if not curve:
        return None
    # time-weighted average over the rotation
    tot, last_t, last_v = 0.0, 0.0, 0.0
    for t, v, _ in curve:
        tot += last_v * (t - last_t)
        last_t, last_v = t, v
    tot += last_v * (rot.duration - last_t)
    return tot / rot.duration


def swap(team: list[str], out: str, incoming: str, profile: str = "standard", carry: str | None = None) -> dict:
    from gtc.forward.generator import roles

    new = [incoming if m == out else m for m in team]
    a, b = _side(team, profile), _side(new, profile)
    ea, eb = a["evaluation"], b["evaluation"]
    carry = carry or roles(team)[0]
    da, db = ea.dps, eb.dps
    delta = db - da
    parts: list[tuple[str, float]] = []
    pa = ea.per_character.get(out, 0.0) / ea.rotation_duration
    pb = eb.per_character.get(incoming, 0.0) / eb.rotation_duration
    parts.append((f"{out} personal damage (lost)", -pa))
    parts.append((f"{incoming} personal damage (gained)", pb))
    lost = {k: v * da for k, v in a["contrib"].items() if k.startswith(f"{out}:") and v > 0.002}
    gained = {k: v * db for k, v in b["contrib"].items() if k.startswith(f"{incoming}:") and v > 0.002}
    for k, v in sorted(lost.items(), key=lambda kv: -kv[1]):
        parts.append((f"{k} (lost)", -v))
    for k, v in sorted(gained.items(), key=lambda kv: -kv[1]):
        parts.append((f"{k} (gained)", v))
    rx = {}
    for k in set(ea.per_reaction) | set(eb.per_reaction):
        d = eb.per_reaction.get(k, 0.0) / eb.rotation_duration - ea.per_reaction.get(k, 0.0) / ea.rotation_duration
        if abs(d) > 0.005 * max(da, 1.0):
            rx[k] = d
    explained = sum(v for _, v in parts)
    carry_change = eb.per_character.get(carry, 0.0) / eb.rotation_duration - ea.per_character.get(carry, 0.0) / ea.rotation_duration
    auras_a = ((a["rotation"].reactions or {}).get("_detail") or {}).get("aura_uptime", {}) if getattr(a["rotation"], "reactions", None) else {}
    auras_b = ((b["rotation"].reactions or {}).get("_detail") or {}).get("aura_uptime", {}) if getattr(b["rotation"], "reactions", None) else {}
    system = {}
    for el in sorted(set(auras_a) | set(auras_b)):
        x, y = auras_a.get(el, 0.0), auras_b.get(el, 0.0)
        if abs(x - y) > 0.03:
            system[f"{el} aura uptime"] = (round(x, 2), round(y, 2))
    fa, fb = _fanfare(a), _fanfare(b)
    if fa is not None or fb is not None:
        system["Furina average Fanfare"] = (None if fa is None else round(fa), None if fb is None else round(fb))
    rot = {"cycle_s": (round(a["rotation"].duration, 1), round(b["rotation"].duration, 1)),
           "carry_field_share": (a["realisation"]["field_share"].get(carry), b["realisation"]["field_share"].get(carry)),
           "energy": {m: (ea.energy.get(m, {}).get("status"), eb.energy.get(m, {}).get("status"))
                      for m in set(ea.energy) | set(eb.energy)}}
    lines = [f"Before: {da:,.0f} DPS   After: {db:,.0f} DPS   Delta: {delta:+,.0f} ({delta / da:+.1%})"]
    for k, v in sorted(parts, key=lambda kv: -abs(kv[1])):
        if abs(v) >= 0.003 * da:
            lines.append(f"  {v:+,.0f}  {k}")
    for k, v in sorted(rx.items(), key=lambda kv: -abs(kv[1])):
        lines.append(f"  {v:+,.0f}  {k} reaction damage")
    lines.append(f"  {carry_change:+,.0f}  {carry}'s own damage (moves with the buffs and reactions above)")
    for k, (x, y) in system.items():
        lines.append(f"  {k}: {x} -> {y}")
    lines.append(f"  rotation {rot['cycle_s'][0]} s -> {rot['cycle_s'][1]} s; {carry} field share "
                 f"{rot['carry_field_share'][0]} -> {rot['carry_field_share'][1]}")
    bad = [f"{m}: {x} -> {y}" for m, (x, y) in rot["energy"].items() if x != y]
    if bad:
        lines.append("  energy " + "; ".join(bad))
    lines.append(f"  {delta - explained:+,.0f}  other (overlap between effects, rotation shape)")
    lines.append(f"Net: {delta / da:+.1%}")
    return {"before": round(da), "after": round(db), "delta": round(delta), "change": round(delta / da, 4),
            "parts": [(k, round(v)) for k, v in parts], "reactions": {k: round(v) for k, v in rx.items()},
            "carry_change": round(carry_change), "system": system, "rotation": rot,
            "other": round(delta - explained), "lines": lines,
            "uncertainty": (ea.uncertainty, eb.uncertainty),
            "builds": {"before": a.get("build_report"), "after": b.get("build_report")}}
