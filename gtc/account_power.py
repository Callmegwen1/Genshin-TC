"""Account-specific power (phase 11): MetaPower, CurrentPower and AccountCeiling, from one build-adjustment mechanism.

  MetaPower       the team at community standard (5-stars C0 with an R1 weapon, 4-stars C6, standard artifacts and
                  talents): the expected power of gtc/evaluate.py.
  CurrentPower    the team as this account has it: levels, talents, weapons, artifacts and constellations.
  AccountCeiling  the team properly built from what this account owns: owned constellations and weapons, levels
                  90, key talents 9, standard artifacts. Owned constellations shift it (measured) or widen it
                  (unknown); weapons below 5 stars widen it, since the standard itself mixes 4- and 5-star weapons.

One mechanism, the per-character build factor:
  own factor  f = exp(sum_k gamma_k x (investment_k - 1)) over level, talents, weapon and artifacts
              (gtc/investment.py, each 0 to 1): 1 when fully built, smaller as each part falls short
  buff factor h = f ** rho: how a support's investment scales the buffs they give
and its propagation to the team through measured shares (the exact lineup's per-hit attribution when it was
simulated, else predicted shares and capability-average buffs):
  team factor F = sum_m own_m x f_m x prod_{s != m} (1 - b_sm x (1 - h_s))
where own_m is m's share of team damage and b_sm the fraction of m's damage that s's buffs supply. Double
counting guard: a support's factor only rescales the part of the carry's damage their buffs make; it is never
added as a separate share, because measured damage shares already include the buffs.

gamma and rho are fitted to exact personal simulations (`calibrate`): your builds against the community's
standard build on the same rotation, for every simulated lineup this account can field. The leave-one-team-out
miss is the model's sd. Where an exact personal simulation exists it overrides the model.

Constellations (the ceiling's other part): a character's owned constellation against the standard one is valued
from same-lineup comparisons in the community database (the median ratio over lineups where only that character
differs) when at least two exist. Otherwise the effect is explicitly unknown: a neutral factor with a wide sd and
the flag "constellation effect unknown", never "no effect".
"""
from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict

from gtc import params
from gtc.sources import SOURCE_DIR

COMPONENTS = ("level", "talents", "weapon", "artifacts")
CALIBRATION_PATH = SOURCE_DIR / "account_power.json"
TRUTH_PATH = SOURCE_DIR / "account_truth.json"
UNKNOWN_CONS_SD = params.get("account_power.unknown_constellation_sd")
MIN_CONS_COMPARISONS = params.get("account_power.min_constellation_comparisons")
WEAPON_SD = params.get("account_power.weapon_sd")
PERSONAL_SIM_SD = params.get("account_power.personal_sim_sd")

_FIT: dict | None = None
_CONS: dict | None = None


def fit() -> dict:
    global _FIT
    if _FIT is None:
        _FIT = json.loads(CALIBRATION_PATH.read_text(encoding="utf-8")) if CALIBRATION_PATH.exists() else {}
    return _FIT


def character_factor(inv, f: dict | None = None, name: str | None = None) -> tuple[float, float]:
    """(own factor, buff factor) of one character's investment, plus their calibrated personal offset when your
    personal simulations measured them (`calibrate`)."""
    f = f or fit()
    gamma = f.get("gamma") or {}
    x = sum(gamma.get(k, 0.0) * (getattr(inv, k) - 1.0) for k in COMPONENTS)
    if name is not None:
        x += (f.get("offsets") or {}).get(name, 0.0)
    own = math.exp(x)
    return own, own ** f.get("rho", 1.0)


def shares(lineup, ev) -> tuple[dict[str, float], dict[str, dict[str, float]]]:
    """(own share per member, buff fraction b[giver][receiver] of the receiver's damage)."""
    from gtc.capabilities import load as load_caps
    from gtc.synergy import table

    key = frozenset(lineup)
    tbl = table()
    e = tbl.by_lineup.get(key) if tbl else None
    if e and e.get("own"):
        own = {m: e["own"].get(m, 0.0) for m in key}
        b: dict[str, dict[str, float]] = defaultdict(dict)
        for giver, given in (e.get("detail") or {}).items():
            # Marginal buff shares overlap when several buffs touch the same hit; scale them to the giver's fair
            # (Shapley) total so the fractions of a receiver's damage do not exceed what the buffs really made.
            marginal = sum(given.values())
            fair = (e.get("buffs_shapley") or {}).get(giver, marginal)
            scale = fair / marginal if marginal > 0 else 0.0
            for k, v in given.items():
                recv = k.split("|", 1)[0]
                b[giver][recv] = b[giver].get(recv, 0.0) + v * scale
        return own, {g: {r: min(0.9, v / own[r]) for r, v in d.items() if own.get(r, 0) > 0} for g, d in b.items()}
    from gtc.evaluate import structure_of

    st, _ = structure_of(key, ev)
    own = dict((st or {}).get("damage_shares") or {})
    caps = load_caps() or {}
    if not own:
        known = {m: caps[m].damage_share for m in key if m in caps}
        total = sum(known.values()) or 1.0
        own = {m: v / total for m, v in known.items()}
    top = max(own, key=lambda m: own[m]) if own else None
    b = {}
    for g in key:
        c = caps.get(g)
        if c is None or not c.buffs_shapley or not top:
            continue
        others = [m for m in key if m != g]
        to_top = c.buff_to_dealer if g != top else 0.0
        d = {}
        for r in others:
            part = c.buffs_shapley * (to_top if r == top else (1 - to_top) / max(1, len(others) - (top in others)))
            if own.get(r, 0) > 0:
                d[r] = min(0.9, part / own[r])
        b[g] = d
    return own, b


def team_factor(own: dict[str, float], buffs: dict[str, dict[str, float]], factors: dict[str, tuple[float, float]]) -> float:
    total = 0.0
    for m, s in own.items():
        f_m = factors.get(m, (1.0, 1.0))[0]
        mult = 1.0
        for g, d in buffs.items():
            if g != m and m in d:
                mult *= 1.0 - d[m] * (1.0 - factors.get(g, (1.0, 1.0))[1])
        total += s * f_m * mult
    return total / (sum(own.values()) or 1.0)


# ---------- constellations ----------

def constellation_table() -> dict[tuple[str, int], dict]:
    """(character, constellation) -> {ratio, n}: same-lineup comparisons against the standard constellation."""
    global _CONS
    if _CONS is None:
        from gtc.sources import gcsim_db

        sims = [t for t in gcsim_db.load() if t.targets == 1 and t.accepted]
        by: dict[frozenset, list] = defaultdict(list)
        for t in sims:
            by[t.names].append(t)
        ratios: dict[tuple[str, int], list[float]] = defaultdict(list)
        for names, ts in by.items():
            base = [t.dps for t in ts if gcsim_db.is_standard(t)]
            if not base:
                continue
            b = statistics.median(base)
            for t in ts:
                for m in t.members:
                    std = 6 if m.rarity == 4 else 0
                    if m.cons == std or (m.weapon_rarity == 5 and m.refine != 1):
                        continue
                    others = all((o.rarity < 5 or o.cons == 0) and (o.weapon_rarity < 5 or o.refine == 1)
                                 for o in t.members if o.name != m.name)
                    if others:
                        ratios[(m.name, m.cons)].append(t.dps / b)
        _CONS = {k: {"ratio": statistics.median(v), "n": len(v),
                     "sd": (statistics.pstdev([math.log(x) for x in v]) / math.sqrt(len(v))) if len(v) > 1 else None}
                 for k, v in ratios.items()}
    return _CONS


def constellation_factor(name: str, cons: int, rarity: int) -> tuple[float, float, str]:
    """(factor on team power, relative sd, status) for owning `cons` instead of the standard constellation."""
    std = 6 if rarity == 4 else 0
    if cons == std:
        return 1.0, 0.0, "standard"
    m = constellation_table().get((name, cons))
    if m and m["n"] >= MIN_CONS_COMPARISONS:
        return m["ratio"], max(m["sd"] or 0.0, 0.02), f"measured on {m['n']} same-lineup comparisons"
    return 1.0, UNKNOWN_CONS_SD, "constellation effect unknown"


# ---------- calibration on exact personal simulations ----------

def _rows(an, ev) -> list[tuple[dict, dict, dict, float]]:
    truth = json.loads(TRUTH_PATH.read_text(encoding="utf-8")) if TRUTH_PATH.exists() else []
    rows = []
    for t in truth:
        lineup = t["lineup"]
        if not all(m in an.investments for m in lineup) or t["ratio"] <= 0:
            continue
        own, b = shares(lineup, ev)
        rows.append((own, b, {m: an.investments[m] for m in lineup}, t["ratio"]))
    return rows


def _loss(rows, f: dict) -> float:
    total = 0.0
    for own, b, invs, ratio in rows:
        factors = {m: character_factor(inv, f, m) for m, inv in invs.items()}
        pred = team_factor(own, b, factors)
        total += (math.log(max(pred, 1e-4)) - math.log(ratio)) ** 2
    return total / len(rows)


def _fit_rows(rows) -> dict:
    """Coordinate search over gamma (0 to 6 per component) and rho (0 to 2), minimising squared log error."""
    f = {"gamma": {k: 1.0 for k in COMPONENTS}, "rho": 1.0}
    grid = [0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0]
    for _ in range(4):
        for k in COMPONENTS:
            best = min(grid, key=lambda g: _loss(rows, {"gamma": {**f["gamma"], k: g}, "rho": f["rho"]}))
            f["gamma"][k] = best
        f["rho"] = min([0.0, 0.25, 0.5, 1.0, 1.5, 2.0], key=lambda r: _loss(rows, {"gamma": f["gamma"], "rho": r}))
    return f


OFFSET_GRID = [x / 4 for x in range(-12, 7)]  # personal offsets in log space, -3 to +1.5


def _fit_offsets(rows, f: dict, lam: float) -> dict:
    """Per-character offsets on top of the investment model, ridge-penalised toward 0 with weight `lam`
    (coordinate search, a few passes)."""
    f = {**f, "offsets": dict(f.get("offsets") or {})}
    names = sorted({m for _, _, invs, _ in rows for m in invs})
    for _ in range(3):
        for m in names:
            mine = [r for r in rows if m in r[2]]

            def obj(o):
                g = {**f, "offsets": {**f["offsets"], m: o}}
                return _loss(mine, g) * len(mine) + lam * o * o
            f["offsets"][m] = min(OFFSET_GRID, key=obj)
    f["offsets"] = {k: v for k, v in f["offsets"].items() if v}
    return f


def calibrate(an, ev) -> dict:
    """Fit gamma and rho on every team with exact personal truth, then a ridge-penalised offset per character
    (the calibrated per-character build factor); the penalty is chosen and the error measured leaving one team
    out at a time. The leave-one-team-out miss is the model's sd."""
    rows = _rows(an, ev)
    if len(rows) < 4:
        return {"teams": len(rows), "note": "too few personal simulations to calibrate"}

    def full_fit(rs, lam):
        g = _fit_rows(rs)
        return _fit_offsets(rs, g, lam) if lam is not None else g

    def loo(lam):
        out = []
        for i, (own, b, invs, ratio) in enumerate(rows):
            fi = full_fit(rows[:i] + rows[i + 1:], lam)
            pred = team_factor(own, b, {m: character_factor(inv, fi, m) for m, inv in invs.items()})
            out.append(math.log(pred / ratio))
        return out

    trials = {lam: loo(lam) for lam in (None, 8.0, 2.0, 0.5)}
    lam = min(trials, key=lambda k: statistics.median(abs(x) for x in trials[k]))
    misses = trials[lam]
    f = full_fit(rows, lam)
    f["penalty"] = lam
    f["loo_by_penalty"] = {str(k): round(statistics.median(abs(x) for x in v), 4) for k, v in trials.items()}
    absm = sorted(abs(x) for x in misses)
    sd = absm[int(0.683 * len(absm))]
    naive = sorted(abs(math.log(1.0 / r)) for *_, r in rows)  # predicting "no build effect" at all
    out = {**f, "teams": len(rows), "loo_sd": round(sd, 4), "loo_median_abs": round(statistics.median(absm), 4),
           "within_1sd": round(sum(x <= sd for x in absm) / len(absm), 3),
           "within_2sd": round(sum(x <= 2 * sd for x in absm) / len(absm), 3),
           "no_model_median_abs": round(statistics.median(naive), 4)}
    CALIBRATION_PATH.write_text(json.dumps(out, indent=1), encoding="utf-8")
    global _FIT
    _FIT = out
    return out


# ---------- the three powers of one team on this account ----------

_TRUTH: dict | None = None


def personal_truth() -> dict[frozenset, dict]:
    """Exact personal simulations by lineup (your builds against the standard build on the same rotation)."""
    global _TRUTH
    if _TRUTH is None:
        rows = json.loads(TRUTH_PATH.read_text(encoding="utf-8")) if TRUTH_PATH.exists() else []
        _TRUTH = {frozenset(r["lineup"]): r for r in rows if r.get("ratio", 0) > 0}
    return _TRUTH


def _full(inv, weapon_value: float | None = None):
    """The same investment at a proper build: level, talents and artifacts full; the weapon at level 90."""
    from types import SimpleNamespace

    return SimpleNamespace(level=1.0, talents=1.0, artifacts=1.0, weapon=1.0 if weapon_value is None else weapon_value)


def account_power(a, ctx: dict) -> dict:
    """{meta, current, ceiling} for an Assessment. ctx: investments, characters (snapshot by key), weapon_value
    (weapon rarity -> value of a level 90 weapon), owned weapons by type for newcomers."""
    from gtc.estimate import Estimate

    meta = a.estimate
    if meta is None or not meta.value:
        return {}
    lineup = list(a.team.members)
    ev = ctx["ev"]
    own, b = shares(lineup, ev)
    f = fit()
    rel_meta = meta.sd / meta.value
    invs, chars = ctx["investments"], ctx["characters"]

    # Current: exact personal simulation when one exists, else the calibrated build factor.
    truth = personal_truth().get(frozenset(lineup))
    owned = all(m in invs for m in lineup)
    if truth and owned:
        f_cur, rel_cur, cur_basis = truth["ratio"], PERSONAL_SIM_SD, "your builds simulated on this lineup's community rotation"
    else:
        factors = {m: character_factor(invs[m], f, m) if m in invs else (1.0, 1.0) for m in lineup}
        f_cur = team_factor(own, b, factors)
        rel_cur = f.get("loo_sd", 0.3) if any(m in invs for m in lineup) else 0.0
        cur_basis = "build factors calibrated on your personal simulations" if rel_cur else "fully built (not owned)"
    current = Estimate(meta.value * f_cur, meta.value * f_cur * math.hypot(rel_meta, rel_cur), meta.tier,
                       [cur_basis])

    # Ceiling: properly built from what you own. Levels, talents and artifacts are full, so their factors are 1. A
    # weapon's rarity is not shifted: the community standard itself mixes 4- and 5-star weapons, so a 4-star at
    # level 90 is not known to fall short of it; a weapon below 5 stars widens the sd instead (WEAPON_SD per member,
    # weighted by their share of the damage). Owned constellations: measured factor or explicitly unknown.
    cons_mult, cons_var, notes, weapon_var = 1.0, 0.0, [], 0.0
    for m in lineup:
        c = chars.get(m)
        if c is not None:
            w_rarity = c.weapon.rarity
            cons, rarity = c.constellation, c.rarity
        else:  # a newcomer: C0, with the best weapon of their type you own
            w_rarity = ctx["newcomer_weapon"].get(m, 4)
            cons, rarity = 0, ctx["rarity"].get(m, 5)
        if w_rarity < 5:
            weapon_var += (WEAPON_SD * own.get(m, 0.25)) ** 2
        cf, csd, status = constellation_factor(m, cons, rarity)
        cons_mult *= cf
        cons_var += csd ** 2
        if status != "standard":
            notes.append(f"{m} C{cons}: {status}" + (f" (x{cf:.2f})" if status.startswith("measured") else ""))
    f_ceil = cons_mult
    rel_ceil = math.sqrt(rel_meta ** 2 + cons_var + weapon_var)
    ceiling = Estimate(meta.value * f_ceil, meta.value * f_ceil * rel_ceil, meta.tier, notes)
    # Model 6.3: the parts of each sd, relative, so reports can say where the uncertainty comes from: the team's own
    # power (simulation spread or pair-model error), the build model's held-out miss (current only; an exact personal
    # simulation replaces it), and owned constellations and weapons (ceiling only).
    sd_parts = {"current": {"team": round(rel_meta, 4), "build": round(rel_cur, 4)},
                "ceiling": {"team": round(rel_meta, 4), "constellations": round(math.sqrt(cons_var), 4),
                            "weapons": round(math.sqrt(weapon_var), 4)}}
    return {"meta": meta, "current": current, "ceiling": ceiling, "sd_parts": sd_parts,
            "unknown_constellations": [n.split(":")[0] for n in notes if "unknown" in n]}


def context(an, ev) -> dict:
    """What account_power needs from an analysis."""
    from gtc import gamedata
    from gtc.investment import _curve

    scoring = an.evidence.kb.scoring if hasattr(an.evidence, "kb") else {}
    game = gamedata.load_characters()
    wtypes = gamedata.load_weapons()
    rarity_value = scoring.get("weapon_rarity", {5: 1.0, 4: 0.8, 3: 0.5})
    weapon_value = {int(k): float(v) * _curve(scoring["level_curve"], 90) for k, v in rarity_value.items()} if scoring else {}
    best_by_type: dict[str, int] = {}
    for w in an.snapshot.all_weapons():
        t = wtypes.get(w.name, {}).get("type")
        if t:
            best_by_type[t] = max(best_by_type.get(t, 0), w.rarity)
    return {"ev": ev, "investments": an.investments, "characters": an.snapshot.by_key(), "weapon_value": weapon_value,
            "newcomer_weapon": {n: best_by_type.get(g.get("weapon"), 4) for n, g in game.items()},
            "rarity": {n: g.get("rarity", 5) for n, g in game.items()}}


def collect_truth(an, cands, progress=print) -> int:
    """Exact personal simulations for every candidate lineup with a standard community config: the community build
    and your builds (Bursts skipped when you cannot afford them) on the same rotation. Saved after each team, so an
    interrupted run keeps what it finished; gcsim runs are cached, so a rerun only simulates what changed."""
    from gtc import gamedata
    from gtc.sim import ITERATIONS, Keys, TeamSim, find_config, render, run
    from gtc.sources import gcsim_db

    names, chars = gamedata.names(), an.snapshot.by_key()
    by_id = {t.id: t for t in gcsim_db.load()}
    lineups = sorted({frozenset(a.team.members) for a in cands if frozenset(a.team.members) in an.evidence.lineup_median}, key=sorted)
    out = []
    for L in lineups:
        lineup = sorted(L)
        if not all(m in chars for m in lineup):
            continue
        cfg = find_config(lineup, names)
        entry = by_id.get(cfg.entry_id) if cfg else None
        if entry is None or not gcsim_db.is_standard(entry):
            continue  # the meta reference must be a standard community build
        try:
            meta = run(render(cfg, {}, Keys(), ITERATIONS)[0])
            ts = TeamSim(lineup, chars, names)
            cur, base = ts.reality(), ts.baseline()
        except Exception as exc:  # a config gcsim cannot finish in time
            progress(f"{' / '.join(lineup)}: skipped ({type(exc).__name__})")
            continue
        if meta.error or cur.error or not meta.dps:
            continue
        out.append({"lineup": lineup, "meta": meta.dps, "current": cur.dps, "potential_er_fixed": base.dps,
                    "ratio": cur.dps / meta.dps, "char_meta": {ts._name(k) or k: v for k, v in meta.character_dps.items()},
                    "char_current": ts.character_dps(cur)})
        TRUTH_PATH.write_text(json.dumps(out, indent=1), encoding="utf-8")
        progress(f"{' / '.join(lineup)}: your builds deal {cur.dps / meta.dps:.0%} of the standard build")
    global _TRUTH
    _TRUTH = None
    return len(out)
