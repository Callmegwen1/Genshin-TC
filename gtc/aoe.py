"""Multi-target strength: how much more a team deals against grouped enemies than against one.

For the strongest simulated lineups of every archetype (and at least one lineup per simulated character),
the community config is run twice with our own gcsim: against the standard single target and against three
targets in a spread line (radius 1, 1.5 apart, the layout of the database's own multi-target sims). The
lineup's AoE ratio is three-target DPS over single-target DPS, and each member's ratio is their own damage
the same way. Written to data/sources/aoe.json by `python -m gtc aoe`.

An unsimulated lineup's ratio is its members' ratios weighted by their predicted damage shares. A character
never run gets the median ratio of their element, then the overall median.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from statistics import median

from gtc import params
from gtc.sources import SOURCE_DIR

AOE_PATH = SOURCE_DIR / "aoe.json"
TARGETS_3 = ("target lvl=100 resist=0.1 radius=1 pos=-1.5,2.4 hp=999999999;\n"
             "target lvl=100 resist=0.1 radius=1 pos=0,2.4 hp=999999999;\n"
             "target lvl=100 resist=0.1 radius=1 pos=1.5,2.4 hp=999999999;")
LINEUPS_PER_FAMILY = params.get("aoe.lineups_per_family")
ITERATIONS = params.get("aoe.iterations")
MIN_OWN_SHARE = params.get("aoe.min_own_share")


def _three_targets(text: str) -> str:
    lines = [l for l in text.splitlines() if not l.strip().startswith("target ")]
    return "\n".join(lines) + "\n" + TARGETS_3 + "\n"


def select_lineups() -> list[frozenset]:
    """The best few lineups of each archetype family, plus each simulated character's best lineup."""
    from gtc.derive import FAMILY_LINEUPS
    from gtc.synergy import load_database

    db = {frozenset(e["lineup"]): e for e in load_database().values() if "lineup" in e and len(e["lineup"]) == 4}
    families = json.loads(FAMILY_LINEUPS.read_text(encoding="utf-8")) if FAMILY_LINEUPS.exists() else {}
    chosen: list[frozenset] = []
    for lineups in families.values():
        ranked = sorted((frozenset(x) for x in lineups if frozenset(x) in db), key=lambda L: -db[L]["dps"])
        chosen += ranked[:LINEUPS_PER_FAMILY]
    covered = {m for L in chosen for m in L}
    best_for: dict[str, frozenset] = {}
    for L, e in db.items():
        for m in L:
            if m not in best_for or e["dps"] > db[best_for[m]]["dps"]:
                best_for[m] = L
    chosen += [L for m, L in best_for.items() if m not in covered]
    return list(dict.fromkeys(chosen))


def build(progress=print, workers: int = 14) -> dict:
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from gtc import gamedata
    from gtc.sim import Config, Keys, _raw_entries, render, run
    from gtc.sources import gcsim_db

    names, keys = gamedata.names(), Keys()
    raw = _raw_entries()
    by_lineup: dict[frozenset, list] = defaultdict(list)
    for t in gcsim_db.load():
        if gcsim_db.is_standard(t):
            by_lineup[t.names].append(t)
    jobs = []
    for L in select_lineups():
        sims = sorted(by_lineup.get(L, []), key=lambda t: t.dps)
        if not sims:
            continue
        t = sims[len(sims) // 2]
        e = raw.get(t.id)
        if not e:
            continue
        char_keys = {}
        for line in e["config"].splitlines():
            m = re.match(r"\s*([a-z0-9]+)\s+char\s", line)
            if m:
                display = names.character(m.group(1)) or names.character(keys.char_canonical.get(m.group(1), ""))
                if display:
                    char_keys[display] = m.group(1)
        text, _ = render(Config(e["config"], t.id, t.dps, char_keys), {}, keys, iterations=ITERATIONS)
        jobs.append((L, text))

    def work(job):
        L, text = job
        one, three = run(text), run(_three_targets(text))
        if one.error or three.error or not one.dps:
            return L, None
        members = {}
        for gname, d1 in one.character_dps.items():
            name = names.character(gname) or names.character(keys.char_canonical.get(gname, ""))
            if name and d1 >= MIN_OWN_SHARE * one.dps:
                members[name] = three.character_dps.get(gname, 0.0) / d1
        return L, {"lineup": sorted(L), "single": one.dps, "three": three.dps, "ratio": three.dps / one.dps, "members": members}

    results = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i, fut in enumerate(as_completed([pool.submit(work, j) for j in jobs]), 1):
            L, r = fut.result()
            if r:
                results.append(r)
            if i % 25 == 0:
                progress(f"{i} of {len(jobs)} lineups run against three targets")
    per_char: dict[str, list[float]] = defaultdict(list)
    for r in results:
        for m, ratio in r["members"].items():
            per_char[m].append(ratio)
    out = {"lineups": {"|".join(r["lineup"]): r["ratio"] for r in results},
           "characters": {m: {"ratio": median(v), "n": len(v)} for m, v in sorted(per_char.items())},
           "runs": results}
    AOE_PATH.write_text(json.dumps(out, indent=1), encoding="utf-8")
    global _DATA
    _DATA = out
    return out


_DATA: dict | None = None


def load() -> dict:
    global _DATA
    if _DATA is None:
        _DATA = json.loads(AOE_PATH.read_text(encoding="utf-8")) if AOE_PATH.exists() else {}
    return _DATA


def reference_ratio() -> float | None:
    """The median measured lineup ratio: an average team's AoE power equals its single-target power."""
    vals = list(load().get("lineups", {}).values())
    return median(vals) if vals else None


def character_ratio(name: str) -> tuple[float, str]:
    """(ratio, source) for one character: measured, else their element's median, else the overall median."""
    from gtc import gamedata

    d = load().get("characters", {})
    if name in d:
        return d[name]["ratio"], "measured"
    game = gamedata.load_characters()
    el = game.get(name, {}).get("element")
    same = [v["ratio"] for n, v in d.items() if game.get(n, {}).get("element") == el]
    if same:
        return median(same), f"median of {el} characters"
    allr = [v["ratio"] for v in d.values()]
    return (median(allr), "overall median") if allr else (1.0, "no data")


def lineup_ratio(members: list[str], shares: dict[str, float] | None = None) -> tuple[float, str]:
    """A lineup's AoE ratio: measured if it was run, otherwise its members' ratios weighted by damage share."""
    key = "|".join(sorted(members))
    measured = load().get("lineups", {}).get(key)
    if measured is not None:
        return measured, "measured"
    if shares is None:
        from gtc.capabilities import neighbours

        nb = neighbours()
        got = nb.profile(list(members)) if nb else None
        shares = {m: v["damage_share"] for m, v in got[0].items()} if got else {m: 1 / len(members) for m in members}
    total = sum(shares.values()) or 1.0
    return sum(shares.get(m, 0.0) / total * character_ratio(m)[0] for m in members), "from members' ratios"
