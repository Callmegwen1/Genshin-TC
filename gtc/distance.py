"""Functional distance: how far a lineup is from the simulated data, and how uncertain that makes a pair-model
estimate (phase 10).

The pair model's error used to be one of two numbers: about 10% for a lineup one member from a simulated lineup,
13% further away. But a swap of Bennett for another ATK buffer is not like a swap of Bennett for a second
on-field carry, and a member with one simulated lineup (Varka) is not known as well as one with a thousand. Here
the error is a function of what changed between the lineup and its nearest simulated lineup:

  away             members changed (1, 2, 3+)
  damage_delta     |sum of the newcomers' mean damage shares - the leavers'|  (capability profiles)
  field_delta      the same for field time
  apply_delta      L1 distance between newcomers' and leavers' element application (per 10 s, / 10)
  reaction_delta   L1 distance between their reaction ownership vectors
  unseen_with_carry  1 when a newcomer was never simulated with the nearest lineup's damage owner
  scarcity         1 / (1 + log(1 + lineups of the least simulated member))

Fitted on held-out lineups (5-fold, each fold's model fitted without it): the mean absolute log error is linear in
the features; the sd is that times sqrt(pi/2) (a normal error's sd over its mean absolute value), floored. The
fit uses half the folds and coverage is reported on the other half. The estimator itself is unchanged: data
availability chooses it (exact simulation, pair model, role rules or kit); distance only sets its sd.
"""
from __future__ import annotations

import math
from collections import defaultdict
from itertools import combinations

import numpy as np

FEATURES = ("away", "damage_delta", "field_delta", "apply_delta", "reaction_delta", "unseen_with_carry", "scarcity")
SD_FLOOR = 0.03
_MODEL: dict | None = None


def _vec(caps, names, attr) -> dict[str, float]:
    out: dict[str, float] = defaultdict(float)
    for n in names:
        c = caps.get(n)
        if c is None:
            continue
        for k, v in (getattr(c, attr) or {}).items():
            out[k] += v
    return out


def _l1(a: dict, b: dict) -> float:
    return sum(abs(a.get(k, 0.0) - b.get(k, 0.0)) for k in set(a) | set(b))


def features(lineup, nearest, owner: str | None, counts: dict[str, int], together, caps) -> dict[str, float]:
    """Features of `lineup` relative to its nearest simulated lineup. `together(a, b)` says whether two characters
    were simulated together; `counts` holds lineups per character."""
    key = frozenset(lineup)
    near = frozenset(nearest) if nearest else frozenset()
    joining, leaving = sorted(key - near), sorted(near - key)
    f = {"away": float(min(3, len(joining)) if near else 3)}

    def total(names, attr):
        return sum(getattr(caps[n], attr) for n in names if n in caps)

    f["damage_delta"] = abs(total(joining, "damage_share") - total(leaving, "damage_share"))
    f["field_delta"] = abs(total(joining, "field_share") - total(leaving, "field_share"))
    f["apply_delta"] = _l1(_vec(caps, joining, "apply"), _vec(caps, leaving, "apply")) / 10
    f["reaction_delta"] = _l1(_vec(caps, joining, "reaction_damage"), _vec(caps, leaving, "reaction_damage"))
    f["unseen_with_carry"] = float(bool(owner) and any(j != owner and not together(j, owner) for j in joining))
    least = min((counts.get(m, 0) for m in key), default=0)
    f["scarcity"] = 1.0 / (1.0 + math.log(1 + least))
    return f


def _predict(model: dict, f: dict[str, float]) -> float:
    if model.get("form") == "loglinear":  # model 6.3: sd = exp(a + b.x), fitted by maximum likelihood
        return max(SD_FLOOR, math.exp(model["intercept"] + sum(model["coef"].get(k, 0.0) * f[k] for k in FEATURES)))
    mean_abs = model["intercept"] + sum(model["coef"][k] * f[k] for k in FEATURES)
    return max(SD_FLOOR, mean_abs * math.sqrt(math.pi / 2))


def _ml_fit(rows, active: list[str]) -> list[float]:
    """Maximum-likelihood weights of a log-linear sd, sd = exp(a + b.x), for errors assumed normal (Newton steps)."""
    X = np.array([[1.0] + [f[k] for k in active] for f, _ in rows])
    e = np.array([err for _, err in rows])
    w = np.zeros(X.shape[1])
    w[0] = math.log(0.1)
    for _ in range(100):
        r = e ** 2 / np.exp(2 * (X @ w))
        step = np.linalg.solve((X * (2 * r)[:, None]).T @ X / len(e) + 1e-6 * np.eye(len(w)), X.T @ (1 - r) / len(e))
        w = w - step
        if np.max(np.abs(step)) < 1e-9:
            break
    return w.tolist()


def sd(f: dict[str, float]) -> float | None:
    """The relative sd for a pair-model estimate with these features (None before `measure` has run)."""
    global _MODEL
    if _MODEL is None:
        from gtc import estimate

        _MODEL = (estimate.load().get("distance") or {}).get("model") or {}
    return _predict(_MODEL, f) if _MODEL else None


def _held_out_rows(folds: int = 5, seed: int = 7) -> list[tuple[dict, float]]:
    from gtc import pairmodel
    from gtc.capabilities import load as load_caps

    caps = load_caps()
    data = pairmodel.lineup_data()
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(data))
    rows = []
    for k in range(folds):
        test_ids = set(order[k::folds].tolist())
        train = [d for i, d in enumerate(data) if i not in test_ids]
        model = pairmodel.fit(train, with_se=False)
        counts: dict[str, int] = defaultdict(int)
        seen: set[frozenset] = set()
        triples: dict[frozenset, list] = defaultdict(list)
        doubles: dict[frozenset, list] = defaultdict(list)
        for lineup, dps, _, _, lead in train:
            for m in lineup:
                counts[m] += 1
            for p in combinations(sorted(lineup), 2):
                seen.add(frozenset(p))
                doubles[frozenset(p)].append((lineup, dps, lead))
            for t in combinations(sorted(lineup), 3):
                triples[frozenset(t)].append((lineup, dps, lead))
        for i in test_ids:
            lineup, dps, _, _, lead = data[i]
            pred = model.predict(lineup, lead)
            if not pred:
                continue
            near = [x for t in combinations(sorted(lineup), 3) for x in triples.get(frozenset(t), [])]
            if not near:
                near = [x for p in combinations(sorted(lineup), 2) for x in doubles.get(frozenset(p), [])]
            best = max(near, key=lambda x: (len(x[0] & lineup), x[1], sorted(x[0]))) if near else None
            f = features(lineup, best[0] if best else None, best[2] if best else None, counts,
                         lambda a, b: frozenset((a, b)) in seen, caps)
            rows.append((f, abs(math.log(pred / dps))))
    return rows


def measure() -> dict:
    """Fit the error model on half the held-out rows and report coverage on the other half.

    Model 6.3: sd = exp(a + b.x), fitted by maximum likelihood. The earlier least-squares fit to the mean absolute
    error was dominated by the many well-covered lineups and left low-data ones overconfident (held out: 63% within
    1 sd and 85% within 2 where the least simulated member has 6 to 20 lineups); maximum likelihood fits the
    spread itself (68% and 90%) and has the higher held-out log likelihood (1.704 against 1.699).
    A feature whose fitted effect is negative (more change, less error) is noise in this data, so it is dropped and
    the rest refitted until every effect is >= 0."""
    rows = _held_out_rows()
    fit_rows, test_rows = rows[0::2], rows[1::2]
    active = list(FEATURES)
    while True:
        w = _ml_fit(fit_rows, active)
        negative = [k for k, b in zip(active, w[1:]) if b < 0]
        if not negative:
            break
        active = [k for k in active if k not in negative]
    coef = {k: 0.0 for k in FEATURES}
    coef.update({k: float(b) for k, b in zip(active, w[1:])})
    model = {"form": "loglinear", "intercept": float(w[0]), "coef": coef, "dropped": sorted(set(FEATURES) - set(active))}

    def coverage(rs, sd_of):
        within1 = sum(e <= sd_of(f) for f, e in rs) / len(rs)
        within2 = sum(e <= 2 * sd_of(f) for f, e in rs) / len(rs)
        return round(within1, 3), round(within2, 3)

    flat = {1.0: _flat_sd(fit_rows, 1), 2.0: _flat_sd(fit_rows, 2), 3.0: _flat_sd(fit_rows, 3)}
    by_away: dict[str, dict] = {}
    for a in (1.0, 2.0, 3.0):
        rs = [r for r in test_rows if r[0]["away"] == a]
        if rs:
            by_away[str(int(a))] = {"n": len(rs), "model": coverage(rs, lambda f: _predict(model, f)),
                                    "flat": coverage(rs, lambda f: flat[f["away"]] or 0.1)}
    sds = sorted(_predict(model, f) for f, _ in test_rows)
    return {"model": model, "n_fit": len(fit_rows), "n_test": len(test_rows),
            "coverage_model": coverage(test_rows, lambda f: _predict(model, f)),
            "coverage_flat": coverage(test_rows, lambda f: flat[f["away"]] or 0.1),
            "sd_range": [round(sds[int(0.05 * len(sds))], 3), round(sds[len(sds) // 2], 3), round(sds[int(0.95 * len(sds))], 3)],
            "by_away": by_away,
            "log_likelihood_gain": round(_ll(test_rows, lambda f: _predict(model, f)) - _ll(test_rows, lambda f: flat[f["away"]] or 0.1), 3)}


def _flat_sd(rows, away) -> float | None:
    errs = sorted(e for f, e in rows if f["away"] == away)
    return errs[int(0.683 * len(errs))] if errs else None


def _ll(rows, sd_of) -> float:
    """Mean Gaussian log likelihood of the errors under each row's sd (higher is better)."""
    return sum(-math.log(sd_of(f)) - e * e / (2 * sd_of(f) ** 2) for f, e in rows) / len(rows)


def for_lineup(lineup, ev) -> tuple[dict[str, float], frozenset | None, int]:
    """(features, nearest simulated lineup, members away) for a lineup the pair model will predict."""
    from gtc.capabilities import load as load_caps
    from gtc.evaluate import _together
    from gtc.evaluate import _neighbourhood
    from gtc.pairmodel import load as load_pairs

    key = frozenset(lineup)
    idx = _neighbourhood(ev)
    near = {x for t in combinations(sorted(key), 3) for x in idx.get(frozenset(t), [])}
    if not near:
        pairs = ev.__dict__.get("_pair_lineups")
        if pairs is None:
            pairs = defaultdict(list)
            for names in ev.lineup_median:
                if len(names) == 4:
                    for p in combinations(sorted(names), 2):
                        pairs[frozenset(p)].append(names)
            ev._pair_lineups = pairs
        near = {x for p in combinations(sorted(key), 2) for x in pairs.get(frozenset(p), [])}
    best = min(near, key=lambda x: (-len(x & key), -ev.lineup_median[x], sorted(x))) if near else None
    st = ev.measured_structure(best) if best else None
    owner = (st or {}).get("owners", [None])[0] if st and st.get("type") in ("hypercarry", "dual_carry") else None
    pm = load_pairs()
    seen = _together(ev)
    f = features(key, best, owner, pm.counts if pm else {}, lambda a, b: frozenset((a, b)) in seen, load_caps() or {})
    return f, best, 4 - len(best & key) if best else 4
