"""Decision policy: how expected power and its uncertainty become choices (phase 10).

Expected power (gtc/evaluate.py) answers "how strong is this team?". Uncertainty answers "how sure are we?". The
policy here turns the two into decisions, and is the only place they meet:
  utility(estimate)   expected - RISK x sd: what plans and rankings maximise, so an optimizer picking the best of
                      many estimates does not favour the overestimated ones (the winner's curse). RISK was
                      calibrated on measured data (decision regret, phase 4).
  compare(a, b)       "better", "roughly_equal" or "worse", with P(a > b). Inside the tie zone (P between
                      1 - TIE and TIE) no ranking claim is made. TIE is calibrated on held-out comparisons
                      (`calibrate_tie`): the smallest P at which claims made at that probability are right at
                      least CLAIM_ACCURACY of the time.
"""
from __future__ import annotations

import math

from gtc import params

RISK = params.get("decision.risk")
CLAIM_ACCURACY = params.get("decision.claim_accuracy")


def utility(est) -> float:
    """Decision utility of an Estimate or PowerEstimate."""
    value = getattr(est, "value", None)
    if value is None:
        value = est.expected
    return value - RISK * est.sd


def tie_probability() -> float:
    """The calibrated tie-zone edge (stored in uncertainty.json by `python -m gtc derive`)."""
    from gtc import estimate

    return (estimate.load().get("compare") or {}).get("tie", 0.8)


def compare(a, b, limit: float = 1.0) -> dict:
    """Compare two estimates. `limit` caps how sure the result may be (the mechanics-coverage guard)."""
    from gtc.estimate import prob_greater

    p = min(max(prob_greater(a, b), 1 - limit), limit)
    tie = tie_probability()
    kind = "better" if p >= tie else "worse" if p <= 1 - tie else "roughly_equal"
    return {"comparison": kind, "probability": p}


def compare_words(a, b, limit: float = 1.0) -> str:
    c = compare(a, b, limit)
    p = c["probability"]
    if c["comparison"] == "better":
        return f"likely better ({p:.0%})"
    if c["comparison"] == "worse":
        return f"likely worse ({1 - p:.0%} that it is worse)"
    return f"roughly equivalent ({p:.0%} that it is better)"


def calibrate_tie(seed: int = 3, min_group: int = 6) -> dict:
    """Held-out comparisons inside archetype families: lineups predicted by the cross-validated pair model (with the
    pair model's measured sd) are compared with each other, the truth being their measured values. Reports how often
    a claimed "better" is right at each stated probability, and the smallest edge whose claims reach CLAIM_ACCURACY."""
    import random

    from gtc import estimate, pairmodel

    data = pairmodel.lineup_data()
    cv = pairmodel.cv_predictions(data)
    rel = estimate._u("pair", "near", "sd", default=0.1)
    groups: dict[str, list] = {}
    for d in data:
        if d[0] in cv and d[3] != "other":
            groups.setdefault(d[3], []).append(d)
    rng = random.Random(seed)
    pairs = []
    for rows in groups.values():
        if len(rows) < min_group:
            continue
        for _ in range(len(rows) * 3):
            x, y = rng.sample(rows, 2)
            px, py = cv[x[0]], cv[y[0]]
            s = math.hypot(px * rel, py * rel)
            p = 0.5 * (1 + math.erf((px - py) / (s * math.sqrt(2)))) if s > 0 else 0.5
            pairs.append((max(p, 1 - p), (px > py) == (x[1] > y[1])))
    bins = []
    for lo in (0.5, 0.6, 0.7, 0.8, 0.9):
        sel = [ok for p, ok in pairs if lo <= p < lo + 0.1]
        if sel:
            bins.append({"stated": f"{lo:.1f}-{lo + 0.1:.1f}", "n": len(sel), "right": round(sum(sel) / len(sel), 3)})
    # The edge is set by the claims made AT it, not by all claims above it (near-certain comparisons would carry
    # the average): the smallest edge whose own band (edge to edge + 0.05) is right CLAIM_ACCURACY of the time.
    tie = 0.95
    for edge in (0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95):
        band = [ok for p, ok in pairs if edge <= p < edge + 0.05]
        if len(band) >= 50 and sum(band) / len(band) >= CLAIM_ACCURACY:
            tie = edge
            break
    return {"tie": tie, "claim_accuracy": CLAIM_ACCURACY, "pairs": len(pairs), "reliability": bins}
