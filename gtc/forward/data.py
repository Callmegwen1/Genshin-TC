"""Game numbers from Project Amber (personal-use cache): character and weapon base stats by level, ascension stats,
and talent scaling tables at any talent level. These are the inputs a theorycrafter's spreadsheet starts from.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache

from gtc.sources.fetch import get

API = "https://gi.yatta.moe/api/v2"
PROP = {"FIGHT_PROP_BASE_HP": "base_hp", "FIGHT_PROP_BASE_ATTACK": "base_atk", "FIGHT_PROP_BASE_DEFENSE": "base_def",
        "FIGHT_PROP_CRITICAL": "cr", "FIGHT_PROP_CRITICAL_HURT": "cd", "FIGHT_PROP_CHARGE_EFFICIENCY": "er",
        "FIGHT_PROP_ELEMENT_MASTERY": "em", "FIGHT_PROP_ATTACK_PERCENT": "atk_pct", "FIGHT_PROP_HP_PERCENT": "hp_pct",
        "FIGHT_PROP_DEFENSE_PERCENT": "def_pct", "FIGHT_PROP_HEAL_ADD": "heal",
        "FIGHT_PROP_PHYSICAL_ADD_HURT": "Physical", "FIGHT_PROP_FIRE_ADD_HURT": "Pyro", "FIGHT_PROP_WATER_ADD_HURT": "Hydro",
        "FIGHT_PROP_ELEC_ADD_HURT": "Electro", "FIGHT_PROP_ICE_ADD_HURT": "Cryo", "FIGHT_PROP_WIND_ADD_HURT": "Anemo",
        "FIGHT_PROP_ROCK_ADD_HURT": "Geo", "FIGHT_PROP_GRASS_ADD_HURT": "Dendro"}
WEAPON_TYPE = {"sword": "WEAPON_SWORD_ONE_HAND", "claymore": "WEAPON_CLAYMORE", "polearm": "WEAPON_POLE",
               "catalyst": "WEAPON_CATALYST", "bow": "WEAPON_BOW"}
PARAM = re.compile(r"\{param(\d+):([A-Z0-9]+)\}")


def _json(path: str):
    body = get(f"{API}/{path}", "amber", max_age_days=60, delay=0.3, browser=False)
    return json.loads(body)["data"] if body else None


@lru_cache(maxsize=2)
def _curves(kind: str) -> dict:
    return _json(f"static/{kind}Curve")


def _character(name: str) -> dict:
    from gtc.kitcompile import amber

    d = amber().get(name)
    if d is None:
        raise KeyError(f"no Amber data for {name}")
    return d


def _leveled(upgrade: dict, curves: dict, level: int, ascension: int) -> dict[str, float]:
    out: dict[str, float] = {}
    for p in upgrade.get("prop") or []:
        key = PROP.get(p["propType"])
        if key:
            out[key] = out.get(key, 0.0) + p["initValue"] * curves[str(level)]["curveInfos"][p["type"]]
    for pr in upgrade.get("promote") or []:
        if pr.get("promoteLevel", 0) == ascension:
            for k, v in (pr.get("addProps") or {}).items():
                key = PROP.get(k)
                if key:
                    out[key] = out.get(key, 0.0) + v
    return out


def ascension_for(level: int) -> int:
    return sum(1 for cap in (20, 40, 50, 60, 70, 80) if level > cap)


@lru_cache(maxsize=512)
def character_stats(name: str, level: int = 90) -> dict[str, float]:
    """Base HP / ATK / DEF and the ascension stat at a level (ascended to that level's cap)."""
    up = _character(name)["upgrade"]
    st = _leveled(up, _curves("avatar"), level, ascension_for(level))
    st.setdefault("cr", 0.0)
    st["cr"] += 0.05
    st.setdefault("cd", 0.0)
    st["cd"] += 0.5
    st.setdefault("er", 0.0)
    st["er"] += 1.0
    return st


@lru_cache(maxsize=1)
def weapons_index() -> dict:
    return _json("en/weapon")["items"]


def weapon_id(name: str) -> str | None:
    for k, v in weapons_index().items():
        if v["name"].lower() == name.lower():
            return k
    return None


@lru_cache(maxsize=256)
def weapon_stats(name: str, level: int = 90) -> dict[str, float]:
    """A weapon's base ATK and substat at a level. Passives are not included here."""
    wid = weapon_id(name)
    if wid is None:
        raise KeyError(f"no Amber weapon {name}")
    up = _json(f"en/weapon/{wid}")["upgrade"]
    return _leveled(up, _curves("weapon"), level, ascension_for(level))


# ---------- talent tables ----------

def talent_entries(name: str) -> list[dict]:
    """[{name, kind (normal|skill|burst|passive), promote}] in Amber order: the first type-0 talent is the Normal
    Attack, the second type-0 the Elemental Skill, type 1 the Burst, type 2 passives."""
    out, zeros = [], 0
    for t in (_character(name).get("talent") or {}).values():
        typ = str(t.get("type"))
        if typ == "0":
            kind = "normal" if zeros == 0 else "skill"
            zeros += 1
        elif typ == "1":
            kind = "burst"
        else:
            kind = "passive"
        out.append({"name": t.get("name", ""), "kind": kind, "promote": t.get("promote"), "description": t.get("description", "")})
    return out


def talent_kind(name: str, talent: str) -> str | None:
    """normal | skill | burst | passive for a talent named in a kit `source` (prefix match)."""
    s = (talent or "").lower()
    best = None
    for t in talent_entries(name):
        if t["name"] and s.startswith(t["name"].lower()):
            if best is None or len(t["name"]) > len(best["name"]):
                best = t
    return best["kind"] if best else None


def _clean_label(label: str) -> str:
    label = re.sub(r"#?\{LAYOUT_MOBILE#[^}]*\}\{LAYOUT_PC#([^}]*)\}\{LAYOUT_PS#[^}]*\}", r"\1", label)
    return re.sub(r"<[^>]+>", "", label).strip()


@lru_cache(maxsize=4096)
def table(name: str, kind: str, level: int = 9) -> dict[str, list[float]]:
    """{label: [values]} for one talent (normal | skill | burst) at a talent level. A label with several numbers
    ("4-Hit DMG: 41.6%×3", "Press/Hold Duration: 10s/15s") keeps them all, in order; a "×N" suffix repeats."""
    t = next((x for x in talent_entries(name) if x["kind"] == kind), None)
    pr = (t or {}).get("promote")
    lv = pr.get(str(level)) if isinstance(pr, dict) else None
    if not lv:
        return {}
    params = lv.get("params") or []
    out = {}
    for row in lv.get("description") or []:
        if "|" not in row:
            continue
        label, fmt = row.split("|", 1)
        vals = [params[int(i) - 1] for i, _ in PARAM.findall(fmt) if 0 < int(i) <= len(params)]
        m = re.search(r"[×x*×�](\d+)", fmt)
        if m and len(vals) == 1:
            vals = vals * int(m.group(1))
        out[_clean_label(label)] = vals
    return out


_STAT_WORDS = (("elemental mastery", "em"), ("max hp", "hp"), ("hp", "hp"), ("def", "def"), ("atk", "atk"))


@lru_cache(maxsize=4096)
def terms(name: str, kind: str, label: str, level: int = 9) -> list[tuple[float, str | None]]:
    """The row's scaling terms in order: [(value, stat)], the stat read from the text after each number ("Max HP",
    "Elemental Mastery", "ATK", "DEF"; None when the text names none). "Tri-Karma Purification DMG: 103.2% ATK + 206.4%
    Elemental Mastery" gives two terms; Kuki's "Single Instance DMG: 3.6% Max HP" one HP term."""
    t = next((x for x in talent_entries(name) if x["kind"] == kind), None)
    pr = (t or {}).get("promote")
    lv = pr.get(str(level)) if isinstance(pr, dict) else None
    if not lv:
        return []
    params = lv.get("params") or []
    for row in lv.get("description") or []:
        if "|" not in row:
            continue
        lab, fmt = row.split("|", 1)
        if _clean_label(lab).lower() != label.lower():
            continue
        out = []
        ms = list(PARAM.finditer(fmt))
        for j, m in enumerate(ms):
            i = int(m.group(1))
            if not 0 < i <= len(params):
                continue
            tail = fmt[m.end(): ms[j + 1].start() if j + 1 < len(ms) else len(fmt)].lower()
            stat = next((s for w, s in _STAT_WORDS if w in tail), None)
            out.append((params[i - 1], stat))
        return out
    return []


def value(name: str, kind: str, label: str, level: int = 9, index: int = 0) -> float | None:
    """One number from a talent table (case-insensitive label prefix match)."""
    tab = table(name, kind, level)
    key = next((k for k in tab if k.lower() == label.lower()), None) or \
        next((k for k in tab if k.lower().startswith(label.lower())), None)
    if key is None or index >= len(tab[key]):
        return None
    return tab[key][index]
