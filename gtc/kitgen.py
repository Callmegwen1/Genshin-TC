"""Generated kits for the theorycraft calculator, from gcsim logs.

For every simulated character, one representative simulation (their median-DPS lineup) is run with gcsim's
per-hit log. Every buff they give a teammate is read from the hits it touched: the stat, its median value, and
its uptime, the share of the receivers' damage it was active on. RES shred is read the same way from the
enemy's resistance modifiers. The result, knowledge/generated/kits_auto.yaml, uses the kits.yaml format;
hand-written kits (knowledge/kits.yaml, knowledge/kits_custom/) override a generated entry as a whole.

Buffs from team artifact sets (Viridescent Venerer, Noblesse Oblige...) are left out: the calculator applies
those from the set table when the holder wears the set.

What the logs cannot give: talent multipliers for own damage (the calculator measures a newcomer's own damage
in a simulation instead), conditional buffs gcsim did not trigger in that rotation, and constellations other
than the community standard (5-stars C0, 4-stars C6).
"""
from __future__ import annotations

import re
from collections import defaultdict
from statistics import median

import yaml

from gtc import KNOWLEDGE_DIR, params

KITS_AUTO_PATH = KNOWLEDGE_DIR / "generated" / "kits_auto.yaml"
MIN_UPTIME = params.get("kitgen.min_uptime")
STAT_MAP = {"atk%": "atk_pct", "hp%": "hp_pct", "def%": "def_pct", "atk": "atk", "hp": "hp", "def": "def",
            "em": "em", "cr": "cr", "cd": "cd", "dmg%": "dmg_pct", "dmgp": "dmg_pct",
            "pyro%": "Pyro", "hydro%": "Hydro", "electro%": "Electro", "cryo%": "Cryo", "anemo%": "Anemo",
            "geo%": "Geo", "dendro%": "Dendro", "phys%": "Physical", "physical%": "Physical"}


def _representatives() -> dict[str, frozenset]:
    """Each character's median-DPS simulated lineup (four members)."""
    from gtc.synergy import load_database

    by_char: dict[str, list] = defaultdict(list)
    for e in load_database().values():
        if "lineup" in e and len(e["lineup"]) == 4:
            for m in e["lineup"]:
                by_char[m].append(e)
    out = {}
    for m, entries in by_char.items():
        entries.sort(key=lambda e: e["dps"])
        out[m] = frozenset(entries[len(entries) // 2]["lineup"])
    return out


def extract(sample: dict, names, kits: dict, who: str) -> list[dict]:
    """Effects `who` gives teammates in one gcsim per-hit log."""
    from gtc.synergy import TEAM_SET_KEYS, Attributor, _stats
    from gtc.sources.names import norm

    att = Attributor(sample, names, kits)
    members = att.members
    # Team-set buffs the calculator already applies from its set table are left out; other sets' buffs
    # (Noblesse Oblige, Deepwood Memories...) stay with their holder, or they would be lost.
    in_table = set((kits.get("_sets") or {}).keys())
    skip_prefixes = [norm(p) for p, set_name in TEAM_SET_KEYS.items() if set_name in in_table]
    if who not in members:
        return []
    dmg_by: dict[str, float] = defaultdict(float)
    seen: dict[tuple, dict] = {}  # (key, stat) -> {"values": [], "dmg": {receiver: damage}}
    shred: dict[tuple, dict] = {}  # (key, element) -> {"values": [], "dmg": 0}
    ele_dmg: dict[str, float] = defaultdict(float)
    for l in att.logs:
        if l.get("event") != "damage":
            continue
        lg = l["logs"]
        dmg = float(lg.get("damage") or 0)
        idx = l.get("char_index", -1)
        if dmg <= 0 or not 0 <= idx < len(members):
            continue
        receiver = members[idx]
        dmg_by[receiver] += dmg
        ele = str(lg.get("ele", "")).lower()
        ele_dmg[ele] += dmg
        mods = [(k, v) for k, v in lg.items() if isinstance(v, list) and k not in ("resist_mods", "pre_damage_mods")]
        pdm = lg.get("pre_damage_mods")
        if isinstance(pdm, list):
            mods += [(pdm[i], pdm[i + 1]) for i in range(0, len(pdm) - 1, 2) if isinstance(pdm[i], str)]
        for key, entries in mods:
            if any(norm(key).startswith(p) for p in skip_prefixes) or att.owner_of(key, receiver) != who:
                continue
            for stat, v in _stats(entries):
                if stat in STAT_MAP:
                    rec = seen.setdefault((key, stat), {"values": [], "dmg": defaultdict(float)})
                    rec["values"].append(v)
                    rec["dmg"][receiver] += dmg
        rm = lg.get("resist_mods")
        if isinstance(rm, list):
            for i in range(0, len(rm) - 1, 2):
                key, info = rm[i], rm[i + 1]
                if not isinstance(info, list) or "status: added" not in info or any(norm(key).startswith(p) for p in skip_prefixes):
                    continue
                if att.resist_owner(key, receiver) != who:
                    continue
                amount = next((float(x.split(":")[1]) for x in info if str(x).startswith("amount")), 0.0)
                el = next((x.split(":")[1].strip() for x in info if str(x).startswith("ele")), "")
                if el and el.lower() != ele:
                    continue
                rec = shred.setdefault((key, el.lower() or "all"), {"values": [], "dmg": 0.0})
                rec["values"].append(-amount)
                rec["dmg"] += dmg
    effects = []
    for (key, stat), rec in sorted(seen.items()):
        receivers = [r for r in rec["dmg"] if r != who]
        if not receivers:
            continue  # a self-buff: already part of their own measured damage
        got = sum(rec["dmg"][r] for r in receivers)
        avail = sum(dmg_by[r] for r in receivers)
        uptime = got / avail if avail else 0.0
        if uptime < MIN_UPTIME:
            continue
        target = ("party" if who in rec["dmg"] else "others") if len(receivers) >= 2 else "active"
        effects.append({"kind": "stat", "stat": STAT_MAP[stat], "target": target, "value": round(median(rec["values"]), 4),
                        "uptime": round(min(1.0, uptime), 3), "note": f"generated from gcsim key {key}"})
    for (key, el), rec in sorted(shred.items()):
        uptime = rec["dmg"] / ele_dmg[el] if ele_dmg.get(el) else 0.0
        if uptime < MIN_UPTIME or not rec["values"]:
            continue
        element = "all" if el == "all" else el.capitalize()
        effects.append({"kind": "res_shred", "element": element, "value": round(median(rec["values"]), 4),
                        "uptime": round(min(1.0, uptime), 3), "note": f"generated from gcsim key {key}"})
    return effects


def build(progress=print, workers: int = 14) -> int:
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from gtc import gamedata
    from gtc.sim import Config, Keys, _raw_entries, render
    from gtc.sources import gcsim_db
    from gtc.synergy import run_sample
    from gtc.tc.engine import load_kits

    names, keys, kits = gamedata.names(), Keys(), load_kits(generated=False)
    game = gamedata.load_characters()
    raw = _raw_entries()
    by_lineup: dict[frozenset, list] = defaultdict(list)
    for t in gcsim_db.load():
        if gcsim_db.is_standard(t):
            by_lineup[t.names].append(t)
    jobs = []
    for who, L in sorted(_representatives().items()):
        sims = sorted(by_lineup.get(L, []), key=lambda t: t.dps)
        if not sims or sims[len(sims) // 2].id not in raw:
            continue
        t = sims[len(sims) // 2]
        e = raw[t.id]
        ck = {}
        for line in e["config"].splitlines():
            m = re.match(r"\s*([a-z0-9]+)\s+char\s", line)
            if m:
                d = names.character(m.group(1)) or names.character(keys.char_canonical.get(m.group(1), ""))
                if d:
                    ck[d] = m.group(1)
        text, _ = render(Config(e["config"], t.id, t.dps, ck), {}, keys, iterations=1)
        jobs.append((who, L, text))

    def work(job):
        who, L, text = job
        try:
            return who, L, extract(run_sample(text, keep=False), names, kits, who)
        except Exception as exc:  # a config gcsim cannot run any more
            return who, L, None

    out = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i, fut in enumerate(as_completed([pool.submit(work, j) for j in jobs]), 1):
            who, L, effects = fut.result()
            if effects is not None:
                out[who] = {"element": game.get(who, {}).get("element", ""), "generated": True,
                            "from_lineup": " / ".join(sorted(L)), "effects": effects}
            if i % 25 == 0:
                progress(f"{i} of {len(jobs)} characters read")
    header = ("# GENERATED by `python -m gtc kits` from gcsim per-hit logs. Do not edit; a character described in\n"
              "# knowledge/kits.yaml or knowledge/kits_custom/ overrides their entry here.\n")
    KITS_AUTO_PATH.write_text(header + yaml.safe_dump(dict(sorted(out.items())), sort_keys=False, allow_unicode=True, width=160),
                              encoding="utf-8")
    return len(out)
