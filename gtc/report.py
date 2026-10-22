"""Build the account analysis and render it as Markdown.

Four measures per team. Each says where its number came from.

  Archetype tier   How strong the archetype is at its best, compared with every other archetype.
                   100 = the strongest teams in the game under standard assumptions. Not about your account.
  Lineup fit       How close these four come to the best lineup for the same carry. Not about investment.
  Build progress   How much of these four's fully built strength you already have. Only about investment.
  Team rating      Archetype tier x Lineup fit x Build progress, adjusted for execution difficulty.
                   The one number that compares any two of your teams.
"""
from __future__ import annotations

from gtc import params

from collections import defaultdict
from dataclasses import dataclass, field

from gtc import gamedata
from gtc.evidence import PRYDWEN_TIER_VALUE, Evidence, Measure, expert_level, fit_calibration, is_coarse, signature_ok
from gtc.investment import Investment, rate
from gtc.knowledge import Knowledge, Template
from gtc.snapshot import Snapshot
from gtc.teams import Incomplete, Member, Team, evaluate_lineup, fill_template, find_incomplete, ideal_team

BUILT_THRESHOLD = params.get("report.built_threshold")
# Ranking subtracts RISK x sd from each team's expected potential (the decision policy, gtc/decision.py). The sds are measured per
# evidence tier on held-out lineups; this replaced the fixed discounts of phase 1 and 2.
CANDIDATES_PER_TEMPLATE = params.get("report.candidates_per_template")


@dataclass
class Assessment:
    team: Team
    tier: Measure
    fit: Measure
    build: float
    rating: float
    execution: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    lead: str = ""
    potential: float = 0.0  # ranking value: expected potential minus RISK x sd (see `estimate`)
    estimate: object = None  # gtc.estimate.Estimate of the potential: expected value, sd and evidence tier
    power: dict = field(default_factory=dict)  # {"single_target", "aoe": Estimate, "sustain": 0-100}, see team_power
    evaluation: object = None  # gtc.evaluate.TeamEvaluation behind this assessment
    account: dict = field(default_factory=dict)  # {meta, current, ceiling} on this account (gtc/account_power.py)

    # Two different numbers, kept apart: `expected_power` is what the team is expected to deal and is the only power
    # number shown to the user; `decision_utility` (= potential, expected minus RISK x sd) is what plans and rankings
    # maximise, and is never printed as if it were the team's strength.
    @property
    def expected_power(self) -> float:
        return self.estimate.value if self.estimate is not None else self.potential

    @property
    def decision_utility(self) -> float:
        return self.potential

    @property
    def label(self) -> str:
        """The team's name from its identity (phase 8); the template's label only when no identity exists."""
        e = self.evaluation
        return (e.identity.get("label") if e and e.identity else None) or self.team.template.label

    @property
    def primary_actor(self) -> str | None:
        e = self.evaluation
        return e.identity.get("primary_actor") if e and e.identity else None

    @property
    def today_power(self) -> float:
        """Expected power at today's build progress (display; `rating` is the decision version)."""
        return self.expected_power * self.build / 100


@dataclass
class Analysis:
    snapshot: Snapshot
    investments: dict[str, Investment]
    evidence: Evidence
    my_teams: list[tuple[list[str], Assessment | None]]
    per_archetype: list[Assessment]
    incomplete: list[Incomplete]
    abyss_pair: tuple[Assessment, Assessment] | None
    build_priorities: list[tuple[str, float, list[str]]]
    bench: list[str]
    unknown: list[str]
    review: list[str]
    disagreements: list[str]
    coarse_ids: set[str] = field(default_factory=set)
    roster: list[Member] = field(default_factory=list)
    model: "Model | None" = None


def build_universe(kb: Knowledge, ev: Evidence | None = None) -> list[Member]:
    """Every tagged character in the game, fully built, at the community standard: 5-stars at C0
    and 4-stars at C6, the same assumptions gcsim and Prydwen comparisons use."""
    game = gamedata.load_characters()
    out = []
    for k, info in kb.characters.items():
        if k in game:
            con = 6 if game[k]["rarity"] == 4 else 0
            roles = {**info.roles_at(con), **(ev.faction_roles(k) if ev else {})}
            out.append(Member(k, game[k]["element"], 1.0, roles, con))
    return out


def load_evidence(kb: Knowledge) -> Evidence:
    from gtc.sources import gcsim_db, kqm, prydwen

    return Evidence(kb, gamedata.load_characters(), gcsim_db.load(), prydwen.load(), kqm.load())


class Model:
    """Our own lineup-fit estimate: model potential of a lineup over the model's ideal team for that lead."""

    def __init__(self, kb: Knowledge, universe: list[Member]):
        self.kb, self.universe = kb, universe
        self.by_key = {m.key: m for m in universe}
        self._ideal: dict[tuple[str, str | None], Team | None] = {}

    def ideal(self, template: Template, lead: str | None) -> Team | None:
        key = (template.id, lead)
        if key not in self._ideal:
            self._ideal[key] = ideal_team(template, self.universe, self.kb, lead=lead)
        return self._ideal[key]

    def fit(self, template: Template, lineup: list[str], lead: str) -> float | None:
        if any(k not in self.by_key for k in lineup):
            return None
        members = [self.by_key[k] for k in lineup]
        for fixed in ([lead, None] if template.compare == "lead" else [None]):
            teams = fill_template(template, members, self.kb, limit=1, lead=fixed, rank_by="potential")
            ideal = self.ideal(template, fixed)
            if teams and ideal:
                return min(100.0, 100 * teams[0].potential / ideal.potential)
        return None


def calibrate(ev: Evidence, model: Model, kb: Knowledge, leads: set[str]) -> None:
    """Collect every lineup that both the model and a source can score, then fit the calibration."""
    anchors = []
    for t in kb.templates.values():
        for lead in leads:
            pool = ev.sims_for(t, lead)
            if not pool:
                continue
            top = max(s.dps for s in pool)
            best_by_lineup: dict[frozenset, float] = {}
            for s in pool:
                best_by_lineup[s.names] = max(best_by_lineup.get(s.names, 0), s.dps)
            for names, dps in best_by_lineup.items():
                if lead is not None and lead not in names:
                    continue
                m = model.fit(t, sorted(names), lead)
                if m is not None:
                    anchors.append((f"{' / '.join(sorted(names))} ({t.label})", t.id, lead, m, 100 * dps / top))
    for lead in (x for x in leads if x):
        for team in ev.prydwen.get("characters", {}).get(lead, {}).get("teams", []):
            lineup = [m["name"] for m in team["members"]]
            for t in kb.templates.values():
                m = model.fit(t, lineup, lead)
                if m is not None and signature_ok(t, [ev.element(n) for n in lineup]):
                    anchors.append((f"{' / '.join(lineup)} (Prydwen)", t.id, lead, m, team["percent"]))
                    break
    ev.calibration = fit_calibration(anchors, {t.id for t in kb.templates.values() if is_coarse(t)})


def pair_model_fit(t: Template, lineup: list[str], lead: str | None, ev: Evidence) -> Measure | None:
    """Lineup fit from the fitted character and pair effects (gtc/pairmodel.py): predicted team DPS over the
    best simulated lineup of the same carry and archetype, the same basis as a measured fit. Held out, its median
    error is 6.2% one member from a simulated lineup and 11% two or more away; `anchored` marks the first case."""
    from gtc.pairmodel import load

    pm = load()
    pool = ev.sims_for(t, lead, standard=True)
    if pm is None or not pool or not pm.known(lineup):
        return None
    from gtc.evaluate import unseen_carry_pair

    if unseen_carry_pair(lineup, pm, ev):  # outside what the pair model was validated on
        return None
    pred = pm.predict(lineup, lead)
    top = max(ev.lineup_median.get(s.names, s.dps) for s in pool)
    if not pred or not top:
        return None
    pairs = sorted(((pm.pair_effect(a, b), a, b) for a in lineup for b in lineup if a < b and pm.pair_effect(a, b)),
                   key=lambda x: -abs(x[0][0]))[:2]
    note = "; ".join(f"{a} + {b} {e[0]:+.0%}" for e, a, b in pairs)
    near = max(len(s.names & set(lineup)) for s in pool) >= len(lineup) - 1
    return Measure(min(100.0, 100 * pred / top), "pairmodel",
                   f"fitted character and pair effects predict {pred / 1000:.0f}k DPS against {top / 1000:.0f}k for the best "
                   f"simulated {lead or 'team'} lineup" + (f" (strongest pairs: {note})" if note else ""), anchored=near)


def anchored_fit(t: Template, lineup: list[str], lead: str, ev: Evidence, model: Model) -> Measure | None:
    """Estimate an unsimulated lineup from the most similar simulated lineups of the same carry: their
    measured fit, scaled by the ratio of the two lineups on the calibrated curve (the raw model compresses
    differences between teammates; the curve fitted on measurements expands them). Only lineups one member
    away count, and the lowest estimate wins. Otherwise the calibrated estimate stands."""
    cache = ev.__dict__.setdefault("_anchor_cache", {})
    key = (t.id, frozenset(lineup), lead)
    if key in cache:
        return cache[key]
    # The pair model first (the one-member swap estimate it replaced was deleted in phase 10).
    result = pair_model_fit(t, lineup, lead, ev)
    if result is not None:
        cache[key] = result
        return result
    m_new = model.fit(t, lineup, lead)
    if m_new:
        options: dict[int, list[tuple[float, frozenset]]] = {}
        for names in {s.names for s in ev.sims_for(t, lead, standard=True)}:
            shared = len(names & set(lineup))
            if shared < 2 or names == frozenset(lineup):
                continue
            m_anchor = model.fit(t, sorted(names), lead)
            measured = ev.measured_fit(t, sorted(names), lead) if m_anchor else None
            if measured and measured.value:
                est = measured.value * ev.calibration.curve_for(m_new, t.id) / ev.calibration.curve_for(m_anchor, t.id)
                options.setdefault(shared, []).append((est, names))
        if options:
            # Closest lineups first (one member away); if none, any sharing two or more members. The lowest estimate
            # wins: an untested lineup should never outrank a tested one through the model's optimism.
            shared = max(options)
            best = options[shared]
            est, names = min(best, key=lambda x: x[0])
            away = len(lineup) - shared
            result = Measure(min(100.0, est), "model", f"estimated from the simulated lineup {' / '.join(sorted(names))}, "
                             f"{away} member{'s' if away > 1 else ''} away, on the calibrated scale"
                             + (f" (lowest of {len(best)} such estimates)" if len(best) > 1 else ""))
            if away > 1:
                # Further away: also compare with every anchor sharing at least two members, and keep the lowest.
                floor = min(e for opts in options.values() for e, _ in opts)
                if floor < est:
                    result = Measure(min(100.0, floor), "model", result.detail + "; capped by the most conservative simulated comparison")
    cache[key] = result
    return result


def assess(team: Team, ev: Evidence, model: Model, kb: Knowledge) -> Assessment:
    """The team evaluation (gtc/evaluate.py) in the shape the report, planner and pulls read."""
    from gtc.evaluate import evaluate

    e = evaluate(team, ev, model, kb)
    t = team.template
    # The team's lead is its identity's primary actor (phase 8), whatever template generated it; the template's lead
    # stays only where identity names no single carry.
    lead = e.identity.get("primary_actor") or e.identity["template_lead"]
    tier, fit, best_sim, tags = (e.explanation[k] for k in ("tier", "fit", "best_sim", "execution"))
    build = 100 * team.current / team.potential if team.potential else 0.0
    # Every number is an estimate with a measured sd and evidence tier. Teams are ranked by expected potential
    # minus RISK x sd: an optimizer that picks the best of many estimates otherwise favours whichever happens
    # to be overestimated (the winner's curse), and the penalty grows with how uncertain the evidence is.
    power = {k: p.as_estimate() for k, p in e.power.items()}
    est = power["single_target"]
    power["sustain"] = e.sustain
    from gtc.decision import utility

    potential = max(0.0, utility(est))
    rating = potential * build / 100

    evidence = []
    if best_sim is not None and best_sim.names != frozenset(team.members):
        tlead = e.identity["template_lead"]  # the archetype pool the best lineup comes from
        who = f"{tlead} lineup" if tlead else "lineup without a single carry"
        evidence.append(f"Best simulated {who} for this archetype: {' / '.join(sorted(best_sim.names))}.")
    pt = ev.prydwen_tier(lead)
    if pt:
        sty = ", ".join(x for x in pt["stygian"] if x) or "unrated"
        evidence.append(f"Prydwen rates {lead} {pt['overall']} as {pt['category']} (assumes {pt['assumed_constellation']}), Stygian Onslaught {sty}.")
    evidence += ev.kqm_mentions(team.members)
    notes = [f"{m}: {n.text}" for m in team.members for n in kb.characters[m].notes if n.templates is None or t.id in n.templates]
    return Assessment(team, tier, fit, round(build), round(rating, 1), tags, evidence, notes, lead, round(potential, 1), est,
                      power, e)


def team_power(team: Team, est, kb: Knowledge) -> dict:
    """Team power by dimension. Single target is the potential estimate. AoE scales it by the team's measured
    (or member-predicted) three-target ratio relative to the median team, so an average team keeps its value
    and a team built on single-target damage loses some; a member-predicted ratio drops the evidence to at least
    tier D. Sustain is the best healer or shield quality on the team, 0 to 100."""
    from gtc import aoe
    from gtc.estimate import Estimate, worst_tier

    out = {"single_target": est}
    ref = aoe.reference_ratio()
    if est is not None and ref:
        ratio, source = aoe.lineup_ratio(team.members)
        f = ratio / ref
        tier = est.tier if source == "measured" else worst_tier([est.tier, "D"])
        out["aoe"] = Estimate(est.value * f, est.sd * f, tier, est.sources + [f"AoE ratio {ratio:.2f} ({source})"])
    roles = kb.scoring.get("sustain_roles", ["healer", "shield"])
    best = max((f.member.roles.get(r, 0) for f in team.fills for r in roles), default=0)
    out["sustain"] = 20.0 * best
    return out


def potential_estimate(t: Template, lineup: list[str], lead, tier: Measure, best_sim, fit: Measure, ev: Evidence,
                       kb: Knowledge):
    """Expected potential (archetype tier x lineup fit), its sd and evidence tier."""
    from gtc import estimate

    if tier.value is None or fit.value is None or fit.source == "none":
        return estimate.Estimate(0.0, 0.0, "F", [])
    best_n = ev.lineup_n.get(best_sim.names, 1) if best_sim is not None else 1
    if tier.source == "gcsim":
        tier_est = estimate.Estimate(tier.value, tier.value * estimate.community_rel_sd(best_n), "B", ["gcsim"])
    else:  # a Prydwen tier-list rating standing in for missing simulations
        tier_est = estimate.Estimate(tier.value, ev.calibration_sd(kb)[1], "E", ["Prydwen tier list"])
    mine_n = ev.lineup_n.get(frozenset(lineup), 1)
    is_top = best_sim is not None and best_sim.names == frozenset(lineup)
    fit_est = estimate.fit_estimate(fit, mine_n, best_n, is_top, ev.calibration_sd(kb))
    if fit.source == "gcsim" and tier.source == "gcsim":
        # Both are medians over the same best lineup, so its noise cancels: potential = this lineup's median
        # over the normalizer, which carries only this lineup's own noise.
        value = tier.value * fit.value / 100
        return estimate.Estimate(value, value * estimate.community_rel_sd(mine_n), "B", ["gcsim"])
    return estimate.combine(tier_est, fit_est)


def analyze(snapshot: Snapshot, kb: Knowledge, ev: Evidence | None = None) -> Analysis:
    ev = ev or load_evidence(kb)
    investments = {c.key: rate(c, kb.characters.get(c.key), kb.scoring, ev.kqm.get(c.key)) for c in snapshot.characters}
    roster = [
        Member(c.key, c.element, investments[c.key].total,
               {**kb.characters[c.key].roles_at(c.constellation), **ev.faction_roles(c.key)}, c.constellation)
        for c in snapshot.characters if c.key in kb.characters
    ]
    model = Model(kb, build_universe(kb, ev))
    # Each template's best few lineups, searched once with the exact pruned search (identical to enumerating
    # everything and keeping the top CANDIDATES_PER_TEMPLATE) and reused below.
    top_teams = {t.id: fill_template(t, roster, kb, limit=CANDIDATES_PER_TEMPLATE) for t in kb.templates.values()}
    leads: set[str] = set()
    for t in kb.templates.values():
        for team in top_teams[t.id]:
            leads.add(ev.damage_lead(team))
    calibrate(ev, model, kb, leads)

    my_teams = []
    for keys in kb.my_teams:
        team = evaluate_lineup(keys, roster, kb)
        my_teams.append((keys, assess(team, ev, model, kb) if team else None))

    per_archetype, incomplete, candidates = [], [], []
    for t in kb.templates.values():
        teams = top_teams[t.id]
        if not teams:
            inc = find_incomplete(t, roster, kb)
            if inc:
                incomplete.append(inc)
            continue
        assessed = [assess(x, ev, model, kb) for x in teams]
        candidates += assessed
        per_archetype.append(max(assessed, key=lambda a: a.rating))
    per_archetype.sort(key=lambda a: (-a.rating, sorted(a.team.members)))

    pair, best_sum = None, -1.0
    ranked = sorted(candidates, key=lambda a: -a.rating)
    for i, a in enumerate(ranked):
        for b in ranked[i + 1:]:
            if a.rating + b.rating <= best_sum:
                break
            if not set(a.team.members) & set(b.team.members):
                pair, best_sum = (a, b), a.rating + b.rating
                break

    # Build priorities: team rating each character is holding back, over the best team of each archetype.
    # Stronger archetypes count more because the loss is scaled by archetype tier. Your own teams count double.
    gap: dict[str, float] = defaultdict(float)
    used_in: dict[str, set[str]] = defaultdict(set)
    floor = kb.scoring["investment_floor"]
    for a, mult in [(a, 1.0) for a in per_archetype] + [(a, 2.0) for _, a in my_teams if a]:
        team = a.team
        total_w = sum(f.slot.weight for f in team.fills)
        scale = (a.tier.value or 0) / 100 * (a.fit.value or 0) / 100
        for f in team.fills:
            share = f.slot.weight * (f.quality / 5) * (1 - floor) * (1 - f.member.investment) / total_w
            gap[f.member.key] += mult * 100 * scale * share * team.template.ceiling
            used_in[f.member.key].add(team.template.label)
    priorities = sorted(((k, round(v, 1), sorted(used_in[k])) for k, v in gap.items() if v >= 1), key=lambda x: -x[1])

    disagreements = []
    for a in per_archetype:
        pt = ev.prydwen_tier(a.lead)
        if a.tier.source == "gcsim" and pt and pt["category"] == "DPS":
            p = PRYDWEN_TIER_VALUE[pt["overall"]]
            if abs(p - a.tier.value) >= 20:
                disagreements.append(f"{a.team.template.label} led by {a.lead}: gcsim puts the archetype at {a.tier}, Prydwen rates {a.lead} {pt['overall']} (about {p}).")

    owned = {c.key for c in snapshot.characters}
    return Analysis(
        snapshot=snapshot, investments=investments, evidence=ev, my_teams=my_teams, per_archetype=per_archetype,
        incomplete=incomplete, abyss_pair=pair, build_priorities=priorities,
        bench=sorted(k for k in owned if k in kb.characters and k not in used_in),
        unknown=sorted(k for k in owned if k not in kb.characters),
        review=sorted(k for k, i in kb.characters.items() if i.review and k in owned),
        disagreements=disagreements, coarse_ids={t.id for t in kb.templates.values() if is_coarse(t)},
        roster=roster, model=model,
    )


SOURCE_LABEL = {"gcsim": "gcsim", "prydwen": "Prydwen", "pairmodel": "pair model",
                "model": "estimate", "none": "no data"}


def _line(t: Team) -> str:
    return " / ".join(t.members)


def _m(m: Measure) -> str:
    return f"{m} ({SOURCE_LABEL[m.source]})"


def render(a: Analysis) -> str:
    s, ev = a.snapshot, a.evidence
    built = sum(1 for i in a.investments.values() if i.total >= BUILT_THRESHOLD)
    pr = ev.prydwen
    out = [
        f"# Team report for UID {s.uid}",
        "",
        f"Engine model {params.version()} ({params.fingerprint()}).",
        "",
        f"Snapshot from {s.source}, taken {s.taken_at}. {len(s.characters)} characters owned, {built} rated at least {BUILT_THRESHOLD:.0%} invested.",
        "",
        "## How to read this",
        "",
        "- **Archetype tier** is how strong the archetype is at its best, compared with every other archetype. 100 is the strongest teams in the game. It says nothing about your account.",
        "- **Lineup fit** is how close your four come to the best lineup for the same carry. Investment does not affect it.",
        "- **Build progress** is how much of these four's fully built strength you already have.",
        "- **Team rating** is the team's expected power at today's build: its expected power at full build (from this lineup's own simulations, or the pair model) times build progress, with a small penalty when Prydwen marks the carry as needing expert play. Tier and fit explain where the full-build number sits. It is the one number that compares any two of your teams.",
        "",
        "Each number names its source: **gcsim** is simulated damage, **Prydwen** is their published figure, and **estimate** is this engine's own model, calibrated against the measured numbers.",
        "",
        "## Your teams",
        "",
    ]
    for keys, x in a.my_teams:
        if x is None:
            out += [f"**{' / '.join(keys)}** did not match any template. Check the names or add a template.", ""]
            continue
        out += _team_block(x, a)

    out += ["## Every archetype on your account", "",
            "Best team you own per archetype, ranked by team rating.", "",
            "| Archetype | Best team you own | Archetype tier | Lineup fit | Build | Team rating |", "|---|---|---|---|---|---|"]
    for x in a.per_archetype:
        out.append(f"| {x.label} | {_line(x.team)} | {_m(x.tier)} | {_m(x.fit)} | {x.build}% | **{x.today_power:.0f}** |")
    out.append("")

    if a.abyss_pair:
        t1, t2 = a.abyss_pair
        out += ["## Best Spiral Abyss pair", "",
                f"- **First half:** {_line(t1.team)}, as {t1.label}. Team rating {t1.today_power:.0f}.",
                f"- **Second half:** {_line(t2.team)}, as {t2.label}. Team rating {t2.today_power:.0f}.", ""]

    out += ["## Build priorities", "",
            "How much team rating each character is holding back through low investment, summed over your best team in each archetype. Your own teams count double.", "",
            "| Character | Investment | Rating held back | Used in |", "|---|---|---|---|"]
    for k, v, teams in a.build_priorities[:12]:
        out.append(f"| {k} | {a.investments[k].total:.0%} | {v} | {', '.join(teams)} |")
    out.append("")

    out += ["## Archetypes you cannot build yet", ""]
    if not a.incomplete:
        out.append("Every template can be filled.")
    for inc in a.incomplete:
        if inc.missing:
            needs = "; ".join(f"{sl.name} ({', '.join(sl.elements or ['any element'])}, quality {sl.min_quality}+)" for sl in inc.missing)
            out.append(f"- **{inc.template.label}** is missing: {needs}.")
        else:
            out.append(f"- **{inc.template.label}** cannot be completed: {inc.reason}.")
    out.append("")

    cal = ev.calibration
    coarse = a.coarse_ids
    out += ["## Engine check", ""]
    if cal.anchors:
        out += [f"The model's lineup-fit estimates were compared with {len(cal.anchors)} measured lineups from gcsim and Prydwen.", "",
                "| | Average error |", "|---|---|",
                f"| Raw model | {cal.error(False, coarse):.0f} points |",
                f"| Calibrated per archetype | {cal.error(True, coarse, local=False):.0f} points |",
                f"| Plus per-carry correction, tested leave-one-out | {cal.error(True, coarse):.0f} points |", ""]
        worst = sorted(cal.anchors, key=lambda x: -abs(cal.apply(x[3], x[1], x[1] in coarse, x[2]) - x[4]))[:5]
        out += ["Largest remaining misses, worth reviewing in the knowledge files:", ""]
        out += [f"- {name}: estimate {cal.apply(mv, tid, tid in coarse, lead):.0f}, measured {mm:.0f}." for name, tid, lead, mv, mm in worst]
        out.append("")
    else:
        out += ["No measured lineups overlap with the model yet, so estimates are uncalibrated.", ""]
    if a.disagreements:
        out += ["Sources disagree on these archetypes:", ""] + [f"- {d}" for d in a.disagreements] + [""]

    out += ["## Sources", "",
            f"- **gcsim database** (db.kqm.gg): {len(ev.sims)} accepted single-target simulations, {len(ev.standard)} under standard assumptions.",
            f"- **Prydwen**: tier list for version {pr.get('version')}, updated {pr.get('tier_list_updated')}. {len(pr.get('characters', {}))} character guides.",
            f"- **Keqing Mains**: {len(ev.kqm)} quickguides.", ""]

    out += ["## Not used by any top team", "", ", ".join(a.bench) or "None.", ""]
    if a.unknown:
        out += ["## Missing from the knowledge base", "", "Add these to characters.yaml: " + ", ".join(a.unknown) + ".", ""]
    if a.review:
        out += ["## Entries flagged for your review", "", "I was unsure about these tags in characters.yaml: " + ", ".join(a.review) + ".", ""]
    return "\n".join(out)


def _team_block(x: Assessment, a: Analysis) -> list[str]:
    t = x.team
    out = [f"### {_line(t)}", "", f"Recognised as *{t.template.label}*.", "",
           "| Archetype tier | Lineup fit | Build progress | Team rating |", "|---|---|---|---|",
           f"| {_m(x.tier)} | {_m(x.fit)} | {x.build}% | **{x.today_power:.0f}** |", "",
           f"- **Archetype tier:** {x.tier.detail}.",
           f"- **Lineup fit:** {x.fit.detail}."]
    if x.execution and x.lead:
        out.append(f"- **Execution:** Prydwen tags {x.lead} as {', '.join(x.execution)}.")
    out.append("")
    if x.evidence:
        out += ["Evidence:", ""] + [f"- {e}" for e in x.evidence] + [""]
    if x.notes:
        out += ["Notes, not scored:", ""] + [f"- {n}" for n in x.notes] + [""]
    return out
