"""Golden-output regression harness.

Captures what the engine concludes for a fixed set of accounts and compares it with stored outputs:

    python -m gtc golden --check               compare; prints a readable diff, exit status 1 on any change
    python -m gtc golden --update --reason "…"  rewrite the stored outputs; the reason and the list of changed keys
                                               are appended to tests/golden/CHANGES.md (no silent updates)

Accounts: the user's real snapshot and every distinct roster in knowledge/benchmark.yaml and the scenario tests.
For each it records the candidate teams (lineup, generating template, label, lead, expected value, sd, evidence
tier, fit source, ranking value), the plan, the plans per content mode, viable carries, carries for the owned
supports, and pull values (gain, sd, tier, kind) for a fixed pool. Numbers are rounded to one decimal so that
harmless float noise does not show as a change.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

GOLDEN_DIR = Path(__file__).resolve().parents[1] / "tests" / "golden"
CHANGES = GOLDEN_DIR / "CHANGES.md"
DEFAULT_POOL = ["Columbina", "Mavuika", "Varka", "Furina", "Yelan", "Escoffier", "Nahida", "Neuvillette", "Xilonen", "Citlali", "Skirk"]


def _r(x):
    return None if x is None else round(float(x), 1)


def _team(a) -> dict:
    e = a.estimate
    return {"lineup": sorted(a.team.members), "template": a.team.template.id, "label": a.label,
            "lead": a.lead, "expected": _r(e.value) if e else None, "sd": _r(e.sd) if e else None,
            "tier": e.tier if e else None, "fit_source": a.fit.source, "ranking": _r(a.potential),
            "route": a.evaluation.power["single_target"].basis.route if a.evaluation and "single_target" in a.evaluation.power else None,
            "evidence_state": a.evaluation.power["single_target"].basis.evidence_state if a.evaluation and "single_target" in a.evaluation.power else None,
            "evidence_quality": a.evaluation.power["single_target"].basis.quality if a.evaluation and "single_target" in a.evaluation.power else None}


def rosters() -> dict[str, dict]:
    """Every distinct roster from the benchmark and the scenario tests, with the pool to price pulls on."""
    from gtc.benchmark import load_cases

    out: dict[str, dict] = {}
    for c in load_cases():
        names = c.get("roster") or []
        if len(names) < 4:
            continue
        key = "|".join(sorted(names))
        entry = out.setdefault(key, {"roster": sorted(names), "pool": set(), "ids": []})
        entry["pool"] |= set(c.get("pool") or [])
        entry["ids"].append(c["id"])
    for entry in out.values():
        entry["pool"] = sorted(entry["pool"] or DEFAULT_POOL)
    return out


def _decomp(d: dict) -> dict:
    keep = ("best_team_gain", "second_team_gain", "new_mechanics", "new_viable_teams", "improved", "displaced",
            "support_contention", "redundancy_score")
    return {k: d[k] for k in keep if k in d}


def capture_account(am, roster, pool: list[str]) -> dict:
    from gtc import gamedata, profiles

    plan, cands = am.plan(roster)
    element_of = {k: v.get("element") for k, v in gamedata.load_characters().items()}
    modes = profiles.all_plans(cands, element_of)
    owned = {m.key for m in roster}
    values = []
    for name in pool:
        if name in owned:
            continue
        v = am.value_of(name, roster, plan, cands)
        if v is not None:
            e = v.estimate
            values.append({"name": name, "gain": _r(v.gain), "expected": _r(e.value) if e else None, "sd": _r(e.sd) if e else None,
                           "tier": e.tier if e else None, "kind": v.kind,
                           "best_team": sorted(v.team.team.members) if v.team else None,
                           "decomposition": _decomp(v.decomposition)})
    values.sort(key=lambda x: (-(x["gain"] or 0), x["name"]))
    return {
        "candidates": sorted((_team(a) for a in cands), key=lambda t: (-(t["ranking"] or 0), t["lineup"])),
        "plan": [_team(a) for a in sorted(plan.teams, key=lambda a: -a.potential)],
        "plan_value": _r(plan.value),
        "modes": {k: {"score": _r(p.score), "teams": [sorted(a.team.members) for a in p.teams], "note": p.note,
                      "core": sorted(p.core)} for k, p in sorted(modes.items())},
        "viable_carries": sorted(am.viable_carries(cands)),
        "carries_for_supports": [[n, sorted(a.team.members), _r(a.potential)] for n, a in am.best_carries_for(roster)],
        "pulls": values,
    }


def capture(progress=print) -> dict[str, dict]:
    from gtc import SNAPSHOT_DIR
    from gtc.benchmark import engine, roster
    from gtc.snapshot import Snapshot, latest_snapshot

    am = engine()
    out = {}
    snap = Snapshot.load(latest_snapshot(SNAPSHOT_DIR))
    owned = {c.key for c in snap.characters}
    pool = sorted(n for n in am.universe if n not in owned and n in am.kb.characters)
    progress("account: your snapshot")
    out["account"] = capture_account(am, am.an.roster, pool)
    for i, (key, entry) in enumerate(sorted(rosters().items()), 1):
        progress(f"roster {i}: {', '.join(entry['ids'])}")
        name = "roster_" + "_".join(sorted(entry["ids"]))[:80]
        try:
            out[name] = {"benchmark_cases": entry["ids"], **capture_account(am, roster(am, entry["roster"]), entry["pool"])}
        except KeyError as exc:
            out[name] = {"benchmark_cases": entry["ids"], "error": str(exc)}
    return out


def _path(name: str) -> Path:
    return GOLDEN_DIR / f"{name}.json"


def _dump(obj) -> str:
    return json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def _diff(old, new, path="") -> list[str]:
    """Readable leaf-level differences."""
    if isinstance(old, dict) and isinstance(new, dict):
        out = []
        for k in sorted(set(old) | set(new)):
            if k not in old:
                out.append(f"+ {path}{k}: {json.dumps(new[k], ensure_ascii=False)[:200]}")
            elif k not in new:
                out.append(f"- {path}{k}: {json.dumps(old[k], ensure_ascii=False)[:200]}")
            else:
                out += _diff(old[k], new[k], f"{path}{k}.")
        return out
    if isinstance(old, list) and isinstance(new, list) and len(old) == len(new):
        out = []
        for i, (a, b) in enumerate(zip(old, new)):
            out += _diff(a, b, f"{path}{i}.")
        return out
    if old != new:
        return [f"~ {path[:-1]}: {json.dumps(old, ensure_ascii=False)[:160]} -> {json.dumps(new, ensure_ascii=False)[:160]}"]
    return []


def check(current: dict | None = None) -> list[str]:
    current = current if current is not None else capture(progress=lambda m: None)
    diffs = []
    stored = {p.stem for p in GOLDEN_DIR.glob("*.json")}
    for name, data in current.items():
        p = _path(name)
        if not p.exists():
            diffs.append(f"+ {name}: no stored golden output")
            continue
        old = json.loads(p.read_text(encoding="utf-8"))
        diffs += [f"[{name}] {d}" for d in _diff(old, json.loads(_dump(data)))]
    for name in sorted(stored - set(current)):
        diffs.append(f"- {name}: stored golden output no longer produced")
    return diffs


def update(reason: str, current: dict | None = None) -> list[str]:
    if not reason or len(reason.strip()) < 10:
        raise ValueError("a golden update needs a reason (at least a sentence)")
    current = current if current is not None else capture(progress=lambda m: None)
    diffs = check(current)
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    for name, data in current.items():
        _path(name).write_text(_dump(data), encoding="utf-8")
    for p in GOLDEN_DIR.glob("*.json"):
        if p.stem not in current:
            p.unlink()
    from gtc import params
    changed = sorted({d.split("]")[0].strip("[") if d.startswith("[") else d.split(":")[0] for d in diffs})
    entry = [f"## {datetime.now():%Y-%m-%d %H:%M}, model {params.version()}", "", reason.strip(), "",
             f"{len(diffs)} changed values in {len(changed)} outputs" + (": " + ", ".join(changed[:30]) if changed else "") + ".", ""]
    if diffs:
        entry += ["```"] + diffs[:200] + (["..."] if len(diffs) > 200 else []) + ["```", ""]
    prev = CHANGES.read_text(encoding="utf-8") if CHANGES.exists() else "# Golden output changes\n\nEvery update of tests/golden, newest last.\n\n"
    CHANGES.write_text(prev + "\n".join(entry) + "\n", encoding="utf-8")
    return diffs
