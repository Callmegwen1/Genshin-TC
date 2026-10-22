"""Content profiles (planner v2, phase 12): the same team power, chosen by what each game mode rewards.

Each mode has its own utility over the exact non-overlapping search:
    abyss      two teams, half single target and half AoE. Utility min(v1', v2') + EPSILON x (v1' + v2') over
               values above replacement, v' = max(0, v - REPLACEMENT): both halves must be cleared, so a balanced
               92 / 92 beats 100 / 55, and a missing second team counts 0. When the chosen second team is below
               `minimum_secondary_value` the plan says "No second team worth building yet." (explanation only:
               the objective has no cliff since model 6.3).
    stygian    one team, single target: the best single team.
    general    the four-team plan, mostly single target: weighted sum of each team's value above replacement.
    theater    breadth: Imaginarium Theater uses each character once across many stages and rotates the allowed
               elements, so it rewards many competent teams over distinct characters and elements.

Profiles never change a team's power, only which teams and dimensions count. Defined in knowledge/model.yaml.
Explanations (never the objective): the two-team Pareto frontier ("100 / 55 maximum primary" against
"92 / 92 balanced") and the locked core of the best team (members whose removal costs the most).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from gtc import params

PROFILES = params.get("profiles.definitions")
ALL_ELEMENTS = ("Pyro", "Hydro", "Electro", "Cryo", "Anemo", "Geo", "Dendro")
CORE_LOSS = params.get("profiles.core_loss")  # a member is core when removing them costs this share of the team
REPLACEMENT = params.get("account.replacement_value")  # a team earns only its value above this (model 6.3: no cliff)


@dataclass
class ProfilePlan:
    profile: str
    score: float
    teams: list = field(default_factory=list)  # Assessments
    note: str = ""
    frontier: list = field(default_factory=list)  # [(v1, v2, teams)] two-team plans no other plan beats on both
    core: dict = field(default_factory=dict)  # member of the best team -> share of its value lost without them


from gtc.decision import utility  # noqa: E402


def team_value(a, weights: dict[str, float]) -> float:
    """Risk-adjusted value of a team under a profile's dimension weights (expected minus RISK sd per dimension)."""
    total = 0.0
    for dim, w in weights.items():
        e = (a.power or {}).get(dim)
        if e is not None:
            total += w * max(0.0, utility(e))
    return total


def plan_for(profile: str, cands: list, element_of: dict[str, str]) -> ProfilePlan:
    spec = PROFILES[profile]
    objective = spec.get("objective", "weighted")
    if objective == "breadth":
        return _breadth(profile, spec, cands, element_of)
    if objective == "balanced":
        return _balanced(profile, spec, cands)
    weights = spec["weights"]
    over = lambda a: max(0.0, team_value(a, weights) - REPLACEMENT)
    ranked = sorted((a for a in cands if over(a) > 0), key=lambda a: (-team_value(a, weights), sorted(a.team.members)))
    plan = ProfilePlan(profile, *weighted_search(ranked, spec["team_weights"], over))
    if plan.teams:
        plan.core = locked_core(plan.teams[0], cands, weights)
    return plan


def weighted_search(ranked: list, team_weights: list[float], value) -> tuple[float, list]:
    """Exact branch and bound: disjoint teams maximising the weighted sum (weights to teams in value order)."""
    best: list = [0.0, []]
    n = len(team_weights)
    vals = [value(a) for a in ranked]

    def walk(i, chosen, used, total):
        if len(chosen) == n or i >= len(ranked):
            if total > best[0]:
                best[0], best[1] = total, list(chosen)
            return
        k = len(chosen)
        bound = total + sum(w * v for w, v in zip(team_weights[k:], vals[i:]))
        if bound <= best[0]:
            return
        c = ranked[i]
        if not set(c.team.members) & used:
            walk(i + 1, chosen + [c], used | set(c.team.members), total + team_weights[k] * vals[i])
        walk(i + 1, chosen, used, total)

    walk(0, [], set(), 0.0)
    return round(best[0], 1), best[1]


def _balanced(profile: str, spec: dict, cands: list) -> ProfilePlan:
    """Two disjoint teams maximising min(v1', v2') + EPSILON x (v1' + v2'), v' = max(0, v - REPLACEMENT); a plan with
    one team has v2' = 0. Exact: for each first team, the best second team is the strongest disjoint team below it
    (the utility rises with the second value)."""
    weights, eps, floor = spec["weights"], spec["epsilon"], spec["minimum_secondary_value"]
    ranked = sorted(cands, key=lambda a: (-team_value(a, weights), sorted(a.team.members)))
    vals = [team_value(a, weights) for a in ranked]
    over = lambda v: max(0.0, v - REPLACEMENT)
    util = lambda v1, v2: min(over(v1), over(v2)) + eps * (over(v1) + over(v2))
    pairs = []
    for i, a in enumerate(ranked):
        sa = set(a.team.members)
        j = next((j for j in range(i + 1, len(ranked)) if not sa & set(ranked[j].team.members)), None)
        if j is not None:
            pairs.append((vals[i], vals[j], [a, ranked[j]]))
    single = ProfilePlan(profile, round(util(vals[0], 0.0), 1) if ranked else 0.0, ranked[:1],
                         "No second team worth building yet.")
    best = max(pairs, key=lambda p: (util(p[0], p[1]), p[0]), default=None)
    if best is None or util(best[0], best[1]) <= single.score or best[1] < floor:
        # The note is an explanation: the best second team the account can field is below a credible level.
        if ranked:
            single.core = locked_core(ranked[0], cands, weights)
        return single
    frontier = []
    for p in sorted(pairs, key=lambda p: (-p[0], -p[1])):
        if not any(q[0] >= p[0] and q[1] >= p[1] and q is not p for q in pairs):
            if not frontier or p[1] > frontier[-1][1]:
                frontier.append((round(p[0], 1), round(p[1], 1), [sorted(t.team.members) for t in p[2]]))
    plan = ProfilePlan(profile, round(util(best[0], best[1]), 1), best[2], frontier=frontier[:3])
    plan.core = locked_core(best[2][0], cands, weights)
    return plan


def locked_core(a, cands: list, weights: dict[str, float]) -> dict[str, float]:
    """Explanation only: for each member of the team, the share of its value lost when they are replaced by the
    best candidate team that keeps the other three members. Members losing at least CORE_LOSS are the core."""
    v = team_value(a, weights)
    if v <= 0:
        return {}
    out = {}
    members = set(a.team.members)
    for m in members:
        rest = members - {m}
        alt = max((team_value(c, weights) for c in cands if rest <= set(c.team.members) and m not in c.team.members), default=0.0)
        loss = max(0.0, (v - alt) / v)
        if loss >= CORE_LOSS:
            out[m] = round(loss, 3)
    return out


def _breadth(profile: str, spec: dict, cands: list, element_of: dict[str, str]) -> ProfilePlan:
    """Disjoint competent teams, strongest first, up to `max_teams`: their summed value, scaled by how many of
    the seven elements their members cover (Theater bans and allows elements by season)."""
    weights = spec["weights"]
    competent = [a for a in cands if team_value(a, weights) >= spec["competent_value"]]
    chosen, used = [], set()
    for a in sorted(competent, key=lambda a: -team_value(a, weights)):
        if len(chosen) >= spec["max_teams"]:
            break
        if not set(a.team.members) & used:
            chosen.append(a)
            used |= set(a.team.members)
    covered = {element_of.get(m) for m in used} & set(ALL_ELEMENTS)
    cov = spec["element_coverage"]
    score = sum(team_value(a, weights) for a in chosen) * ((1 - cov) + cov * len(covered) / len(ALL_ELEMENTS))
    return ProfilePlan(profile, round(score, 1), chosen,
                       f"{len(chosen)} competent teams over {len(used)} characters, {len(covered)} of 7 elements")


def all_plans(cands: list, element_of: dict[str, str]) -> dict[str, ProfilePlan]:
    return {p: plan_for(p, cands, element_of) for p in PROFILES}
