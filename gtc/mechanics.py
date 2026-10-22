"""Universal game mechanics (phase M2): the one deterministic facts layer the mechanical reasoner reads.

It does not restate what already has an authoritative home; it re-exports it:
  reactions, their classes, elements, auras, ownership     gtc/reactions.py (REACTIONS, BY_KEY, reaction_between,
                                                          mechanic_elements, mechanic_name)
  RES and DEF multipliers, crit, EM curves                 gtc/tc/formulas.py (res_mult, def_mult, ...)
and adds the concepts the reasoner needs that had no home:
  reaction categories      amplifying (multiplies the trigger hit), additive (catalyze: flat damage on the trigger
                           hit), transformative and lunar (own reaction damage), control (Freeze, Quicken: a state
                           other reactions or buffs use), crystallize (a shield)
  aura states              Frozen (Cryo + Hydro), Quicken (Electro + Dendro): states a reaction keeps on the enemy
  aura consumption         a third element that reacts with the auras a mechanic relies on removes them (Pyro in a
                           Freeze team melts and vaporises its Cryo and Hydro auras); Anemo and Geo only swirl or
                           crystallise them
  damage-bonus categories  how a buff enters the damage formula (see DAMAGE_BONUS)
  buff applicability       a buff reaches a damage instance only if its target, element and damage-type filters
                           match the character dealing it (`effect_applies`)
  field time               how much on-field time a kit needs (high / medium / low / minimal): only one character
                           is on field at a time, so two kits whose own damage needs field time compete for it
  energy dependency        how much a kit relies on its Burst being available every rotation
"""
from __future__ import annotations

from itertools import combinations

from gtc.reactions import BY_KEY, ELEMENTS, REACTIONS, mechanic_elements, mechanic_name, reaction_between  # noqa: F401
from gtc.tc.formulas import crit_avg, def_mult, res_mult  # noqa: F401

CATEGORY = {"amplifying": "amplifying", "catalyze": "additive", "transformative": "transformative",
            "lunar": "transformative", "control": "control", "crystallize": "crystallize"}
AURA_STATES = {"freeze": ("Cryo", "Hydro"), "quicken": ("Electro", "Dendro")}
GROUPING_ELEMENTS = ("Anemo", "Geo")  # react with auras without removing a mechanic (Swirl spreads, Crystallize shields)

DAMAGE_BONUS = {
    "atk": "flat ATK added to the attack stat",
    "atk_pct": "percentage ATK",
    "flat_dmg": "flat damage added to the base damage of matching hits (Shenhe's Icy Quill)",
    "dmg_bonus": "DMG% bonus, additive with other DMG% of the same hit",
    "elemental_dmg_bonus": "elemental DMG% bonus for one element",
    "crit_rate": "CRIT Rate", "crit_dmg": "CRIT DMG", "em": "Elemental Mastery",
    "reaction_bonus": "reaction DMG bonus", "reaction_base": "reaction base damage increase",
    "reaction_conversion": "turns one reaction into another (Lunar, Stellar)",
    "res_shred": "lowers enemy RES (res_mult)", "def_shred": "lowers enemy DEF (def_mult)",
    "dmg_taken": "enemy takes more damage, a separate multiplier (Mona's Omen)",
}
FIELD_TIME = {"high": 0.45, "medium": 0.25, "low": 0.1, "minimal": 0.03}  # rough share of a rotation the kit needs


def reaction_of(key: str):
    """The Reaction for a reaction key or a calculator channel (electro_charged, lunar_charged, swirl)."""
    if key in BY_KEY:
        return BY_KEY[key]
    return next((r for r in REACTIONS if (r.channel or r.key) == key), None)


def conditioned_buffs() -> dict[str, str]:
    """{character: reaction} for kits whose buffs need a reaction (reviewed kits' reactions.requires): a team built
    around such a buff depends on the reaction even when its own damage is small (Chevreuse needs Overloaded)."""
    from gtc.kits import reviewed_kits

    return {n: k["reactions"]["requires"][0] for n, k in sorted(reviewed_kits().items())
            if (k.get("reactions") or {}).get("requires")}


def element_of(name: str) -> str | None:
    from gtc.kit_conditions import _element

    return _element(name)


def category(reaction: str) -> str | None:
    r = BY_KEY.get(reaction)
    return CATEGORY.get(r.cls) if r else None


def possible_reactions(elements) -> set[str]:
    """Reaction keys any two of these elements can produce."""
    out = set()
    for a, b in combinations(sorted(set(elements)), 2):
        for x, y in ((a, b), (b, a)):
            r = reaction_between(x, y)
            if r is not None:
                out.add(r.key)
    return out


def consumes_auras(element: str, mechanic: str) -> list[str]:
    """The auras of `mechanic` that `element` reacts with and removes (empty for its own elements, Anemo and Geo)."""
    need = set(mechanic_elements(mechanic))
    if element in need or element in GROUPING_ELEMENTS:
        return []
    return sorted(e for e in need if reaction_between(element, e) is not None or reaction_between(e, element) is not None)


def effect_applies(effect: dict, receiver_damage: dict, receiver_is_active: bool = True, same: bool = False) -> bool:
    """Does a buff reach a character's damage? Target (self / active / party / party_others / enemy / matching
    element), element filter and damage-type filter must all match. `receiver_damage` is {element, types}."""
    target = effect.get("target")
    if target == "self" and not same:
        return False
    if target == "party_others" and same:
        return False
    if target == "active" and not receiver_is_active:
        return False
    aff = effect.get("affects") or {}
    els = aff.get("elements") or ["all"]
    if "all" not in els and receiver_damage.get("element") not in els:
        return False
    types = aff.get("damage_types") or ["all"]
    if "all" not in types and not set(types) & set(receiver_damage.get("types") or []):
        return False
    return True
