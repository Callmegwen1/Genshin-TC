"""Shadow production mode (phase N): run both engines, show only the legacy one, log the comparison.

For every production team (the account's best team per archetype, the player's own teams) and a fixed focus list
(the reference lineups and the roadmap's named cases), both numbers are computed:
    LegacyPower   gtc/report.py's expected power (community evidence, pair model, build factors)
    ForwardPower  the blind theorycraft with realistic standard builds (phase G), its uncertainty and confidence
and written to data/validation/shadow_log.json (personal use, no UID): the difference, the legacy power's source tier,
the forward coverage, and how the ranking would change. Nothing here changes what the UI shows.

Known systematic difference: legacy evidence assumes community-standard investment (5-stars C0, 4-stars C6);
ForwardPower is C0 for everyone with realistic accessible weapons. Ratios are read with that in mind.
"""
from __future__ import annotations

import json
import time

from gtc import ROOT

OUT = ROOT / "data" / "validation" / "shadow_log.json"
FOCUS = ["Kamisato Ayaka", "Razor", "Flins", "Raiden Shogun", "Escoffier", "Xiangling", "Hu Tao", "Neuvillette",
         "Nahida", "Kuki Shinobu"]


def _names(keys: list[str]) -> list[str]:
    from gtc import gamedata

    n = gamedata.names()
    return [n.character(k) or k for k in keys]


def forward_coverage(lineup: list[str]) -> dict:
    from gtc.forward.library import load_hand
    from gtc.forward.teamgen import evaluable

    kit = [m for m in lineup if load_hand(m) is not None]
    playable = [m for m in lineup if evaluable(m)]
    return {"kit_files": len(kit), "evaluable": len(playable), "complete": len(playable) == len(lineup)}


def _forward(lineup: list[str], profile: str) -> dict:
    from gtc.forward.blind import theorycraft

    cov = forward_coverage(lineup)
    if not cov["complete"]:
        return {"coverage": cov, "dps": None, "why": "a member has no kit file and no measurements"}
    try:
        r = theorycraft(lineup, profile=profile)
    except Exception as e:
        return {"coverage": cov, "dps": None, "why": f"{type(e).__name__}: {e}"}
    ev = r["evaluation"]
    return {"coverage": cov, "dps": round(ev.dps), "sd": ev.uncertainty, "confidence": ev.confidence,
            "matters_most": (ev.uncertainty_detail or {}).get("matters_most"),
            "shares": {k: round(v, 3) for k, v in ev.damage_share.items()}, "rotation_s": round(r["rotation"].duration, 1)}


def _legacy(a) -> dict:
    est = a.estimate
    return {"power": round(a.expected_power), "sd": round(getattr(est, "sd", 0.0) or 0.0, 3) if est else None,
            "tier": getattr(est, "tier", None) if est else None, "rating": round(a.rating, 3)}


def run(profile: str = "standard", focus_only: bool = False, limit: int | None = None) -> dict:
    from gtc import knowledge
    from gtc.forward.reference import REFERENCE
    from gtc.report import analyze, assess, build_universe
    from gtc.snapshot import Snapshot, latest_snapshot
    from gtc.teams import evaluate_lineup
    from gtc import SNAPSHOT_DIR
    from gtc.report import load_evidence

    t0 = time.time()
    kb = knowledge.load()
    rows = []
    if not focus_only:
        an = analyze(Snapshot.load(latest_snapshot(SNAPSHOT_DIR)), kb)
        seen = set()
        teams = [a for _, a in an.my_teams if a] + list(an.per_archetype)
        for a in teams[: limit or len(teams)]:
            lineup = _names(a.team.members)
            if frozenset(lineup) in seen:
                continue
            seen.add(frozenset(lineup))
            rows.append({"set": "production", "archetype": getattr(a.team.template, "id", None), "lineup": lineup,
                         "legacy": _safe(lambda: _legacy(a)), "forward": _forward(lineup, profile)})
            _checkpoint(rows, profile)
    # focus: the reference lineups at community-standard investment (the universe roster), legacy vs forward
    ev = load_evidence(kb)
    universe = build_universe(kb, ev)
    from gtc.report import Model

    model = Model(kb, universe)
    keys_of = {n: k for k, n in zip([m.key for m in universe], _names([m.key for m in universe]))}
    for e in REFERENCE:
        keys = [keys_of.get(m) for m in e["team"]]
        if None in keys:
            continue
        team = evaluate_lineup(keys, universe, kb)
        leg = _safe(lambda: _legacy(assess(team, ev, model, kb))) if team else {"power": None}
        rows.append({"set": "focus", "family": e["family"], "lineup": e["team"], "legacy": leg,
                     "forward": _forward(e["team"], profile)})
        _checkpoint(rows, profile)
    for r in rows:
        lp, fp = r["legacy"].get("power"), r["forward"].get("dps")
        r["ratio"] = round(fp / lp, 3) if lp and fp else None
        r["focus_members"] = [m for m in r["lineup"] if m in FOCUS]
    both = [r for r in rows if r["ratio"] is not None]
    by_legacy = sorted(both, key=lambda r: -r["legacy"]["power"])
    by_forward = sorted(both, key=lambda r: -r["forward"]["dps"])
    rank_l = {id(r): i for i, r in enumerate(by_legacy)}
    rank_f = {id(r): i for i, r in enumerate(by_forward)}
    for r in both:
        r["rank_legacy"], r["rank_forward"] = rank_l[id(r)] + 1, rank_f[id(r)] + 1
    n = len(both)
    rho = None
    if n > 2:
        d2 = sum((rank_l[id(r)] - rank_f[id(r)]) ** 2 for r in both)
        rho = round(1 - 6 * d2 / (n * (n * n - 1)), 3)
    ratios = sorted(r["ratio"] for r in both)
    # recommendation changes: per archetype, the top team under each engine (production set)
    changes = []
    groups = {}
    for r in both:
        if r["set"] == "production":
            groups.setdefault(r.get("archetype"), []).append(r)
    for arch, rs in groups.items():
        top_l = max(rs, key=lambda r: r["legacy"]["power"])
        top_f = max(rs, key=lambda r: r["forward"]["dps"])
        if top_l is not top_f:
            changes.append({"archetype": arch, "legacy_top": top_l["lineup"], "forward_top": top_f["lineup"]})
    top5_l = [r["lineup"] for r in by_legacy[:5]]
    top5_f = [r["lineup"] for r in by_forward[:5]]
    out = {"profile": profile, "teams": len(rows), "compared": n, "spearman": rho,
           "recommendation_changes": changes, "top5_legacy": top5_l, "top5_forward": top5_f,
           "top5_overlap": len({frozenset(x) for x in top5_l} & {frozenset(x) for x in top5_f}),
           "median_ratio": ratios[n // 2] if n else None,
           "largest_disagreements": [{"lineup": r["lineup"], "ratio": r["ratio"], "legacy": r["legacy"]["power"],
                                      "forward": r["forward"]["dps"]}
                                     for r in sorted(both, key=lambda r: -abs(__import__("math").log(r["ratio"])))[:8]],
           "not_covered": [r["lineup"] for r in rows if r["forward"].get("dps") is None],
           "rows": rows, "seconds": round(time.time() - t0, 1),
           "note": "legacy assumes 5-stars C0 / 4-stars C6; forward is C0 with accessible weapons"}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    _store(out)
    return out


def _safe(fn) -> dict:
    try:
        return fn()
    except Exception as e:   # noqa: BLE001
        return {"power": None, "error": f"{type(e).__name__}: {e}"}


def _checkpoint(rows: list, profile: str) -> None:
    """Incremental log: a long run that fails part-way keeps what it computed."""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.with_name("shadow_log.partial.json").write_text(json.dumps({"profile": profile, "rows": rows}, indent=1, default=str),
                                                          encoding="utf-8")


def _store(out: dict) -> None:
    """Every shadow run is kept in the results database (by forward version) so versions can be compared."""
    import sqlite3

    from gtc.forward import FORWARD_VERSION
    from gtc.forward.results import DB

    con = sqlite3.connect(DB)
    with con:
        con.execute("""create table if not exists shadow (run text, version text, created text, profile text, set_ text,
                       lineup text, legacy real, forward real, ratio real, rank_legacy int, rank_forward int,
                       confidence text, coverage text)""")
        run = time.strftime("%Y%m%d-%H%M%S")
        for r in out["rows"]:
            f = r.get("forward") or {}
            con.execute("insert into shadow values (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (run, FORWARD_VERSION, time.strftime("%Y-%m-%d %H:%M"), out["profile"], r.get("set"),
                         " / ".join(r["lineup"]), (r.get("legacy") or {}).get("power"), f.get("dps"), r.get("ratio"),
                         r.get("rank_legacy"), r.get("rank_forward"), f.get("confidence"),
                         json.dumps(f.get("coverage"))))
    con.close()
