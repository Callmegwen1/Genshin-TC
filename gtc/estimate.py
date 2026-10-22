"""Every number as an estimate with a measured uncertainty and an evidence tier.

Evidence tiers, ordered by their MEASURED accuracy (the plan's first draft put swaps above the pair model;
held out, the pair model next to a simulated lineup is the more accurate of the two):

  A  personal simulation of this exact lineup (gcsim's standard error over its iterations)
  B  community simulations of this exact lineup (their median; one submission misses by about 10%)
  C  pair-effect model one member from a simulated lineup (about 10%)
  C  also: a Prydwen team rating (within about 5 fit points of gcsim on 20 teams)
  D  pair-effect model further away (about 13%); since phase 10 the pair model's sd follows the lineup's
     functional distance (gtc/distance.py)
  E  rules only: role tags calibrated on simulations (measured at run time, in fit points)
  F  insufficient data, shown as "cannot evaluate", never silently guessed

Each tier's standard deviation is MEASURED from held-out errors (`measure`), never chosen by hand, and written
to data/sources/uncertainty.json by `python -m gtc derive`. The relative tiers (B, C, D) store a relative sd,
so a team's sd in fit points is its value times that. Tier E is measured at run time from the calibration's
leave-one-out misses, in fit points.

The sd of a tier is the 68.3rd percentile of absolute held-out errors (one sd for a normal distribution) on a
random half of the cases; the other half checks coverage: about 68% of errors should fall within 1 sd and
95% within 2 sd. Real errors have heavier tails than a normal distribution, so the 2 sd coverage is reported
as measured.
"""
from __future__ import annotations

from gtc import params

import json
import math
import random
from dataclasses import dataclass, field

from gtc.sources import SOURCE_DIR

UNCERTAINTY_PATH = SOURCE_DIR / "uncertainty.json"
TIERS = "ABCDEF"
TIER_TEXT = {"A": "your own simulation", "B": "community simulations", "C": "pair model next to a simulation, or Prydwen",
             "D": "pair model or swap estimate", "E": "role rules only", "F": "cannot evaluate"}


@dataclass
class Estimate:
    value: float
    sd: float  # one standard deviation, same units as value
    tier: str
    sources: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return f"{self.value:.0f} ± {self.sd:.0f} ({self.tier})"


def prob_greater(a: Estimate, b: Estimate) -> float:
    """P(A > B) for independent normal errors."""
    s = math.hypot(a.sd, b.sd)
    if s <= 0:
        return 1.0 if a.value > b.value else 0.0 if a.value < b.value else 0.5
    return 0.5 * (1 + math.erf((a.value - b.value) / (s * math.sqrt(2))))


def _sd_and_coverage(errors: list[float], seed: int = 5) -> dict:
    """sd fitted on half the absolute errors, coverage checked on the other half."""
    rng = random.Random(seed)
    errs = [abs(e) for e in errors]
    rng.shuffle(errs)
    fit, test = errs[: len(errs) // 2], errs[len(errs) // 2:]
    fit.sort()
    sd = fit[min(len(fit) - 1, int(0.683 * len(fit)))] if fit else 0.0
    within1 = sum(e <= sd for e in test) / len(test) if test else None
    within2 = sum(e <= 2 * sd for e in test) / len(test) if test else None
    return {"sd": sd, "n": len(errs), "within_1sd": within1, "within_2sd": within2}


def _log_err(pred: float, actual: float) -> float:
    return math.log(pred / actual)


def measure_community() -> dict:
    """Tier B. One submitter's value for a lineup against the median of the other submitters' values (sd1); the
    lineup value (median of n submitters) then has sd about 1.2533 sd1 / sqrt(n). Submitters, not submissions,
    are the independent votes (gcsim_db.lineup_values). Coverage is checked on lineups with four or more
    submitters, comparing the medians of two random halves."""
    from collections import defaultdict

    from gtc.sources import gcsim_db

    groups: dict[frozenset, list[float]] = {k: [x for x in v.by_submitter.values() if x > 0]
                                            for k, v in gcsim_db.lineup_values().items()}
    errs = []
    for vals in groups.values():
        if len(vals) >= 3:
            for i, v in enumerate(vals):
                others = sorted(vals[:i] + vals[i + 1:])
                errs.append(_log_err(v, _median(others)))
    single = _sd_and_coverage(errs)
    rng = random.Random(9)
    z = []
    for vals in groups.values():
        if len(vals) >= 4:
            v = vals[:]
            rng.shuffle(v)
            a, b = v[: len(v) // 2], v[len(v) // 2:]
            sd = math.hypot(community_sd(single["sd"], len(a)), community_sd(single["sd"], len(b)))
            z.append(abs(_log_err(_median(a), _median(b))) / sd if sd else 0.0)
    return {"sd_single": single["sd"], "n": single["n"], "halves": len(z),
            "within_1sd": sum(x <= 1 for x in z) / len(z) if z else None,
            "within_2sd": sum(x <= 2 for x in z) / len(z) if z else None}


def community_sd(sd_single: float, n: int) -> float:
    """sd of the median of n submissions: the single-submission sd for one or two, then 1.2533 sd / sqrt(n)."""
    if n <= 1:
        return sd_single
    if n == 2:
        return sd_single / math.sqrt(2)
    return 1.2533 * sd_single / math.sqrt(n)


def _median(v: list[float]) -> float:
    v = sorted(v)
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


def measure_pair_model() -> dict:
    """Tier D: cross-validated pair model, one member from a simulated lineup and two or more away."""
    from gtc import pairmodel

    data = pairmodel.lineup_data()
    cv = pairmodel.cv_predictions(data)
    near = [_log_err(cv[d[0]], d[1]) for d in data if d[0] in cv]
    far = pairmodel.far_validation(data, targets=120, return_errors=True)
    return {"near": _sd_and_coverage(near), "far": _sd_and_coverage([math.log(1 + e) for e in far])}


def measure_prydwen() -> dict:
    """Prydwen's team percentages against gcsim: for teams Prydwen lists, its percentage minus the lineup's
    measured fit (median DPS over the carry's best simulated lineup), in fit points."""
    from gtc import knowledge
    from gtc.report import load_evidence

    ev = load_evidence(knowledge.load())
    errs = []
    for lead, info in ev.prydwen.get("characters", {}).items():
        mine = [s for s in ev._by_member.get(lead, []) if id(s) in ev._standard_ids and ev.attributed(s, lead)]
        if not mine:
            continue
        top = max(ev.lineup_median.get(s.names, s.dps) for s in mine)
        theirs = {s.names for s in mine}  # lineups whose damage is this character's (support pages list others' teams)
        for team in info.get("teams", []):
            names = frozenset(m["name"] for m in team["members"])
            if names in theirs and team.get("percent"):
                errs.append(team["percent"] - min(100.0, 100 * ev.lineup_median[names] / top))
    return _sd_and_coverage(errs)


def measure() -> dict:
    from gtc import decision, distance, provisional, structure, typicality

    out = {"B": measure_community(), "pair": measure_pair_model(), "prydwen": measure_prydwen(),
           "provisional": provisional.measure(), "structure": structure.calibrate(), "typicality": typicality.measure(),
           "distance": distance.measure(), "compare": decision.calibrate_tie()}
    UNCERTAINTY_PATH.write_text(json.dumps(out, indent=1), encoding="utf-8")
    global _U
    _U = out
    return out


_U: dict | None = None


def load() -> dict:
    global _U
    if _U is None:
        _U = json.loads(UNCERTAINTY_PATH.read_text(encoding="utf-8")) if UNCERTAINTY_PATH.exists() else {}
    return _U


# Fallbacks before `derive` has measured anything: what phase 3 first measured.
_FALLBACK = {"single": 0.098, "near": 0.099, "far": 0.143, "prydwen": 12.0}


def _u(*path, default):
    d = load()
    for k in path:
        d = (d or {}).get(k)
    return d if d is not None else default


def community_rel_sd(n: int) -> float:
    return community_sd(_u("B", "sd_single", default=_FALLBACK["single"]), n)


def exact_rel_sd(lv) -> tuple[float, float]:
    """(total, between-build) relative sd of a lineup's community value (a gcsim_db.LineupValue).

    Within one build, independent submitters are repeated measurements: the sd shrinks with their number
    (community_rel_sd). Different builds are not: Deathmatch and Ballad of the Fjords Hu Tao are two different
    teams under the "standard" label, and no number of submitters on one of them says which the standard is. So the
    disagreement between build medians is added in full: its variance, in logs, minus the part that within-build
    noise alone would produce (each build median carries sd_single^2 / its submitters), floored at 0. Builds that
    agree add nothing."""
    within = community_rel_sd(lv.n_submitters)
    builds = [(v, n) for v, n in getattr(lv, "by_build", {}).values() if v > 0]
    if len(builds) < 2:
        return within, 0.0
    logs = [math.log(v) for v, _ in builds]
    mean = sum(logs) / len(logs)
    var = sum((x - mean) ** 2 for x in logs) / (len(logs) - 1)
    single = _u("B", "sd_single", default=_FALLBACK["single"])
    noise = sum(single ** 2 / n for _, n in builds) / len(builds)
    between = math.sqrt(max(0.0, var - noise))
    return math.hypot(within, between), between


QUALITY_SPREAD_MIXED = params.get("estimate.quality_spread_mixed")  # submitter medians differing by more: mixed
QUALITY_SPREAD_POOR = params.get("estimate.quality_spread_poor")  # by more than this: poor
QUALITY_CARRY_SHARE = params.get("estimate.quality_carry_share")  # usually this share of team damage: a usual carry
QUALITY_OWNER_SHARE = params.get("estimate.quality_owner_share")  # a damage owner usually below this: unusual owner


def community_quality(lv, lineup, structure: dict | None = None, caps: dict | None = None) -> tuple[str, list[str]]:
    """How trustworthy a lineup's community simulations are as ground truth (model 6.4): "good", "unconfirmed",
    "mixed" or "poor", with reasons. An exact community value is not automatically clean: submitters may disagree, builds
    may differ, and a rotation may not play the team as intended (Hu Tao vape submissions whose measured damage
    owner is Yelan). Used for presentation and confidence; the value itself is not rewritten.
      single submitter                      unconfirmed (nobody else confirms it; nothing contradicts it either)
      submitter medians spread > 25% / 50%  mixed / poor
      several builds with between-build sd  mixed (> 0.15)
      unusual damage ownership              mixed; poor together with another problem: a usual carry is in the
                                            lineup, but the measured damage owner usually deals little"""
    why = []
    level = 0
    if lv is None:
        return "poor", ["no community value"]
    single = lv.n_submitters <= 1
    if lv.n_submitters > 1 and lv.spread > QUALITY_SPREAD_POOR:
        why.append(f"submitters disagree by {lv.spread:.0%}")
        level = 2
    elif lv.n_submitters > 1 and lv.spread > QUALITY_SPREAD_MIXED:
        why.append(f"submitters disagree by {lv.spread:.0%}")
        level = max(level, 1)
    _, between = exact_rel_sd(lv)
    if between > 0.15:
        why.append(f"{lv.n_builds} different builds disagree (between-build sd {between:.0%})")
        level = max(level, 1)
    owners = (structure or {}).get("owners") or []
    if caps and owners and owners[0] in caps:
        usual = {m: caps[m].damage_share for m in lineup if m in caps}
        carries = [m for m, v in usual.items() if v >= QUALITY_CARRY_SHARE and m != owners[0]]
        if carries and usual.get(owners[0], 1.0) < QUALITY_OWNER_SHARE:
            why.append(f"{owners[0]} owns the damage although {', '.join(carries)} usually carries "
                       f"(the rotation may not play the team as intended)")
            level = 2 if level >= 1 else 1
    if set(getattr(lv, "by_submitter", {}) or {}) == {"unknown"}:
        # every submission predates the current database (migrated) or has no submitter: older game versions and
        # rotations, which power creep and kit changes may have outdated (Ayaka / Shenhe / Mona / Kazuha)
        why.append("only legacy submissions (migrated from the old database)")
    # Held out (leave one submission out, 703 predictions), the labels do not predict larger errors than the sd
    # already allows (p68 miss: good 8.6%, mixed 9.9%), so they inform presentation, not the sd or confidence.
    if level == 0 and single:
        return "unconfirmed", ["one submitter"] + [w for w in why if w.startswith("only legacy")]
    return ("good", "mixed", "poor")[level], why


def fit_estimate(measure, lineup_n: int = 1, top_n: int = 1, is_top: bool = False,
                 model_sd: tuple[float, float] | None = None) -> Estimate:
    """The evidence tier and sd of a lineup fit (a gtc.evidence.Measure).

    gcsim: the lineup's median against the best lineup's median, both community medians.
    pairmodel: C next to a simulated lineup (Measure.anchored), D further away.
    prydwen: C, its sd measured against gcsim in fit points.
    model: E, model_sd = (anchored, unanchored) leave-one-out sd from the calibration, in fit points."""
    v = measure.value or 0.0
    src = measure.source
    if src == "gcsim":
        rel = community_rel_sd(lineup_n) if is_top else math.hypot(community_rel_sd(lineup_n), community_rel_sd(top_n))
        return Estimate(v, v * rel, "B", ["gcsim"])
    if src == "pairmodel":
        near = getattr(measure, "anchored", True)
        rel = _u("pair", "near" if near else "far", "sd", default=_FALLBACK["near" if near else "far"])
        return Estimate(v, v * rel, "C" if near else "D", ["pair model"])
    if src == "prydwen":
        return Estimate(v, _u("prydwen", "sd", default=_FALLBACK["prydwen"]), "C", ["Prydwen"])
    if src == "model":
        anchored_sd, unanchored_sd = model_sd or (15.0, 20.0)
        return Estimate(v, anchored_sd if getattr(measure, "anchored", True) else unanchored_sd, "E", ["role model"])
    return Estimate(v, 0.0, "F", [])


def combine(tier_est: Estimate, fit_est: Estimate) -> Estimate:
    """Potential = archetype tier x lineup fit / 100. Relative errors add in quadrature; the tier of the
    result is the weaker of the two."""
    value = tier_est.value * fit_est.value / 100
    rel = math.hypot(tier_est.sd / tier_est.value if tier_est.value else 0.0,
                     fit_est.sd / fit_est.value if fit_est.value else 0.0)
    worst = max(tier_est.tier, fit_est.tier, key=TIERS.index)
    return Estimate(value, value * rel, worst, tier_est.sources + fit_est.sources)


def worst_tier(tiers) -> str:
    tiers = [t for t in tiers if t]
    return max(tiers, key=TIERS.index) if tiers else "F"
