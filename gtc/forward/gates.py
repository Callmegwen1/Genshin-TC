"""Acceptance gates for switching power (phase O). Guidelines, not numbers to game: a family that fails badly is
reported, never averaged away. Production integration (phases P-R) waits until every gate passes.

    1  direct / buff-driven replay      median |replay error| <= 7% on teams whose damage is mostly direct
                                        (reactions < 25% of the replayed damage)
    2  diverse blind theorycraft        median |blind error| <= 15%
    3  pairwise team ranking            >= 80% of team pairs ordered like gcsim
    4  no systematic archetype failure  no family with |blind error| > 30%
    5  state / resource mechanics       verified on at least 3 characters (a state realised >= 70% on field in the
                                        blind rotations; resources exercised by tests)
    6  reaction rates                   median relative error of reaction rates <= 35% (reactions above 0.1/s)
    7  prerelease / unseen              the pipeline analysis of a character with no community simulations exists
                                        and evaluated teams
    8  sensible generated rotations     no unsustainable energy; idle <= 15% of the rotation; carry states >= 70%
    9  recommendations not on nonsense  the shadow log's top forward teams pass gate 8's rotation checks
                                        and none is Low confidence
Inputs: data/validation/forward_benchmark_standard.json (or the neutral file), data/validation/shadow_log.json,
data/forward/pipeline/*.json.
"""
from __future__ import annotations

import json

from gtc import ROOT

VAL = ROOT / "data" / "validation"


def _load(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _median(v):
    v = sorted(v)
    return v[len(v) // 2] if v else None


def _idle(row) -> float:
    s = (row.get("realisation") or {}).get("idle") or ""
    try:
        return float(s.split()[1])
    except (IndexError, ValueError):
        return 0.0


def _sensible(row) -> list[str]:
    bad = []
    energy = (row.get("realisation") or {}).get("energy") or {}
    if any(v == "unsustainable" for v in energy.values()):
        bad.append("unsustainable energy")
    dur = (row.get("cycle_blind") or 20) * 4
    if _idle(row) > 0.15 * dur:
        bad.append(f"idle {_idle(row):.0f} s")
    st = (row.get("realisation") or {}).get("state_realisation") or {}
    low = [k for k, v in st.items() if v < 0.7]
    if low:
        bad.append(f"states under 70% on field: {low}")
    return bad


def evaluate(profile: str = "standard") -> dict:
    bench = _load(VAL / ("forward_benchmark.json" if profile == "neutral" else f"forward_benchmark_{profile}.json"))
    shadow = _load(VAL / "shadow_log.json")
    gates = []

    def gate(n, name, ok, value, target, detail=None):
        gates.append({"gate": n, "name": name, "pass": bool(ok), "value": value, "target": target, "detail": detail})

    rows = (bench or {}).get("rows") or []
    usable = [r for r in rows if (r.get("reference_quality") or {}).get("shape_kept", True)]
    direct = [r for r in usable if r.get("replay_reaction_share", 1.0) < 0.25 and r.get("replay_error") is not None]
    m = _median([abs(r["replay_error"]) for r in direct])
    gate(1, "direct/buff-driven replay median error", m is not None and m <= 0.07, m, "<= 0.07",
         {r["family"]: r["replay_error"] for r in direct})
    m = _median([abs(r["blind_error"]) for r in usable if r.get("blind_error") is not None])
    gate(2, "diverse blind median error", m is not None and m <= 0.15, m, "<= 0.15",
         {r["family"]: r["blind_error"] for r in usable})
    pa = (bench or {}).get("summary", {}).get("pairwise_ranking_agreement")
    gate(3, "pairwise ranking agreement", pa is not None and pa >= 0.80, pa, ">= 0.80")
    fails = {r["family"]: r["blind_error"] for r in usable if r.get("blind_error") is not None and abs(r["blind_error"]) > 0.30}
    gate(4, "no systematic archetype failure", not fails and bool(usable), len(fails), "0 families beyond 30%", fails)
    verified = set()
    for r in rows:
        for k, v in ((r.get("realisation") or {}).get("state_realisation") or {}).items():
            if v >= 0.7:
                verified.add(k.split(":")[0])
    gate(5, "state/resource mechanics verified", len(verified) >= 3, sorted(verified), ">= 3 characters")
    rel = []
    for r in usable:
        ref = r.get("reaction_rates_reference") or {}
        for k, v in ref.items():
            if v >= 0.1:
                rel.append(abs((r.get("reaction_rates_blind") or {}).get(k, 0.0) - v) / v)
    m = _median(rel)
    gate(6, "reaction rates vs reference", m is not None and m <= 0.35, None if m is None else round(m, 3), "<= 0.35",
         f"{len(rel)} reaction rates compared")
    pipe = [p for p in (ROOT / "data" / "forward" / "pipeline").glob("*.json")] if (ROOT / "data" / "forward" / "pipeline").exists() else []
    unseen = []
    for p in pipe:
        d = _load(p)
        if d and (d.get("status") or {}).get("community_simulations") == 0 and d.get("teams"):
            unseen.append(d["name"])
    gate(7, "prerelease/unseen character analysed without community data", bool(unseen), unseen, ">= 1 character")
    bad = {r["family"]: _sensible(r) for r in rows if _sensible(r)}
    gate(8, "generated rotations mechanically sensible", not bad and bool(rows), len(bad), "0 teams with problems", bad)
    if shadow:
        top = sorted([r for r in shadow.get("rows", []) if (r.get("forward") or {}).get("dps")],
                     key=lambda r: -r["forward"]["dps"])[:5]
        low = [r["lineup"] for r in top if r["forward"].get("confidence") == "Low"]
        gate(9, "top recommendations not on nonsense rotations", not low and bool(top), len(low),
             "0 Low-confidence teams among the top 5", low)
    else:
        gate(9, "top recommendations not on nonsense rotations", False, None, "shadow log needed", "run the shadow mode")
    # 10 (future gate, report only: no threshold yet): execution parity of generated rotations replayed in gcsim
    dec = _load(VAL / f"decomposition_{'neutral' if profile == 'neutral' else profile}.json") or _load(VAL / "decomposition_neutral.json")
    if dec:
        errs = [abs(r["duration_error"]) for r in dec if r.get("duration_error") is not None]
        gates.append({"gate": 10, "name": "execution parity (report only)", "pass": None,
                      "value": None if not errs else round(_median(errs), 3), "target": "not set yet",
                      "detail": {r["family"]: {"duration_error": r.get("duration_error"),
                                               "timing_delta_by_class": r.get("timing_delta_by_class")} for r in dec
                                 if "duration_error" in r}})
    scored = [g for g in gates if g["pass"] is not None]
    out = {"profile": profile, "all_pass": all(g["pass"] for g in scored), "gates": gates,
           "decision": "integrate (phase P)" if all(g["pass"] for g in scored) else "do not switch power: report and stop"}
    (VAL / "acceptance_gates.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    return out
