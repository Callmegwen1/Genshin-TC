"""Builds for the forward model (FM-8). One stat dictionary per character, in fractions (0.466 = 46.6%):
base_atk, base_hp, base_def (character + weapon), atk / hp / def flat additions, atk_pct / hp_pct / def_pct, em, cr,
cd, er, dmg_pct, and <Element> DMG%.

    META_STANDARD    the house theorycraft build, the same for everyone so characters and teams compare on equal
                     terms: level 90, talents 9/9/9, C0, a Favonius weapon of their type at level 90 (passive only
                     generates energy, so it is damage-neutral), no artifact set bonus, and a fixed artifact budget
                     (below). Enemy: level 100, 10% RES, one target.
    CURRENT_ACCOUNT  the player's snapshot: their level, talents, constellation, weapon (base ATK and substat from
                     Amber) and artifacts' main and substats. Set bonuses and weapon passives are not modelled yet:
                     they are listed in `unmodelled`, never guessed.
    ACCOUNT_CEILING  the house artifact budget on the player's own level-90 character, talents 9/9/9, their
                     constellation and their best owned weapon of the right type (by base ATK).

Artifact budget (house): flower 4780 HP, plume 311 ATK, sands = the stat they are built for (46.6% ATK/HP, 58.3% DEF),
goblet = 46.6% of their element (58.3% Physical), circlet 31.1% CRIT Rate; EM builds take 187 EM on all three; substats: CRIT Rate 23.1%, CRIT DMG
46.2%, 9.9% of the scaling stat, 11% ER, 40 EM, 33 ATK, 508 HP (about 20 rolls, KQM-style).
"""
from __future__ import annotations

from functools import lru_cache

from dataclasses import dataclass, field

from gtc.forward import data as D

ENEMY_LEVEL, ENEMY_RES = 100, 0.10
FAVONIUS = {"sword": "Favonius Sword", "claymore": "Favonius Greatsword", "polearm": "Favonius Lance",
            "catalyst": "Favonius Codex", "bow": "Favonius Warbow"}
GCSIM_FAVONIUS = {"sword": "favoniussword", "claymore": "favoniusgreatsword", "polearm": "favoniuslance",
                  "catalyst": "favoniuscodex", "bow": "favoniuswarbow"}
SANDS = {"atk": ("atk_pct", 0.466), "hp": ("hp_pct", 0.466), "def": ("def_pct", 0.583), "em": ("em", 187.0)}
SUBS = {"cr": 0.231, "cd": 0.462, "er": 0.11, "em": 40.0, "atk": 33.0, "hp": 508.0}
SCALING_SUB = {"atk": ("atk_pct", 0.099), "hp": ("hp_pct", 0.099), "def": ("def_pct", 0.124), "em": ("em", 40.0)}


@dataclass
class Build:
    name: str
    profile: str
    level: int
    constellation: int
    talents: dict[str, int]
    weapon: str
    stats: dict[str, float]
    unmodelled: list[str] = field(default_factory=list)
    artifacts: dict[str, float] = field(default_factory=dict)  # the artifact part alone (for rendering gcsim)
    gear: dict = field(default_factory=dict)   # {"weapon", "refine", "sets": {name: pieces}}: passives and set effects (phase H)

    def total(self, stat: str) -> float:
        s = self.stats
        if stat in ("atk", "hp", "def"):
            return s.get(f"base_{stat}", 0) * (1 + s.get(f"{stat}_pct", 0)) + s.get(stat, 0)
        return s.get(stat, 0)


@lru_cache(maxsize=None)
def _game(name: str) -> dict:
    from gtc import gamedata

    return gamedata.load_characters().get(name) or {}


def weapon_type(name: str) -> str:
    from gtc.kits import _WEAPON_ALIAS

    w = _game(name).get("weapon")
    return _WEAPON_ALIAS.get(w, w)


def scaling_stat(name: str) -> str:
    """The stat a character is built for: their own damage's scaling stat, or, for a support whose own damage is
    incidental, the stat their buffs, heals or shields scale with (Kazuha and Sucrose are built for EM). Default ATK."""
    from gtc.kits import kit

    k = kit(name) or {}
    scal = [sc for sc in k.get("scaling") or [] if sc.get("stat") in SANDS]
    support = (k.get("behavior") or {}).get("damage_ownership") in ("incidental", "none")
    if support:
        for sc in scal:
            if sc.get("for") in ("buff", "heal", "shield"):
                return sc["stat"]
    for sc in scal:
        if sc.get("for") == "damage":
            return sc["stat"]
    return "atk"


def _merge(*parts: dict) -> dict[str, float]:
    out: dict[str, float] = {}
    for p in parts:
        for k, v in p.items():
            out[k] = out.get(k, 0.0) + v
    return out


def house_artifacts(name: str) -> dict[str, float]:
    el = _game(name).get("element", "Physical")
    sc = scaling_stat(name)
    sands_key, sands_val = SANDS[sc]
    sub_key, sub_val = SCALING_SUB[sc]
    if sc == "em":  # EM builds go EM / EM / EM, as the community plays them
        return _merge({"hp": 4780.0, "atk": 311.0, "em": 3 * 187.0}, SUBS, {sub_key: sub_val})
    goblet = ("Physical", 0.583) if (_damage_element(name) == "Physical") else (el, 0.466)
    return _merge({"hp": 4780.0, "atk": 311.0, sands_key: sands_val, goblet[0]: goblet[1], "cr": 0.311},
                  SUBS, {sub_key: sub_val})


def _damage_element(name: str) -> str:
    from gtc.kits import kit

    return ((kit(name) or {}).get("behavior", {}).get("damage") or {}).get("element") or _game(name).get("element", "")


def meta_standard(name: str) -> Build:
    wname = FAVONIUS[weapon_type(name)]
    arts = house_artifacts(name)
    stats = _merge(D.character_stats(name, 90), D.weapon_stats(wname, 90), arts)
    return Build(name, "META_STANDARD", 90, 0, {"normal": 9, "skill": 9, "burst": 9}, wname, stats,
                 ["weapon passive (Favonius: energy only)", "no artifact set bonus by design"], arts)


GOOD = {"hp": "hp", "hp_": "hp_pct", "atk": "atk", "atk_": "atk_pct", "def": "def", "def_": "def_pct", "eleMas": "em",
        "critRate_": "cr", "critDMG_": "cd", "enerRech_": "er", "heal_": "heal", "physical_dmg_": "Physical"} | {
    f"{e.lower()}_dmg_": e for e in ("Pyro", "Hydro", "Electro", "Cryo", "Anemo", "Geo", "Dendro")}
FLAT_GOOD = {"hp", "atk", "def", "eleMas"}


def _good(key: str, value: float) -> tuple[str, float] | None:
    k = GOOD.get(key)
    if k is None:
        return None
    return k, (value if key in FLAT_GOOD else value / 100)


def current_account(c) -> Build:
    """CURRENT_ACCOUNT from a snapshot Character (gtc/snapshot.py)."""
    unmodelled = []
    try:
        w = D.weapon_stats(c.weapon.name, max(1, c.weapon.level))
    except KeyError:
        w = {}
        unmodelled.append(f"weapon {c.weapon.name} not in Amber: no weapon stats")
    unmodelled.append(f"weapon passive ({c.weapon.name} R{c.weapon.refinement})")
    arts: dict[str, float] = {}
    sets: dict[str, int] = {}
    for a in c.artifacts:
        for key, val in [(a.main_stat, a.main_value)] + [(s["key"], s["value"]) for s in a.substats]:
            g = _good(key, val)
            if g:
                arts[g[0]] = arts.get(g[0], 0.0) + g[1]
        sets[a.set_name] = sets.get(a.set_name, 0) + 1
    unmodelled += [f"{n} {p}-piece bonus" for n, p in sets.items() if p >= 2]
    stats = _merge(D.character_stats(c.name, c.level), w, arts)
    t = c.talents.effective
    return Build(c.name, "CURRENT_ACCOUNT", c.level, c.constellation, dict(t), c.weapon.name, stats, unmodelled, arts)


def account_ceiling(c, owned_weapons: list | None = None) -> Build:
    """ACCOUNT_CEILING: house artifacts, level 90, talents 9/9/9 (constellation talent bonuses kept), the player's
    constellation, and their best owned weapon of the right type by base ATK."""
    wtype = weapon_type(c.name)
    best, best_atk = c.weapon.name, -1.0
    for w in owned_weapons or [c.weapon]:
        try:
            st = D.weapon_stats(w.name, 90)
        except KeyError:
            continue
        typ = D.weapons_index().get(D.weapon_id(w.name) or "", {}).get("type")
        if typ == D.WEAPON_TYPE.get(wtype) and st.get("base_atk", 0) > best_atk:
            best, best_atk = w.name, st["base_atk"]
    try:
        ws = D.weapon_stats(best, 90)
    except KeyError:
        ws = {}
    arts = house_artifacts(c.name)
    stats = _merge(D.character_stats(c.name, 90), ws, arts)
    t = {"normal": 9 + c.talents.normal_bonus, "skill": 9 + c.talents.skill_bonus, "burst": 9 + c.talents.burst_bonus}
    return Build(c.name, "ACCOUNT_CEILING", 90, c.constellation, t, best, stats,
                 [f"weapon passive ({best})", "no artifact set bonus (house artifacts)"], arts)


def house_builds(lineup, er_added: dict | None = None) -> dict[str, Build]:
    """META_STANDARD for a lineup, with the Energy Recharge each character needs added (FM-7: the same builds the
    validation gcsim run uses)."""
    out = {}
    for m in lineup:
        b = meta_standard(m)
        extra = (er_added or {}).get(m)
        if extra:
            b.artifacts = {**b.artifacts, "er": b.artifacts.get("er", 0.0) + extra}
            b.stats = {**b.stats, "er": b.stats.get("er", 0.0) + extra}
        out[m] = b
    return out


def gcsim_lines(key: str, b: Build) -> list[str]:
    """gcsim build lines for a house build (validation runs): same level, talents, constellation, a Favonius
    weapon, no set, and the artifact stats."""
    from gtc.stats import GCSIM_KEYS  # noqa: F401  (vocabulary reference)

    gk = {"hp": "hp", "atk": "atk", "def": "def", "hp_pct": "hp%", "atk_pct": "atk%", "def_pct": "def%", "em": "em",
          "cr": "cr", "cd": "cd", "er": "er", "heal": "heal", "Physical": "phys%"} | {
        e: f"{e.lower()}%" for e in ("Pyro", "Hydro", "Electro", "Cryo", "Anemo", "Geo", "Dendro")}
    t = b.talents
    stats = " ".join(f"{gk[k]}={round(v, 4)}" for k, v in b.artifacts.items() if k in gk)
    return [f"{key} char lvl={b.level}/90 cons={b.constellation} talent={t['normal']},{t['skill']},{t['burst']};",
            f'{key} add weapon="{GCSIM_FAVONIUS[weapon_type(b.name)]}" refine=1 lvl=90/90;',
            f"{key} add stats {stats};"]
