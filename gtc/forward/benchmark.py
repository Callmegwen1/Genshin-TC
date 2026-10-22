"""Blind theorycraft benchmark (phase E). Two accuracies, reported separately:

    REPLAY  the forward model on the community rotation (house builds) vs gcsim's crit-averaged damage on the same
            traced events: tests the calculator
    BLIND   the engine builds the rotation itself from kit files (no simulation of the team, no community rotation),
            then the reference is revealed: tests the brain

Per team (blind vs reference): DPS error, cycle-length error, damage-share error (mean absolute, per member),
reaction-rate error per reaction kind, ER-requirement error per member, buff-coverage error for the carry's major
buffs (blind rotation vs the forward model replaying the reference rotation). Across the set: pairwise ranking
agreement (does blind order each pair of teams like gcsim does).

`run()` writes data/validation/forward_benchmark.json (personal-use).
"""
from __future__ import annotations

import json
import time
from itertools import combinations

from gtc import ROOT

OUT = ROOT / "data" / "validation" / "forward_benchmark.json"


def _rates(hits, duration: float) -> dict:
    out: dict[str, float] = {}
    for h in hits:
        k = h.reaction or h.amp or h.cata
        if not k:
            continue
        k = "swirl" if k.startswith("swirl") else "overloaded" if k in ("overload", "overloaded") else k
        out[k] = out.get(k, 0.0) + 1
    return {k: round(v / duration, 3) for k, v in out.items()}


def _cycle(rot) -> float:
    bursts = {}
    for a in rot.actions:
        if a.action == "burst":
            bursts[a.char] = bursts.get(a.char, 0) + 1
    n = max(bursts.values()) if bursts else 1
    return rot.duration / max(n, 1)


def run_team(entry: dict, profile: str = "neutral") -> dict:
    from gtc.forward.blind import theorycraft
    from gtc.forward.deps import realisation
    from gtc.forward.library import load_hand
    from gtc.forward.model import evaluate
    from gtc.forward.reactions import plausibility
    from gtc.forward.trace import house_trace

    team = entry["team"]
    t0 = time.time()
    independent = all(load_hand(m) is not None for m in team)
    r = theorycraft(team, profile=profile)
    b_ev, b_rot = r["evaluation"], r["rotation"]
    t1 = time.time()
    # ---- reveal ---- (the same gear for gcsim when the profile is standard)
    rot, info = house_trace(team, r.get("builds"))
    replay = evaluate(rot, info.get("builds"), info=info)
    from gtc.forward.simquality import reference_quality

    rq = reference_quality(team, info)
    same = sum(h.gcsim_expected for h in rot.hits) / rot.duration
    gc_mean = info.get("gcsim_dps")
    gc_chars = info.get("gcsim_char_dps") or {}
    tot = sum(gc_chars.values()) or 1.0
    from gtc import gamedata

    names = gamedata.names()
    gc_share = {(names.character(k) or k): v / tot for k, v in gc_chars.items()}
    share_err = sum(abs(b_ev.damage_share.get(m, 0) - gc_share.get(m, 0)) for m in team) / len(team)
    b_rates, g_rates = _rates(b_rot.hits, b_rot.duration), _rates(rot.hits, rot.duration)
    rx_err = {k: round(b_rates.get(k, 0) - g_rates.get(k, 0), 3) for k in set(b_rates) | set(g_rates)}
    er_ref = {m: (v or {}).get("required_er") for m, v in (info.get("energy") or {}).items()}
    er_err = {m: round((b_ev.energy.get(m, {}).get("required_er") or 0) - (er_ref.get(m) or 0), 3) for m in team
              if er_ref.get(m) and b_ev.energy.get(m, {}).get("required_er")}
    b_real = r["realisation"]["buff_coverage_of_carry_damage"]
    carry = r["plan"].carries[0]
    ref_real = realisation(rot, replay, (carry,))["buff_coverage_of_carry_damage"]
    buff_err = {k: round(b_real.get(k, 0) - ref_real.get(k, 0), 2) for k in set(b_real) | set(ref_real)}
    return {"team": team, "family": entry["family"], "independent": independent,
            "blind_dps": round(b_ev.dps), "replay_dps": round(replay.dps), "gcsim_same_rotation": round(same),
            "gcsim_mean": round(gc_mean) if gc_mean else None,
            "blind_error": round(b_ev.dps / gc_mean - 1, 3) if gc_mean else None,
            "replay_error": round(replay.dps / same - 1, 3) if same else None,
            "blind_rotation": b_rot.source, "blind_first_cycle": [(round(a.t, 1), a.char, a.action) for a in b_rot.actions
                                                                  if a.t < _cycle(b_rot) + 0.5],
            "cycle_blind": round(_cycle(b_rot), 1), "cycle_reference": round(_cycle(rot), 1),
            "shares_blind": {k: round(v, 3) for k, v in b_ev.damage_share.items()},
            "shares_reference": {k: round(v, 3) for k, v in gc_share.items()}, "share_error": round(share_err, 3),
            "reaction_rates_blind": b_rates, "reaction_rates_reference": g_rates, "reaction_rate_error": rx_err,
            "reaction_flags": plausibility(b_rates),
            "replay_reaction_share": round(sum(replay.per_reaction.values()) / replay.total_damage, 3) if replay.total_damage else None,
            "er_error": er_err, "buff_coverage_error": buff_err, "realisation": r["realisation"],
            "graph": r["graph"], "unknown": b_ev.unknown[:8], "uncertainty": b_ev.uncertainty,
            "seconds": {"blind": round(t1 - t0, 1)}, "profile": profile,
            "builds": r.get("build_report"), "reference_quality": rq,
            "confidence": b_ev.confidence, "uncertainty_detail": b_ev.uncertainty_detail}


def run(teams: list | None = None, profile: str = "neutral") -> dict:
    from gtc.forward.reference import REFERENCE

    rows = [run_team(e, profile) for e in (teams or REFERENCE)]
    pairs = [(a, b) for a, b in combinations(rows, 2) if a["gcsim_mean"] and b["gcsim_mean"]]
    agree = sum((a["blind_dps"] - b["blind_dps"]) * (a["gcsim_mean"] - b["gcsim_mean"]) > 0 for a, b in pairs)
    errs = sorted(abs(r["blind_error"]) for r in rows if r["blind_error"] is not None)
    rerrs = sorted(abs(r["replay_error"]) for r in rows if r["replay_error"] is not None)
    hq = [r for r in rows if (r.get("reference_quality") or {}).get("shape_kept", True) and r["blind_error"] is not None]
    hq_err = sorted(abs(r["blind_error"]) for r in hq)
    hq_rep = sorted(abs(r["replay_error"]) for r in hq if r["replay_error"] is not None)
    summary = {"teams": len(rows), "blind_median_abs_error": errs[len(errs) // 2] if errs else None,
               "references_shape_kept": len(hq),
               "blind_median_abs_error_shape_kept": hq_err[len(hq_err) // 2] if hq_err else None,
               "replay_median_abs_error_shape_kept": hq_rep[len(hq_rep) // 2] if hq_rep else None,
               "replay_median_abs_error": rerrs[len(rerrs) // 2] if rerrs else None,
               "pairwise_ranking_agreement": round(agree / len(pairs), 3) if pairs else None,
               "within_15pct": sum(e <= 0.15 for e in errs), "independent_teams": sum(r["independent"] for r in rows)}
    out = {"summary": summary, "rows": rows}
    path = OUT if profile == "neutral" else OUT.with_name(f"forward_benchmark_{profile}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    return out
