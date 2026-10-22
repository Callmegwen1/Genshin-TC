"""One stat vocabulary for the whole engine: the GOOD keys used by Genshin Optimizer and scanners.

Percent stats are stored in percent units (46.6 means 46.6%), as in GOOD.
"""
from __future__ import annotations

import re

# HoYoLAB property_type id to GOOD key.
HOYOLAB_IDS = {
    2: "hp", 3: "hp_", 5: "atk", 6: "atk_", 8: "def", 9: "def_", 20: "critRate_", 22: "critDMG_",
    23: "enerRech_", 26: "heal_", 28: "eleMas", 30: "physical_dmg_", 40: "pyro_dmg_", 41: "electro_dmg_",
    42: "hydro_dmg_", 43: "dendro_dmg_", 44: "anemo_dmg_", 45: "geo_dmg_", 46: "cryo_dmg_",
}

LABELS = {
    "hp": "Flat HP", "hp_": "HP%", "atk": "Flat ATK", "atk_": "ATK%", "def": "Flat DEF", "def_": "DEF%",
    "critRate_": "CRIT Rate", "critDMG_": "CRIT DMG", "enerRech_": "Energy Recharge", "heal_": "Healing Bonus",
    "eleMas": "Elemental Mastery", "physical_dmg_": "Physical DMG", "pyro_dmg_": "Pyro DMG", "electro_dmg_": "Electro DMG",
    "hydro_dmg_": "Hydro DMG", "dendro_dmg_": "Dendro DMG", "anemo_dmg_": "Anemo DMG", "geo_dmg_": "Geo DMG",
    "cryo_dmg_": "Cryo DMG",
}

# Words guides use for stats, mapped to GOOD keys. Longest phrases are matched first.
GUIDE_WORDS = {
    "crit rate": "critRate_", "crit dmg": "critDMG_", "crit": "crit", "energy recharge": "enerRech_", "er": "enerRech_",
    "elemental mastery": "eleMas", "em": "eleMas", "atk%": "atk_", "atk": "atk_", "hp%": "hp_", "hp": "hp_",
    "def%": "def_", "def": "def_", "healing bonus": "heal_", "healing": "heal_", "flat atk": "atk", "flat hp": "hp",
    "physical dmg": "physical_dmg_", "pyro dmg": "pyro_dmg_", "electro dmg": "electro_dmg_", "hydro dmg": "hydro_dmg_",
    "dendro dmg": "dendro_dmg_", "anemo dmg": "anemo_dmg_", "geo dmg": "geo_dmg_", "cryo dmg": "cryo_dmg_",
    "elemental dmg bonus": "elemental_dmg_", "elemental dmg": "elemental_dmg_", "dmg bonus": "elemental_dmg_",
}

# Prydwen's usage-statistics stat names.
PRYDWEN_KEYS = {
    "atk_": "atk_", "hp_": "hp_", "def_": "def_", "ele_mas": "eleMas", "ener_rech_": "enerRech_", "crit_rate_": "critRate_",
    "crit_dmg_": "critDMG_", "heal_": "heal_", "physical_dmg_": "physical_dmg_",
} | {f"{e}_dmg_": f"{e}_dmg_" for e in ("pyro", "electro", "hydro", "dendro", "anemo", "geo", "cryo")}

# gcsim `add stats` keys. gcsim uses fractions for percent stats.
GCSIM_KEYS = {
    "hp": "hp", "hp_": "hp%", "atk": "atk", "atk_": "atk%", "def": "def", "def_": "def%", "critRate_": "cr",
    "critDMG_": "cd", "enerRech_": "er", "eleMas": "em", "heal_": "heal", "physical_dmg_": "phys%",
} | {f"{e}_dmg_": f"{e}%" for e in ("pyro", "electro", "hydro", "dendro", "anemo", "geo", "cryo")}

FLAT_KEYS = {"hp", "atk", "def", "eleMas"}

# Average value of one 5-star substat roll, used to count rolls when a source does not give them.
ROLL_VALUE = {"critRate_": 3.3, "critDMG_": 6.6, "atk_": 4.95, "hp_": 4.95, "def_": 6.2, "enerRech_": 5.5, "eleMas": 19.8,
              "atk": 16.5, "hp": 254, "def": 19.7}


def to_gcsim(key: str, value: float) -> tuple[str, float] | None:
    gk = GCSIM_KEYS.get(key)
    if gk is None:
        return None
    return gk, (value if key in FLAT_KEYS else value / 100)


def element_dmg_key(element: str) -> str:
    return f"{element.lower()}_dmg_"


def crit_value(substats: list[dict]) -> float:
    """CRIT Value: 2 x CRIT Rate + CRIT DMG, from substats only. A common shorthand for artifact quality."""
    cr = sum(s["value"] for s in substats if s["key"] == "critRate_")
    cd = sum(s["value"] for s in substats if s["key"] == "critDMG_")
    return 2 * cr + cd


def _stat_token(token: str) -> list[str]:
    t = re.sub(r"\(.*?\)", "", token.lower()).replace("bonus", "").strip(" .:")
    for phrase in sorted(GUIDE_WORDS, key=len, reverse=True):
        if re.search(rf"(^|[^a-z]){re.escape(phrase)}($|[^a-z])", t):
            key = GUIDE_WORDS[phrase]
            return ["critRate_", "critDMG_"] if key == "crit" else [key]
    return []


def parse_priority(text: str) -> list[list[str]]:
    """'ER (until requirement) > CRIT > ATK% > EM' becomes [[enerRech_], [critRate_, critDMG_], [atk_], [eleMas]].
    '>' separates tiers; '/' and '=' join equals. Unknown words are dropped."""
    tiers = []
    for tier in re.split(r"\s*(?:>|≥|&gt;)\s*", text):
        keys = []
        for tok in re.split(r"\s*(?:/|=|,)\s*", tier):
            for k in _stat_token(tok):
                if k not in keys:
                    keys.append(k)
        if keys:
            tiers.append(keys)
    return tiers
