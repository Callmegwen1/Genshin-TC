"""Team recognition: fill archetype templates from a roster and score the results.

Raw team scores are on an internal scale: 100 means every slot holds a perfect, fully built
character, times the archetype's ceiling, plus synergy bonuses. Each team gets two raw scores:
  current    uses each character's real investment
  potential  assumes every member is fully built
The report turns raw scores into readable 0-100 numbers (see report.py).
"""
from __future__ import annotations

from gtc import params

from dataclasses import dataclass, field

from gtc.knowledge import MAX_QUALITY, NON_PREFERRED_FACTOR, Knowledge, Slot, Template


@dataclass
class Member:
    """What the team engine needs to know about one character."""
    key: str
    element: str
    investment: float
    roles: dict[str, int]
    constellation: int = 0


@dataclass
class SlotFill:
    slot: Slot
    member: Member
    role: str  # the role that qualified them, or the top contributor for value slots
    quality: float
    breakdown: list[tuple[str, float]] = field(default_factory=list)  # (part, points) for value slots


@dataclass
class Team:
    template: Template
    fills: list[SlotFill]
    current: float = 0.0
    potential: float = 0.0
    reasons: list[str] = field(default_factory=list)

    @property
    def members(self) -> list[str]:
        return [f.member.key for f in self.fills]

    @property
    def lead(self) -> str:
        """The character in the first slot, usually the carry. Ideal teams are compared per lead."""
        return self.fills[0].member.key


@dataclass
class Incomplete:
    template: Template
    missing: list[Slot]
    reason: str


def slot_quality(slot: Slot, roles: dict[str, int]) -> tuple[str, float, list[tuple[str, float]]] | None:
    """Return (role, quality, breakdown) if the character qualifies for the slot, else None."""
    eligible = [r for r in slot.roles if roles.get(r, 0) >= slot.min_quality]
    if not eligible:
        return None
    if slot.value:
        parts = [("base", slot.value.get("base", 0.0))]
        parts += [(r, w * roles[r]) for r, w in slot.value.items() if r != "base" and roles.get(r)]
        quality = min(MAX_QUALITY, sum(p for _, p in parts))
        top = max(parts[1:], key=lambda p: p[1], default=(eligible[0], 0))[0]
        return top, quality, parts
    options = [(r, roles[r] * (1.0 if not slot.prefers or r in slot.prefers else NON_PREFERRED_FACTOR)) for r in eligible]
    role, q = max(options, key=lambda x: x[1])
    return role, q, []


def slot_candidates(slot: Slot, template: Template, roster: list[Member]) -> list[tuple[Member, str, float, list]]:
    """Every character in the roster who can fill this slot, best first."""
    out = []
    for m in roster:
        if slot.elements and m.element not in slot.elements:
            continue
        if template.allowed_elements and m.element not in template.allowed_elements:
            continue
        q = slot_quality(slot, m.roles)
        if q:
            out.append((m, *q))
    return sorted(out, key=lambda x: -x[2])


# ---------- teammates judged against THIS carry ----------
# Generated archetypes rate a support by how teams of the whole family perform with them ("good in Geo-carry
# teams"), which says nothing about a particular carry: Raiden and Sara rated 5/5 next to Noelle without ever
# being simulated with her. In those archetypes a teammate's quality is also capped by their measured share
# of team damage alongside this carry. The lower of the two counts, so the search bound stays exact.
SUSTAIN_ROLES = {"healer", "shield"}  # their value is survival, which damage shares do not measure
PAIR_THRESHOLDS = params.get("teams.pair_thresholds")  # share of team damage for quality 5, 4, 3, 2 (else 1)
UNPROVEN_QUALITY = params.get("teams.unproven_quality")  # never simulated with this carry
SINGLE_TEAM_CAP = params.get("teams.single_team_cap")  # measured in only one team with this carry
_MATE_Q: dict[tuple[str, str], float] = {}


def carry_mate_quality(carry: str, mate: str) -> float:
    key = (carry, mate)
    if key not in _MATE_Q:
        from gtc.synergy import table

        tbl = table()
        rows = tbl.obs.get((carry, mate), []) if tbl else []
        if not tbl or not any(c == carry for c, _ in tbl.obs.keys()):
            q = MAX_QUALITY  # nothing simulated for this carry at all: no evidence either way
        elif not rows:
            q = UNPROVEN_QUALITY
        else:
            v = sum(r["own"] + r["buffs"] + r.get("enable", 0.0) for r in rows) / len(rows)
            q = next((5.0 - i for i, t in enumerate(PAIR_THRESHOLDS) if v >= t), 1.0)
            if len(rows) == 1:
                q = min(q, SINGLE_TEAM_CAP)
        _MATE_Q[key] = q
    return _MATE_Q[key]


def elements_fit(template: Template, elements: list[str]) -> bool:
    """The archetype's element pattern: required elements present, forbidden ones absent, nothing outside `only`.
    An Electro-Charged team must contain Hydro; a Freeze team cannot contain Pyro."""
    sig = template.signature or {}
    present = set(elements)
    if not set(sig.get("require", [])) <= present:
        return False
    if set(sig.get("forbid", [])) & present:
        return False
    only = sig.get("only")
    return not only or present <= set(only)


def _count_role(members: list[Member], role: str) -> int:
    return sum(1 for m in members if m.roles.get(role, 0) > 0)


def score(team: Team, kb: Knowledge) -> None:
    """Fill in raw current and potential scores and the reasons behind adjustments."""
    sc = kb.scoring
    floor = sc["investment_floor"]
    total_w = sum(f.slot.weight for f in team.fills)
    members = [f.member for f in team.fills]
    reasons = []

    def base(potential: bool) -> float:
        s = 0.0
        for f in team.fills:
            inv = 1.0 if potential else f.member.investment
            s += f.slot.weight * (f.quality / MAX_QUALITY) * (floor + (1 - floor) * inv)
        return 100 * team.template.ceiling * s / total_w

    extra = 0.0
    keys = team.members
    for b in team.template.bonuses:
        if _count_role(members, b["role"]) >= b["at_least"]:
            extra += b["bonus"]
            reasons.append(f"+{b['bonus']} {b['reason']}")
    for b in sc.get("faction_bonuses", []):
        if b.get("templates") and team.template.id not in b["templates"]:
            continue
        if _count_role(members, b["role"]) >= b["at_least"]:
            extra += b["bonus"]
            reasons.append(f"+{b['bonus']} {b['reason']}")
    for p in team.template.pair_bonuses:
        if all(k in keys for k in p["pair"]):
            extra += p["bonus"]
            reasons.append(f"+{p['bonus']} {p['pair'][0]} with {p['pair'][1]}")
    penalty = sc["no_sustain_penalty"] if team.template.sustain_penalty is None else team.template.sustain_penalty
    if penalty and not any(_count_role(members, r) for r in sc["sustain_roles"]):
        extra -= penalty
        reasons.append(f"-{penalty} no healer or shield")

    team.current = round(base(False) + extra, 1)
    team.potential = round(base(True) + extra, 1)
    team.reasons = reasons


def _max_extra(template: Template, kb: Knowledge) -> float:
    """Largest total bonus any lineup could earn in this template (an upper bound for pruning)."""
    bonus = sum(max(b.get("bonus", 0), 0) for b in template.bonuses)
    bonus += sum(max(p.get("bonus", 0), 0) for p in template.pair_bonuses)
    bonus += sum(max(b.get("bonus", 0), 0) for b in kb.scoring.get("faction_bonuses", [])
                 if not b.get("templates") or template.id in b["templates"])
    return bonus


def fill_template(template: Template, roster: list[Member], kb: Knowledge, limit: int | None = None,
                  lead: str | None = None, rank_by: str = "current", must: str | None = None) -> list[Team]:
    """Ways to fill a template from this roster, best first.

    lead fixes who fills the first slot; must keeps only lineups containing that character.
    rank_by is "current" or "potential". Each distinct set of characters appears once, with its best
    slot assignment. With a limit, branch and bound skips partial lineups that cannot reach the top `limit`:
    the bound is the potential with every remaining slot at its best candidate, which is never below the
    lineup's current or potential score, so the result is identical to scoring everything.

    With `must`, that character is placed into each slot they can fill first and the rest of the lineup is
    searched around them; the per-slot results are merged. This is exact: a member set's best assignment puts
    `must` in some slot j, so if it is in the overall top `limit` it is also in the top `limit` of search j.
    Ties keep the order of the plain depth-first search (each lineup ranks by where that search would first
    reach it), so results match it exactly; the plain search is deterministic for a given roster order.
    """
    from gtc import timing

    timing.count("search.fill_template")
    steps = [0]
    cands = [slot_candidates(s, template, roster) for s in template.slots]
    if lead is not None:
        cands[0] = [c for c in cands[0] if c[0].key == lead]
    if any(not c for c in cands):
        return []
    other = "potential" if rank_by == "current" else "current"
    # Position of each candidate in its slot's list: a lineup's depth-first visiting order is the tuple of these.
    index = [{c[0].key: n for n, c in enumerate(slot)} for slot in cands]

    def order(item):
        t, first = item
        return (-getattr(t, rank_by), -getattr(t, other), first)

    if must is None:
        found = _search(template, cands, kb, limit, rank_by, steps, index)
    else:
        found = {}
        for j, slot in enumerate(cands):
            mine = [c for c in slot if c[0].key == must]
            if not mine:
                continue
            forced = [mine if i == j else [c for c in cs if c[0].key != must] for i, cs in enumerate(cands)]
            if any(not c for c in forced):
                continue
            for k, (t, first) in _search(template, forced, kb, limit, rank_by, steps, index).items():
                prev = found.get(k)
                if prev is None:
                    found[k] = (t, first)
                else:
                    # The plain search keeps the first-reached position and the strictly better assignment.
                    best = t if getattr(t, rank_by) > getattr(prev[0], rank_by) or (
                        getattr(t, rank_by) == getattr(prev[0], rank_by) and first < prev[1]) else prev[0]
                    found[k] = (best, min(first, prev[1]))
    teams = [t for t, _ in sorted(found.values(), key=order)]
    timing.count("search.steps", steps[0])
    return teams[:limit] if limit else teams


def _search(template: Template, cands: list, kb: Knowledge, limit: int | None, rank_by: str, steps: list[int],
            index: list[dict[str, int]]) -> dict[frozenset, tuple[Team, tuple[int, ...]]]:
    """Exact branch and bound over slot candidates: for each member set, its best assignment and the visiting
    position (per-slot candidate indexes in the unrestricted lists) where the search first reached it, pruned to
    what can still reach the top `limit` by `rank_by`."""
    import heapq

    best_by_members: dict[frozenset, Team] = {}
    first_seen: dict[frozenset, tuple[int, ...]] = {}
    total_w = sum(s.weight for s in template.slots)
    scale = 100 * template.ceiling / total_w
    best_q = [max(c[2] for c in slot) for slot in cands]
    rest = [sum(template.slots[j].weight * best_q[j] / 5 for j in range(i, len(cands))) for i in range(len(cands) + 1)]
    max_extra = _max_extra(template, kb)
    state = {"threshold": float("-inf"), "since": 0}

    def refresh():
        if limit and len(best_by_members) >= limit:
            vals = heapq.nlargest(limit, (getattr(t, rank_by) for t in best_by_members.values()))
            state["threshold"] = vals[-1]
        state["since"] = 0

    def walk(i: int, chosen: list[SlotFill], used: set[str], acc: float) -> None:
        steps[0] += 1
        if limit and scale * (acc + rest[i]) + max_extra < state["threshold"]:
            return
        if i == len(template.slots):
            members = [f.member for f in chosen]
            if not all(_count_role(members, r["role"]) >= r["at_least"] for r in template.requires):
                return
            if not elements_fit(template, [m.element for m in members]):
                return  # mechanical validity (phase 9): roles, slots and the mechanic's elements; see gtc/validity.py
            team = Team(template=template, fills=list(chosen))
            score(team, kb)
            k = frozenset(used)
            prev = best_by_members.get(k)
            if prev is None or getattr(team, rank_by) > getattr(prev, rank_by):
                best_by_members[k] = team
                if prev is None:
                    first_seen[k] = tuple(index[n][f.member.key] for n, f in enumerate(chosen))
                state["since"] += 1
                if state["since"] >= 50:
                    refresh()
            return
        w = template.slots[i].weight
        generic = i > 0 and template.id.startswith("auto_") and chosen
        for m, role, q, parts in cands[i]:
            if m.key in used:
                continue
            if generic and role not in SUSTAIN_ROLES:
                q = min(q, carry_mate_quality(chosen[0].member.key, m.key))
            chosen.append(SlotFill(template.slots[i], m, role, q, parts))
            used.add(m.key)
            walk(i + 1, chosen, used, acc + w * q / 5)
            used.discard(m.key)
            chosen.pop()

    walk(0, [], set(), 0.0)
    return {k: (t, first_seen[k]) for k, t in best_by_members.items()}


def ideal_team(template: Template, universe: list[Member], kb: Knowledge, lead: str | None = None) -> Team | None:
    """Best fully built team for this archetype from every tagged character in the game."""
    found = fill_template(template, universe, kb, limit=1, lead=lead, rank_by="potential")
    return found[0] if found else None


def find_incomplete(template: Template, roster: list[Member], kb: Knowledge) -> Incomplete | None:
    """Explain why a template cannot be filled. Returns None if it can."""
    missing = [s for s in template.slots if not slot_candidates(s, template, roster)]
    if missing:
        return Incomplete(template, missing, "no owned character fits " + ", ".join(s.name for s in missing))
    if not fill_template(template, roster, kb, limit=1):
        reqs = "; ".join(r.get("reason", r["role"]) for r in template.requires) or "slots overlap on the same characters"
        return Incomplete(template, [], reqs)
    return None


def manual_team(members: list[Member]) -> Team:
    """A team entered by hand that no archetype template generates: four open slots, so nothing about the
    generation rules can reject it (gtc/validity.py). Its power comes from the lineup alone."""
    from gtc.knowledge import Slot, Template
    from gtc.validity import MANUAL_ID

    t = Template(MANUAL_ID, "Manual team", [Slot(f"Slot {i + 1}", []) for i in range(len(members))])
    return Team(t, [SlotFill(t.slots[i], m, "manual", 1.0) for i, m in enumerate(members)])


def evaluate_lineup(keys: list[str], roster: list[Member], kb: Knowledge) -> Team | None:
    """Score a specific lineup against whichever template fits it best."""
    subset = [m for m in roster if m.key in keys]
    if len(subset) != len(keys):
        return None
    best = None
    for t in kb.templates.values():
        for team in fill_template(t, subset, kb, limit=1):
            if set(team.members) == set(keys) and (best is None or team.current > best.current):
                best = team
    return best


def best_disjoint_pair(teams: list[Team]) -> tuple[Team, Team] | None:
    """Best two teams sharing no characters, as needed for Spiral Abyss halves."""
    best, best_sum = None, -1.0
    ranked = sorted(teams, key=lambda t: -t.current)
    for i, a in enumerate(ranked):
        if a.current + ranked[0].current <= best_sum:
            break
        for b in ranked[i + 1:]:
            if a.current + b.current <= best_sum:
                break
            if not set(a.members) & set(b.members):
                best, best_sum = (a, b), a.current + b.current
                break
    return best
