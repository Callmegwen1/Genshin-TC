"""A fitted model of character and pair effects over every standard simulated lineup at once.

    log(team DPS) = intercept + sum of character effects + lead effect + sum of pair effects + noise

A character's effect is what they add as a teammate; their lead effect is what they add on top when the team's
damage is built around them (its measured damage owner). Without the split, a carry's strength from leading
their own teams is credited when they fill a support slot in someone else's.

Fitted by ridge regression: least squares with shrinkage toward zero, stronger for pairs than for characters,
so a pair seen in only a few lineups does not get an extreme value. A pair effect is how much better two
characters do together than their separate effects predict: Nahida + Kuki as a Hyperbloom core, with nobody
labelled the carry. Raw pair averages are confounded by the third and fourth members; the regression
separates them. It also predicts lineups two or more members away from any simulation.

Each lineup's value is the median of its standard simulations (per-submitter medians, gcsim_db.aggregate).

Damage capacity (model 6.3): one more term, coef x log(S), where S is the sum of the members' average measured
damage shares (how much of a team's damage each of them usually deals). Without it, most of a carry's value sits
in the intercept that every lineup shares, so a lineup with nobody to deal the damage (Escoffier / Citlali /
Furina / Kazuha: the Skirk team without Skirk) kept most of the carry's team value. Cross-validated it lowers the
error (median 6.48% to 6.42%, mean 8.38% to 8.34%) and the overprediction of low-capacity lineups (S below 0.6:
+5.1% to +3.7%), with a stable coefficient (0.30 to 0.36 across folds). Each training lineup's S leaves out its own
simulation, as at prediction time.

Kit conditions (model 6.5): one effect per party-composition condition in knowledge/kit_conditions.yaml, active
when the support is present and the condition is unmet (Escoffier with fewer than four Hydro/Cryo members,
Chevreuse outside an all Pyro/Electro party). Cross-validated it lowers the error (median 6.41% to 6.25%, p68 9.85%
to 9.63%) and the overprediction of such lineups (+3.0% to +0.6%); the Escoffier and Chevreuse effects are stable
across folds (about -16% and -13%). Penalised like character effects.

No archetype effect (removed in phase 5): it made a lineup's predicted power depend on which template generated
it, and cross-validated it bought almost nothing (median error 6.42% with it and 6.48% without one member from a
simulated lineup, 10.9% and 11.6% further away, measured with each lineup's true archetype known, which real use
does not have). The archetype is still returned by `lineup_data` for grouping.

Written to data/sources/pair_effects.json by `python -m gtc derive`, with standard errors and the
cross-validated accuracy.
"""
from __future__ import annotations

from gtc import params

import json
import math
from collections import defaultdict
from dataclasses import dataclass, field
from itertools import combinations

import numpy as np

from gtc.sources import SOURCE_DIR

PAIR_EFFECTS_PATH = SOURCE_DIR / "pair_effects.json"
LAMBDA_CHAR = params.get("pairmodel.lambda_char")  # ridge penalty for character effects (cross-validated: flat between 0.03 and 0.3)
LAMBDA_PAIR = params.get("pairmodel.lambda_pair")  # ridge penalty for pair effects (cross-validated: 1.0 beats 0.3 and 3.0)
MIN_PAIR_LINEUPS = params.get("pairmodel.min_pair_lineups")  # a pair needs at least this many lineups to get its own effect
OTHER = "other"
CARRY_LIKE_SHARE = params.get("pairmodel.carry_like_share")  # damage owner in at least this share of their lineups


def lineup_data() -> list[tuple[frozenset, float, int, str, str | None]]:
    """(lineup, median DPS, number of simulations, archetype, damage lead) for every standard four-member lineup.
    The lead is the measured top damage owner of a hypercarry or dual-carry lineup, else None."""
    from gtc.derive import FAMILY_LINEUPS
    from gtc.sources import gcsim_db

    values = {k: v for k, v in gcsim_db.lineup_values().items() if len(k) == 4}
    family: dict[frozenset, str] = {}
    if FAMILY_LINEUPS.exists():
        for tid, lineups in json.loads(FAMILY_LINEUPS.read_text(encoding="utf-8")).items():
            for x in lineups:
                family.setdefault(frozenset(x), tid)
    from gtc.synergy import DB_PATH, load_database

    leads: dict[frozenset, str] = {}
    if DB_PATH.exists():
        for e in load_database().values():
            st = (e.get("profile") or {}).get("structure") or {}
            if "lineup" in e and st.get("type") in ("hypercarry", "dual_carry") and st.get("owners"):
                leads[frozenset(e["lineup"])] = st["owners"][0]
    out = []
    for lineup, v in values.items():
        if v.value > 0:
            out.append((lineup, v.value, v.n_submitters, family.get(lineup, OTHER), leads.get(lineup)))
    return out


@dataclass
class PairModel:
    intercept: float = 0.0
    chars: dict[str, float] = field(default_factory=dict)
    leads: dict[str, float] = field(default_factory=dict)  # extra effect when the team is built around them
    pairs: dict[str, float] = field(default_factory=dict)  # "A|B" with A < B
    pair_se: dict[str, float] = field(default_factory=dict)
    char_se: dict[str, float] = field(default_factory=dict)
    sigma: float = 0.0
    counts: dict[str, int] = field(default_factory=dict)  # lineups behind each character and pair
    lead_counts: dict[str, int] = field(default_factory=dict)  # lineups whose damage is built around each character
    validation: dict = field(default_factory=dict)
    shares: dict[str, float] = field(default_factory=dict)  # average measured damage share per character
    capacity_coef: float = 0.0  # effect of log(damage capacity) on log DPS
    capacity_mean: float = 0.0  # mean log capacity of the training lineups (the term is centred on it)
    conditions: dict[str, float] = field(default_factory=dict)  # support -> effect when its party condition is unmet

    @staticmethod
    def key(a: str, b: str) -> str:
        return "|".join(sorted((a, b)))

    def known(self, lineup) -> bool:
        return all(m in self.chars for m in lineup)

    def predict(self, lineup, lead: str | None = None) -> float | None:
        """Predicted team DPS, or None when a member was never simulated. `lead` is whose damage the team is
        built around (None for a team without a single carry)."""
        if not self.known(lineup):
            return None
        v = self.intercept + sum(self.chars[m] for m in lineup) + (self.leads.get(lead, 0.0) if lead in lineup else 0.0)
        v += sum(self.pairs.get(self.key(a, b), 0.0) for a, b in combinations(sorted(lineup), 2))
        if self.capacity_coef and all(m in self.shares for m in lineup):
            v += self.capacity_coef * (math.log(max(CAPACITY_FLOOR, sum(self.shares[m] for m in lineup))) - self.capacity_mean)
        if self.conditions:
            from gtc.kit_conditions import unmet

            v += sum(self.conditions.get(n, 0.0) for n in unmet(lineup))
        return math.exp(v)

    def capacity(self, lineup) -> float | None:
        """Sum of the members' average measured damage shares (None when one has no measurement)."""
        if not all(m in self.shares for m in lineup):
            return None
        return sum(self.shares[m] for m in lineup)

    def carry_like(self, name: str) -> bool:
        """Mostly simulated as the team's damage owner (at least half of their lineups)."""
        n = self.counts.get(name, 0)
        return n > 0 and self.lead_counts.get(name, 0) / n >= CARRY_LIKE_SHARE

    def pair_effect(self, a: str, b: str) -> tuple[float, float] | None:
        """(effect, standard error) of a pair as a multiplier on team DPS minus 1, e.g. 0.12 = +12%."""
        k = self.key(a, b)
        if k not in self.pairs:
            return None
        return math.exp(self.pairs[k]) - 1, self.pair_se.get(k, 0.0)

    def to_json(self) -> dict:
        return vars(self)

    @classmethod
    def from_json(cls, d: dict) -> "PairModel":
        d = {k: v for k, v in d.items() if k != "families"}  # files written before phase 5
        return cls(**d)


CAPACITY_FLOOR = params.get("pairmodel.capacity_floor")  # a lineup's damage capacity never counts below this (log floor)
_SHARES: dict | None = None


def lineup_shares() -> dict[str, dict[frozenset, float]]:
    """Per character: their measured damage share in each simulated lineup (the synergy database)."""
    global _SHARES
    if _SHARES is None:
        from gtc.synergy import load_database

        _SHARES = defaultdict(dict)
        for e in load_database().values():
            mem = (e.get("profile") or {}).get("members") or {}
            if len(e.get("lineup", [])) == 4:
                for m, v in mem.items():
                    _SHARES[m][frozenset(e["lineup"])] = v.get("damage_share", 0.0)
    return _SHARES


def _capacities(data) -> tuple[dict[str, float], list[float | None]]:
    """(average damage share per character over the training lineups, each training lineup's capacity with its own
    simulation left out)."""
    keys = {d[0] for d in data}
    table = lineup_shares()
    sums = {m: (sum(v for k, v in d.items() if k in keys), sum(1 for k in d if k in keys)) for m, d in table.items()}
    avg = {m: s / n for m, (s, n) in sums.items() if n}
    caps = []
    for d in data:
        total = 0.0
        for m in d[0]:
            s, n = sums.get(m, (0.0, 0))
            own = table.get(m, {}).get(d[0])
            if own is not None:
                s, n = s - own, n - 1
            if n <= 0:
                total = None
                break
            total += s / n
        caps.append(None if total is None else max(CAPACITY_FLOOR, total))
    return avg, caps


def _design(data, char_idx, pair_idx, lead_idx):
    n_feat = len(char_idx) + len(lead_idx) + len(pair_idx)
    X = np.zeros((len(data), n_feat))
    off_c, off_l = 0, len(char_idx)
    off_p = off_l + len(lead_idx)
    for i, d in enumerate(data):
        lineup, lead = d[0], d[4]
        for m in lineup:
            if m in char_idx:
                X[i, off_c + char_idx[m]] = 1.0
        if lead in lead_idx:
            X[i, off_l + lead_idx[lead]] = 1.0
        for a, b in combinations(sorted(lineup), 2):
            k = PairModel.key(a, b)
            if k in pair_idx:
                X[i, off_p + pair_idx[k]] = 1.0
    return X


def fit(data, lam_char: float = LAMBDA_CHAR, lam_pair: float = LAMBDA_PAIR, with_se: bool = True,
        use_leads: bool = True) -> PairModel:
    pair_n: dict[str, int] = defaultdict(int)
    char_n: dict[str, int] = defaultdict(int)
    lead_n: dict[str, int] = defaultdict(int)
    for d in data:
        if use_leads and d[4]:
            lead_n[d[4]] += 1
    for lineup, *_ in data:
        for m in lineup:
            char_n[m] += 1
        for a, b in combinations(sorted(lineup), 2):
            pair_n[PairModel.key(a, b)] += 1
    chars = sorted(char_n)
    leads = sorted(lead_n)
    pairs = sorted(k for k, n in pair_n.items() if n >= MIN_PAIR_LINEUPS)
    char_idx = {c: i for i, c in enumerate(chars)}
    pair_idx = {p: i for i, p in enumerate(pairs)}
    lead_idx = {c: i for i, c in enumerate(leads)}
    X = _design(data, char_idx, pair_idx, lead_idx)
    y = np.array([math.log(d[1]) for d in data])
    mean = y.mean()
    pen = np.concatenate([np.full(len(chars), lam_char), np.full(len(leads), lam_char),
                          np.full(len(pairs), lam_pair)])
    # Damage capacity (see the module docstring): one unpenalised column, centred; lineups without a measurement
    # sit at the mean.
    shares, caps = _capacities(data)
    logs = [math.log(c) for c in caps if c is not None]
    cap_mean = sum(logs) / len(logs) if logs else 0.0
    col = np.array([[math.log(c) - cap_mean if c is not None else 0.0] for c in caps])
    use_cap = len(logs) > 1 and float(col.std()) > 1e-9  # no damage-share measurements (e.g. synthetic data): no term
    if use_cap:
        X = np.hstack([X, col])
        pen = np.concatenate([pen, [0.0]])
    # Kit conditions: one column per conditional support seen in the data, 1 when present and unmet.
    from gtc.kit_conditions import conditions, unmet

    cond_names = [n for n in sorted(conditions()) if n in char_idx]
    if cond_names:
        X = np.hstack([X, np.array([[float(n in unmet(d[0])) for n in cond_names] for d in data])])
        pen = np.concatenate([pen, np.full(len(cond_names), lam_char)])
    A = X.T @ X + np.diag(pen)
    beta = np.linalg.solve(A, X.T @ (y - mean))
    resid = y - mean - X @ beta
    dof = max(1, len(y) - int(np.trace(X @ np.linalg.solve(A, X.T)))) if with_se else max(1, len(y))
    sigma = float(math.sqrt(float(resid @ resid) / dof))
    se = np.sqrt(np.diag(np.linalg.inv(A)) * sigma ** 2) if with_se else np.zeros(len(beta))
    nf, nc, nl = 0, len(chars), len(leads)
    model = PairModel(
        intercept=float(mean),
        chars={c: float(beta[nf + i]) for c, i in char_idx.items()},
        leads={c: float(beta[nf + nc + i]) for c, i in lead_idx.items()},
        pairs={p: float(beta[nf + nc + nl + i]) for p, i in pair_idx.items()},
        pair_se={p: float(se[nf + nc + nl + i]) for p, i in pair_idx.items()},
        char_se={c: float(se[nf + i]) for c, i in char_idx.items()},
        sigma=sigma,
        counts={**{c: char_n[c] for c in chars}, **{p: pair_n[p] for p in pairs}},
        lead_counts=dict(lead_n),
        shares={m: v for m, v in shares.items() if m in char_idx} if use_cap else {},
        capacity_coef=float(beta[-1 - len(cond_names)]) if use_cap else 0.0,
        capacity_mean=float(cap_mean) if use_cap else 0.0,
        conditions={n: float(b) for n, b in zip(cond_names, beta[len(beta) - len(cond_names):])} if cond_names else {},
    )
    return model


def cv_predictions(data, folds: int = 5, lam_char: float = LAMBDA_CHAR, lam_pair: float = LAMBDA_PAIR,
                   seed: int = 7) -> dict[frozenset, float]:
    """Each lineup's prediction from a model fitted without it (k-fold)."""
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(data))
    out = {}
    for k in range(folds):
        test_ids = set(order[k::folds].tolist())
        model = fit([d for i, d in enumerate(data) if i not in test_ids], lam_char, lam_pair, with_se=False)
        for i in test_ids:
            pred = model.predict(data[i][0], data[i][4])
            if pred is not None:
                out[data[i][0]] = pred
    return out


def cross_validate(data, folds: int = 5, lam_char: float = LAMBDA_CHAR, lam_pair: float = LAMBDA_PAIR, seed: int = 7) -> dict:
    """K-fold over lineups. Error is |predicted / simulated - 1|, reported by distance: how many members the
    held-out lineup is from the closest training lineup with the same members otherwise."""
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(data))
    errors: dict[str, list[float]] = defaultdict(list)
    for k in range(folds):
        test_ids = set(order[k::folds].tolist())
        train = [d for i, d in enumerate(data) if i not in test_ids]
        model = fit(train, lam_char, lam_pair, with_se=False)
        train_sets = [d[0] for d in train]
        for i in test_ids:
            lineup, dps, _, _, lead = data[i]
            pred = model.predict(lineup, lead)
            if pred is None:
                continue
            shared = max(len(lineup & t) for t in train_sets)
            bucket = {3: "1 away", 2: "2 away"}.get(shared, "3+ away")
            err = abs(pred / dps - 1)
            errors[bucket].append(err)
            errors["all"].append(err)
    return {b: {"n": len(v), "median_error": float(np.median(v)), "within_10pct": float(np.mean(np.array(v) <= 0.10))}
            for b, v in errors.items()}


def tune(data) -> tuple[float, float, dict]:
    """Pick the penalties with the lowest cross-validated median error."""
    best = None
    for lc in (0.1, 0.3, 1.0):
        for lp in (0.3, 1.0, 3.0):
            cv = cross_validate(data, lam_char=lc, lam_pair=lp)
            score = cv["all"]["median_error"]
            if best is None or score < best[0]:
                best = (score, lc, lp, cv)
    return best[1], best[2], best[3]


def build(tune_penalties: bool = False) -> PairModel:
    data = lineup_data()
    lc, lp = LAMBDA_CHAR, LAMBDA_PAIR
    if tune_penalties:
        lc, lp, cv = tune(data)
    else:
        cv = cross_validate(data, lam_char=lc, lam_pair=lp)
    model = fit(data, lc, lp)
    model.validation = {"lambda_char": lc, "lambda_pair": lp, "lineups": len(data), "cross_validation": cv}
    PAIR_EFFECTS_PATH.write_text(json.dumps(model.to_json()), encoding="utf-8")
    global _MODEL
    _MODEL = model
    return model


_MODEL: PairModel | None = None


def load() -> PairModel | None:
    global _MODEL
    if _MODEL is None and PAIR_EFFECTS_PATH.exists():
        _MODEL = PairModel.from_json(json.loads(PAIR_EFFECTS_PATH.read_text(encoding="utf-8")))
    return _MODEL


def far_validation(data, targets: int = 150, lam_char: float = LAMBDA_CHAR, lam_pair: float = LAMBDA_PAIR,
                   seed: int = 11, return_errors: bool = False):
    """Large lineup changes: for sampled lineups, refit without every lineup sharing three or more members with
    them, so the nearest training lineup is at least two members away, then predict."""
    rng = np.random.default_rng(seed)
    errors = []
    for i in rng.choice(len(data), size=min(targets, len(data)), replace=False):
        lineup, dps, _, _, lead = data[i]
        train = [d for d in data if len(d[0] & lineup) < 3]
        model = fit(train, lam_char, lam_pair, with_se=False)
        pred = model.predict(lineup, lead)
        if pred is not None:
            errors.append(abs(pred / dps - 1))
    if return_errors:
        return errors
    v = np.array(errors)
    return {"n": len(v), "median_error": float(np.median(v)), "within_10pct": float(np.mean(v <= 0.10))}
