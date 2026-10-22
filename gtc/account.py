"""Account-level reasoning: the best teams an account can build, and what a new character would change.

"Available" means owned. Teams are chosen by potential (archetype tier x lineup fit, everyone fully
built); investment is reported separately as the cost of getting there.

The account plan is the set of four teams sharing no characters that maximises a weighted sum of
potentials: the two strongest count fully (Spiral Abyss halves), the third half, the fourth a quarter.

A new character's value is the change in that weighted sum when they join the account fully built,
plus an explanation of WHY:
  fills a gap        they replace a weak member of a team you already play
  new archetype      they lead a team that was not in your plan
  sidegrade          they lead a team in an archetype or element you already field well, competing
                     for the same teammates
This is marginal value for this account, not "who is strongest". An account without enough carries
is detected and the carries that best use its existing supports are ranked separately.
"""
from __future__ import annotations

from gtc import params

from dataclasses import dataclass, field

from gtc import gamedata
from gtc.knowledge import Knowledge
from gtc.report import Analysis, Assessment, assess, build_universe
from gtc.teams import Member, fill_template, slot_candidates

PLAN_WEIGHTS = params.get("account.plan_weights")
TEAMS_PER_TEMPLATE = params.get("account.teams_per_template")
VIABLE_CARRY_POTENTIAL = params.get("account.viable_carry_potential")  # a carry whose best team reaches this potential counts as a real main DPS
CARRY_CATEGORY_MIN = params.get("account.carry_category_min")
REPLACEMENT = params.get("account.replacement_value")  # a plan team earns only its value above this (phase 12)


@dataclass
class Plan:
    teams: list[Assessment]

    # Planner v2 (phase 12): a plan team earns only what it reaches above replacement level (REPLACEMENT, the value
    # of a lineup that is not worth building). Two leftover lineups at 34 and 30 are worth less than one team at
    # 55, so the plan no longer breaks up the best team to field them.
    @property
    def value(self) -> float:
        return sum(w * (a.potential - REPLACEMENT) for w, a in self.weighted())

    @property
    def members(self) -> set[str]:
        return {m for a in self.teams for m in a.team.members}

    def weighted(self) -> list[tuple[float, Assessment]]:
        return list(zip(PLAN_WEIGHTS, sorted(self.teams, key=lambda a: (-a.potential, sorted(a.team.members)))))

    @property
    def expected(self) -> float:
        """Weighted expected value above replacement (no risk adjustment)."""
        return sum(w * ((a.estimate.value if a.estimate else a.potential) - REPLACEMENT) for w, a in self.weighted())

    @property
    def power(self) -> float:
        """Weighted expected power of the teams (no replacement level): for comparisons with the meta plan."""
        return sum(w * (a.estimate.value if a.estimate else a.potential) for w, a in self.weighted())


def _choice(a: Assessment) -> tuple[float, float, float]:
    """Which generating template names a lineup when several give it the same power: the one whose lead is the
    structure's most probable damage dealer (phase 7), then the one whose own estimate fits the lineup best."""
    e = a.evaluation
    primary = (e.structure or {}).get("primary") if e else None
    lead_match = primary.get(a.lead, 0.0) if primary and a.lead else 0.0
    return a.potential, lead_match, (e.explanation.get("template_estimate", 0.0) if e else 0.0)


def gain_estimate(new: Plan, base: Plan, factor: float = 1.0):
    """Expected change in plan value with its sd and evidence tier. Teams in both plans cancel, so only the
    teams that change carry uncertainty; the tier is the weakest among the new plan's changed teams."""
    from gtc.estimate import Estimate, worst_tier

    base_sets = {frozenset(a.team.members) for a in base.teams}
    new_sets = {frozenset(a.team.members) for a in new.teams}
    var = 0.0
    tiers = []
    for plan, others in ((new, base_sets), (base, new_sets)):
        for w, a in plan.weighted():
            if frozenset(a.team.members) not in others and a.estimate:
                var += (w * a.estimate.sd) ** 2
                if plan is new:
                    tiers.append(a.estimate.tier)
    return Estimate(factor * (new.expected - base.expected), factor * var ** 0.5, worst_tier(tiers) if tiers else "B", [])


@dataclass
class CharacterValue:
    name: str
    gain: float
    kind: str  # fills a gap, new archetype, sidegrade, upgrade, no change
    explanation: list[str] = field(default_factory=list)
    team: Assessment | None = None
    plan: Plan | None = None
    weapon_note: str = ""
    is_carry: bool = False
    estimate: object = None  # gtc.estimate.Estimate of the expected gain, with sd and the weakest evidence tier
    coverage: str = "complete"  # mechanics coverage of the teams the gain rests on (gtc/coverage.py, temporary)
    coverage_missing: list = field(default_factory=list)
    # Pull value v2 (phase 12): the actual deltas behind the gain (see AccountModel.decompose)
    decomposition: dict = field(default_factory=dict)

    @property
    def statistical_confidence(self) -> float:
        """Probability the gain is real (above zero), from the measured sds alone."""
        from gtc.estimate import Estimate, prob_greater
        return prob_greater(self.estimate, Estimate(0.0, 0.0, "B")) if self.estimate else 0.5

    @property
    def confidence(self) -> float:
        """Recommendation confidence: the statistical confidence, capped when the mechanics the gain depends on are
        not represented by the evidence (temporary guard, gtc/coverage.py)."""
        from gtc.coverage import cap
        return cap(self.statistical_confidence, self.coverage)


class AccountModel:
    def __init__(self, an: Analysis, kb: Knowledge, account_basis: bool = False):
        """account_basis=True (the account report): plans and pull values compare teams as this account can
        properly build them (AccountCeiling, gtc/account_power.py): owned constellations and weapons, a newcomer at
        C0 with the best weapon of their type you own. False (benchmark and golden scenarios, which describe fully
        built rosters): community-standard MetaPower."""
        self.an, self.kb, self.ev, self.model = an, kb, an.evidence, an.model
        self.account_ctx = None
        if account_basis:
            from gtc.account_power import context

            self.account_ctx = context(an, an.evidence)
        self._assessed: dict[tuple, Assessment] = {}
        self._with: dict[tuple, list[Assessment]] = {}  # (roster key, newcomer) -> candidates containing them
        self.universe = {m.key: m for m in build_universe(kb, self.ev)}
        self.game = gamedata.load_characters()

    # ---------- teams ----------
    def _assess(self, team) -> Assessment:
        from gtc import timing

        # Constellations are part of the key: they change roles, so one engine shared across rosters must not reuse
        # an assessment made for a different constellation.
        key = (team.template.id, tuple(team.members), tuple(sorted((f.member.key, f.member.constellation) for f in team.fills)))
        if key not in self._assessed:
            timing.count("assess_miss")
            a = assess(team, self.ev, self.model, self.kb)
            if self.account_ctx is not None and a.estimate is not None:
                from gtc.account_power import account_power
                from gtc.decision import utility

                ap = account_power(a, self.account_ctx)
                if ap:
                    a.account = ap
                    # The comparison basis becomes the account ceiling: the plan and pull values maximise it.
                    a.estimate = ap["ceiling"]
                    a.potential = round(max(0.0, utility(ap["ceiling"])), 1)
            self._assessed[key] = a
        else:
            timing.count("assess_hit")
        return self._assessed[key]

    def candidates(self, roster: list[Member], must_include: str | None = None) -> list[Assessment]:
        from gtc import timing

        timing.count("candidates")
        out: dict[frozenset, Assessment] = {}
        for t in self.kb.templates.values():
            if must_include and not any(c[0].key == must_include for s in t.slots for c in slot_candidates(s, t, roster)):
                continue
            for team in fill_template(t, roster, self.kb, limit=TEAMS_PER_TEMPLATE, rank_by="potential", must=must_include):
                a = self._assess(team)
                k = frozenset(team.members)
                # Power no longer depends on the generating template except on the role-rules route, so templates
                # producing the same four usually tie; the one whose own estimate fits them best names the team.
                if k not in out or _choice(a) > _choice(out[k]):
                    out[k] = a
        return sorted(out.values(), key=lambda a: (-a.potential, sorted(a.team.members)))

    def assess_lineup(self, names: list[str], roster: list[Member]) -> dict:
        """Any four characters, as a future manual Team Builder enters them (model 6.3). Returns
        {"status": "invalid" | "well_supported" | "unusual", "reasons": [...], "assessment": Assessment | None}.
        Only mechanical legality rejects a team (gtc/validity.py); a team no archetype template generates is still
        evaluated, from its lineup alone. Characters the roster does not own join fully built at C0."""
        from gtc import validity
        from gtc.teams import manual_team

        reasons = validity.mechanical(names, self.kb.characters)
        if reasons:
            return {"status": "invalid", "reasons": reasons, "assessment": None}
        owned = {m.key: m for m in roster}
        members = [owned[k] if k in owned else self.newcomer(k) for k in names]
        exact = [a for a in self.candidates(members) if set(a.team.members) == set(names)]
        a = exact[0] if exact else self._assess(manual_team(members))
        v = a.evaluation.validity if a.evaluation else {}
        return {"status": v.get("support", "unusual"), "reasons": v.get("support_reasons", []), "assessment": a}

    @staticmethod
    def best_plan(cands: list[Assessment], n: int = 4, pool: int | None = None) -> Plan:
        """Exact search with branch and bound over every candidate. A truncated pool loses plans whose
        third or fourth team ranks low overall, so there is no cap unless one is asked for."""
        cands = cands[:pool] if pool else cands
        # Planner v2 (model 6.3): a team earns max(0, value - REPLACEMENT), continuous at the threshold, so there is
        # no separate useful-team gate (it made 29.6 count for nothing and 30.0 for full value). A team at or below
        # replacement adds nothing, so it is left out of the search.
        cands = [c for c in cands if c.potential > REPLACEMENT]
        best: list = [0.0, []]

        def walk(i, chosen, used, total):
            if len(chosen) == n or i >= len(cands):
                if total > best[0]:
                    best[0], best[1] = total, list(chosen)
                return
            k = len(chosen)
            bound = total + sum(w * (c.potential - REPLACEMENT) for w, c in zip(PLAN_WEIGHTS[k:n], cands[i:]))
            if bound <= best[0]:
                return
            c = cands[i]
            if not (set(c.team.members) & used):
                walk(i + 1, chosen + [c], used | set(c.team.members), total + PLAN_WEIGHTS[k] * (c.potential - REPLACEMENT))
            walk(i + 1, chosen, used, total)

        walk(0, [], set(), 0.0)
        return Plan(best[1])

    def plan(self, roster: list[Member]) -> tuple[Plan, list[Assessment]]:
        cands = self.candidates(roster)
        return self.best_plan(cands), cands

    # ---------- carries ----------
    def carry_strength(self, name: str) -> int:
        roles = (self.kb.characters.get(name).roles if name in self.kb.characters else {})
        return max((q for r, q in roles.items() if r.startswith("carry_") and r != "carry_unsimulated"), default=0)

    def is_primary_carry(self, name: str) -> bool:
        """Prydwen's best-rated category decides: Columbina is a T0 support first, a T1.5 carry second."""
        entries = [e for e in self.ev.prydwen.get("tiers", {}).get(name, []) if e.get("overall")]
        if not entries:
            return self.carry_strength(name) >= CARRY_CATEGORY_MIN
        order = ["T0", "T0.5", "T1", "T1.5", "T2", "T3", "T4", "T5"]
        best = min(entries, key=lambda e: order.index(e["overall"]))
        return best["category"] == "DPS"

    def viable_carries(self, cands: list[Assessment]) -> dict[str, Assessment]:
        out = {}
        for a in cands:
            lead = a.lead
            if lead and self.is_primary_carry(lead) and a.potential >= VIABLE_CARRY_POTENTIAL and lead not in out:
                out[lead] = a
        return out

    # ---------- new characters ----------
    def newcomer(self, name: str) -> Member:
        u = self.universe[name]
        info = self.kb.characters[name]
        roles = {**info.roles_at(0), **self.ev.faction_roles(name)}
        return Member(name, u.element, 1.0, roles, 0)

    def candidates_with(self, name: str, roster: list[Member]) -> list[Assessment]:
        """Candidates containing `name`, with them added as a fully built C0 newcomer when not owned. Shared by
        pull values and carries-for-supports, which ask the same question for the same roster."""
        from gtc import timing

        key = (tuple((m.key, m.constellation, round(m.investment, 6)) for m in roster), name)
        if key not in self._with:
            timing.count("candidates_with_miss")
            owned = {m.key for m in roster}
            self._with[key] = self.candidates(roster + ([self.newcomer(name)] if name not in owned else []), must_include=name)
        else:
            timing.count("candidates_with_hit")
        return self._with[key]

    def best_team_with(self, name: str, roster: list[Member]) -> Assessment | None:
        """The strongest team `name` can lead (or join) using only `roster` as teammates."""
        cands = self.candidates_with(name, roster)
        led = [a for a in cands if a.lead == name] or cands
        return led[0] if led else None

    def value_of(self, name: str, roster: list[Member], base: Plan, base_cands: list[Assessment],
                 admit=None) -> CharacterValue | None:
        """Pull value v2 (phase 12): the literal change in the account plan when `name` joins, never discounted by a
        label. What changed is decomposed (`decompose`), and the kind and the explanation describe those deltas.
        `admit` (model 6.5, the advisor pool, gtc/advisor.py) restricts which candidate teams the plans may use; `base`
        must then be the plan over the same pool. Team power is never changed by it."""
        if name not in self.universe or name not in self.kb.characters:
            return None
        extra = self.candidates_with(name, roster)
        if not extra:
            return None
        info = self.kb.characters[name]
        if info.provisional and not any(a.estimate and a.estimate.value > 0 for a in extra):
            return None  # a provisional kit, but no team this account could build is close to a Prydwen-listed team
        merged = sorted({frozenset(a.team.members): a for a in base_cands + extra}.values(), key=lambda a: (-a.potential, sorted(a.team.members)))
        if admit is not None:
            merged = admit(merged)
            keep = {frozenset(a.team.members) for a in merged}
            extra = [a for a in extra if frozenset(a.team.members) in keep]
            if not extra:
                return None
        new_plan = self.best_plan(merged)
        gain = new_plan.value - base.value
        mine = [a for a in new_plan.teams if name in a.team.members]
        best_team = mine[0] if mine else max(extra, key=lambda a: a.potential)
        d = self.decompose(name, roster, base, new_plan, extra, best_team)
        kind = _kind(d, gain)
        expl = _explain(name, d, kind, best_team)
        est = gain_estimate(new_plan, base)
        from gtc import coverage

        base_sets = {frozenset(b.team.members) for b in base.teams}
        moved = [x for x in new_plan.teams if frozenset(x.team.members) not in base_sets] or [best_team]
        covs = [x.evaluation.coverage for x in moved if x.evaluation is not None and x.evaluation.coverage]
        status = coverage.worst(c["status"] for c in covs) if covs else coverage.UNKNOWN
        missing = sorted({m for c in covs for m in c["missing"]})
        return CharacterValue(name, round(gain, 1), kind, expl, best_team, new_plan, is_carry=self.is_primary_carry(name),
                              estimate=est, coverage=status, coverage_missing=missing, decomposition=d)

    def decompose(self, name: str, roster: list[Member], base: Plan, new: Plan, extra: list[Assessment],
                  best_team: Assessment) -> dict:
        """The actual deltas of a pull: plan, best-team, second-team and expected (ceiling) gains; new mechanics and
        viable teams; owned characters improved and displaced; support contention; functional redundancy with what
        the account already fields; build compatibility. Everything is read from the two plans."""
        def ranked(plan):
            return sorted(plan.teams, key=lambda a: (-a.potential, sorted(a.team.members)))

        def nth(plan, i):
            r = ranked(plan)
            return r[i].potential if len(r) > i else 0.0

        def central(teams):
            return {m for a in teams if a.evaluation for m in (a.evaluation.identity or {}).get("central", [])}

        owned = {m.key for m in roster}
        team_of = lambda plan: {m: a for a in plan.teams for m in a.team.members}
        before, after = team_of(base), team_of(new)
        improved = sorted(m for m in owned if m in before and m in after and after[m].potential > before[m].potential + 0.5)
        displaced = sorted(m for m in owned if m in before and m not in after)
        mates = [m for m in best_team.team.members if m != name]
        # Contention: teammates the newcomer's team takes from a plan team other than the one it grows out of (the
        # plan team sharing the most members with it).
        sources = [before[m] for m in mates if m in before]
        home = max(list({id(b): b for b in sources}.values()), key=lambda b: (sum(x is b for x in sources), b.potential),
                   default=None)
        contention = sorted(m for m in mates if m in before and before[m] is not home)
        mine_central = set((best_team.evaluation.identity or {}).get("central", [])) if best_team.evaluation else set()
        base_central = central(base.teams)
        # Only the mechanics of the character's own team: other plan teams reshuffling is not something they bring.
        new_mech = sorted(mine_central - base_central) if name in after else []
        # Functional redundancy: overlap with what the account already does, never element alone.
        roles = {r for r, q in self.kb.characters[name].roles.items() if q >= 3}
        role_overlap = max((len(roles & {r for r, q in self.kb.characters[o].roles.items() if q >= 3}) /
                            len(roles | {r for r, q in self.kb.characters[o].roles.items() if q >= 3})
                            for o in owned if o in self.kb.characters and o != name), default=0.0) if roles else 0.0
        mech_overlap = len(mine_central & base_central) / len(mine_central) if mine_central else 0.0
        demand_overlap = len(contention) / len(mates) if mates else 0.0
        base_sets = [set(b.team.members) for b in base.teams]
        team_overlap = max((len(set(best_team.team.members) & b) for b in base_sets), default=0) / 4
        base_carries = {(b.primary_actor, self.universe[b.primary_actor].element) for b in ranked(base)[:2]
                        if b.primary_actor and b.primary_actor in self.universe}
        my_el = self.universe[name].element if name in self.universe else None
        coverage_overlap = float(best_team.primary_actor == name and any(el == my_el for _, el in base_carries))
        redundancy = {"role": round(role_overlap, 2), "mechanic": round(mech_overlap, 2), "support_demand": round(demand_overlap, 2),
                      "team": round(team_overlap, 2), "content_coverage": coverage_overlap}
        ctx = self.account_ctx or {}
        weapon = (ctx.get("newcomer_weapon") or {}).get(name)
        return {
            "plan_gain": round(new.value - base.value, 1),
            "best_team_gain": round(nth(new, 0) - nth(base, 0), 1),
            "second_team_gain": round(nth(new, 1) - nth(base, 1), 1),
            "expected_gain": round(new.expected - base.expected, 1),
            "new_mechanics": new_mech,
            "new_viable_teams": sum(1 for a in extra if a.potential > REPLACEMENT and frozenset(a.team.members) not in {frozenset(b) for b in base_sets}),
            "improved": improved, "displaced": displaced, "support_contention": contention,
            "redundancy": redundancy, "redundancy_score": round(sum(redundancy.values()) / len(redundancy), 2),
            "leads": best_team.primary_actor == name, "in_plan": name in after,
            "joined_lift": _lift(best_team, before, name),
            "best_owned_weapon_rarity": weapon,
        }

    def best_carries_for(self, roster: list[Member], limit: int = 5) -> list[tuple[str, Assessment]]:
        """Unowned carries ranked by the best team they would lead with the characters you already own."""
        owned = {m.key for m in roster}
        out = []
        for name in self.universe:
            if name in owned or name not in self.kb.characters or not self.is_primary_carry(name):
                continue
            a = self.best_team_with(name, roster)
            if a and a.lead == name:
                out.append((name, a))
        return sorted(out, key=lambda x: (-x[1].potential, x[0]))[:limit]


def _provisional_note(a) -> str:
    """The label every provisional number carries (phase 13: "Provisional / kit-based")."""
    e = a.evaluation
    p = e.power.get("single_target") if e else None
    if p is None or "provisional" not in p.basis.flags:
        return ""
    who = p.basis.sources[0].removeprefix("provisional kit for ").removesuffix(" (no simulations yet)") if p.basis.sources else "a member"
    return (f"**Provisional / kit-based:** no simulations of {who} yet. Estimated from a hand-written kit "
            "(knowledge/kits_provisional/) and Prydwen's ratings: "
            + "; ".join(p.basis.sources[1:]) + f". Uncertainty ±{p.basis.sd_relative:.0%}.")


FILL_LIFT = params.get("account.fill_lift")  # joining a team that rises by this share fills a gap (a label only)


def _lift(team, before: dict, name: str) -> float | None:
    """Relative rise of the plan team the newcomer joins (the one sharing the most members); None when it completes a
    team that had no place in the plan before."""
    shared = [before[m] for m in team.team.members if m != name and m in before]
    if not shared:
        return None
    unique = list({id(b): b for b in shared}.values())
    old = max(unique, key=lambda b: (sum(x is b for x in shared), b.potential, sorted(b.team.members)))
    return round((team.potential - old.potential) / old.potential, 3) if old.potential else None


CLEAR, COMPETITIVE, LOWER = "Clear recommendation", "Competitive / roughly equal", "Lower-value"


def pull_groups(values: list) -> dict[str, str]:
    """Model 6.4: confidence groups for pulls instead of a hard ranking. The leader is the highest gain; every
    other candidate is compared with the leader only (a tie is not transitive), through compare() with the
    mechanics-coverage cap:
      Clear recommendation          the leader, when it is better than every other candidate
      Competitive / roughly equal   the leader and every candidate compare() cannot separate from it
      Lower-value                   candidates the leader is better than
    Candidates without an estimate are lower-value."""
    from gtc import coverage
    from gtc.decision import compare

    shown = [v for v in values if v.estimate is not None]
    if not shown:
        return {}
    lead = shown[0]
    out = {}
    for v in shown[1:]:
        lim = coverage.cap(1.0, coverage.worst([lead.coverage, v.coverage]))
        r = compare(lead.estimate, v.estimate, lim)["comparison"]
        out[v.name] = COMPETITIVE if r == "roughly_equal" else LOWER
    out[lead.name] = COMPETITIVE if COMPETITIVE in out.values() else CLEAR
    for v in values:
        out.setdefault(v.name, LOWER)
    return out


def near_alternatives(plan: Plan, cands: list[Assessment]) -> list[tuple]:
    """Model 6.3: for each plan team, lineups one member away (the other three kept, nobody taken from another plan
    team) that compare() calls roughly equal. The planner must choose one internally; reports keep the tie visible.
    Returns (plan team, alternative, member out, member in, probability the plan's choice is better)."""
    from gtc.decision import compare

    out = []
    used = {m for a in plan.teams for m in a.team.members}
    for t in sorted(plan.teams, key=lambda a: (-a.potential, sorted(a.team.members))):
        mine = set(t.team.members)
        for c in cands:
            cs = set(c.team.members)
            if len(cs & mine) != 3 or (cs - mine) & used or c.estimate is None or t.estimate is None:
                continue
            r = compare(t.estimate, c.estimate)
            if r["comparison"] == "roughly_equal":
                out.append((t, c, next(iter(mine - cs)), next(iter(cs - mine)), r["probability"]))
    # the closest one per team
    best: dict[int, list] = {}
    for row in sorted(out, key=lambda r: (abs(r[4] - 0.5), r[3])):
        best.setdefault(id(row[0]), [])
        if len(best[id(row[0])]) < 1:
            best[id(row[0])].append(row)
    return [r for rows in best.values() for r in rows]


def _kind(d: dict, gain: float) -> str:
    """The pull's observed impact (phase 12): a description of the deltas, never a factor on the gain.
      no change       the plan does not improve
      fills a gap     joins your characters as a support and lifts their team a lot, or completes a team that
                      had no place in the plan before (even when that team runs on a new mechanic)
      upgrade         joins an existing team and lifts it a little
      new archetype   leads (or enables) a new team that runs on a mechanic the plan did not have
      sidegrade       leads a team that replaces one of the same kind: shared mechanics, or a carry of the same
                      element competing for the same supports (element alone is never enough)
      luxury          improves only the plan's lower teams"""
    if gain <= 0.5 or not d["in_plan"]:
        return "no change"
    r = d["redundancy"]
    if d["leads"]:
        if d["displaced"] and (r["mechanic"] >= 0.5 or (r["content_coverage"] and d["support_contention"])):
            return "sidegrade"
        if d["best_team_gain"] <= 0.5 and d["second_team_gain"] <= 0.5:
            return "luxury"
        return "new archetype" if d["new_mechanics"] or not r["mechanic"] else "upgrade"
    if d["best_team_gain"] <= 0.5 and d["second_team_gain"] <= 0.5:
        return "luxury"
    # A support completing or strongly lifting a team for characters you own fills a gap, whatever mechanic that
    # team runs on (a new mechanic is named in the explanation).
    lift = d["joined_lift"]
    return "fills a gap" if lift is None or lift >= FILL_LIFT else "upgrade"


def _explain(name: str, d: dict, kind: str, team) -> list[str]:
    from gtc.reactions import mechanic_name

    line = " / ".join(team.team.members) if team else ""
    out = []
    if kind == "no change":
        out.append(f"Their best team here ({line}, {team.expected_power:.0f}) does not improve your plan." if team else "No team of theirs improves your plan.")
        return out
    who = "Leads" if d["leads"] else "Joins"
    out.append(f"{who} {line} ({team.label}), {team.expected_power:.0f}.")
    parts = []
    if d["best_team_gain"] > 0.5:
        parts.append(f"best team +{d['best_team_gain']:.0f}")
    if d["second_team_gain"] > 0.5:
        parts.append(f"second team +{d['second_team_gain']:.0f}")
    if parts:
        out.append("Plan change: " + ", ".join(parts) + ".")
    if d["new_mechanics"]:
        out.append("New for your account: " + ", ".join(mechanic_name(m) for m in d["new_mechanics"]) + ".")
    if d["improved"]:
        out.append("Improves the teams of " + ", ".join(d["improved"]) + ".")
    if d["displaced"]:
        out.append("Takes over from " + ", ".join(d["displaced"]) + " in your plan.")
    if d["support_contention"]:
        out.append("Competes for " + ", ".join(d["support_contention"]) + ", who your plan already uses.")
    r = d["redundancy"]
    if kind not in ("sidegrade", "no change"):
        # Model 6.4: redundancy is described next to the observed kind, never folded into it or into the gain.
        level = "high" if d["redundancy_score"] >= 0.5 else "moderate" if d["redundancy_score"] >= 0.25 else ""
        if level or r["content_coverage"]:
            what = ("another on-field carry of an element your top teams already carry" if r["content_coverage"]
                    else "overlaps with roles and teams you already field")
            out.append(f"Functional redundancy: {level or 'some'} ({what}); the gain above is the literal plan change.")
    if kind == "sidegrade":
        why = []
        if r["mechanic"] >= 0.5:
            why.append("runs on the same mechanics as a team you have")
        if r["content_coverage"]:
            why.append("is another carry of an element your top teams already carry")
        out.append("Redundant here: " + " and ".join(why) + " (a description; the gain is not discounted for it).")
    return out


def weapon_note(name: str, guides, owned_weapons, weapon_types: dict, game: dict, data_level: str = "full") -> str:
    """Whether the account owns a weapon the guides recommend. With a basic import only equipped weapons are
    known, so the engine never claims one is missing."""
    recs = [w for w, _, _ in guides.weapons(name)]
    wtype = game.get(name, {}).get("weapon")
    mine = [w.name for w in owned_weapons if w.name in recs and weapon_types.get(w.name, {}).get("type") == wtype]
    if mine:
        return f"You own a recommended weapon: {sorted(set(mine), key=recs.index)[0]}."
    if not recs:
        return ""
    if data_level == "basic":
        return ("None of your equipped weapons is one the guides recommend; spare weapons were not imported "
                "(import a scanner export to check them).")
    return "You own none of the weapons the guides recommend for them."


def partner_notes(name: str, owned: set[str], prydwen: dict) -> list[str]:
    out = []
    for other, entries in prydwen.get("tiers", {}).items():
        for e in entries:
            for tag in e.get("tags", []):
                if tag.startswith("partner") and name.lower() in tag.lower() and other in owned:
                    out.append(f"Prydwen pairs your {other} with {name} (a pairing, not a judgement of any particular full team).")
    own_tags = [t for e in prydwen.get("tiers", {}).get(name, []) for t in e.get("tags", []) if t.startswith("partner")]
    for t in own_tags:
        partner = t.split("(", 1)[-1].rstrip(")").strip()
        if any(partner.lower() in o.lower() for o in owned):
            out.append(f"Prydwen pairs {name} with your {partner.title()} (a pairing, not a judgement of any particular full team).")
    return sorted(set(out))


# ---------- report ----------

def build_report(snapshot, kb, top: int = 6) -> str:
    from gtc.report import analyze
    from gtc.review import Guides, build_review

    from gtc import timing

    timing.start("analyze: team report pass and calibration")
    an = analyze(snapshot, kb)
    timing.stop("analyze: team report pass and calibration")
    timing.start("account model setup")
    am = AccountModel(an, kb, account_basis=True)
    timing.stop("account model setup")
    roster = an.roster
    owned = {m.key for m in roster}
    timing.start("plan: candidates and exact search")
    plan, cands = am.plan(roster)
    timing.stop("plan: candidates and exact search")
    timing.start("meta plan: whole game")
    # The strongest plan in the game is a community-standard comparison: a separate, meta-basis model.
    meta_plan, _ = AccountModel(an, kb).plan(list(am.universe.values()))
    timing.stop("meta plan: whole game")
    timing.start("pull values")
    carries = am.viable_carries(cands)
    guides = Guides(an.evidence, gamedata.names(), {c.key: c.element for c in snapshot.characters})
    weapons, weapon_types = snapshot.all_weapons(), gamedata.load_weapons()

    values = []
    blind = []
    blind_provisional = []
    for name in sorted(am.universe):
        if name in owned:
            continue
        info = kb.characters.get(name)
        if info and "carry_unsimulated" in info.roles and not any(r.startswith(("carry_", "support_")) and r != "carry_unsimulated" for r in info.roles):
            blind.append(name)
            continue
        v = am.value_of(name, roster, plan, cands)
        if v is None:
            (blind_provisional if info and info.provisional else blind).append(name)
            continue
        v.weapon_note = weapon_note(name, guides, weapons, weapon_types, am.game, snapshot.data_level)
        v.explanation += partner_notes(name, owned, an.evidence.prydwen)
        values.append(v)
    values.sort(key=lambda v: (-v.gain, v.name))
    timing.stop("pull values")
    timing.start("carries for owned supports")
    best_carries = am.best_carries_for(roster, limit=3)
    timing.stop("carries for owned supports")

    an.my_teams = [(a.team.members, a) for a in plan.teams]
    timing.start("review: rules and personal sims")
    review = build_review(snapshot, kb, extra_teams=0, exclusive=True, an=an)
    timing.stop("review: rules and personal sims")
    timing.start("content modes and rendering")

    out = [f"# Account plan for UID {snapshot.uid}", "", f"Engine model {params.version()} ({params.fingerprint()}). Data level: {snapshot.data_level}.", "",
           "Teams use characters you own, judged at full build (potential). Today's power and build progress show how far each is from that.", "",
           "## Your best four teams", "",
           "Three numbers per team, all expected values with one standard deviation:", "",
           "- **Ceiling**: the team properly built from what you own (your constellations, your weapons at level 90, "
           "standard artifacts, talents and levels). Plans and pull values compare teams on this basis, a newcomer at "
           "C0 with the best weapon of their type you own.",
           "- **Meta**: the same team at community standard (5-stars C0, 4-stars C6, standard builds).",
           "- **Current**: the team as you have it today: your own builds simulated on the team's community rotation "
           "where possible, otherwise build factors calibrated on 48 such simulations of your account.",
           "- The ± parts in brackets say where the uncertainty comes from: the team's power evidence (team), the "
           "build model's held-out miss (build), and owned constellations or weapons whose effect is not measured.", "",
           "Evidence tier of the team's strength: A your own simulation, B community simulations, C the pair model next "
           "to a simulation, D the pair model further away, E role rules or a provisional kit. The evidence state says "
           "where the number comes from: simulation, interpolation (the pair model), kit-model (a provisional kit, no "
           "simulations of a member yet) or rules-only (template role rules). Community simulations are also graded: "
           "good (submitters agree), unconfirmed (one submitter), mixed or poor (submitters or builds disagree, or the "
           "rotation does not play the team as intended). Teams are chosen by a "
           "separate decision score (the ceiling minus two thirds of its sd), never shown as strength. \"mixed builds\" "
           "marks community simulations with different weapons or sets; their disagreement is part of the ±. A "
           "constellation whose effect has no same-lineup measurement is flagged as unknown, not assumed neutral.", "",
           "| # | Team | Identity | Ceiling | Meta | Current | Evidence | Built |", "|---|---|---|---|---|---|---|---|"]
    for i, a in enumerate(sorted(plan.teams, key=lambda a: (-a.potential, sorted(a.team.members))), 1):
        e = a.estimate
        acc = a.account or {}
        fmt = lambda x: f"{x.value:.0f} ± {x.sd:.0f}" if x is not None else "?"
        basis = a.evaluation.power["single_target"].basis if a.evaluation and "single_target" in a.evaluation.power else None
        flags = basis.flags if basis else ()
        q = f" ({basis.quality} community evidence)" if basis and basis.quality and basis.quality != "good" else ""
        tier = (e.tier if e else "?") + (f", {basis.evidence_state}{q}" if basis else "") + (", mixed builds" if "mixed_builds" in flags else "")
        unknown = acc.get("unknown_constellations") or []
        if unknown:
            tier += ", constellation effect unknown: " + ", ".join(unknown)
        built = f"{acc['current'].value / acc['ceiling'].value:.0%}" if acc.get("ceiling") and acc["ceiling"].value else f"{a.build}%"
        parts = acc.get("sd_parts") or {}

        def why(kind, x):
            ps = parts.get(kind) or {}
            bits = [f"{k} ±{v:.0%}" for k, v in ps.items() if v >= 0.005]
            return f" ({', '.join(bits)})" if x is not None and len(bits) > 1 else ""

        out.append(f"| {i} | {' / '.join(a.team.members)} | {a.label} | {fmt(e)}{why('ceiling', e)} | {fmt(acc.get('meta'))} | "
                   f"{fmt(acc.get('current'))}{why('current', acc.get('current'))} | {tier} | {built} |")
    alts = near_alternatives(plan, cands)
    if alts:
        out += ["", "**Choices the evidence cannot separate** (compare() calls them roughly equal; the plan has to pick one, "
                "so its pick is a lean, not a verdict):", ""]
        out += [f"- {' / '.join(t.team.members)}: {inn} instead of {outn} ({alt.estimate.value:.0f} against "
                f"{t.estimate.value:.0f}; {p:.0%} that the plan's choice is better)" for t, alt, outn, inn, p in alts]
    ratio = plan.power / meta_plan.power if meta_plan.power else 0
    out += ["", f"**Against meta:** at full build this plan reaches {ratio:.0%} of the strongest four-team plan in the game "
            f"({' ; '.join(' / '.join(a.team.members) for a in sorted(meta_plan.teams, key=lambda a: (-a.potential, sorted(a.team.members)))[:2])} lead it).", ""]

    from gtc import profiles
    element_of = {k: v.get("element") for k, v in am.game.items()}
    by_mode = profiles.all_plans(cands, element_of)
    labels = {"abyss": "Spiral Abyss (two teams, single target and AoE)", "stygian": "Stygian Onslaught (one team, single target)",
              "general": "General (four teams)", "theater": "Imaginarium Theater (breadth across characters and elements)"}
    out += ["## By content mode", "",
            "The same teams, weighted for what each mode rewards. Scores are decision scores (risk-adjusted), used to "
            "compare plans within a mode, not team power; Theater counts competent teams over distinct characters and "
            "scales by element coverage.", "",
            "| Mode | Score | Teams |", "|---|---|---|"]
    for name, pp in by_mode.items():
        teams = "; ".join(" / ".join(a.team.members) for a in pp.teams) or "none"
        out.append(f"| {labels.get(name, name)} | {pp.score:.0f} | {teams}{(' (' + pp.note + ')') if pp.note else ''} |")
    out.append("")
    ab = by_mode.get("abyss")
    if ab and len(ab.frontier) > 1:
        out += ["**Spiral Abyss trade-offs** (two-team plans no other plan beats on both halves; the planner picks the "
                "most balanced, since both halves must be cleared):", ""]
        out += [f"- {v1:.0f} / {v2:.0f}: " + "; ".join(" / ".join(t) for t in teams) for v1, v2, teams in ab.frontier]
        out.append("")
    gen = by_mode.get("general")
    if gen and gen.core:
        best = gen.teams[0]
        out += [f"**Locked core of {' / '.join(best.team.members)}:** " + ", ".join(
            f"{m} (-{loss:.0%} without them)" for m, loss in sorted(gen.core.items(), key=lambda x: (-x[1], x[0])))
                + ". The other slots can be swapped with little loss.", ""]

    out += ["## Main damage dealers", ""]
    if len(carries) >= 2:
        out.append("You own enough real carries for two Spiral Abyss halves: " + ", ".join(
            f"{n} ({a.expected_power:.0f})" for n, a in sorted(carries.items(), key=lambda x: (-x[1].potential, x[0]))) + ".")
    else:
        out.append(f"**Carry gap:** you own {len(carries)} carry with a team reaching potential {VIABLE_CARRY_POTENTIAL:.0f}"
                   + (f" ({', '.join(carries)})" if carries else "") + ". Two are needed for Spiral Abyss.")
    out += ["", "Carries that would get the most from the supports you already own:", ""]
    def _cov(a) -> str:
        c = a.evaluation.coverage if a.evaluation else {}
        if not c or c.get("status") == "complete":
            return ""
        return f" Mechanics coverage {c['status']}: " + "; ".join(c.get("missing", [])[:2]) + "."

    out += [f"- **{n}**: {' / '.join(a.team.members)} ({a.label}), expected power {a.expected_power:.0f} "
            f"± {a.estimate.sd:.0f} ({a.estimate.tier}).{_cov(a)}" for n, a in best_carries]
    out.append("")

    out += ["## Characters that would change your account the most", "",
            "Value is the literal change in your plan when the character joins, fully built at C0; no label discounts it. "
            "Kind and Why describe what changed: best and second team gains, new mechanics, which owned characters "
            "improve or are displaced, and which supports the new character competes for.", "",
            "Gain is the expected change with one standard deviation and the weakest evidence tier behind it. "
            "Confidence is the probability that the gain is real; below 80% it is a lean, not a verdict. It is capped "
            "when the teams behind the gain rely on a mechanic (RES shred, an element-specific buff) that the pair model "
            "has never fitted with that team's damage dealer: mechanics coverage is then partial (cap 80%) or unknown "
            "(cap 65%), and the statistical confidence is shown beside it.", "",
            "Standing groups the pulls by what the evidence can separate, comparing each with the leader: a clear "
            "recommendation beats every alternative; competitive candidates cannot be separated from the leader, so "
            "their order is not a ranking; lower-value candidates are meaningfully below the leader.", "",
            "| Character | Standing | Gain | Confidence | Kind | Why |", "|---|---|---|---|---|---|"]
    standing = pull_groups(values[:top])
    for v in values[:top]:
        why = " ".join(v.explanation) + (f" {v.weapon_note}" if v.weapon_note else "")
        e = v.estimate
        gain = f"{e.value:+.1f} ± {e.sd:.1f} ({e.tier})" if e else f"{v.gain:+.1f}"
        conf = f"{v.confidence:.0%}" + (f" (statistical {v.statistical_confidence:.0%}; mechanics {v.coverage})"
                                         if v.coverage != "complete" else "")
        if v.coverage_missing:
            why += " Not represented in the evidence: " + "; ".join(v.coverage_missing[:3]) + "."
        prov = _provisional_note(v.team) if v.team else ""
        if prov:
            why = prov + " " + why
        out.append(f"| {v.name} | {standing.get(v.name, LOWER)} | {gain} | {conf} | {v.kind} | {why} |")
    if len(values) >= 2 and values[0].estimate and values[1].estimate:
        from gtc.decision import compare_words
        from gtc import coverage

        competitive = [v.name for v in values[:top] if standing.get(v.name) == COMPETITIVE]
        if competitive:
            out += ["", "**Competitive, so their order above is not a ranking:** " + ", ".join(competitive) + "."]
            pool = [v for v in values[:top] if standing.get(v.name) == COMPETITIVE and v.estimate]
            solid = max(pool, key=lambda v: (v.confidence, -ord(v.estimate.tier[0]), v.gain))
            out += [f"Strongest evidence among them: {solid.name} ({solid.estimate.tier}, {solid.confidence:.0%} that the "
                    f"gain is real). That is about the evidence, not a ranking."]
        elif standing.get(values[0].name) == CLEAR:
            out += ["", f"**Clear recommendation:** {values[0].name}."]
        limit = coverage.cap(1.0, coverage.worst([values[0].coverage, values[1].coverage]))
        out += ["", f"**{values[0].name} against {values[1].name}:** {compare_words(values[0].estimate, values[1].estimate, limit)}."]
    out += ["", "Best support and best carry, separately:", ""]
    sup = next((v for v in values if not v.is_carry), None)
    car = next((v for v in values if v.is_carry), None)
    if car:
        out.append(f"- **Carry:** {car.name} ({car.estimate.value if car.estimate else car.gain:+.1f}, {car.kind}).")
    if sup:
        out.append(f"- **Support:** {sup.name} ({sup.estimate.value if sup.estimate else sup.gain:+.1f}, {sup.kind}).")
    out.append("")
    if blind_provisional:
        out += ["**Provisional kits, but no estimate for your account:** " + ", ".join(blind_provisional) + ". They have no "
                "simulations yet, and none of the teams you could build with them is within two members of a team Prydwen "
                "lists for them, so the engine does not guess.", ""]
    if blind:
        tiers = an.evidence.prydwen.get("tiers", {})
        out += ["**Cannot evaluate yet** (no simulations and no kit numbers): " + ", ".join(
            f"{n} ({'/'.join(e['overall'] for e in tiers.get(n, []) if e.get('overall')) or 'unrated'})" for n in blind) + ".", ""]

    out += ["## What to do, in order", "",
            "From an account review of the four teams above, treated as one plan: no suggestion moves a character between them.", "", "(A) means gcsim ran your own builds on the community rotation. Those runs are precise as simulations, but the number leaves out uncertainty about the rotation and about the community-standard build it compares against, so no ± is shown; treat it as a measured direction and rough size.", "",
            "| # | Change | Team | Gain | Effort |", "|---|---|---|---|---|"]
    seen, rank = set(), 0
    for f in sorted(review.actions(), key=lambda f: (-(f.gain or 0), not f.measured)):
        key = (f.character, f.category if f.category not in ("set", "main stat", "crit") else "artifacts")
        if f.gain is None or f.gain < 0.02 or key in seen:
            continue
        seen.add(key)
        rank += 1
        out.append(f"| {rank} | {f.text} | {f.team} | {f.gain_label} | {f.effort} |")
        if rank >= 12:
            break
    timing.stop("content modes and rendering")
    return "\n".join(out)
