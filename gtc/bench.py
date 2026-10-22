"""Benchmark v2: graded scoring against expert expectations, with a locked validation set.

    python -m gtc bench                         score the calibration and locked sets
    python -m gtc bench --details               also print every assertion
    python -m gtc bench --sweep                 parameter sensitivity on the calibration set
    python -m gtc bench --tune                  grid search on the calibration set (leave-one-out), locked score reported
    python -m gtc bench --record                record scores for the current model version
    python -m gtc bench --unlock --reason "…"   accept a change to the locked set (logged)
    python -m gtc bench --approve               record that the user reviewed and approved the locked set

Each case's assertions score 0 to 1 and the case score is their mean, weighted by the case's confidence (high
3, medium 2, low 1). Pairs score half for the right order and half for the right gap class, judged by the engine's
own probability that one option beats the other: small under 80%, medium 80 to 95%, large above 95%. A pair
expected to be small is a close call: it scores 1 if the engine also calls it a tie, 0.5 if medium, 0 if large.
Assertions the engine cannot express yet (no second team, mechanic centrality, the new structure types) are
counted as pending, never as passes or failures.

Tuning may only read the calibration set (`load_cases("calibration")`); the locked set is pinned by hash.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import date

import yaml

from gtc import KNOWLEDGE_DIR, params

SETS = {"calibration": KNOWLEDGE_DIR / "benchmark_calibration.yaml", "locked": KNOWLEDGE_DIR / "benchmark_locked.yaml"}
LOCK_PATH = KNOWLEDGE_DIR / "benchmark_locked.lock.json"
RESULTS_PATH = KNOWLEDGE_DIR / "bench_results.yaml"
WEIGHT = {"high": 3.0, "medium": 2.0, "low": 1.0}
GAP_ORDER = ["small", "medium", "large"]

# Structure vocabulary of the cases -> gtc/structure.py names: types (one per team) and patterns (independent).
STRUCTURE_NAMES = {"hypercarry": "hypercarry", "dualCarry": "dual_carry", "driver": "driver", "reactionCore": "reaction_core",
                   "distributedDamage": "distributed"}
STRUCTURE_PATTERNS = {"onFieldCarry": "on_field_carry", "quickswap": "quickswap"}

# Parameters that survive the roadmap, with plausible and absurd values for the sensitivity sweep. Parameters
# scheduled for deletion are swept too, so their effect is visible before they go, but get no adversarial cases.
SWEEP = {
    "decision.risk": [0.0, 0.3, 0.674, 1.0, 2.0, 5.0],
    "account.plan_weights": [[1.0, 1.0, 0.5, 0.25], [1.0, 0.5, 0.25, 0.1], [1.0, 1.0, 1.0, 1.0], [1.0, 0.0, 0.0, 0.0]],
    "teams.unproven_quality": [1.0, 2.0, 3.0, 5.0],
    "teams.single_team_cap": [3.0, 4.0, 5.0],
    "account.viable_carry_potential": [0.0, 30.0, 45.0, 60.0],
    "account.replacement_value": [0.0, 10.0, 20.0, 30.0, 40.0],
}
SURVIVAL = {
    "decision.risk": "keep; the decision policy's risk weight (gtc/decision.py, phase 10)",
    "account.plan_weights": "keep; the general four-team utility (the modes have their own utilities since phase 12)",
    "teams.unproven_quality": "keep; a search-ordering heuristic for generated archetypes",
    "teams.single_team_cap": "keep; a search-ordering heuristic for generated archetypes",
    "account.viable_carry_potential": "keep; a reporting threshold for the carry-gap warning",
    "account.replacement_value": "keep; planner v2 value over replacement (phase 12), calibrated plateau 10..35",
}


@dataclass
class Result:
    id: str
    set: str
    question: str
    weight: float
    assertions: list[tuple[str, float | None, str]] = field(default_factory=list)  # (name, score or None if pending, detail)
    outputs: dict[str, float] = field(default_factory=dict)  # numeric outputs, for sensitivity
    error: str = ""

    @property
    def score(self) -> float | None:
        scored = [s for _, s, _ in self.assertions if s is not None]
        return sum(scored) / len(scored) if scored else None

    @property
    def pending(self) -> int:
        return sum(1 for _, s, _ in self.assertions if s is None)


def load_cases(which: str) -> list[dict]:
    return (yaml.safe_load(SETS[which].read_text(encoding="utf-8")) or {}).get("cases", [])


# ---------- engine access ----------

class Engine:
    """One account model plus per-roster caches of plans and evaluations."""

    def __init__(self):
        from gtc.benchmark import engine

        self.am = engine()
        self._plans: dict[tuple, tuple] = {}
        self._cands: dict[tuple, list] = {}

    def roster(self, names: list[str], cons: dict | None = None):
        from gtc.benchmark import roster

        return roster(self.am, names, cons)

    def plan(self, names: list[str], cons: dict | None = None):
        key = (tuple(sorted(names)), tuple(sorted((cons or {}).items())))
        if key not in self._plans:
            r = self.roster(names, cons)
            self._plans[key] = (r, *self.am.plan(r))
        return self._plans[key]

    def lineup(self, names: list[str]):
        """The engine's assessment of exactly this lineup, as the manual Team Builder would evaluate it (model 6.3:
        any legal team, generated by a template or not), or None if it is not a legal team or has no number."""
        key = tuple(sorted(names))
        if key not in self._cands:
            self._cands[key] = self.am.assess_lineup(list(names), self.roster(names))
        a = self._cands[key]["assessment"]
        return a if a is not None and a.estimate is not None and a.estimate.tier != "F" else None


def _gap_class(p: float) -> str:
    p = max(p, 1 - p)
    return "small" if p < 0.8 else "medium" if p < 0.95 else "large"


def _pair_score(better, worse, gap: str) -> tuple[float, str]:
    from gtc.estimate import Estimate, prob_greater

    if better is None:
        return 0.0, "the option expected to be better forms no team or cannot be evaluated"
    if worse is None:
        worse = Estimate(0.0, 0.0, "B")  # forms no team: worth nothing, so the better option wins by a mile
    eb = better if isinstance(better, Estimate) else Estimate(better, 0.0, "B")
    ew = worse if isinstance(worse, Estimate) else Estimate(worse, 0.0, "B")
    p = prob_greater(eb, ew)
    got = _gap_class(p)
    detail = f"{eb.value:.1f}±{eb.sd:.1f} vs {ew.value:.1f}±{ew.sd:.1f}, P(better)={p:.2f}, gap {got}"
    if gap == "small":
        return {"small": 1.0, "medium": 0.5, "large": 0.0}[got], detail
    if p <= 0.5:
        return 0.0, detail  # wrong order: no credit for the gap either
    d = abs(GAP_ORDER.index(got) - GAP_ORDER.index(gap))
    return 0.5 + (0.5 if d == 0 else 0.25 if d == 1 else 0.0), detail


def _kendall(expected: list, values: dict[str, float]) -> float:
    """Kendall tau over the expected order (inner lists are ties), mapped to 0..1."""
    rank = {}
    for i, group in enumerate(expected):
        for name in (group if isinstance(group, list) else [group]):
            rank[name] = i
    names = [n for n in rank if values.get(n) is not None]
    agree = total = 0
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if rank[a] == rank[b]:
                continue
            total += 1
            agree += (values[a] > values[b]) == (rank[a] < rank[b])
    return agree / total if total else 1.0


def _templates_for(kb, mechanic: str) -> list:
    """Archetype templates that perform a mechanic, until identity v2 names mechanics directly (phase 8)."""
    aliases = {"vaporize": ("vaporize", "international"), "aggravate": ("aggravate", "quicken"),
               "lunar_charged": ("lunar_charged",), "mono_pyro": ("mono_pyro",), "anemo_carry": ("anemo_carry",)}
    keys = aliases.get(mechanic, (mechanic,))
    return [t for t in kb.templates.values() if any(k in t.id for k in keys)]


# ---------- evaluation ----------

def evaluate(case: dict, eng: Engine, which: str) -> Result:
    res = Result(case["id"], which, case["question"], WEIGHT.get(case.get("confidence", "medium"), 2.0))
    try:
        getattr(_Q, case["question"])(case, eng, res)
    except KeyError as exc:
        res.error = f"unknown character or key: {exc}"
        res.assertions.append(("error", 0.0, res.error))
    return res


class _Q:
    @staticmethod
    def pull_ranking(case, eng, res):
        r, base, cands = eng.plan(case["account"]["roster"], case["account"].get("cons"))
        est = {}
        for name in case["candidates"]:
            v = eng.am.value_of(name, r, base, cands)
            est[name] = v.estimate if v is not None else None
            if v is not None:
                res.outputs[f"gain:{name}"] = v.estimate.value
        values = {k: (e.value if e else None) for k, e in est.items()}
        if case.get("expected_ranking"):
            res.assertions.append(("ranking", _kendall(case["expected_ranking"], values), str(values)))
        for p in case.get("pairs", []):
            s, d = _pair_score(est.get(p["better"]), est.get(p["worse"]), p["gap"])
            res.assertions.append((f"{p['better']}>{p['worse']} ({p['gap']})", s, d))
        for name, (lo, hi) in (case.get("magnitude") or {}).items():
            v = values.get(name)
            s = 0.0 if v is None else 1.0 if lo <= v <= hi else max(0.0, 1 - min(abs(v - lo), abs(v - hi)) / max(hi - lo, 1.0))
            res.assertions.append((f"gain of {name} in [{lo}, {hi}]", s, f"{v}"))

    @staticmethod
    def team_ranking(case, eng, res):
        est = {}
        for key, names in case["lineups"].items():
            a = eng.lineup(names)
            est[key] = a.estimate if a is not None else None
            if a is not None:
                res.outputs[f"team:{key}"] = a.estimate.value
        if case.get("expected_ranking"):
            res.assertions.append(("ranking", _kendall(case["expected_ranking"], {k: (e.value if e else None) for k, e in est.items()}), ""))
        for p in case.get("pairs", []):
            s, d = _pair_score(est.get(p["better"]), est.get(p["worse"]), p["gap"])
            res.assertions.append((f"{p['better']}>{p['worse']} ({p['gap']})", s, d))

    @staticmethod
    def plan(case, eng, res):
        _, plan, cands = eng.plan(case["account"]["roster"], case["account"].get("cons"))
        exp = case["expect"]
        res.outputs["plan_value"] = plan.value
        for i, a in enumerate(sorted(plan.teams, key=lambda a: (-a.potential, sorted(a.team.members)))):
            res.outputs[f"plan_team_{i}"] = a.potential
        members = {m for a in plan.teams for m in a.team.members}
        if exp.get("team_with"):
            team = next((a for a in plan.teams if exp["team_with"] in a.team.members), None)
            names = set(team.team.members) if team else set()
            for m in exp.get("includes", []):
                res.assertions.append((f"{exp['team_with']} team includes {m}", float(m in names), " / ".join(sorted(names))))
            for m in exp.get("excludes", []):
                res.assertions.append((f"{exp['team_with']} team excludes {m}", float(bool(team) and m not in names), " / ".join(sorted(names))))
        for m in exp.get("members_in_plan", []):
            res.assertions.append((f"{m} in the plan", float(m in members), ""))
        if "max_teams" in exp:
            res.assertions.append((f"at most {exp['max_teams']} teams", float(len(plan.teams) <= exp["max_teams"]), str(len(plan.teams))))
        if exp.get("no_secondary"):
            from gtc import gamedata, profiles

            el = {k: v.get("element") for k, v in gamedata.load_characters().items()}
            ab = profiles.plan_for("abyss", cands, el)
            res.assertions.append(("no second team worth building", float(len(plan.teams) == 1 and len(ab.teams) == 1),
                                   f"plan {len(plan.teams)} teams; abyss: {ab.note or len(ab.teams)}"))

    @staticmethod
    def validity(case, eng, res):
        lineup, exp, kb = case["lineup"], case["expect"], eng.am.kb
        from gtc import validity as mech

        illegal = mech.mechanical(lineup, kb.characters)
        if "legal" in exp:
            # Mechanical validity (model 6.3): any legal four-character team, generated by a template or not.
            res.assertions.append(("legal team" if exp["legal"] else "illegal team", float((not illegal) == exp["legal"]),
                                   "; ".join(illegal) or "legal"))
        if illegal:
            return
        if "support" in exp:
            got = eng.am.assess_lineup(list(lineup), eng.roster(sorted(set(lineup))))["status"]
            res.assertions.append((f"support: {exp['support']}", float(got == exp["support"]), got))
        a = eng.lineup(lineup)
        if "forms_team" in exp:
            name = "forms a team" if exp["forms_team"] else "cannot form a team"
            res.assertions.append((name, float((a is not None) == exp["forms_team"]),
                                   a.team.template.id if a else "no archetype accepts it"))
        if a is not None:
            res.outputs["value"] = a.estimate.value
        for mech in exp.get("invalid_as", []):
            from gtc.teams import fill_template

            r = eng.roster(lineup)
            formed = [t.id for t in _templates_for(kb, mech)
                      if any(set(x.members) == set(lineup) for x in fill_template(t, r, kb, limit=3, rank_by="potential"))]
            res.assertions.append((f"cannot perform {mech}", float(not formed), ", ".join(formed) or "rejected"))
        for mech in exp.get("not_identity", []):
            # Identity v2: "identified as" a mechanic means it is central AND belongs to the team's carry (Clorinde with
            # Columbina and Ineffa runs on Lunar-Charged, but it is theirs, not Clorinde's).
            ident = a.evaluation.identity if a and a.evaluation else {}
            central = ident.get("central") or []
            owners = (ident.get("owners") or {}).get(mech) or []
            actor = ident.get("primary_actor")
            theirs = mech in central and (not owners or not actor or actor in owners)
            res.assertions.append((f"not identified as {mech}", float(not theirs), ident.get("label") or "no team"))
        if exp.get("weaker_than"):
            ref = eng.lineup(exp["weaker_than"])
            # a lineup with no number is worth nothing, the convention _pair_score already uses
            ok = ref is not None and (a is None or a.estimate.value < ref.estimate.value)
            res.assertions.append(("weaker than the reference team", float(ok),
                                   f"{a.estimate.value if a else None} vs {ref.estimate.value if ref else None}"))

    @staticmethod
    def identity(case, eng, res):
        lineup, exp = case["lineup"], case["expect"]
        a = eng.lineup(lineup)
        ident = a.evaluation.identity if a and a.evaluation else None
        if ident is None:
            from gtc.identity import identify

            ident = identify(lineup, eng.am.ev)
        lead = ident.get("primary_actor")
        if "primary_actor" in exp:
            res.assertions.append((f"primary actor {exp['primary_actor']}", float(lead == exp["primary_actor"]), str(lead)))
        for n in exp.get("not_primary", []):
            res.assertions.append((f"{n} is not the primary actor", float(a is not None and lead != n), str(lead)))
        if "structure" in exp:
            # Structure v2 (phase 7) gives probabilities: the assertion scores the probability of the expected
            # structure, so a near-threshold team earns partial credit instead of all or nothing.
            from gtc.evaluate import structure_of as evaluated_structure

            want = exp["structure"]
            st, _ = evaluated_structure(lineup, eng.am.ev)
            st = st or {}
            if want in STRUCTURE_PATTERNS:
                p = (st.get("patterns") or {}).get(STRUCTURE_PATTERNS[want], 0.0)
            else:
                p = (st.get("probabilities") or {}).get(STRUCTURE_NAMES.get(want, want), float(st.get("type") == STRUCTURE_NAMES.get(want, want)))
            probs = ", ".join(f"{k} {v:.0%}" for k, v in sorted((st.get("probabilities") or {}).items(), key=lambda kv: -kv[1]) if v >= 0.05)
            res.assertions.append((f"structure {want}", round(p, 3), f"{st.get('type')} ({probs}; {st.get('source', '?')})"))
        # Identity v2 (phase 8): central scores the centrality against the threshold; incidental is full credit when
        # present but not central, half when absent, nothing when it is claimed as central.
        from gtc.identity import CENTRAL, INCIDENTAL

        systems = ident.get("systems") or {}
        for mech in exp.get("central", []):
            c = systems.get(mech, 0.0)
            res.assertions.append((f"{mech} is central", round(min(1.0, c / CENTRAL), 3), f"centrality {c:.2f}; {ident.get('label')}"))
        for mech in exp.get("incidental", []):
            c = systems.get(mech, 0.0)
            score = 0.0 if c >= CENTRAL else 1.0 if c >= INCIDENTAL else 0.5
            res.assertions.append((f"{mech} is incidental", score, f"centrality {c:.2f}; {ident.get('label')}"))
        for token in exp.get("label_excludes", []):
            # What the label claims: the carry and the central mechanics, not the "incidental ..." mention.
            label = a.label if a else ""
            claimed = " · ".join(p for p in label.split(" · ") if not p.startswith("incidental"))
            res.assertions.append((f"label avoids '{token}'", float(a is not None and token.lower() not in claimed.lower()), label))

    @staticmethod
    def carries(case, eng, res):
        _, _, cands = eng.plan(case["account"]["roster"], case["account"].get("cons"))
        viable = eng.am.viable_carries(cands)
        for k, a in viable.items():
            res.outputs[f"carry:{k}"] = a.potential
        for n in case["expect"].get("viable_includes", []):
            res.assertions.append((f"{n} counts as a viable carry", float(n in viable), ", ".join(sorted(viable)) or "none"))
        for n in case["expect"].get("viable_excludes", []):
            res.assertions.append((f"{n} is not a viable carry", float(n not in viable), ", ".join(sorted(viable)) or "none"))

    @staticmethod
    def mode(case, eng, res):
        from gtc import gamedata, profiles

        el = {n: g["element"] for n, g in gamedata.load_characters().items()}
        scores = {}
        for key, names in case["accounts"].items():
            _, _, cands = eng.plan(names)
            scores[key] = {m: p.score for m, p in profiles.all_plans(cands, el).items()}
            for m, v in scores[key].items():
                res.outputs[f"{key}:{m}"] = v
        for mode, order in case["expect"].items():
            vals = [scores[k][mode] for k in order]
            res.assertions.append((f"{mode}: {' > '.join(order)}", float(all(x > y for x, y in zip(vals, vals[1:]))), str(vals)))


def run(which: tuple[str, ...] = ("calibration", "locked"), eng: Engine | None = None) -> list[Result]:
    eng = eng or Engine()
    return [evaluate(c, eng, w) for w in which for c in load_cases(w)]


# ---------- summaries ----------

def summarize(results: list[Result]) -> dict:
    scored = [r for r in results if r.score is not None]
    wsum = sum(r.weight for r in scored)
    out = {"cases": len(results), "scored_cases": len(scored),
           "score": round(sum(r.weight * r.score for r in scored) / wsum, 4) if wsum else None,
           "pending_assertions": sum(r.pending for r in results)}
    by_q = {}
    for r in scored:
        by_q.setdefault(r.question, []).append(r.score)
    out["by_question"] = {q: round(sum(v) / len(v), 3) for q, v in sorted(by_q.items())}
    pairs = [(n, s) for r in results for n, s, _ in r.assertions if s is not None and ">" in n]
    order_ok = [s >= 0.5 for n, s in pairs if "(small)" not in n]
    close = [s for n, s in pairs if "(small)" in n]
    out["pairwise_order_accuracy"] = round(sum(order_ok) / len(order_ok), 3) if order_ok else None
    out["close_calls_kept_close"] = round(sum(close) / len(close), 3) if close else None
    # Validity as a classifier: positive class = "rejected".
    tp = fp = fn = tn = 0
    for r in results:
        for n, s, _ in r.assertions:
            if s is None or not (n.startswith("cannot") or n == "forms a team"):
                continue
            expect_reject = n.startswith("cannot")
            correct = s == 1.0
            if expect_reject:
                tp += correct
                fn += not correct
            else:
                tn += correct
                fp += not correct
    out["validity"] = {"rejected_correctly": tp, "missed_invalid": fn, "valid_kept": tn, "valid_rejected": fp}
    return out


def render(results: list[Result], details: bool = False) -> str:
    lines = []
    for which in dict.fromkeys(r.set for r in results):
        mine = [r for r in results if r.set == which]
        s = summarize(mine)
        lock = "" if which != "locked" else f" ({'approved' if lock_state().get('approved') else 'not yet approved by the user: provisional'})"
        lines.append(f"{which}{lock}: score {s['score']:.1%} over {s['scored_cases']} cases, {s['pending_assertions']} pending assertions")
        lines.append(f"  by question: {s['by_question']}")
        lines.append(f"  pairwise order {s['pairwise_order_accuracy']}, close calls kept close {s['close_calls_kept_close']}, validity {s['validity']}")
        if which == "calibration":
            d = decision_regret()
            lines.append(f"  decision regret on measured data (choosing by expected - risk x sd, risk {d['risk']}): "
                         f"{d['mean_regret']:.2%} over {d['families']} families")
        for r in mine:
            sc = "pending" if r.score is None else f"{r.score:.2f}"
            lines.append(f"  {sc:>7}  {r.id}")
            if details or (r.score is not None and r.score < 1):
                for n, a, d in r.assertions:
                    mark = "  ..." if a is None else f"{a:5.2f}"
                    lines.append(f"           {mark}  {n}: {d}")
    return "\n".join(lines)


# ---------- the locked set ----------

def locked_hash() -> str:
    return hashlib.sha256(SETS["locked"].read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:16]


def lock_state() -> dict:
    return json.loads(LOCK_PATH.read_text(encoding="utf-8")) if LOCK_PATH.exists() else {}


def check_lock() -> tuple[bool, str]:
    st = lock_state()
    if not st:
        return False, "the locked set has no lock file: run python -m gtc bench --unlock --reason 'initial lock'"
    if st["hash"] != locked_hash():
        return False, ("knowledge/benchmark_locked.yaml changed since it was locked; if intended, run "
                       "python -m gtc bench --unlock --reason '...' (never during tuning)")
    return True, ""


def unlock(reason: str) -> None:
    if not reason or len(reason.strip()) < 10:
        raise ValueError("unlocking the locked set needs a reason")
    st = lock_state() or {"history": [], "approved": False}
    st["history"].append({"date": date.today().isoformat(), "hash": locked_hash(), "reason": reason.strip(),
                          "approval_reset": bool(st.get("approved"))})
    st["hash"] = locked_hash()
    st["approved"] = False  # a changed set needs the user's review again
    LOCK_PATH.write_text(json.dumps(st, indent=1), encoding="utf-8")


def approve() -> None:
    ok, msg = check_lock()
    if not ok:
        raise ValueError(msg)
    st = lock_state()
    st["approved"] = True
    st["history"].append({"date": date.today().isoformat(), "hash": st["hash"], "reason": "approved by the user"})
    LOCK_PATH.write_text(json.dumps(st, indent=1), encoding="utf-8")


# ---------- sensitivity and tuning (calibration set only) ----------

def _with(overrides: dict, which=("calibration",)) -> list[Result]:
    previous = params.apply(overrides)
    try:
        return run(which)
    finally:
        params.apply(previous)


def sweep(progress=print) -> dict:
    """Continuous sensitivity: for each parameter value, the calibration score and how much the engine's numeric
    outputs move against the current setting (mean relative change), and which cases' scores change."""
    base = run(("calibration",))
    base_score = summarize(base)["score"]
    base_out = {(r.id, k): v for r in base for k, v in r.outputs.items()}
    base_case = {r.id: r.score for r in base}
    table = {}
    for key, values in SWEEP.items():
        rows = []
        for val in values:
            res = _with({key: val})
            moved = []
            for r in res:
                for k, v in r.outputs.items():
                    b = base_out.get((r.id, k))
                    if b:
                        moved.append(abs(v - b) / abs(b))
            changed_cases = sorted(r.id for r in res if (r.score or 0) != (base_case.get(r.id) or 0))
            regret = decision_regret(val)["mean_regret"] if key == "decision.risk" else None
            rows.append({"value": val, "score": summarize(res)["score"], "score_change": round(summarize(res)["score"] - base_score, 4),
                         "decision_regret": round(regret, 4) if regret is not None else None,
                         "mean_output_change": round(sum(moved) / len(moved), 4) if moved else 0.0,
                         "outputs_moved": sum(1 for m in moved if m > 0.005), "cases_changed": changed_cases})
            progress(f"{key} = {val}: score {rows[-1]['score']:.3f}, outputs moved {rows[-1]['outputs_moved']}")
        table[key] = {"survival": SURVIVAL.get(key, ""), "current": params.get(key), "rows": rows}
    return {"base_score": base_score, "parameters": table}


TUNE_GRID = {"decision.risk": [0.3, 0.674, 1.0], "account.plan_weights": [[1.0, 1.0, 0.5, 0.25], [1.0, 0.5, 0.25, 0.1], [1.0, 1.0, 1.0, 1.0]]}


def tune(progress=print) -> dict:
    """Grid search on the calibration set only, scored leave-one-out by case; the locked set is scored at the
    chosen and the current setting for comparison, never used to choose. Nothing is applied automatically."""
    import itertools

    keys = list(TUNE_GRID)
    combos = [dict(zip(keys, c)) for c in itertools.product(*(TUNE_GRID[k] for k in keys))]
    current = {k: params.get(k) for k in keys}
    cur_i = next((i for i, c in enumerate(combos) if c == current), None)
    table = []
    for c in combos:
        res = _with(c)
        table.append({r.id: (r.score, r.weight) for r in res})
        progress(f"{c}: {summarize(res)['score']:.3f}")
    ids = list(table[0])

    def score_without(i, skip):
        num = sum(s * w for k, (s, w) in table[i].items() if k != skip and s is not None)
        den = sum(w for k, (s, w) in table[i].items() if k != skip and s is not None)
        return num / den if den else 0.0

    def choose(skip):
        return max(range(len(combos)), key=lambda i: (round(score_without(i, skip), 9), i == cur_i))

    loo_num = loo_den = 0.0
    for case in ids:
        s, w = table[choose(case)][case]
        if s is not None:
            loo_num += s * w
            loo_den += w
    best = choose(None)
    locked_current = summarize(run(("locked",)))["score"]
    locked_best = summarize(_with(combos[best], ("locked",)))["score"]
    return {"current": current, "best": combos[best],
            "calibration_current": score_without(cur_i, None) if cur_i is not None else None,
            "calibration_best": score_without(best, None),
            "calibration_leave_one_out": loo_num / loo_den if loo_den else None,
            "locked_current": locked_current, "locked_at_best": locked_best}


def record(results: list[Result], extra: dict | None = None) -> None:
    data = (yaml.safe_load(RESULTS_PATH.read_text(encoding="utf-8")) or {}) if RESULTS_PATH.exists() else {}
    entry = {"date": date.today().isoformat(), "fingerprint": params.fingerprint(), "locked_hash": locked_hash(),
             "locked_approved": bool(lock_state().get("approved"))}
    for which in ("calibration", "locked"):
        mine = [r for r in results if r.set == which]
        if mine:
            entry[which] = summarize(mine)
    if extra:
        entry.update(extra)
    data[params.version()] = entry
    RESULTS_PATH.write_text("# GENERATED by `python -m gtc bench --record`.\n" + yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


# ---------- decision regret: calibrating risk on measured data ----------

_CV_CACHE: dict | None = None


def decision_regret(risk: float | None = None, trials: int = 40, seed: int = 3, min_group: int = 6) -> dict:
    """How well choosing by expected value minus `risk` x sd picks the truly best team, on measured data.

    Within each archetype family with at least `min_group` simulated lineups, half the lineups (at random) are
    treated as unsimulated: their value is the pair model's held-out prediction, with the measured sd of that
    evidence; the other half are read as measured, with a reading drawn around the true value at the community
    sd, so neither kind of evidence is treated as exact. The engine's rule picks the best by
    expected minus risk x sd; regret is the true best value minus the true value of the pick, relative to the
    true best. Averaged over families and random splits. Too little risk falls for overestimated predictions
    (the winner's curse); too much refuses good predicted teams. Ground truth is measured, not opinion."""
    import random

    from gtc import estimate, pairmodel

    global _CV_CACHE
    if _CV_CACHE is None:
        data = pairmodel.lineup_data()
        _CV_CACHE = {"data": data, "cv": pairmodel.cv_predictions(data)}
    data, cv = _CV_CACHE["data"], _CV_CACHE["cv"]
    risk = params.get("decision.risk") if risk is None else risk
    groups: dict[str, list] = {}
    for d in data:
        if d[0] in cv and d[3] != "other":
            groups.setdefault(d[3], []).append(d)
    groups = {k: v for k, v in groups.items() if len(v) >= min_group}
    rel_pred = estimate.load().get("pair", {}).get("near", {}).get("sd", 0.1)
    rng = random.Random(seed)
    regrets = []
    for _ in range(trials):
        for fam, rows in groups.items():
            best_true = max(r[1] for r in rows)
            opts = []
            for lineup, true, n, _, _ in rows:
                if rng.random() < 0.5:
                    est, sd = cv[lineup], cv[lineup] * rel_pred
                else:
                    # A measured value is itself a noisy reading of the truth: draw it with the community sd.
                    sd = true * estimate.community_rel_sd(n)
                    est = true + rng.gauss(0.0, sd)
                opts.append((est - risk * sd, true))
            pick = max(opts)[1]
            regrets.append((best_true - pick) / best_true)
    return {"risk": risk, "families": len(groups), "mean_regret": sum(regrets) / len(regrets)}
