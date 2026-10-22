"""New-character / prerelease pipeline (phase I), the Lohen experiment made routine:

    source data (Amber tables and kit text, the structured kit)  ->  reviewed kit file (knowledge/forward/actions or
    knowledge/forward/prerelease: actions, states, resources, facts)  ->  candidate-team needs (teamgen, phase J)  ->
    team generation  ->  rotation generation  ->  ForwardModel with realistic builds (phase G)  ->  uncertainty
    (phase L)  ->  swap comparisons (phase K)

No community simulation of the character is used. Every stored analysis carries a fingerprint of everything it read
(the kit file, its annotations, the Amber tables and base stats, the structured kit); `refresh()` reruns only the
characters whose fingerprint changed, so a beta multiplier change updates personal damage, teams and rotations.

Kit status and fact confidence come from the kit file:
    status: {release_status: released | prerelease, kit_version: beta_v1 | ... | release | amber-current}
    facts:  known (confirmed: official tables / text), assumed (provisional), unknown (no credit), or entries
            {text, confidence: confirmed | reliable | provisional | unknown, source}
Results are written to data/forward/pipeline/<name>.json (personal use).
"""
from __future__ import annotations

import hashlib
import json
import time

import yaml

from gtc import KNOWLEDGE_DIR, ROOT

STORE = ROOT / "data" / "forward" / "pipeline"
CONFIDENCE = {"known": "confirmed", "assumed": "provisional", "unknown": "unknown"}


def _kit_path(name: str):
    for d in ("actions", "prerelease"):
        p = KNOWLEDGE_DIR / "forward" / d / f"{name}.yaml"
        if p.exists():
            return p
    return None


def fingerprint(name: str) -> str:
    """Hash of every input the analysis of `name` reads."""
    from gtc.forward import data as D
    from gtc.forward.effects import annotations
    from gtc.kits import kit

    h = hashlib.sha256()
    p = _kit_path(name)
    h.update((p.read_text(encoding="utf-8") if p else "").encode())
    h.update(yaml.safe_dump(annotations().get(name) or [], sort_keys=True).encode())
    h.update(json.dumps(kit(name) or {}, sort_keys=True, default=str).encode())
    try:
        h.update(json.dumps(D.character_stats(name, 90), sort_keys=True).encode())
        for kind in ("normal", "skill", "burst"):
            h.update(json.dumps(D.table(name, kind, 9), sort_keys=True).encode())
    except KeyError:
        h.update(b"no-amber")
    return h.hexdigest()[:16]


def status(name: str) -> dict:
    """Release status, kit version, community simulations and per-fact confidence."""
    from gtc.forward.library import load_hand, source_lineups

    lib = load_hand(name)
    st = dict(getattr(lib, "status", None) or {}) if lib else {}
    facts = []
    for group, items in ((lib.facts if lib else {}) or {}).items():
        for f in items or []:
            if isinstance(f, dict):
                facts.append({"text": f.get("text"), "confidence": f.get("confidence") or CONFIDENCE.get(group, "unknown"),
                              "source": f.get("source")})
            else:
                facts.append({"text": str(f), "confidence": CONFIDENCE.get(group, "unknown"), "source": None})
    try:
        sims = len(source_lineups(name, n=99))
    except Exception:
        sims = None
    count = {c: sum(f["confidence"] == c for f in facts) for c in ("confirmed", "reliable", "provisional", "unknown")}
    return {"release_status": st.get("release_status", "unknown"), "kit_version": st.get("kit_version", "unknown"),
            "kit_file": bool(lib), "community_simulations": sims, "facts": facts, "fact_confidence": count}


def analyse(name: str, pool: list[str] | None = None, profile: str = "standard", keep: int = 6,
            swaps: int = 3, save: bool = True) -> dict:
    """Teams, rotations, DPS, damage share, major buffs, reactions, ER, conditions, uncertainty and swap comparisons
    for `name`, from kits alone."""
    from gtc.forward.blind import theorycraft
    from gtc.forward.reference import CHARACTERS
    from gtc.forward.swap import swap
    from gtc.forward.teamgen import candidate_teams, needs

    t0 = time.time()
    pool = [m for m in (pool or list(CHARACTERS)) if m != name]
    shortlist, unplayable = candidate_teams(name, pool, keep)
    teams = []
    for c in shortlist[:keep]:
        try:
            r = theorycraft(c["lineup"], profile=profile)
        except Exception as e:      # a teammate without a kit file or measurements
            teams.append({"lineup": c["lineup"], "error": f"{type(e).__name__}: {e}"})
            continue
        ev = r["evaluation"]
        teams.append({
            "lineup": c["lineup"], "dps": round(ev.dps), "personal_share": round(ev.damage_share.get(name, 0.0), 3),
            "shares": {k: round(v, 3) for k, v in ev.damage_share.items()},
            "rotation": [(round(a.t, 1), a.char, a.action) for a in r["rotation"].actions if a.t < 25],
            "rotation_s": round(r["rotation"].duration, 1),
            "reactions": {k: round(v / ev.total_damage, 3) for k, v in ev.per_reaction.items()} if ev.total_damage else {},
            "energy": {m: {"required_er": v.get("required_er"), "status": v.get("status")} for m, v in ev.energy.items()},
            "conditions": [c2 for c2 in ev.condition_states if c2["caster"] == name or c2["state"] != "met"][:12],
            "uncertainty": ev.uncertainty, "confidence": ev.confidence,
            "matters_most": (ev.uncertainty_detail or {}).get("matters_most"),
            "builds": r.get("build_report"), "covers": c.get("covers"), "avoids": c.get("avoids"),
            "realisation": r.get("realisation")})
    ok = sorted([t for t in teams if "dps" in t], key=lambda t: -t["dps"])
    comparisons = []
    if ok and swaps:
        best = ok[0]["lineup"]
        for alt in ok[1:]:
            diff = [m for m in alt["lineup"] if m not in best]
            gone = [m for m in best if m not in alt["lineup"]]
            if len(diff) == 1 and len(gone) == 1:
                s = swap(best, gone[0], diff[0], profile=profile, carry=name)
                comparisons.append({"out": gone[0], "in": diff[0], "change": s["change"], "lines": s["lines"]})
            if len(comparisons) >= swaps:
                break
    out = {"name": name, "fingerprint": fingerprint(name), "computed_at": time.strftime("%Y-%m-%d %H:%M"),
           "profile": profile, "status": status(name), "needs": needs(name), "teams": ok,
           "failed": [t for t in teams if "error" in t], "cannot_evaluate": unplayable, "swaps": comparisons,
           "seconds": round(time.time() - t0, 1)}
    if save:
        STORE.mkdir(parents=True, exist_ok=True)
        (STORE / f"{name}.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    return out


def stored(name: str) -> dict | None:
    p = STORE / f"{name}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def refresh(names: list[str] | None = None, **kw) -> list[str]:
    """Rerun the analyses whose inputs changed (beta numbers, kit file, annotations). Returns who was rerun."""
    names = names or [p.stem for p in STORE.glob("*.json")]
    rerun = []
    for n in names:
        old = stored(n)
        if old is None or old.get("fingerprint") != fingerprint(n):
            analyse(n, profile=(old or {}).get("profile", kw.get("profile", "standard")), **{k: v for k, v in kw.items() if k != "profile"})
            rerun.append(n)
    return rerun
