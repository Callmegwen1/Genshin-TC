"""Team evaluation: one record per candidate team, built by one explicit pipeline.

    validity    legal team, the generating template (provenance), typicality, and how well supported the number is
    structure   measured damage structure of this exact lineup, else predicted from members' capabilities
    identity    archetype, label and damage lead (today: from the generating template; phase 8 replaces it)
    power       expected power per content context, each with its sd and the evidence behind it
    explanation tier and fit ("78% of Flins' best lineup"), the template-based estimate, evidence lines

The template that generated a candidate is provenance (`generated_by`), not identity. Power does not depend on it
whenever the evidence allows (see `lineup_power`): the same four characters get the same power whichever archetype
produced them.

Power is on the archetype tier scale: expected team DPS over the meta normaliser (the mean of the three strongest
standard lineups) x 100, capped at 100. Contexts: "single_target" and "aoe" (single target scaled by the lineup's
three-target ratio over the median team's). Sustain is not power and is kept apart.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from gtc.estimate import Estimate
from gtc.validity import MANUAL_ID, support


@dataclass(frozen=True)
class Basis:
    """Where a power number comes from (the plan's `Evidence`; renamed because gtc.evidence.Evidence is the source data).

    route: exact_community (this lineup's own community simulations), pair_model (fitted character and pair effects),
           role_rules (template role tags calibrated on simulations), none."""
    route: str
    tier: str
    sd_relative: float
    nearest_simulated: frozenset | None = None
    member_distance: int = 0
    functional_distance: float = 0.0  # set by the routing step (phase 10); 0 until then
    sources: tuple[str, ...] = ()
    flags: tuple[str, ...] = ()  # "mixed_builds": the exact data mixes build assumptions (see estimate.exact_rel_sd)
    between_build_sd: float = 0.0  # relative sd from disagreement between those builds, included in sd_relative
    quality: str = ""  # community evidence quality (exact_community): good | unconfirmed | mixed | poor (model 6.4)
    quality_reasons: tuple[str, ...] = ()

    @property
    def evidence_state(self) -> str:
        """simulation, interpolation, kit-model or rules-only (phase 13; gtc/kit_schema.EVIDENCE_STATE)."""
        from gtc.kit_schema import evidence_state

        return evidence_state(self.route)


@dataclass(frozen=True)
class PowerEstimate:
    expected: float
    sd: float
    basis: Basis

    def as_estimate(self) -> Estimate:
        return Estimate(self.expected, self.sd, self.basis.tier, list(self.basis.sources))


@dataclass
class TeamEvaluation:
    lineup: frozenset
    generated_by: str
    validity: dict
    structure: dict | None
    identity: dict
    power: dict[str, PowerEstimate]
    sustain: float = 0.0
    explanation: dict = field(default_factory=dict)
    # Mechanics coverage (gtc/coverage.py, temporary): {"status": complete | partial | unknown, "missing": [...]}
    coverage: dict = field(default_factory=dict)


def structure_of(lineup, ev) -> tuple[dict | None, bool]:
    """(structure, measured): this lineup's measured damage structure, else one predicted from members' capabilities."""
    from gtc.capabilities import load as load_caps, predict_structure

    st = ev.measured_structure(frozenset(lineup))
    if st is not None:
        return st, True
    caps = load_caps()
    if caps and all(m in caps for m in lineup):
        return predict_structure(list(lineup), caps), False
    return None, False


EXTRAPOLATED = ("pair_model", "role_rules", "provisional_kit")  # routes whose sd typicality widens (phase 9)
CARRY_STRUCTURES = ("hypercarry", "dual_carry")  # structures the pair model's lead effect was fitted on


def power_lead(structure: dict | None, types=CARRY_STRUCTURES) -> str | None:
    """The member whose damage the team is built around, from the structure alone (no template)."""
    if structure and structure.get("type") in types and structure.get("owners"):
        return structure["owners"][0]
    return None


def _neighbourhood(ev) -> dict:
    """Every three-member subset of a standard simulated lineup -> those lineups (for distance to the data)."""
    idx = ev.__dict__.get("_triples")
    if idx is None:
        from itertools import combinations

        idx = {}
        for names in ev.lineup_median:
            if len(names) == 4:
                for tri in combinations(sorted(names), 3):
                    idx.setdefault(frozenset(tri), []).append(names)
        ev._triples = idx
    return idx


def _together(ev) -> set[frozenset]:
    """Every pair of characters simulated together in some standard lineup."""
    pairs = ev.__dict__.get("_pairs_seen")
    if pairs is None:
        from itertools import combinations

        pairs = {frozenset(p) for names in ev.lineup_median for p in combinations(sorted(names), 2)}
        ev._pairs_seen = pairs
    return pairs


def unseen_carry_pair(lineup, pm, ev) -> tuple[str, str] | None:
    """Two characters who are mostly simulated as their team's damage owner and were never simulated together.
    The pair model adds their effects as if both could have the field; its accuracy was measured on lineups people
    simulate, which never contain such a pair, so it does not cover them (Mualani next to Neuvillette)."""
    from itertools import combinations

    seen = _together(ev)
    for a, b in combinations(sorted(lineup), 2):
        if pm.carry_like(a) and pm.carry_like(b) and frozenset((a, b)) not in seen:
            return a, b
    return None


def lineup_power(lineup, ev) -> PowerEstimate | None:
    """Single-target power of four characters, whatever template produced them, before execution difficulty:
      exact_community  this lineup's own standard community simulations: median over the normaliser (tier B); the
                       sd adds disagreement between build assumptions in full (estimate.exact_rel_sd)
      provisional_kit  members known only from a provisional kit: a simulated carry's Prydwen page, their own Prydwen
                       tier, or their analogue in their place (tier E, gtc/provisional.py)
      pair_model       predicted DPS over the normaliser when every member has been simulated (tier C one member
                       from a simulated lineup, D further), sd measured on held-out lineups against their own value;
                       not for two carries never simulated together (`unseen_carry_pair`)
    None when neither applies; the caller falls back to the template's role rules."""
    from gtc import estimate

    cache = ev.__dict__.setdefault("_power_cache", {})
    key = frozenset(lineup)
    if key in cache:
        return cache[key]
    out = None
    norm = ev.normalizer
    if norm and key in ev.lineup_median:
        value = min(100.0, 100 * ev.lineup_median[key] / norm)
        lv = getattr(ev, "lineup_values", {}).get(key)
        if lv is not None:
            rel, between = estimate.exact_rel_sd(lv)
            flags = ("mixed_builds",) if lv.mixed_builds else ()
        else:
            rel, between, flags = estimate.community_rel_sd(ev.lineup_n.get(key, 1)), 0.0, ()
        q, q_why = (estimate.community_quality(lv, key, ev.measured_structure(key), _caps())
                    if lv is not None else ("unconfirmed", []))
        out = PowerEstimate(value, value * rel, Basis("exact_community", "B", rel, key, 0, sources=("gcsim",),
                                                      flags=flags, between_build_sd=between, quality=q,
                                                      quality_reasons=tuple(q_why)))
    elif norm:
        from gtc.pairmodel import load

        pm = load()
        # Model 6.4 tested declining lineups below the simulated damage-capacity range and rejected it: the
        # validation's apparent 2.8x overprediction of pure-buffer lineups was mostly the simulation harness (a
        # removed carry's field time left idle; carry-removed swaps of community-simulated lineups land at 41% of
        # their community value), and held out the pair model predicts the 75 simulated low-capacity lineups
        # fine (p68 miss 17.5%). Such lineups keep a number, widened by the low_capacity typicality finding.
        if pm is not None and pm.known(key) and not unseen_carry_pair(key, pm, ev):
            st, _ = structure_of(key, ev)
            # The lead effect goes to the most probable carry. Averaging it over the structure distribution was
            # tested in phase 7 and scored worse on the calibration set (80.4% against 81.6%), so it is not used.
            pred = pm.predict(key, power_lead(st))
            if pred:
                # The sd comes from the lineup's functional distance to its nearest simulated lineup (phase 10:
                # members changed, capability and application deltas, a newcomer never simulated with the carry,
                # the data behind the least simulated member). The flat near/far sd is the fallback.
                from gtc import distance

                f, near, away = distance.for_lineup(key, ev)
                value = min(100.0, 100 * pred / norm)
                which = "near" if away <= 1 else "far"
                rel = distance.sd(f) or estimate._u("pair", which, "sd", default=estimate._FALLBACK[which])
                out = PowerEstimate(value, value * rel, Basis("pair_model", "C" if away <= 1 else "D", rel, near, away,
                                                              functional_distance=round(rel, 4), sources=("pair model",)))
        elif pm is not None and not pm.known(key):
            # A member was never simulated: a provisional kit (gtc/provisional.py) if one exists.
            from gtc.provisional import provisional_power

            out = provisional_power(key, ev)
    cache[key] = out
    return out


def _caps():
    from gtc.capabilities import load

    return load()


def _identity(members, ev, st, measured, template, lead) -> dict:
    """Identity v2 (gtc/identity.py) plus the generating template, kept as provenance only."""
    from gtc.identity import identify

    ident = dict(identify(members, ev, st, measured))
    ident.update({"archetype": template.id, "template_label": template.label, "template_lead": lead})
    return ident


def _unsimulated_provisional(members, kb) -> str | None:
    from gtc.pairmodel import load

    pm = load()
    for m in members:
        info = kb.characters.get(m)
        if info is not None and info.provisional and (pm is None or m not in pm.chars):
            return m
    return None


def evaluate(team, ev, model, kb) -> TeamEvaluation:
    """The pipeline: structure, then power from the lineup alone where the evidence allows, then the explanation
    through the generating template (tier and fit), which is also the fallback when a member was never simulated."""
    from gtc import report
    from gtc.coverage import lineup_coverage
    from gtc.evidence import expert_level

    t = team.template
    st, measured = structure_of(team.members, ev)
    lead = ev.damage_lead(team)
    tier, best_sim = ev.archetype_tier(t, lead)
    fit = ev.lineup_fit(t, team.members, lead, model.fit(t, team.members, lead))
    if fit.source == "model":
        fit = report.anchored_fit(t, team.members, lead, ev, model) or fit
    legacy = report.potential_estimate(t, team.members, lead, tier, best_sim, fit, ev, kb)
    base = lineup_power(team.members, ev)
    # Execution difficulty belongs to whoever the team's damage is built around, read from the structure.
    exec_lead = power_lead(st, CARRY_STRUCTURES + ("driver",)) if base is not None else lead
    tags = ev.execution_tags(exec_lead) if exec_lead else []
    exec_factor = 1 - kb.scoring.get("execution_penalty_per_level", 0.03) * expert_level(tags)
    provisional_member = _unsimulated_provisional(team.members, kb)
    if base is not None:
        est = base.as_estimate()
        basis = base.basis
    elif provisional_member:
        # A character known only from a provisional kit, in a team the provisional route will not value (a kit
        # restriction is broken, or the team is too far from anything to compare with): no number, rather than
        # the template's role-rules guess.
        from gtc.provisional import declined

        why = declined(ev, team.members) or f"{provisional_member} has only a provisional kit, and nothing to compare this team with"
        est = Estimate(0.0, 0.0, "F", [why])
        basis = Basis("none", "F", 0.0, sources=tuple(est.sources), flags=("provisional",))
    elif t.id == MANUAL_ID:
        # A hand-entered team no archetype generates: no template to take role rules from, so no number.
        est = Estimate(0.0, 0.0, "F", ["no simulations of this lineup, and the pair model cannot predict it "
                                       "(a member never simulated, or two carries never simulated together)"])
        basis = Basis("none", "F", 0.0, sources=tuple(est.sources))
    else:  # role rules through the generating template: the one route where the template still sets the number
        est = Estimate(legacy.value, legacy.sd, legacy.tier, list(legacy.sources))
        route = "none" if est.tier == "F" else "role_rules"
        basis = Basis(route, est.tier, est.sd / est.value if est.value else 0.0, sources=tuple(est.sources))
    # Typicality (phase 9): how unusual the lineup is widens the uncertainty of extrapolated estimates only; a
    # lineup measured by its own simulations keeps its measured sd.
    from gtc import typicality
    from gtc.structure import carry_probability

    prim = (st or {}).get("primary") or {}
    actor = max(prim, key=lambda m: (prim[m], m)) if prim and carry_probability(st) >= 0.5 else None
    found = typicality.findings(team.members, actor)
    widen = typicality.sd_factor(len(found)) if basis.route in EXTRAPOLATED else 1.0
    if widen != 1.0:
        est.sd *= widen
        basis = Basis(basis.route, basis.tier, basis.sd_relative * widen, basis.nearest_simulated, basis.member_distance,
                      basis.functional_distance, basis.sources, basis.flags + ("atypical",), basis.between_build_sd,
                      basis.quality, basis.quality_reasons)
    est.value *= exec_factor
    est.sd *= exec_factor
    power = report.team_power(team, est, kb)
    contexts = {k: PowerEstimate(v.value, v.sd, Basis(basis.route, v.tier, basis.sd_relative, basis.nearest_simulated,
                                                      basis.member_distance, sources=tuple(v.sources), flags=basis.flags,
                                                      between_build_sd=basis.between_build_sd, quality=basis.quality,
                                                      quality_reasons=basis.quality_reasons))
                for k, v in power.items() if isinstance(v, Estimate)}
    legacy_value = legacy.value * exec_factor
    return TeamEvaluation(
        lineup=frozenset(team.members),
        generated_by=t.id,
        validity={"ok": True, "mechanical": "legal four-character team", "generated_by": t.id, "typicality": found,
                  "sd_factor": round(widen, 3),
                  **dict(zip(("support", "support_reasons"),
                             support(basis.route, basis.tier, found, lineup_coverage(team.members, basis, st)[0],
                                     basis.quality, basis.quality_reasons)))},
        structure=None if st is None else {**st, "source": "measured" if measured else "predicted"},
        identity=_identity(team.members, ev, st, measured, t, lead),
        power=contexts,
        sustain=power.get("sustain", 0.0),
        coverage=dict(zip(("status", "missing"), lineup_coverage(team.members, basis, st))),
        explanation={"tier": tier, "fit": fit, "best_sim": best_sim, "execution": tags, "exec_factor": exec_factor,
                     "template_estimate": legacy_value,
                     # the lineup's measured reaction, amplification, aura and conditional-buff profile (phase 6)
                     "measurements": ev.measured_profile(frozenset(team.members)) if measured else None},
    )
