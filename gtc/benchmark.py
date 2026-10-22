"""Benchmark: the engine's answers against expert answers (knowledge/benchmark.yaml).

    python -m gtc benchmark            score the current model
    python -m gtc benchmark --record   score it and record the result for the current model version
    python -m gtc benchmark --tune     fit the tunable parameters in TUNE_GRID, with leave-one-out
                                       cross-validation so the cases are not simply memorised

Results are kept per model version in knowledge/benchmark_results.yaml, with the fingerprint of the tunable
files, so tests can check that no parameter changed without a version bump and a benchmark run.
"""
from __future__ import annotations

import itertools
import time
from dataclasses import dataclass
from datetime import date

import yaml

from gtc import KNOWLEDGE_DIR, SNAPSHOT_DIR, gamedata, knowledge, params

BENCHMARK_PATH = KNOWLEDGE_DIR / "benchmark.yaml"
RESULTS_PATH = KNOWLEDGE_DIR / "benchmark_results.yaml"

# Parameters the tuner may change, with the values it tries. Kept small: every combination runs the benchmark.
TUNE_GRID = {
    "decision.risk": [0.3, 0.674, 1.0],
    "teams.unproven_quality": [1.0, 2.0, 3.0],
}


@dataclass
class Result:
    id: str
    kind: str
    passed: bool
    detail: str


def load_cases() -> list[dict]:
    return (yaml.safe_load(BENCHMARK_PATH.read_text(encoding="utf-8")) or {}).get("cases", [])


def engine():
    """A fresh account model, calibrated on the stored snapshot (the calibration needs real teams)."""
    from gtc.account import AccountModel
    from gtc.report import analyze
    from gtc.snapshot import Snapshot, latest_snapshot

    from gtc import teams

    teams._MATE_Q.clear()  # teammate qualities depend on tunable values
    kb = knowledge.load()
    an = analyze(Snapshot.load(latest_snapshot(SNAPSHOT_DIR)), kb)
    return AccountModel(an, kb)


def roster(am, names: list[str], cons: dict[str, int] | None = None):
    from gtc.teams import Member

    game = gamedata.load_characters()
    out = []
    for n in names:
        if n not in game or n not in am.kb.characters:
            raise KeyError(f"benchmark names unknown character {n}")
        c = (cons or {}).get(n, 6 if game[n]["rarity"] == 4 else 0)
        out.append(Member(n, game[n]["element"], 1.0, {**am.kb.characters[n].roles_at(c), **am.ev.faction_roles(n)}, c))
    return out


def _contains(members, expect: dict) -> tuple[bool, str]:
    ms = set(members)
    missing = [m for m in expect.get("includes", []) if m not in ms]
    present = [m for m in expect.get("excludes", []) if m in ms]
    any_of = expect.get("includes_any")
    ok = not missing and not present and (not any_of or bool(ms & set(any_of)))
    why = []
    if missing:
        why.append(f"missing {', '.join(missing)}")
    if present:
        why.append(f"has {', '.join(present)}")
    if any_of and not ms & set(any_of):
        why.append(f"none of {', '.join(any_of)}")
    return ok, " / ".join(members) + (f" ({'; '.join(why)})" if why else "")


def evaluate(case: dict, am) -> Result:
    from gtc.report import assess
    from gtc.teams import evaluate_lineup, fill_template

    kind = case["kind"]
    r = roster(am, case.get("roster", []), case.get("cons"))
    try:
        if kind == "best_team":
            if case.get("template"):  # this archetype's own best team, before lineups are deduplicated across archetypes
                t = am.kb.templates[case["template"]]
                cands = sorted((am._assess(x) for x in fill_template(t, r, am.kb, limit=12, rank_by="potential")),
                               key=lambda a: -a.potential)
            else:
                cands = am.candidates(r)
            pool = [a for a in cands if (not case.get("lead") or a.lead == case["lead"])
                    and (not case.get("template") or a.team.template.id == case["template"])]
            if not pool:
                return Result(case["id"], kind, False, "no team formed")
            ok, d = _contains(pool[0].team.members, case["expect"])
            return Result(case["id"], kind, ok, d)
        if kind == "no_team":
            templates = [am.kb.templates[case["template"]]] if case.get("template") else list(am.kb.templates.values())
            # Phase 9: templates only generate candidates, so a template forming a lineup proves nothing. The team
            # this case forbids exists only if the lineup's identity agrees with the template's reading of it: its
            # primary actor is the template's own lead.
            found = []
            for t in templates:
                for team in fill_template(t, r, am.kb, limit=5, lead=case.get("lead"), rank_by="potential"):
                    if not set(case.get("members", [])) <= set(team.members):
                        continue
                    a = assess(team, am.ev, am.model, am.kb)
                    if a.primary_actor and a.primary_actor == team.lead:
                        found.append(f"{t.label}: {' / '.join(team.members)} (identity: {a.label})")
            return Result(case["id"], kind, not found, found[0] if found else "none identified as the forbidden team")
        if kind == "plan_team":
            plan, _ = am.plan(r)
            who = case.get("lead") or case.get("member")
            team = next((a for a in plan.teams if (a.lead == who if case.get("lead") else who in a.team.members)), None)
            if team is None:
                return Result(case["id"], kind, False, f"no team with {who} in the plan")
            ok, d = _contains(team.team.members, case["expect"])
            return Result(case["id"], kind, ok, d)
        if kind in ("pull_top", "pull_kind"):
            base, cands = am.plan(r)
            vals = sorted((v for n in case["pool"] if (v := am.value_of(n, r, base, cands))), key=lambda v: -v.gain)
            order = ", ".join(f"{v.name} {v.gain:+.1f} ({v.kind})" for v in vals[:4])
            if kind == "pull_top":
                if not vals:
                    return Result(case["id"], kind, False, "no values")
                # The phase 3 decision rule: options within noise are ties. The expected answer passes unless the
                # engine's top pick is likely better than every acceptable answer (80% or more).
                from gtc.estimate import prob_greater
                top = vals[0]
                ok = top.name in case["top_in"] or any(
                    v.name in case["top_in"] and v.estimate and top.estimate and prob_greater(top.estimate, v.estimate) < 0.8
                    for v in vals)
                return Result(case["id"], kind, ok, order)
            v = next((v for v in vals if v.name == case["character"]), None)
            ok = v is not None and v.kind in case["kind_in"]
            if ok and case.get("not_top"):
                ok = vals.index(v) >= case["not_top"]
            return Result(case["id"], kind, ok, order)
        if kind == "better_lineup":
            names = list(dict.fromkeys(case["better"] + case["worse"]))
            full = roster(am, names)
            better, worse = evaluate_lineup(case["better"], full, am.kb), evaluate_lineup(case["worse"], full, am.kb)
            if better is None:
                return Result(case["id"], kind, False, "the better lineup forms no valid team")
            vb = assess(better, am.ev, am.model, am.kb).estimate.value
            if worse is None:
                return Result(case["id"], kind, True, f"{vb:.0f} against no valid team")
            vw = assess(worse, am.ev, am.model, am.kb).estimate.value
            return Result(case["id"], kind, vb > vw, f"{vb:.0f} against {vw:.0f}")
        if kind == "carry_gap":
            _, cands = am.plan(r)
            if am.viable_carries(cands):
                return Result(case["id"], kind, False, f"found carries {', '.join(am.viable_carries(cands))}")
            best = am.best_carries_for(r)
            if not best:
                return Result(case["id"], kind, False, "no carry recommended")
            name, team = best[0]
            owned = [m for m in team.team.members if m != name]
            return Result(case["id"], kind, am.is_primary_carry(name) and len(owned) == 3, f"{name}: {' / '.join(team.team.members)}")
    except KeyError as exc:
        return Result(case["id"], kind, False, f"error: {exc}")
    raise ValueError(f"unknown benchmark kind {kind}")


def run(cases: list[dict] | None = None, am=None) -> list[Result]:
    cases = cases if cases is not None else load_cases()
    am = am or engine()
    return [evaluate(c, am) for c in cases]


def score(results: list[Result]) -> float:
    return sum(r.passed for r in results) / len(results) if results else 0.0


def tune(progress=print) -> dict:
    """Every combination in TUNE_GRID is run once over all cases. Leave-one-out: for each case, the
    combination with the best score on the OTHER cases is chosen (ties go to the current values), and the
    case is scored with it. The cross-validated score is the share of cases passed that way; the in-sample
    best combination is reported too, but only the cross-validated score says how well tuning generalises."""
    cases = load_cases()
    keys = list(TUNE_GRID)
    current = tuple(params.get(k) for k in keys)
    combos = list(itertools.product(*(TUNE_GRID[k] for k in keys)))
    table: dict[tuple, list[bool]] = {}
    for i, combo in enumerate(combos, 1):
        previous = params.apply(dict(zip(keys, combo)))
        try:
            t0 = time.time()
            table[combo] = [r.passed for r in run(cases, engine())]
        finally:
            params.apply(previous)
        progress(f"{i}/{len(combos)} {dict(zip(keys, combo))}: {sum(table[combo])}/{len(cases)} ({time.time() - t0:.0f}s)")
    n = len(cases)
    cv_pass = 0
    for i in range(n):
        def others(c):
            return sum(p for j, p in enumerate(table[c]) if j != i)
        best = max(combos, key=lambda c: (others(c), c == current))
        cv_pass += table[best][i]
    best_in_sample = max(combos, key=lambda c: (sum(table[c]), c == current))
    # Cases whose outcome changes anywhere in the grid: only these can inform tuning. Zero means the benchmark
    # cannot tell the tried values apart, and the defaults stand.
    sensitive = [cases[i]["id"] for i in range(n) if len({table[c][i] for c in combos}) > 1]
    return {"cases": n, "sensitive_cases": sensitive, "current": dict(zip(keys, current)), "current_score": sum(table[current]) / n if current in table else None,
            "cv_score": cv_pass / n, "best": dict(zip(keys, best_in_sample)), "best_score": sum(table[best_in_sample]) / n}


def record(results: list[Result], cv: dict | None = None) -> None:
    data = (yaml.safe_load(RESULTS_PATH.read_text(encoding="utf-8")) or {}) if RESULTS_PATH.exists() else {}
    entry = {"fingerprint": params.fingerprint(), "date": date.today().isoformat(), "score": round(score(results), 3),
             "passed": sum(r.passed for r in results), "cases": len(results),
             "failures": [r.id for r in results if not r.passed]}
    if cv:
        entry["tuning"] = cv
    data[params.version()] = entry
    RESULTS_PATH.write_text("# GENERATED by `python -m gtc benchmark --record`.\n" + yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def render(results: list[Result]) -> str:
    out = [f"Benchmark, model {params.version()}: {sum(r.passed for r in results)} of {len(results)} cases "
           f"({score(results):.0%})", ""]
    for r in results:
        out.append(f"{'PASS' if r.passed else 'FAIL'}  {r.id:42} {r.detail}")
    return "\n".join(out)
