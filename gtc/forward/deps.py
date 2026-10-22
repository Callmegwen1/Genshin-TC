"""Rotation brain v2 (phase D): what must happen before the damage window, as a small action graph read from the kits,
and the realisation metrics a rotation is judged by besides DPS.

Graph nodes are the supports' setups and the carry window. Edges come from mechanics, not from names:
    hard   stack builders before their consumer: a kit rule that gains a resource from teammates' actions
           (Raiden's Resolve from other Bursts) puts those teammates before the consumer's window
    soft   aura appliers before a support whose buff needs a swirled element (Kazuha, Sucrose); supports whose buffs
           are short go last (closest to the window); a Burst that needs teammates' state (Furina's Fanfare needs HP
           changes) after the actions that create it
Orderings that break a hard edge are pruned; soft edges are reported with the chosen rotation.

Metrics (`realisation`): buff coverage of the carry's damage per major buff, the carry's field time in its windows,
state realisation (share of a state spent on field), idle time, energy status per member.
"""
from __future__ import annotations


def graph(lineup: list[str], carries: tuple, libs: dict) -> dict:
    from gtc.forward.effects import annotations
    from gtc.kits import kit

    hard, soft = [], []
    supports = [m for m in lineup if m not in carries]
    for c in carries:
        for rule in (libs.get(c).rules if libs.get(c) else []) or []:
            on = rule.get("on") or {}
            if on.get("event") == "action" and on.get("by") in ("party_others", "party"):
                for s in supports:
                    hard.append((s, c, f"{c} gains {rule['do'][0].get('gain', {}).get('resource', 'a resource')} from {s}'s {on.get('action')}"))
    appliers = {m for m in lineup for a in ((kit(m) or {}).get("behavior", {}).get("application") or [])
                if a.get("element") in ("Pyro", "Hydro", "Electro", "Cryo")}
    for m in supports:
        for p in annotations().get(m) or []:
            if p.get("element_from") == "swirl":
                for a in appliers - {m}:
                    soft.append((a, m, f"{m}'s {p['match']} needs an element to swirl, which {a} applies"))
    return {"hard": hard, "soft": soft}


def respects(order: tuple, carries: tuple, g: dict) -> bool:
    seq = list(order) + list(carries)
    pos = {m: i for i, m in enumerate(seq)}
    return all(pos.get(a, -1) < pos.get(b, 99) for a, b, _ in g["hard"])


def realisation(rot, ev, carries: tuple) -> dict:
    """How well the rotation realises its kits, beside DPS."""
    carry = carries[0] if carries else None
    out = {}
    cev = [e for e in ev.events if e.char == carry and e.damage > 0]
    tot = sum(e.damage for e in cev) or 1.0
    cover = {}
    for e in cev:
        for b in set(e.buffs + e.debuffs):
            cover[b] = cover.get(b, 0.0) + e.damage
    out["buff_coverage_of_carry_damage"] = {k: round(v / tot, 2) for k, v in sorted(cover.items(), key=lambda kv: -kv[1])[:8]}
    ft = rot.field_time()
    out["field_share"] = {m: round(v / rot.duration, 2) for m, v in ft.items()}
    states = (getattr(rot, "timeline", None) or {}).get("states", [])
    real = {}
    for st in states:
        m, name, a, b = st[:4]
        nominal = st[4] if len(st) > 4 else b
        if nominal - a > 60:          # open-ended states (no duration) are not realisation questions
            continue
        # the share of the state's full duration the owner spends on field inside it: a state ended early by a swap
        # (Raiden's Musou Isshin left after one attack) counts its lost remainder
        on = sum(max(0.0, min(b, y) - max(a, x)) for x, y, w in rot.segments if w == m)
        real.setdefault(f"{m}:{name}", []).append(on / max(nominal - a, 1e-6))
    out["state_realisation"] = {k: round(sum(v) / len(v), 2) for k, v in real.items()}
    waited = next((n for n in rot.notes if n.startswith("waited")), "")
    out["idle"] = waited
    out["energy"] = {m: v.get("status") for m, v in (ev.energy or {}).items()}
    return out
