"""Genshin damage formulas, taken from gcsim's source (pkg/enemy/damage.go, pkg/core/combat/reaction.go).

All functions return multipliers or damage for one hit. Crit is applied as an average:
1 + CRIT Rate x CRIT DMG, with CRIT Rate clamped to [0, 1].
"""
from __future__ import annotations

import json
from functools import lru_cache

from gtc import KNOWLEDGE_DIR

ENEMY_LEVEL = 100  # the gcsim database standard target
ENEMY_RES = 0.10


@lru_cache(maxsize=1)
def _level_base() -> list[float]:
    return json.loads((KNOWLEDGE_DIR / "generated" / "reaction_level_base.json").read_text(encoding="utf-8"))


def reaction_base(level: int) -> float:
    """Level multiplier used by every transformative and Lunar reaction. 1446.85 at level 90."""
    table = _level_base()
    return table[max(0, min(level - 1, len(table) - 1))]


def res_mult(res: float) -> float:
    if res < 0:
        return 1 - res / 2
    if res < 0.75:
        return 1 - res
    return 1 / (4 * res + 1)


def def_mult(char_level: int = 90, enemy_level: int = ENEMY_LEVEL, def_shred: float = 0.0, def_ignore: float = 0.0) -> float:
    shred = min(def_shred, 0.9)
    return (char_level + 100) / ((char_level + 100) + (enemy_level + 100) * (1 - shred) * (1 - min(def_ignore, 1.0)))


def crit_avg(cr: float, cd: float) -> float:
    return 1 + max(0.0, min(cr, 1.0)) * cd


def em_lunar(em: float) -> float:
    """EM term for Lunar reactions and direct Lunar damage: 6 EM / (2000 + EM)."""
    return 6 * em / (2000 + em)


def em_transformative(em: float) -> float:
    return 16 * em / (2000 + em)


def em_amplifying(em: float) -> float:
    return 2.78 * em / (1400 + em)


def em_additive(em: float) -> float:
    return 5 * em / (1200 + em)


from gtc.reactions import LUNAR_MULT  # noqa: E402  (Lunar multipliers, gtc/reactions.py)


def direct_hit(motion: float, stat: float, dmg_bonus: float, cr: float, cd: float, res: float,
               char_level: int = 90, def_shred: float = 0.0, base_bonus: float = 0.0) -> float:
    """Ordinary talent hit: motion value x scaling stat x (1 + DMG%) x DEF x RES x crit."""
    return motion * stat * (1 + base_bonus) * (1 + dmg_bonus) * def_mult(char_level, def_shred=def_shred) * res_mult(res) * crit_avg(cr, cd)


def lunar_direct_hit(motion: float, stat: float, em: float, react_bonus: float, base_bonus: float,
                     cr: float, cd: float, res: float, reaction: str = "lunar_charged") -> float:
    """Direct Lunar damage (Flins's special Burst, Ineffa's A1): no DMG%, ignores DEF, can crit."""
    return motion * stat * (1 + base_bonus) * LUNAR_MULT[reaction] * (1 + em_lunar(em) + react_bonus) * res_mult(res) * crit_avg(cr, cd)


def lunar_reaction_hit(level: int, em: float, react_bonus: float, base_bonus: float, cr: float, cd: float, res: float,
                       reaction: str = "lunar_charged") -> float:
    """One contributor's share of a Lunar-Charged reaction hit, before the 60/30/5/5 contributor weights."""
    return LUNAR_MULT[reaction] * (1 + em_lunar(em) + react_bonus) * reaction_base(level) * (1 + base_bonus) * res_mult(res) * crit_avg(cr, cd)


LUNAR_CONTRIBUTOR_WEIGHTS = [0.6, 0.3, 0.05, 0.05]


def transformative_hit(level: int, coefficient: float, em: float, react_bonus: float, res: float) -> float:
    """Swirl (coefficient 0.6), Overloaded (2.75), etc. No crit, no DEF."""
    return coefficient * reaction_base(level) * (1 + em_transformative(em) + react_bonus) * res_mult(res)
