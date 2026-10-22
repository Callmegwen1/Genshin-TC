"""Typicality: how much a lineup resembles teams that have been simulated (phase 9).

Before phase 9, resemblance rules learned from simulated teams rejected compositions outright ("Hydro never appears
in simulated Mono Pyro teams", "two on-field characters", "Skirk always has Cryo and Hydro teammates"). Those rules
say a team is unusual, not that it cannot work, so validity no longer uses them. They become findings here, and
each finding widens the uncertainty of an estimate that extrapolates (pair model, role rules, provisional kit):
the farther a team is from what was simulated, the less the models' measured accuracy applies to it. A lineup
with its own community simulations is measured, so typicality never touches it.

Findings, all independent of any template (power must not depend on the template that generated a lineup):
  carry_needs        the primary actor's teammates lack an element present in 95% of their simulated teams
  unseen_element     a teammate element the primary actor has never been simulated with
  onfield_crowding   more predicted on-field characters than 98% of simulated teams have
  low_capacity       the members' average damage shares sum to less than 98% of simulated teams' (model 6.3): nobody
                     in the lineup usually deals much of a team's damage, so the pair model extrapolates outside the
                     lineups it was fitted on

The sd multiplier per finding is measured (`measure`): on simulated lineups, the held-out pair-model error of
lineups with findings against those without.
"""
from __future__ import annotations

from collections import defaultdict

from gtc import params

ONFIELD_PERCENTILE = params.get("typicality.onfield_percentile")
CAPACITY_PERCENTILE = params.get("typicality.capacity_percentile")
_CAPACITY_MIN: float | None = None

_SEEN: dict[str, set[str]] | None = None
_ONFIELD_MAX: int | None = None


def _element(name: str) -> str:
    from gtc.identity import _element_of

    return name[10:-1] if name.startswith("Traveler (") else _element_of().get(name, "?")


def seen_elements() -> dict[str, set[str]]:
    """Per character who owns their lineup's damage: every teammate element in their simulated lineups."""
    global _SEEN
    if _SEEN is None:
        from gtc.synergy import load_database

        _SEEN = defaultdict(set)
        for e in load_database().values():
            st = (e.get("profile") or {}).get("structure") or {}
            if st.get("type") in ("hypercarry", "dual_carry") and st.get("owners") and len(e.get("lineup", [])) == 4:
                c = st["owners"][0]
                _SEEN[c] |= {_element(m) for m in e["lineup"] if m != c}
    return _SEEN


def onfield_max() -> int:
    """On-field characters (by capability) in the 98th percentile of simulated lineups."""
    global _ONFIELD_MAX
    if _ONFIELD_MAX is None:
        from gtc.capabilities import load as load_caps, team_profile
        from gtc.synergy import load_database

        caps = load_caps()
        counts = sorted(team_profile(e["lineup"], caps)["onfield"] for e in load_database().values()
                        if e.get("profile") and len(e.get("lineup", [])) == 4)
        _ONFIELD_MAX = counts[min(len(counts) - 1, int(ONFIELD_PERCENTILE * len(counts)))] if counts else 2
    return _ONFIELD_MAX


def capacity_min() -> float:
    """Damage capacity of simulated lineups at CAPACITY_PERCENTILE (gtc/pairmodel.py: sum of average damage shares)."""
    global _CAPACITY_MIN
    if _CAPACITY_MIN is None:
        from gtc import pairmodel

        pm = pairmodel.load()
        caps = sorted(c for c in (pm.capacity(d[0]) for d in pairmodel.lineup_data()) if c is not None) if pm else []
        _CAPACITY_MIN = caps[int(CAPACITY_PERCENTILE * len(caps))] if caps else 0.0
    return _CAPACITY_MIN


def findings(lineup, primary: str | None) -> list[str]:
    """Readable typicality findings for a lineup and its primary actor."""
    from gtc.capabilities import load as load_caps, team_profile
    from gtc.validity import carry_rules

    out = []
    if primary:
        mates = {_element(m) for m in lineup if m != primary}
        need = (carry_rules().get(primary) or {}).get("teammate_elements") or []
        missing = [e for e in need if e not in mates]
        if missing:
            out.append(f"carry_needs: {primary} has a {' and '.join(missing)} teammate in 95% of their simulated teams")
        seen = seen_elements().get(primary)
        if seen:
            new = sorted(mates - seen)
            if new:
                out.append(f"unseen_element: {primary} was never simulated with a {'/'.join(new)} teammate")
    caps = load_caps()
    if caps and all(m in caps for m in lineup):
        n = team_profile(list(lineup), caps)["onfield"]
        if n > onfield_max():
            out.append(f"onfield_crowding: {n} on-field characters; 98% of simulated teams have at most {onfield_max()}")
    from gtc.pairmodel import load as load_pairs

    pm = load_pairs()
    cap = pm.capacity(lineup) if pm is not None else None
    if cap is not None and cap < capacity_min():
        out.append(f"low_capacity: members' usual damage shares sum to {cap:.2f}; 98% of simulated teams have at least "
                   f"{capacity_min():.2f}, so nobody here usually carries a team's damage")
    return out


def sd_factor(n_findings: int) -> float:
    """How much an extrapolated estimate's sd grows with the number of findings (measured, uncertainty.json)."""
    from gtc import estimate

    per = (estimate.load().get("typicality") or {}).get("per_finding", 0.5)
    return 1.0 + per * n_findings


def measure() -> dict:
    """On simulated lineups: held-out pair-model error (68.3rd percentile of |log error|) for lineups with and
    without typicality findings; the sd grows by `per_finding` for each finding."""
    import math

    from gtc import pairmodel

    data = pairmodel.lineup_data()
    cv = pairmodel.cv_predictions(data)
    groups: dict[int, list[float]] = defaultdict(list)
    for lineup, dps, _, _, lead in data:
        if lineup not in cv:
            continue
        n = len(findings(lineup, lead))
        groups[min(n, 2)].append(abs(math.log(cv[lineup] / dps)))

    def sd68(v):
        v = sorted(v)
        return v[int(0.683 * len(v))] if v else None

    base = sd68(groups[0])
    rows = {str(k): {"n": len(v), "sd": round(sd68(v), 4)} for k, v in sorted(groups.items()) if v}
    with_any = groups[1] + groups[2]
    ratio = sd68(with_any) / base if base and with_any else 1.0
    mean_n = (len(groups[1]) + 2 * len(groups[2])) / len(with_any) if with_any else 1.0
    per = max(0.0, (ratio - 1.0) / mean_n)
    return {"groups": rows, "ratio": round(ratio, 3), "per_finding": round(per, 3)}
