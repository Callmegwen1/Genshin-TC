"""Benchmark result store, cohort metadata, failure taxonomy and residual analysis (development diagnostics).

Every decomposition case (gtc/forward/decompose.py) becomes a result row with:
    cohort       team, characters, archetype, reaction family, primary driver, team structure (single / dual window /
                 driver), field-time structure, rotation length, ER pressure, state/resource complexity,
                 summons/procs, aura-changing, target assumption, build profile, model version, reference source
    values       ForwardModel DPS, reference DPS, residual, |error|, same-rotation calculator error, selection and search
                 regret, duration error
    labels       zero or more failure labels (below), and a verdict: MODEL failure or DATA COVERAGE failure
Rows are stored in data/validation/results.sqlite (one table, the full row as JSON plus the key columns), keyed by
model version and run, so versions can be compared.

Failure labels (multi-label; thresholds are diagnostic, not acceptance criteria):
    CALCULATOR_DAMAGE_ERROR    |same-rotation calculator error| > 7%
    ROTATION_SELECTION_ERROR   selection regret > 5% (a better candidate existed among ours)
    ROTATION_SEARCH_ERROR      search regret > 10% (the reference beats every candidate we generated)
    TIMING_ERROR               |duration error| > 5% on the same rotation
    ENERGY_ERROR               gcsim energy waits > 2 s, or a member's received energy differs > 8%
    REACTION_ERROR             a reaction kind with >= 10 events differs > 20% in count, or its main owner differs
    APPLICATION_ERROR          a character-element application count (>= 15) differs > 15%
    ROLE_DRIVER_ERROR          our longest-field character differs from the reference rotation's, with search regret
    STATE_RESOURCE_ERROR       a state the rotation needs is realised < 70% on field, or a resource value is unknown
    KIT_DATA_ERROR             a known data-coverage gap (knowledge/forward/coverage.yaml) applies to a member
    BUILD_ERROR                (realistic builds) the reference's builds and ours differ while the calculator agrees
    BUFF_UPTIME_ERROR          (benchmark rows) a major buff's coverage of the carry differs > 25 points
    TARGETING_ERROR            reserved (single target only for now)
    RANKING_ERROR              set-level: assigned to pairs ordered differently from gcsim (reported in aggregate)
    UNKNOWN_ERROR              |residual| > 15% and no other label explains it
"""
from __future__ import annotations

import json
import math
import sqlite3
import statistics
import time
from collections import Counter, defaultdict
from functools import lru_cache

import yaml

from gtc import KNOWLEDGE_DIR, ROOT

DB = ROOT / "data" / "validation" / "results.sqlite"
COVERAGE = KNOWLEDGE_DIR / "forward" / "coverage.yaml"
LABELS = ("CALCULATOR_DAMAGE_ERROR", "ROTATION_SEARCH_ERROR", "ROTATION_SELECTION_ERROR", "REACTION_ERROR",
          "APPLICATION_ERROR", "ENERGY_ERROR", "TIMING_ERROR", "BUFF_UPTIME_ERROR", "STATE_RESOURCE_ERROR",
          "ROLE_DRIVER_ERROR", "KIT_DATA_ERROR", "TARGETING_ERROR", "BUILD_ERROR", "RANKING_ERROR", "UNKNOWN_ERROR")


@lru_cache(maxsize=1)
def coverage() -> dict:
    return yaml.safe_load(COVERAGE.read_text(encoding="utf-8")) if COVERAGE.exists() else {"gaps": []}


# ---------- cohort ----------

REACTION_FAMILY = {"melt": "Melt", "vaporize": "Vaporize", "aggravate": "Quicken", "spread": "Quicken",
                   "hyperbloom": "Hyperbloom", "bloom": "Bloom", "burgeon": "Burgeon", "overload": "Overloaded",
                   "electrocharged": "Electro-Charged", "lunarcharged": "Lunar", "superconduct": "Superconduct",
                   "swirl": "Swirl", "shatter": "Freeze"}


def cohort(row: dict) -> dict:
    from gtc.forward.library import load_hand
    from gtc.mechanics import element_of

    team = row["team"]
    libs = {m: load_hand(m) for m in team}
    rx = (row.get("reactions") or {}).get("gcsim") or {}
    els = {element_of(m) for m in team}
    fam_counts = Counter()
    for k, v in rx.items():
        fam_counts[REACTION_FAMILY.get(k, k)] += v
    if {"Cryo", "Hydro"} <= els and not ({"Pyro"} & els):
        fam_counts["Freeze"] += 1000          # Freeze has no damage events: elements decide it
    reaction_family = fam_counts.most_common(1)[0][0] if fam_counts else "direct"
    if "lunar" in row.get("family", "").lower():
        reaction_family = "Lunar"
    drivers = row.get("selected_driver", "")
    structure = "dual window" if " then " in drivers else "single carry"
    fs = row.get("field_share_forward") or {}
    top = max(fs.values()) if fs else 0.0
    field = "carry-dominant" if top >= 0.6 else ("shared" if top >= 0.4 else "quickswap")
    states = sum(len((l.states or {}) if l else {}) + len((l.resources or {}) if l else {}) for l in libs.values())
    summons = any(l and (l.summons or l.procs or getattr(l, "reaction_procs", None)) for l in libs.values())
    reaction_density = sum(rx.values()) / max(row.get("gcsim_duration_same_rotation") or 1.0, 1.0)
    er = row.get("er_required_max")
    return {
        "archetype": row.get("family"), "reaction_family": reaction_family, "primary_driver": drivers.split(" then ")[0],
        "team_structure": structure, "field_structure": field,
        "rotation_length": row.get("period") or round((row.get("forward_duration") or 0) / 6, 1),
        "er_pressure": None if er is None else ("high" if er >= 2.0 else "medium" if er >= 1.5 else "low"),
        "state_complexity": "high" if states >= 4 else "medium" if states >= 2 else "low",
        "summons_procs": bool(summons), "aura_changing": len([k for k, v in rx.items() if v >= 5]) >= 2,
        "reaction_density": round(reaction_density, 3), "targets": "single", "build_profile": row.get("profile"),
    }


# ---------- labels ----------

def _rel(a, b):
    return abs(a - b) / max(abs(b), 1e-9)


def labels(row: dict) -> tuple[list[str], str, list[str]]:
    """(labels, verdict MODEL | DATA_COVERAGE | NONE, evidence lines)."""
    out, why = set(), []
    calc = row.get("calculator_error")
    if calc is not None and abs(calc) > 0.07:
        out.add("CALCULATOR_DAMAGE_ERROR")
        why.append(f"same-rotation calculator error {calc:+.1%}")
    if (row.get("selection_regret") or 0) > 0.05:
        out.add("ROTATION_SELECTION_ERROR")
        why.append(f"selection regret {row['selection_regret']:.1%}")
    if (row.get("search_regret") or 0) > 0.10:
        out.add("ROTATION_SEARCH_ERROR")
        why.append(f"search regret {row['search_regret']:.1%}")
    de = row.get("duration_error")
    if de is not None and abs(de) > 0.05:
        out.add("TIMING_ERROR")
        why.append(f"duration error {de:+.1%} ({row.get('timing_delta_by_class')})")
    td = row.get("timing_delta_by_class") or {}
    if td.get("energy", 0) > 2.0:
        out.add("ENERGY_ERROR")
        why.append(f"gcsim energy waits {td['energy']:.1f} s")
    for m, (f, g) in (row.get("energy_received") or {}).items():
        if g and _rel(f, g) > 0.08:
            out.add("ENERGY_ERROR")
            why.append(f"{m} energy {f:.0f} vs {g:.0f}")
    rf, rg = (row.get("reactions") or {}).get("forward") or {}, (row.get("reactions") or {}).get("gcsim") or {}
    of, og = (row.get("reaction_owners") or {}).get("forward") or {}, (row.get("reaction_owners") or {}).get("gcsim") or {}
    for k, g in rg.items():
        f = rf.get(k, 0)
        if g >= 10 and _rel(f, g) > 0.20:
            out.add("REACTION_ERROR")
            why.append(f"{k} {f} vs {g}")
        if g >= 10 and og.get(k) and of.get(k):
            if max(og[k], key=og[k].get) != max(of[k], key=of[k].get):
                out.add("REACTION_ERROR")
                why.append(f"{k} main owner {max(of[k], key=of[k].get)} vs {max(og[k], key=og[k].get)}")
    af, ag = (row.get("applications") or {}).get("forward") or {}, (row.get("applications") or {}).get("gcsim") or {}
    for k, g in ag.items():
        f = af.get(k, 0)
        if g >= 15 and _rel(f, g) > 0.15:
            out.add("APPLICATION_ERROR")
            why.append(f"{k} applications {f} vs {g}")
    ff, fr = row.get("field_share_forward") or {}, row.get("field_share_reference") or {}
    if ff and fr and max(ff, key=ff.get) != max(fr, key=fr.get) and (row.get("search_regret") or 0) > 0.10:
        out.add("ROLE_DRIVER_ERROR")
        why.append(f"field: ours {max(ff, key=ff.get)} vs reference {max(fr, key=fr.get)}")
    for k, v in (row.get("state_realisation") or {}).items():
        if v < 0.7:
            out.add("STATE_RESOURCE_ERROR")
            why.append(f"state {k} realised {v:.0%}")
    gaps = [g for g in coverage().get("gaps") or [] if g["character"] in row["team"] and str(g.get("status", "")).startswith("open")]
    covered = set()
    for g in gaps:
        hit = set(g.get("labels") or []) & out
        if hit:
            out.add("KIT_DATA_ERROR")
            covered |= hit
            why.append(f"data gap: {g['character']}: {g['missing']}")
    res = row.get("residual")
    if res is not None and abs(res) > 0.15 and not out:
        out.add("UNKNOWN_ERROR")
    labs = [l for l in LABELS if l in out]
    uncovered = out - covered - {"KIT_DATA_ERROR"}
    if not labs:
        verdict = "NONE"
    elif "KIT_DATA_ERROR" in out and not uncovered:
        verdict = "DATA_COVERAGE"          # every failure runs through a known data gap
    elif "KIT_DATA_ERROR" in out:
        verdict = "MIXED"                  # a data gap explains part; the rest is the model (search is always model)
    else:
        verdict = "MODEL"
    return labs, verdict, why


TAXONOMY = ("CALCULATOR_ERROR", "TRANSLATION_ERROR", "STRATEGY_EXPRESSIVENESS_ERROR", "ROTATION_SEARCH_ERROR",
            "ROTATION_SELECTION_ERROR", "DATA_COVERAGE_ERROR")


def taxonomy(row: dict, labs: list[str] | None = None) -> list[str]:
    """The case-level failure classes (the benchmark report's taxonomy), kept distinct:
    CALCULATOR_ERROR               same-rotation damage off by > 7%
    TRANSLATION_ERROR              the gcsim script does something else: same-rotation duration off by > 5%
    STRATEGY_EXPRESSIVENESS_ERROR  search regret > 10% and the language's projection of the reference is short of it
                                   (< 85% of the reference, or the search already reaches the projection)
    ROTATION_SEARCH_ERROR          search regret > 10% while the projection shows the language can do better than
                                   what the search generated (best generated < projection - 5 points)
    ROTATION_SELECTION_ERROR       a stronger candidate was generated but not chosen (selection regret > 5%)
    DATA_COVERAGE_ERROR            a known data gap (coverage.yaml) is involved"""
    labs = labs if labs is not None else labels(row)[0]
    out = []
    if row.get("calculator_error") is not None and abs(row["calculator_error"]) > 0.07:
        out.append("CALCULATOR_ERROR")
    if row.get("duration_error") is not None and abs(row["duration_error"]) > 0.05:
        out.append("TRANSLATION_ERROR")
    sr = row.get("search_regret") or 0.0
    ex = row.get("expressiveness") or {}
    proj = ex.get("ratio")
    if sr > 0.10:
        best = 1.0 - sr
        if proj is None or proj < 0.85 or best >= proj - 0.05:
            out.append("STRATEGY_EXPRESSIVENESS_ERROR")
        else:
            out.append("ROTATION_SEARCH_ERROR")
    if (row.get("selection_regret") or 0.0) > 0.05:
        out.append("ROTATION_SELECTION_ERROR")
    if "KIT_DATA_ERROR" in labs:
        out.append("DATA_COVERAGE_ERROR")
    return out


# ---------- store ----------

def _db():
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.execute("""create table if not exists results (
        run text, version text, created text, team text, family text, profile text,
        forward real, reference real, residual real, calc_error real, selection_regret real, search_regret real,
        duration_error real, labels text, verdict text, cohort text, row text)""")
    return con


def record(rows: list[dict], run: str | None = None) -> str:
    """Classify and store decomposition rows; returns the run id."""
    from gtc.forward import FORWARD_VERSION

    run = run or time.strftime("%Y%m%d-%H%M%S")
    con = _db()
    with con:
        for r in rows:
            if "forward_dps" not in r:
                continue
            labs, verdict, why = labels(r)
            co = cohort(r)
            r["labels"], r["verdict"], r["label_evidence"], r["cohort"] = labs, verdict, why, co
            r["taxonomy"] = taxonomy(r, labs)
            con.execute("insert into results values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (run, FORWARD_VERSION, time.strftime("%Y-%m-%d %H:%M"), " / ".join(r["team"]), r["family"],
                         r.get("profile"), r["forward_dps"], r.get("reference_gcsim"), r.get("residual"),
                         r.get("calculator_error"), r.get("selection_regret"), r.get("search_regret"),
                         r.get("duration_error"), json.dumps(labs), verdict, json.dumps(co), json.dumps(r, default=str)))
    con.close()
    return run


def load(run: str | None = None, version: str | None = None) -> list[dict]:
    con = _db()
    q, args = "select run, version, row, labels, verdict, cohort from results", []
    if run:
        q, args = q + " where run = ?", [run]
    elif version:
        q, args = q + " where version = ?", [version]
    out = []
    for run_, ver, row, labs, verdict, co in con.execute(q, args):
        r = json.loads(row)
        r.update({"run": run_, "version": ver, "labels": json.loads(labs), "verdict": verdict, "cohort": json.loads(co)})
        out.append(r)
    con.close()
    return out


def latest_run() -> str | None:
    con = _db()
    v = con.execute("select run from results order by created desc, run desc limit 1").fetchone()
    con.close()
    return v[0] if v else None


# ---------- residual analysis ----------

def _spearman(xs, ys):
    n = len(xs)
    if n < 4:
        return None
    rx = {i: r for r, i in enumerate(sorted(range(n), key=lambda i: xs[i]))}
    ry = {i: r for r, i in enumerate(sorted(range(n), key=lambda i: ys[i]))}
    d2 = sum((rx[i] - ry[i]) ** 2 for i in range(n))
    return round(1 - 6 * d2 / (n * (n * n - 1)), 3)


def analyse(rows: list[dict]) -> dict:
    """Errors by cohort, over/under-estimation, correlations, label Pareto among large failures, failure rates."""
    rows = [r for r in rows if r.get("residual") is not None]
    out = {"cases": len(rows)}
    by = {}
    for key in ("reaction_family", "archetype", "team_structure", "field_structure", "state_complexity",
                "summons_procs", "aura_changing", "er_pressure"):
        groups = defaultdict(list)
        for r in rows:
            groups[str(r["cohort"].get(key))].append(r)
        by[key] = {g: {"n": len(v), "median_abs_residual": round(statistics.median(abs(x["residual"]) for x in v), 3),
                       "median_signed_residual": round(statistics.median(x["residual"] for x in v), 3),
                       "median_abs_calc_error": round(statistics.median(abs(x["calculator_error"] or 0) for x in v), 3)}
                   for g, v in sorted(groups.items())}
    out["by_cohort"] = by
    out["overestimated"] = sorted(r["family"] for r in rows if r["residual"] > 0.10)
    out["underestimated"] = sorted(r["family"] for r in rows if r["residual"] < -0.10)
    absr = [abs(r["residual"]) for r in rows]
    out["correlation_abs_residual"] = {
        "rotation_length": _spearman([r["cohort"]["rotation_length"] or 0 for r in rows], absr),
        "reaction_density": _spearman([r["cohort"]["reaction_density"] for r in rows], absr),
        "state_complexity": _spearman([{"low": 0, "medium": 1, "high": 2}[r["cohort"]["state_complexity"]] for r in rows], absr),
        "summons_procs": _spearman([int(r["cohort"]["summons_procs"]) for r in rows], absr),
        "aura_changing": _spearman([int(r["cohort"]["aura_changing"]) for r in rows], absr)}
    big = [r for r in rows if abs(r["residual"]) > 0.15]
    cnt = Counter(l for r in big for l in r["labels"])
    out["large_failures"] = len(big)
    out["label_pareto_large_failures"] = [(l, n, round(n / len(big), 2)) for l, n in cnt.most_common()] if big else []
    out["label_counts_all"] = dict(Counter(l for r in rows for l in r["labels"]))
    out["taxonomy"] = dict(Counter(t for r in rows for t in (r.get("taxonomy") or taxonomy(r, r["labels"]))))
    out["expressiveness"] = dict(Counter((r.get("expressiveness") or {}).get("verdict", "not assessed") for r in rows))
    out["verdicts"] = dict(Counter(r["verdict"] for r in rows))
    n = len(rows)
    out["failure_rates"] = {
        "calculator (|calc| > 7%)": round(sum("CALCULATOR_DAMAGE_ERROR" in r["labels"] for r in rows) / n, 2) if n else None,
        "selection (> 5%)": round(sum("ROTATION_SELECTION_ERROR" in r["labels"] for r in rows) / n, 2) if n else None,
        "search (> 10%)": round(sum("ROTATION_SEARCH_ERROR" in r["labels"] for r in rows) / n, 2) if n else None}
    # set-level ranking: pairs ordered differently from gcsim (reference)
    pairs = [(a, b) for i, a in enumerate(rows) for b in rows[i + 1:] if a.get("reference_gcsim") and b.get("reference_gcsim")]
    bad = [(a["family"], b["family"]) for a, b in pairs
           if (a["forward_dps"] - b["forward_dps"]) * (a["reference_gcsim"] - b["reference_gcsim"]) < 0]
    out["ranking_agreement"] = round(1 - len(bad) / len(pairs), 3) if pairs else None
    out["ranking_errors"] = bad
    out["same_rotation"] = {
        "median_abs_calc_error": round(statistics.median(abs(r["calculator_error"]) for r in rows), 3) if rows else None,
        "median_abs_duration_error": round(statistics.median(abs(r["duration_error"] or 0) for r in rows), 3) if rows else None}
    return out


def compare_versions(v_old: str, v_new: str) -> dict:
    """What changed between engine versions, per team: residual and labels."""
    old = {r["family"]: r for r in load(version=v_old)}
    new = {r["family"]: r for r in load(version=v_new)}
    out = {}
    for fam in sorted(set(old) & set(new)):
        a, b = old[fam], new[fam]
        out[fam] = {"residual": (a.get("residual"), b.get("residual")),
                    "calc_error": (a.get("calculator_error"), b.get("calculator_error")),
                    "labels_added": sorted(set(b["labels"]) - set(a["labels"])),
                    "labels_removed": sorted(set(a["labels"]) - set(b["labels"]))}
    return out
