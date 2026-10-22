"""Structure v2: probabilistic damage structure (phase 7).

A team's structure is where its damage comes from. The hard rules in gtc/synergy.classify_structure (hypercarry
when one member deals 55%, dual carry when two deal 25% each, ...) bootstrap the vocabulary, but a single label
from them is brittle: in the phase 6 rebuild 4.4% of simulated lineups changed type from sampling noise alone,
and for unsimulated lineups the predicted shares miss by about 30% (log damage share, one sd), so a hard label is
right only 75% of the time. Here the label becomes a distribution.

The shares are uncertain, so they are drawn many times from their measured error and each draw is classified with
the same rules:
  measured lineups   noise of one gcsim sample (phase 6 rebuild against its predecessor), so the probabilities
                     stay close to the measured label and spread only near a threshold
  predicted lineups  the held-out error of the neighbour prediction (gtc.capabilities.Neighbours), times a scale
                     calibrated on held-out log likelihood (`calibrate`)

Output (`estimate`), all continuous values kept:
  probabilities   {hypercarry, dual_carry, reaction_core, driver, distributed}: P, summing to 1
  patterns        {on_field_carry: P(the top damage dealer is on field at least 60%),
                   quickswap: P(two or more members are each on field at least 25%)}
  primary         {member: P(this member deals the most damage)}
  type, owners    the most probable type and its damage owners from the expected shares (what older code reads)
  damage_shares, field_shares, reaction_share, source: measured | predicted
"""
from __future__ import annotations

import hashlib
import math

import numpy as np

from gtc import params

TYPES = ("hypercarry", "dual_carry", "reaction_core", "driver", "distributed")
CARRY_TYPES = ("hypercarry", "dual_carry")
SAMPLES = params.get("structure.samples")
SAMPLE_NOISE = params.get("structure.sample_noise")  # {log_damage, field, reaction}: one gcsim sample's noise
ON_FIELD_CARRY = params.get("structure.on_field_carry")  # the top dealer's field share for an on-field carry
QUICKSWAP_FIELD = params.get("structure.quickswap_field")  # field share each of two members needs for quickswap

_CACHE: dict = {}


def _rules() -> dict:
    from gtc.synergy import STRUCTURE_RULES

    return STRUCTURE_RULES


def prediction_noise() -> dict:
    """Held-out error of predicted shares (measured by `calibrate`, stored in uncertainty.json)."""
    from gtc import estimate

    u = estimate.load().get("structure") or {}
    s = u.get("scale", 1.0)
    return {"log_damage": u.get("log_damage", 0.30) * s, "field": u.get("field", 0.045) * s,
            "reaction": u.get("reaction", 0.032) * s}


_BANK: dict[int, tuple] = {}


def _draws(n_members: int) -> tuple:
    """One fixed bank of standard normal draws, shared by every lineup: deterministic, no per-call random number
    cost, and comparisons between lineups use common random numbers (less noise between them)."""
    if n_members not in _BANK:
        rng = np.random.default_rng(7 + n_members)
        _BANK[n_members] = (rng.standard_normal((SAMPLES, n_members)), rng.standard_normal((SAMPLES, n_members)),
                            rng.standard_normal(SAMPLES))
    return _BANK[n_members]


def _seed(members) -> int:
    return int(hashlib.sha1("|".join(sorted(members)).encode()).hexdigest()[:8], 16)


def _classify(S: np.ndarray, F: np.ndarray, R: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Vectorised classify_structure over draws: S, F (draws x members), R (draws). Returns (type index, top index)."""
    rules = _rules()
    top = S.argmax(axis=1)
    rows = np.arange(len(S))
    ordered = np.sort(S, axis=1)
    top_s = ordered[:, -1]
    second_s = ordered[:, -2] if S.shape[1] > 1 else np.zeros(len(S))
    onfield = np.argmax(F, axis=1)
    hyper = top_s >= rules["hypercarry"]
    dual = ~hyper & (second_s >= rules["dual_carry"])
    core = ~hyper & ~dual & (R >= rules["reaction_core"])
    driver = ~hyper & ~dual & ~core & (F[rows, onfield] >= rules["driver_field"]) & (S[rows, onfield] < rules["driver_damage"])
    t = np.full(len(S), 4)
    t[driver] = 3
    t[core] = 2
    t[dual] = 1
    t[hyper] = 0
    return t, top


def estimate(members: list[str], damage: dict[str, float], field: dict[str, float], reaction: float,
             noise: dict, source: str) -> dict:
    """The structure distribution for given expected shares and their noise."""
    from gtc.synergy import classify_structure

    ms = list(members)
    zd, zf, zr = _draws(len(ms))
    d = np.array([max(damage.get(m, 0.0), 1e-4) for m in ms])
    f = np.array([field.get(m, 0.0) for m in ms])
    S = d * np.exp(noise["log_damage"] * zd)
    S /= S.sum(axis=1, keepdims=True)
    F = np.clip(f + noise["field"] * zf, 0.0, 1.0)
    R = np.clip(reaction + noise["reaction"] * zr, 0.0, 1.0)
    t, top = _classify(S, F, R)
    counts = np.bincount(t, minlength=len(TYPES)) / SAMPLES
    probs = {name: float(counts[i]) for i, name in enumerate(TYPES)}
    rows = np.arange(SAMPLES)
    patterns = {"on_field_carry": float(np.count_nonzero(F[rows, top] >= ON_FIELD_CARRY)) / SAMPLES,
                "quickswap": float(np.count_nonzero((F >= QUICKSWAP_FIELD).sum(axis=1) >= 2)) / SAMPLES}
    tops = np.bincount(top, minlength=len(ms)) / SAMPLES
    primary = {m: float(tops[i]) for i, m in enumerate(ms)}
    point = classify_structure({m: {"damage_share": damage.get(m, 0.0), "field_share": field.get(m, 0.0)} for m in ms},
                               reaction)
    best = max(TYPES, key=lambda x: (probs[x], -TYPES.index(x)))
    owners = point["owners"] if point["type"] == best else _owners_for(best, ms, damage, field)
    return {"type": best, "owners": owners, "probabilities": probs, "patterns": patterns, "primary": primary,
            "damage_shares": {m: round(damage.get(m, 0.0), 4) for m in ms},
            "field_shares": {m: round(field.get(m, 0.0), 4) for m in ms},
            "reaction_share": round(reaction, 4), "source": source}


def _owners_for(kind: str, ms, damage, field) -> list[str]:
    by = sorted(ms, key=lambda m: (-damage.get(m, 0.0), m))
    if kind == "hypercarry":
        return by[:1]
    if kind == "dual_carry":
        return by[:2]
    if kind == "driver":
        onfield = max(ms, key=lambda m: (field.get(m, 0.0), m))
        return [m for m in by[:2] if m != onfield][:1]
    return []


def from_profile(members, prof: dict) -> dict:
    """A measured lineup's structure distribution (one sample's noise). Its type and owners stay the measured ones:
    the probabilities say how close to a threshold the measurement sits."""
    key = ("measured", frozenset(members))
    if key not in _CACHE:
        ms = sorted(prof["members"])
        st = estimate(ms, {m: prof["members"][m]["damage_share"] for m in ms},
                      {m: prof["members"][m]["field_share"] for m in ms}, prof.get("reaction_share", 0.0),
                      SAMPLE_NOISE, "measured")
        measured = prof.get("structure") or {}
        if measured.get("type"):
            st["type"], st["owners"] = measured["type"], list(measured.get("owners") or [])
        _CACHE[key] = st
    return _CACHE[key]


def predict(members, nb=None, caps=None, exclude: frozenset | None = None) -> dict | None:
    """A predicted structure distribution: neighbour shares when every member has been simulated, otherwise the
    members' capability averages renormalised (both with the measured prediction noise)."""
    key = ("predicted", frozenset(members), exclude)
    if key in _CACHE:
        return _CACHE[key]
    from gtc.capabilities import load as load_caps, neighbours

    nb = nb or neighbours()
    got = nb.profile(list(members), exclude) if nb else None
    if got:
        shares, reaction = got
    else:
        caps = caps if caps is not None else load_caps()
        known = {m: caps[m] for m in members if m in caps}
        if not known:
            return None
        total = sum(c.damage_share for c in known.values()) or 1.0
        shares = {m: {"damage_share": c.damage_share / total, "field_share": c.field_share} for m, c in known.items()}
        reaction = sum(c.team_reaction_share for c in known.values()) / len(known)
    ms = sorted(shares)
    out = estimate(ms, {m: shares[m]["damage_share"] for m in ms}, {m: shares[m]["field_share"] for m in ms},
                   reaction, prediction_noise(), "predicted")
    _CACHE[key] = out
    return out


def carry_probability(st: dict | None) -> float:
    """P(the team's damage is built around one or two carries)."""
    if not st:
        return 0.0
    p = st.get("probabilities")
    if p is None:  # an old hard structure
        return 1.0 if st.get("type") in CARRY_TYPES else 0.0
    return sum(p[t] for t in CARRY_TYPES)


# ---------- validation and calibration (held out) ----------

def _held_out(db=None) -> list[tuple[dict, tuple]]:
    from gtc.capabilities import neighbours
    from gtc.synergy import load_database

    db = db or load_database()
    nb = neighbours()
    out = []
    for e in db.values():
        if not e.get("profile") or len(e.get("lineup", [])) != 4:
            continue
        got = nb.profile(e["lineup"], exclude=frozenset(e["lineup"]))
        if got:
            out.append((e, got))
    return out


def _scored(rows, noise) -> dict:
    """Probabilistic and hard metrics of predictions with `noise` against measured structures."""
    ll = brier = 0.0
    hard = top_ok = absurd = 0
    top_ll = 0.0
    bins = [[0, 0.0, 0] for _ in range(10)]  # count, sum of confidence, hits (reliability of the most probable type)
    confusion: dict[tuple[str, str], int] = {}
    for e, (pm, rs) in rows:
        ms = sorted(pm)
        st = estimate(ms, {m: pm[m]["damage_share"] for m in ms}, {m: pm[m]["field_share"] for m in ms}, rs, noise, "predicted")
        meas = e["profile"]["structure"]["type"]
        p = st["probabilities"]
        ll += -math.log(max(p[meas], 1e-3))
        brier += sum((p[t] - (t == meas)) ** 2 for t in TYPES)
        best = st["type"]
        hard += best == meas
        confusion[(meas, best)] = confusion.get((meas, best), 0) + 1
        conf = p[best]
        b = min(9, int(conf * 10))
        bins[b][0] += 1
        bins[b][1] += conf
        bins[b][2] += best == meas
        mm = e["profile"]["members"]
        mtop = max(mm, key=lambda m: mm[m]["damage_share"])
        ptop = max(st["primary"], key=lambda m: st["primary"][m])
        top_ok += ptop == mtop
        top_ll += -math.log(max(st["primary"].get(mtop, 0.0), 1e-3))
        absurd += mm[ptop]["damage_share"] < 0.15
    n = len(rows) or 1
    ece = sum(abs(c[1] - c[2]) for c in bins) / n
    return {"n": len(rows), "type_log_loss": ll / n, "type_brier": brier / n, "type_accuracy": hard / n,
            "type_calibration_error": ece, "top_accuracy": top_ok / n, "top_log_loss": top_ll / n,
            "absurd_rate": absurd / n,
            "reliability": [{"confidence": round(c[1] / c[0], 3), "accuracy": round(c[2] / c[0], 3), "n": c[0]}
                            for c in bins if c[0]],
            "confusion": {f"{a}->{b}": v for (a, b), v in sorted(confusion.items())}}


def calibrate() -> dict:
    """Measure the held-out share errors, then pick the noise scale with the best held-out log likelihood on one
    half of the lineups and report every metric on the other half. Stored under "structure" in uncertainty.json."""
    rows = _held_out()

    def sd68(v):
        a = sorted(abs(x) for x in v)
        return a[int(0.683 * len(a))] if a else 0.0

    dl, df, dr = [], [], []
    for e, (pm, rs) in rows:
        mm = e["profile"]["members"]
        for m in mm:
            dl.append(math.log(max(mm[m]["damage_share"], 0.005)) - math.log(max(pm[m]["damage_share"], 0.005)))
            df.append(mm[m]["field_share"] - pm[m]["field_share"])
        dr.append(e["profile"]["reaction_share"] - rs)
    base = {"log_damage": sd68(dl), "field": sd68(df), "reaction": sd68(dr)}
    order = sorted(rows, key=lambda r: _seed(r[0]["lineup"]))
    fit_half, test_half = order[0::2], order[1::2]
    best = None
    for scale in (0.4, 0.6, 0.8, 1.0, 1.25):
        noise = {k: v * scale for k, v in base.items()}
        ll = _scored(fit_half, noise)["type_log_loss"]
        if best is None or ll < best[0]:
            best = (ll, scale)
    scale = best[1]
    test = _scored(test_half, {k: v * scale for k, v in base.items()})
    hard = _scored(test_half, {k: 0.0 for k in base})  # the old single label, for comparison
    return {**{k: round(v, 4) for k, v in base.items()}, "scale": scale, "held_out": test,
            "hard_labels_held_out": {k: hard[k] for k in ("type_accuracy", "top_accuracy", "absurd_rate", "type_log_loss",
                                                          "type_brier")}}
