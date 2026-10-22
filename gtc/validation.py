"""Out-of-sample validation of the frozen model (model 6.4): about 30 lineups in the model's uncertain region,
simulated locally with gcsim, never used for training or tuning.

Simulating a lineup needs a rotation, and the lineups that matter here have no community config. They are built
the way the pair model extrapolates: from the nearest simulated lineup (three shared members), whose accepted
community config keeps its tuned rotation for those three, with the fourth member swapped:
  - build block: the joining character's lines from their own best standard community config
  - actions: each action line of the leaving character becomes the joining character's next action line from that
    same config (cycled); other references to the leaving character (conditions, `active`) are renamed
A swapped rotation is not tuned, so the method has its own bias. Category M measures it: lineups that do have
community values, rebuilt by the same swap from a neighbouring config and compared with their community value.

Freeze (`freeze`): the lineup list and every prediction are written before any simulation runs, with hashes of the
model parameters, the pair model and the uncertainty calibration, so the results are out-of-sample evidence.
Files: data/validation/v64/ (personal data, git-ignored like data/sims).
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
from collections import Counter

from gtc import KNOWLEDGE_DIR, ROOT

VALID_DIR = ROOT / "data" / "validation" / "v64"
FROZEN_PATH = VALID_DIR / "frozen.json"
RESULTS_PATH = VALID_DIR / "results.json"
BUILD_RE = re.compile(r"\s*([a-z0-9]+)\s+(char|add\s+(?:weapon|set|stats))\b")
HEADER_RE = re.compile(r"\s*(options|target|energy|active|hurt|set_default_target)\b")


def _sha(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16] if path.exists() else "missing"


def model_hashes() -> dict:
    from gtc.estimate import UNCERTAINTY_PATH
    from gtc.pairmodel import PAIR_EFFECTS_PATH
    from gtc import params

    return {"model_version": params.version(), "model.yaml": _sha(KNOWLEDGE_DIR / "model.yaml"),
            "pair_effects.json": _sha(PAIR_EFFECTS_PATH), "uncertainty.json": _sha(UNCERTAINTY_PATH)}


# ---------- configs ----------

def _names():
    from gtc import gamedata

    return gamedata.names()


def _best_configs() -> dict[frozenset, object]:
    """Best accepted single-target standard community sim per lineup (with its raw config available)."""
    from gtc.sim import _raw_entries
    from gtc.sources import gcsim_db

    raw = _raw_entries()
    best: dict[frozenset, object] = {}
    for t in gcsim_db.load():
        if len(t.names) == 4 and t.targets == 1 and t.accepted and gcsim_db.is_standard(t) and t.id in raw:
            if t.names not in best or t.dps > best[t.names].dps:
                best[t.names] = t
    return best


def _keys_for(text: str, names) -> dict[str, str]:
    """gcsim key (as used in this config's build lines) -> display name."""
    from gtc.sim import Keys

    canonical = Keys().char_canonical
    out = {}
    for line in text.splitlines():
        m = BUILD_RE.match(line)
        if m and m.group(2) == "char":
            a = m.group(1)
            d = names.character(a) or names.character(canonical.get(a, ""))
            if d:
                out[a] = d
    return out


def _aliases(display: str, names) -> set[str]:
    from gtc.sim import Keys

    canonical = Keys().char_canonical
    out = {a for a, c in canonical.items() if (names.character(c) or names.character(a)) == display}
    return out | {a for a in canonical if names.character(a) == display}


def _is_action(line: str, aliases: set[str]) -> bool:
    m = re.match(r"\s*([a-z0-9]+)\s+(?!char\b|add\b)", line)
    return bool(m) and m.group(1) in aliases and not BUILD_RE.match(line)


def character_block(name: str, best=None, names=None) -> dict | None:
    """The character's build lines and action lines from their best standard community config."""
    from gtc.sim import _raw_entries

    names = names or _names()
    best = best or _best_configs()
    raw = _raw_entries()
    mine = [t for k, t in best.items() if name in k]
    if not mine:
        return None
    t = max(mine, key=lambda t: t.dps)
    text = raw[t.id]["config"]
    keys = _keys_for(text, names)
    key = next((k for k, d in keys.items() if d == name), None)
    if key is None:
        return None
    aliases = _aliases(name, names) | {key}
    build = [l.strip() for l in text.splitlines() if (m := BUILD_RE.match(l)) and m.group(1) == key]
    actions, seen = [], set()
    for l in _statements(text):
        if _is_action(l, aliases) and not re.search(r"\.[a-z0-9]+\.", l):
            a = re.sub(r"^\s*[a-z0-9]+", key, l.strip())
            if a not in seen:
                seen.add(a)
                actions.append(a)
    return {"key": key, "build": build, "actions": actions or [f"{key} skill;"], "source_id": t.id} if build else None


WAIT_LIMIT = 0.25  # share of the fight spent waiting on failed actions above which a harness run is unreliable
HARNESS_VERSION = 2  # 1 replaced lines (multi-line statements broke, unaffordable Bursts stalled); 2 is statement-level


def _statements(text: str) -> list[str]:
    """One action statement per line: a line continuing an unfinished statement is joined to it; comments dropped."""
    out: list[str] = []
    for line in text.splitlines():
        code = line.split("#", 1)[0].rstrip()
        if not code.strip():
            continue
        if out and not re.search(r"[;{}]\s*$", out[-1]) and not BUILD_RE.match(line):
            out[-1] = out[-1] + " " + code.strip()
        else:
            out.append(code)
    return out


def swap_config(target, best=None, names=None) -> dict | None:
    """A gcsim config for `target` (four names) from its nearest simulated lineup with one member swapped: the
    best-DPS neighbour whose script does not test the leaving character's own state."""
    names = names or _names()
    best = best or _best_configs()
    target = frozenset(target)
    near = sorted(((k, t) for k, t in best.items() if len(k & target) == 3), key=lambda kt: (-kt[1].dps, sorted(kt[0])))
    for base_set, base in near:
        got = _swap_from(target, base_set, base, best, names)
        if got is not None:
            return got
    return None


def _swap_from(target, base_set, base, best, names) -> dict | None:
    from gtc.sim import _raw_entries, guard_bursts

    leaving, joining = next(iter(base_set - target)), next(iter(target - base_set))
    blk = character_block(joining, best, names)
    if blk is None:
        return None
    text = _raw_entries()[base.id]["config"]
    keys = _keys_for(text, names)
    lkey = next((k for k, d in keys.items() if d == leaving), None)
    if lkey is None:
        return None
    laliases = _aliases(leaving, names) | {lkey}
    jkey = blk["key"]
    if jkey in keys and keys[jkey] != joining:  # the joining key collides with another member's key
        return None
    if any(re.search(rf"\.{re.escape(a)}\.", text) for a in laliases):
        return None  # the script tests the leaving character's own state (energy, stacks...): not transferable
    out, done, i = [], False, 0
    for line in _statements(text):
        m = BUILD_RE.match(line)
        if m and m.group(1) == lkey:
            if not done:
                out += blk["build"]
                done = True
            continue
        if _is_action(line, laliases):
            indent = re.match(r"\s*", line).group(0)
            out.append(indent + blk["actions"][i % len(blk["actions"])])
            i += 1
            continue
        for a in sorted(laliases, key=len, reverse=True):
            line = re.sub(rf"(?<![a-z0-9]){re.escape(a)}(?![a-z0-9])", jkey, line)
        out.append(line)
    if i == 0:
        return None
    all_keys = set(keys) | {jkey} | {a for d in list(keys.values()) + [joining] for a in _aliases(d, names)}
    text = guard_bursts("\n".join(out), all_keys)  # an unaffordable Burst is waited for briefly, then skipped
    return {"text": text, "base": sorted(base_set), "base_id": base.id, "base_dps": base.dps,
            "leaving": leaving, "joining": joining, "joining_source": blk["source_id"], "replaced_lines": i,
            "harness": HARNESS_VERSION}


# ---------- predictions ----------

def predict(lineup) -> dict:
    """Everything the frozen model says about a lineup, recorded before it is simulated."""
    from itertools import combinations

    from gtc import distance
    from gtc.bench import Engine
    from gtc.evaluate import lineup_power
    from gtc.pairmodel import load

    global _ENG
    if _ENG is None:
        _ENG = Engine()
    eng = _ENG
    names = sorted(lineup)
    r = eng.am.assess_lineup(names, eng.roster(names))
    a = r["assessment"]
    raw = lineup_power(frozenset(names), eng.am.ev)
    pm = load()
    ev = eng.am.ev
    st = (a.evaluation.structure or {}) if a and a.evaluation else {}
    ident = a.evaluation.identity if a and a.evaluation else {}
    pairs = {}
    if pm and pm.known(names):
        for x, y in combinations(names, 2):
            k = pm.key(x, y)
            if k in pm.pairs:
                pairs[k] = {"effect": round(pm.pairs[k], 3), "lineups": pm.counts.get(k, 0)}
    f = None
    try:
        f, near, away = distance.for_lineup(frozenset(names), ev)
    except Exception:  # noqa: BLE001
        pass
    b = raw.basis if raw else None
    return {
        "lineup": names, "status": r["status"], "status_reasons": r["reasons"],
        "expected": round(raw.expected, 2) if raw else None, "sd": round(raw.sd, 2) if raw else None,
        "rel_sd": round(raw.sd / raw.expected, 4) if raw and raw.expected else None,
        "route": b.route if b else None, "tier": b.tier if b else None, "state": b.evidence_state if b else None,
        "nearest": sorted(b.nearest_simulated) if b and b.nearest_simulated else None,
        "member_distance": b.member_distance if b else None, "distance_features": f,
        "decision_value": a.potential if a else None,
        "primary_actor": ident.get("primary_actor"), "label": ident.get("label"),
        "structure_primary": {k: round(v, 3) for k, v in (st.get("primary") or {}).items()},
        "structure_type": st.get("type"),
        "coverage": a.evaluation.coverage if a and a.evaluation else None,
        "typicality": a.evaluation.validity.get("typicality") if a and a.evaluation else None,
        "capacity": round(pm.capacity(names), 3) if pm and pm.capacity(names) is not None else None,
        "pair_effects": pairs, "normalizer": ev.normalizer,
    }


_ENG = None


def freeze(lineups: list[dict]) -> dict:
    """Record the lineup list, every prediction and the swap configs, with model hashes, before simulating."""
    VALID_DIR.mkdir(parents=True, exist_ok=True)
    if FROZEN_PATH.exists():
        raise FileExistsError(f"{FROZEN_PATH} exists: the validation set is frozen")
    best, names = _best_configs(), _names()
    rows = []
    for spec in lineups:
        cfg = swap_config(spec["lineup"], best, names)
        row = {**spec, "prediction": predict(spec["lineup"]),
               "config": {k: v for k, v in cfg.items() if k != "text"} if cfg else None,
               "config_sha": hashlib.sha1(cfg["text"].encode()).hexdigest()[:16] if cfg else None}
        if spec.get("category") == "M":
            from gtc.sources import gcsim_db

            lv = gcsim_db.lineup_values().get(frozenset(spec["lineup"]))
            row["community_value"] = round(100 * lv.value / row["prediction"]["normalizer"], 2) if lv else None
        rows.append(row)
    listing = json.dumps([r["lineup"] for r in rows])
    out = {"hashes": {**model_hashes(), "lineups": hashlib.sha256(listing.encode()).hexdigest()[:16]}, "rows": rows}
    FROZEN_PATH.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def simulate(progress=print) -> dict:
    """Run every frozen lineup's swap config in gcsim (cached by content). Never touches the training data."""
    from gtc.sim import ITERATIONS, run

    frozen = json.loads(FROZEN_PATH.read_text(encoding="utf-8"))
    best, names = _best_configs(), _names()
    results = []
    for row in frozen["rows"]:
        cfg = swap_config(row["lineup"], best, names)
        if cfg is None:
            results.append({"lineup": row["lineup"], "error": "no swap config"})
            continue
        # The lineups and predictions are frozen; the simulation harness may be fixed (recorded per result).
        text = re.sub(r"iteration=\d+", f"iteration={ITERATIONS}", cfg["text"])
        res = run(text)
        norm = row["prediction"]["normalizer"]
        duration = waited = 0.0
        if res.raw_path and res.raw_path.exists():
            st = json.loads(res.raw_path.read_text(encoding="utf-8"))["statistics"]
            duration = (st.get("duration") or {}).get("mean") or 0.0
            waited = sum((v or {}).get("mean", 0.0) for fa in (st.get("failed_actions") or []) for v in (fa or {}).values())
        results.append({"lineup": row["lineup"], "harness": cfg.get("harness"), "base": cfg["base"],
                        "config_sha": hashlib.sha1(cfg["text"].encode()).hexdigest()[:16], "dps": res.dps, "power": round(100 * res.dps / norm, 2) if res.dps else None,
                        "dps_se": res.dps_se, "error": res.error, "character_dps": res.character_dps,
                        "failed_actions": {k: v for k, v in (res.failed_actions or {}).items() if v},
                        "duration": round(duration, 1), "waited": round(waited, 1),
                        # declared before scoring: a run that spends more than WAIT_LIMIT of the fight waiting on
                        # actions it cannot perform measures the harness, not the team
                        "reliable": bool(res.dps) and (not duration or waited / duration <= WAIT_LIMIT)})
        progress(f"{' / '.join(row['lineup'])}: {results[-1]['power']}")
    out = {"hashes": frozen["hashes"], "results": results}
    RESULTS_PATH.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


# ---------- scoring ----------

def _stats(rows) -> dict:
    """rows: (log error predicted/simulated, predicted relative sd)."""
    if not rows:
        return {}
    e = [x for x, _ in rows]
    ae = sorted(abs(x) for x in e)
    return {"n": len(rows), "median_abs_log_error": round(statistics.median(ae), 3),
            "rmse_log": round(math.sqrt(sum(x * x for x in e) / len(e)), 3), "bias_log": round(statistics.mean(e), 3),
            "median_bias_log": round(statistics.median(e), 3),
            "within_1sd": round(sum(abs(x) <= s for x, s in rows) / len(rows), 2),
            "within_2sd": round(sum(abs(x) <= 2 * s for x, s in rows) / len(rows), 2)}


def score(predictions_override: dict | None = None, include_unreliable: bool = False, final_sd: bool = True) -> dict:
    """Frozen predictions against the validation simulations. The swap method's own bias is measured on category M
    (community value against the swap simulation) and removed from the simulated values of the other categories;
    both raw and method-corrected numbers are reported. `predictions_override` maps a lineup tuple to an alternative
    (expected, rel_sd), to evaluate a candidate fix on the same frozen set."""
    frozen = json.loads(FROZEN_PATH.read_text(encoding="utf-8"))
    sims = {tuple(r["lineup"]): r for r in json.loads(RESULTS_PATH.read_text(encoding="utf-8"))["results"]}
    method = []
    for row in frozen["rows"]:
        s = sims.get(tuple(row["lineup"]))
        if row["category"] == "M" and s and s.get("power") and row.get("community_value") and (s.get("reliable", True) or include_unreliable):
            method.append(math.log(s["power"] / row["community_value"]))
    shift = statistics.median(method) if method else 0.0
    # Post-hoc second control (model 6.4): a swap that REMOVES a carry leaves that carry's field time to a support's
    # actions, a much larger harness bias than a support swap. Measured on community-simulated low-capacity lineups
    # rebuilt by carry-removed swaps (data/validation/v64/carry_controls.json).
    carry_shift, carry_spread = None, None
    cpath = VALID_DIR / "carry_controls.json"
    if cpath.exists():
        c = json.loads(cpath.read_text(encoding="utf-8"))
        carry_shift, carry_spread = c.get("median_log_ratio_reliable"), c.get("spread_reliable")
    from gtc.capabilities import load as load_caps

    caps = load_caps()
    out = {"method_bias_log": round(shift, 3), "method_n": len(method),
           "method_spread": round(statistics.pstdev(method), 3) if len(method) > 1 else None,
           "carry_removed_bias_log": round(carry_shift, 3) if carry_shift is not None else None,
           "by_category": {}, "rows": []}
    groups: dict[str, list] = {}
    for row in frozen["rows"]:
        s = sims.get(tuple(row["lineup"]))
        p = row["prediction"]
        exp, rel = p["expected"], p["rel_sd"]
        if final_sd and rel:
            # the frozen model's final sd: typicality widens extrapolated estimates (gtc/typicality.py)
            from gtc.typicality import sd_factor

            rel = rel * (sd_factor(len(p.get("typicality") or [])) if p["route"] in ("pair_model", "role_rules", "provisional_kit") else 1.0)
        if predictions_override and tuple(row["lineup"]) in predictions_override:
            exp, rel = predictions_override[tuple(row["lineup"])]
        if s and not s.get("reliable", True) and not include_unreliable:
            out["rows"].append({"lineup": row["lineup"], "category": row["category"], "skipped": True,
                                "why": f"harness unreliable: waited {s.get('waited')} s of {s.get('duration')} s"})
            continue
        if not (s and s.get("power") and exp and rel):
            out["rows"].append({"lineup": row["lineup"], "category": row["category"], "skipped": True,
                                "why": (s or {}).get("error") or "no prediction"})
            continue
        leaving = (row.get("config") or {}).get("leaving")
        carry_removed = bool(leaving and leaving in caps and caps[leaving].damage_share >= 0.4 and carry_shift is not None)
        bias, spread = (carry_shift, carry_spread) if carry_removed else (shift, out["method_spread"])
        corrected = s["power"] / math.exp(bias) if row["category"] != "M" else s["power"]
        truth = row["community_value"] if row["category"] == "M" and row.get("community_value") else corrected
        # The method's own spread adds to the comparison's uncertainty (except on M, which measured it).
        sd = math.hypot(rel, spread or 0.0) if row["category"] != "M" else rel
        err = math.log(exp / truth)
        groups.setdefault(row["category"], []).append((err, sd))
        out["rows"].append({"lineup": row["lineup"], "category": row["category"], "kind": row.get("kind"),
                            "predicted": exp, "rel_sd": rel, "simulated_raw": s["power"], "simulated": round(truth, 2),
                            "log_error": round(err, 3), "z": round(err / sd, 2), "route": p["route"],
                            "swap": "carry removed" if carry_removed else "support swap",
                            "capacity": p["capacity"], "status": p["status"]})
    out["by_category"] = {k: _stats(v) for k, v in sorted(groups.items())}
    out["overall"] = _stats([x for k, v in groups.items() if k != "M" for x in v])
    out["worst"] = sorted((r for r in out["rows"] if not r.get("skipped")), key=lambda r: -abs(r["log_error"]))[:10]
    return out
