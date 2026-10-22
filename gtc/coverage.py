"""Mechanics coverage: a temporary confidence guard (model 5.3.1).

The pair model's sd is measured on held-out lineups, so a prediction one member from simulated data looks
statistically tight. But a support's value often hinges on a conditional mechanic (Escoffier's Cryo and Hydro
RES shred, Citlali's Pyro and Hydro shred, an element-specific damage bonus), and the pair model only knows how a
member works with a particular damage dealer when that pair has its own fitted effect. Without one, the member's
average effect from other teams stands in, and a tight sd says nothing about whether the mechanic applies here.

For each evaluated lineup:
  complete  exact community simulations of this lineup (they include every mechanic), or every important
            mechanic of every member has a fitted pair effect with the team's damage dealers
  partial   some member's important mechanic has no fitted pair effect with a damage dealer of this team, or the
            pair was never simulated alongside an element this lineup adds (Chevreuse's buff needs an all Pyro and
            Electro party: her pair with Lyney, learned in Overloaded teams, says nothing about a team with Citlali)
  unknown   no mechanics data, no structure, or the role-rules route

Recommendation confidence = min(statistical confidence, cap for the coverage); caps in knowledge/model.yaml
(`coverage`). This is a stopgap until phases 6 (capabilities and reaction facts), 10 (uncertainty), 11 and 12
replace it, and it changes no value, plan or ranking: only the confidence shown.
"""
from __future__ import annotations

from gtc import params

COMPLETE, PARTIAL, UNKNOWN = "complete", "partial", "unknown"
ORDER = {COMPLETE: 0, PARTIAL: 1, UNKNOWN: 2}
MIN_SHARE = params.get("coverage.min_mechanic_share")  # a buff kind matters at this mean share of team damage
CAPS = params.get("coverage.confidence_cap")  # {partial: x, unknown: y}
DEALER_SHARE = params.get("coverage.dealer_share")  # without measured owners, members dealing this share are dealers

_MECH: dict[str, dict[str, float]] | None = None


def mechanics() -> dict[str, dict[str, float]]:
    """Each character's important team mechanics: the buff kinds in their measured capability profile
    (capabilities.Capability.buff_effects) worth at least MIN_SHARE of team damage on average."""
    global _MECH
    if _MECH is None:
        from gtc.capabilities import load as load_caps

        _MECH = {m: {k: v for k, v in c.buff_effects.items() if v >= MIN_SHARE}
                 for m, c in (load_caps() or {}).items() if c.n}
    return _MECH


_CTX: dict[frozenset, set[str]] | None = None


_ELEMENTS: dict[str, str] | None = None


def _element(name: str) -> str:
    global _ELEMENTS
    if _ELEMENTS is None:
        from gtc import gamedata

        _ELEMENTS = {k: v.get("element", "?") for k, v in gamedata.load_characters().items()}
    return name[10:-1] if name.startswith("Traveler (") else _ELEMENTS.get(name, "?")


def pair_contexts() -> dict[frozenset, set[str]]:
    """For every pair simulated together: the elements of the other members across those standard lineups."""
    global _CTX
    if _CTX is None:
        from itertools import combinations

        from gtc.sources import gcsim_db

        _CTX = {}
        for names in gcsim_db.lineup_values():
            if len(names) != 4:
                continue
            for a, b in combinations(sorted(names), 2):
                _CTX.setdefault(frozenset((a, b)), set()).update(_element(x) for x in names - {a, b})
    return _CTX


def dealers(lineup, structure: dict | None) -> list[str]:
    """Who the team's damage comes from: measured or predicted owners, else members whose average damage share
    is at least DEALER_SHARE."""
    if structure and structure.get("owners"):
        return list(structure["owners"])
    from gtc.capabilities import load as load_caps

    caps = load_caps() or {}
    return [m for m in lineup if m in caps and caps[m].damage_share >= DEALER_SHARE]


def lineup_coverage(lineup, basis, structure: dict | None) -> tuple[str, list[str]]:
    """(status, uncovered mechanics as readable strings)."""
    if basis is None or basis.route == "exact_community":
        return (COMPLETE, []) if basis is not None else (UNKNOWN, ["no evaluation"])
    if basis.route != "pair_model":
        return UNKNOWN, [f"{basis.route} route"]
    from gtc.pairmodel import load

    pm, mech = load(), mechanics()
    targets = dealers(lineup, structure)
    if pm is None or not targets:
        return UNKNOWN, ["no damage dealer identified"]
    missing = []
    ctx = pair_contexts()
    for m in sorted(lineup):
        if m not in mech:
            return UNKNOWN, [f"no mechanics data for {m}"]
        kinds = sorted(mech[m], key=lambda k: -mech[m][k])
        if not kinds:
            continue
        for r in targets:
            if r == m:
                continue
            if pm.key(m, r) not in pm.pairs:
                missing.append(f"{m}'s {', '.join(kinds[:2])} on {r}")
                continue
            new = sorted({_element(x) for x in lineup if x not in (m, r)} - ctx.get(frozenset((m, r)), set()))
            if new:
                missing.append(f"{m} with {r} never simulated alongside a {'/'.join(new)} teammate")
    return (PARTIAL, missing) if missing else (COMPLETE, [])


def worst(statuses) -> str:
    statuses = list(statuses)
    return max(statuses, key=ORDER.get) if statuses else COMPLETE


def cap(confidence: float, status: str) -> float:
    return min(confidence, CAPS.get(status, 1.0))
