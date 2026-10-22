"""Energy feasibility (FM-7): can this rotation fund the Bursts it casts?

For each character over a rotation: Bursts cast (B), Burst cost (C), particle and orb energy received before Energy
Recharge (P, the game's amounts: same element 3 / neutral 2 / off-element 1 per particle, x0.6 off field in a
four-member party; Favonius particles included), and flat energy that ignores ER (F). Everyone starts with full
energy, so the first Burst is free:

    required ER = ((B - 1) x C - F) / P

    sustainable    ER >= required
    marginal       ER >= 0.9 x required (a slightly late Burst, or a few more particles, closes it)
    unsustainable  below that: the rotation cannot repeat as written; a Burst comes late or not at all
    unknown        no Burst in the rotation, or no particles measured

The particle schedule comes from the rotation (the trace's energy events, run with ample ER so nothing stalls).
"""
from __future__ import annotations

from collections import defaultdict


def requirements(rot, burst_cost: dict[str, float]) -> dict[str, dict]:
    bursts: dict[str, list[float]] = defaultdict(list)
    for a in rot.actions:
        if a.action == "burst":
            bursts[a.char].append(a.t)
    out = {}
    for who in rot.lineup:
        times = bursts.get(who, [])
        cost = burst_cost.get(who)
        if not times or not cost:
            out[who] = {"bursts": len(times), "required_er": None, "status": "unknown",
                        "why": "no Burst in the rotation" if not times else "Burst cost unknown"}
            continue
        last = times[-1]
        p = sum(e["amount"] / max(e.get("er") or 1.0, 1e-6) for e in rot.energy
                if e["char"] == who and e["kind"] == "particle" and e["t"] <= last)
        f = sum(e["amount"] for e in rot.energy if e["char"] == who and e["kind"] == "flat" and e["t"] <= last)
        need = (len(times) - 1) * cost - f
        if need <= 0:
            req = 1.0
        elif p <= 0:
            out[who] = {"bursts": len(times), "required_er": None, "status": "unknown", "why": "no particles measured"}
            continue
        else:
            req = need / p
        out[who] = {"bursts": len(times), "cost": cost, "particles": round(p, 1), "flat": round(f, 1),
                    "required_er": round(max(req, 1.0), 3)}
    return out


def status(required: float | None, er: float) -> str:
    if required is None:
        return "unknown"
    if er >= required:
        return "sustainable"
    if er >= 0.9 * required:
        return "marginal"
    return "unsustainable"
