"""Elemental reactions: one table of game facts that every module reads.

Before phase 6 the same facts lived in seven places (synergy's TRANSFORMATIVE, CATALYZE, AMP_AURA,
REACTION_AURAS and CORE_REACTIONS; the theory guard's source names, supported channels and unsupported element
pairs; derive's reaction names per element pair and its "helper" elements; report's reacting elements; the
calculator's Lunar multipliers). They are now derived from REACTIONS below, so a fact changes in one place.
tests/test_reactions.py pins the derived views to their previous literal values.

Facts only: classes, elements, the auras a reaction consumes, gcsim's coefficients, who owns the damage, and
whether the theorycraft calculator models it. Judgments (which partner a carry is usually built with, how much
credit an aura's owner gets) stay with the modules that make them.

Classes:
  amplifying     Vaporize, Melt: multiply the triggering hit
  catalyze       Aggravate, Spread: add flat damage to the triggering hit while Quicken is present
  transformative own reaction damage (Overloaded, Electro-Charged, Superconduct, Shatter, Burning, Bloom,
                 Hyperbloom, Burgeon, Swirl)
  lunar          Lunar reactions (Lunar-Charged, Lunar-Bloom, Lunar-Crystallize): reaction damage from contributors
  control        Freeze, Quicken: no damage of their own; an aura other reactions or buffs use
  crystallize    a shield, no damage

Ownership (who the damage is credited to before enablement):
  trigger        the character whose hit triggered it
  core_creator   Hyperbloom and Burgeon damage belongs to the trigger; enablement goes to whoever made the Dendro core
  contributors   Lunar reactions: shared among the characters gcsim lists as contributors
  none           no damage (control, crystallize)
"""
from __future__ import annotations

from dataclasses import dataclass

ELEMENTS = ("Pyro", "Hydro", "Electro", "Cryo", "Anemo", "Geo", "Dendro")


@dataclass(frozen=True)
class Reaction:
    key: str                 # gcsim's ability name for the reaction damage, or the amp/cata tag
    name: str                # display name
    cls: str                 # amplifying | catalyze | transformative | lunar | control | crystallize
    elements: tuple          # the element pair (or element) that produces it
    auras: tuple = ()        # auras it consumes, whose appliers enable it (synergy enablement)
    coefficient: float = 0.0  # gcsim multiplier on the level base (transformative, catalyze, Lunar)
    ownership: str = "trigger"
    calculator: bool = False  # the theorycraft calculator models this damage channel (gtc/tc)
    channel: str = ""         # theory-guard channel name; defaults to the key
    family: str = ""          # the reaction family a team is named after (derive), e.g. Quicken for Aggravate


REACTIONS: tuple[Reaction, ...] = (
    # amplifying: the aura is the OTHER element (Pyro on Hydro is Vaporize with a Hydro aura)
    Reaction("vaporize", "Vaporize", "amplifying", ("Pyro", "Hydro"), family="Vaporize"),
    Reaction("melt", "Melt", "amplifying", ("Pyro", "Cryo"), family="Melt"),
    # catalyze
    Reaction("aggravate", "Aggravate", "catalyze", ("Electro", "Dendro"), ("quicken",), 1.15, family="Quicken"),
    Reaction("spread", "Spread", "catalyze", ("Dendro", "Electro"), ("quicken",), 1.25, family="Quicken"),
    # transformative
    Reaction("overloaded", "Overloaded", "transformative", ("Pyro", "Electro"), ("pyro", "electro"), 2.75, family="Overloaded"),
    Reaction("overload", "Overloaded", "transformative", ("Pyro", "Electro"), ("pyro", "electro"), 2.75, channel="overloaded",
             family="Overloaded"),
    Reaction("electrocharged", "Electro-Charged", "transformative", ("Hydro", "Electro"), ("hydro", "electro"), 2.0,
             channel="electro_charged", family="Electro-Charged"),
    Reaction("superconduct", "Superconduct", "transformative", ("Cryo", "Electro"), ("cryo", "electro"), 1.5, family="Superconduct"),
    Reaction("shatter", "Shatter", "transformative", ("Cryo", "Hydro"), ("frozen",), 3.0),
    Reaction("burning", "Burning", "transformative", ("Pyro", "Dendro"), ("pyro", "dendro", "burning"), 0.25, family="Burning"),
    Reaction("bloom", "Bloom", "transformative", ("Hydro", "Dendro"), ("hydro", "dendro"), 2.0, family="Bloom"),
    Reaction("hyperbloom", "Hyperbloom", "transformative", ("Electro", "Dendro"), (), 3.0, ownership="core_creator"),
    Reaction("burgeon", "Burgeon", "transformative", ("Pyro", "Dendro"), (), 3.0, ownership="core_creator"),
    Reaction("swirl-pyro", "Swirl", "transformative", ("Anemo", "Pyro"), ("pyro",), 0.6, calculator=True, channel="swirl"),
    Reaction("swirl-hydro", "Swirl", "transformative", ("Anemo", "Hydro"), ("hydro",), 0.6, calculator=True, channel="swirl"),
    Reaction("swirl-electro", "Swirl", "transformative", ("Anemo", "Electro"), ("electro",), 0.6, calculator=True, channel="swirl"),
    Reaction("swirl-cryo", "Swirl", "transformative", ("Anemo", "Cryo"), ("cryo",), 0.6, calculator=True, channel="swirl"),
    # Lunar
    Reaction("lunarcharged", "Lunar-Charged", "lunar", ("Hydro", "Electro"), (), 3.0, ownership="contributors", calculator=True,
             channel="lunar_charged"),
    Reaction("lunarcrystallize", "Lunar-Crystallize", "lunar", ("Geo", "Hydro"), (), 1.6, ownership="contributors",
             channel="lunar_crystallize"),
    Reaction("lunarbloom", "Lunar-Bloom", "lunar", ("Hydro", "Dendro"), (), 0.0, ownership="contributors", channel="lunar_bloom"),
    # control and crystallize: no damage of their own
    Reaction("freeze", "Freeze", "control", ("Cryo", "Hydro"), ownership="none", family="Freeze"),
    Reaction("quicken", "Quicken", "control", ("Electro", "Dendro"), ownership="none", family="Quicken"),
    Reaction("crystallize", "Crystallize", "crystallize", ("Geo",), ownership="none"),
)
BY_KEY = {r.key: r for r in REACTIONS}


def channel_of(r: Reaction) -> str:
    return r.channel or r.key


# ---------- views used by the engine (pinned by tests/test_reactions.py) ----------

# Transformative multipliers by gcsim ability name (synergy solves the reaction bonus from them).
TRANSFORMATIVE = {r.key: r.coefficient for r in REACTIONS if r.cls == "transformative"}
CATALYZE = {r.key: r.coefficient for r in REACTIONS if r.cls == "catalyze"}
# Lunar multipliers by calculator channel.
LUNAR_MULT = {channel_of(r): r.coefficient for r in REACTIONS if r.cls == "lunar" and r.coefficient}
# Reactions whose enablement goes to the Dendro core's creator.
CORE_REACTIONS = {r.key for r in REACTIONS if r.ownership == "core_creator"}
# Auras a transformative reaction consumes (its appliers enable it); Hyperbloom and Burgeon use cores instead.
REACTION_AURAS = {r.key: r.auras for r in REACTIONS if r.cls == "transformative" and r.auras}
# Amplifying: (reaction, triggering element) -> the aura that was consumed.
AMP_AURA = {(r.key, trig.lower()): aura.lower() for r in REACTIONS if r.cls == "amplifying"
            for trig, aura in (r.elements, r.elements[::-1])}
# gcsim damage source tags and names -> theory-guard channel.
AMPLIFYING_SUFFIXES = {r.key: r.key for r in REACTIONS if r.cls == "amplifying"}
CATALYZE_SUFFIXES = {r.key: r.key for r in REACTIONS if r.cls == "catalyze"}
REACTION_SOURCES = {r.key: channel_of(r) for r in REACTIONS
                    if r.cls in ("transformative", "lunar") and not r.key.startswith("swirl-")}
SUPPORTED_CHANNELS = {"direct"} | {channel_of(r) for r in REACTIONS if r.calculator}
# Elements that only react as helpers (Swirl, Crystallize): they never define a reaction family.
HELPERS = {e for e in ELEMENTS if all(r.cls in ("crystallize",) or r.channel == "swirl" or r.cls == "lunar"
                                      for r in REACTIONS if e in r.elements)}
# Elements that hold an aura and react with each other.
REACTING = tuple(e for e in ELEMENTS if e not in HELPERS)


def reaction_between(a: str, b: str) -> Reaction | None:
    """The family-defining reaction of two reacting elements (Pyro + Hydro -> Vaporize, Electro + Dendro -> Quicken)."""
    pair = {a, b}
    return next((r for r in REACTIONS if r.family and set(r.elements) == pair), None)


# Element pairs that react through a channel the calculator does not model. Hydro + Electro is left out: in
# Lunar teams it becomes Lunar-Charged, which is modelled (theory_guard checks that case on its own).
UNSUPPORTED_PAIRS = {frozenset((a, b)) for i, a in enumerate(REACTING) for b in REACTING[i + 1:]
                     if {a, b} != {"Hydro", "Electro"} and reaction_between(a, b) is not None
                     and not reaction_between(a, b).calculator}


def is_reaction_damage(abil: str) -> bool:
    """A damage event that is reaction damage (transformative, Lunar or catalyze), by gcsim ability name."""
    r = BY_KEY.get(abil)
    return r is not None and r.cls in ("transformative", "lunar", "catalyze")


def kind_of(abil: str) -> str:
    """Grouped name for measurements: 'swirl' for every Swirl element, 'overloaded' for both spellings."""
    r = BY_KEY.get(abil)
    if r is None:
        return abil
    return channel_of(r) if r.channel else r.key


def mechanic_name(key: str) -> str:
    """Display name of a mechanic key (a reaction key or channel such as electro_charged, swirl, freeze)."""
    for r in REACTIONS:
        if key in (r.key, channel_of(r)):
            return r.name
    return key.replace("_", " ").title()


def mechanic_elements(key: str) -> tuple:
    """The elements a mechanic needs in the team (for gating predicted signals)."""
    for r in REACTIONS:
        if key in (r.key, channel_of(r)):
            if r.channel == "swirl":
                return ("Anemo",)
            if r.ownership == "core_creator":  # Hyperbloom and Burgeon act on Bloom cores: Hydro and Dendro too
                return tuple(dict.fromkeys(("Hydro", "Dendro") + r.elements))
            return r.elements
    return ()
