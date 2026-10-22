"""Structured character kits, schema 3 (phase M1): the machine-readable mechanics the advisor reasons with.

One YAML file per character in knowledge/kits/, written from the official kit text (Project Amber cache) and
reviewed. Characters without a reviewed kit get a DERIVED kit (`derived_kit`) built from what the engine measured
(capability profiles from simulations), their placement roles and the composition conditions, every field marked
method "derived" and confidence "low". A kit describes a character; it never sets team power.

    schema: 3
    element: <Element>
    weapon: sword | claymore | polearm | bow | catalyst
    roles: [ROLES]
    behavior:
      field_time: high | medium | low | minimal | unknown      how much on-field time the kit needs to work
      on_field_damage: true | false | unknown                   does their own damage need them on field
      off_field: none | some | strong | unknown                 damage or application that persists off field
      driver: true | false
      damage_ownership: carry | sub_dps | incidental | none | unknown
      damage: {element, types: [DAMAGE_TYPES]}
      application: [{element, mode: on_field | off_field, strength: high | medium | low | unknown}]
      energy: {burst_cost: <int> | unknown, dependency: high | medium | low | unknown}
      sustain: {heal: none | low | medium | high | unknown, shield: none | weak | strong | unknown}
    scaling: [{stat: STATS, for: damage | buff | heal | shield, source: [DAMAGE_TYPES or talent]}]
    effects: [EFFECT]
      EFFECT: {kind: EFFECT_KINDS, target: TARGETS, affects: {elements: [...], damage_types: [...], reactions: [...]},
               amount: <number> | <text> | unknown, duration: <seconds> | <text> | unknown, stacking: <text> | unknown,
               conditions: [CONDITION], source: <talent name>}
    conditions: [CONDITION]           composition conditions on this character's own kit
      CONDITION: {type: CONDITION_TYPES, ..., text}
        party_element_count     elements, full (members needed for the full effect), levels (optional)
        party_elements_only     elements, each_required (true: at least one of each)
        party_elements_forbidden elements
        reaction_required       reactions (any of)
        aura_required           auras (any of)
        teammate_role_required  roles (any of)
        reaction_trigger_count  reaction, count
        character_state         state
        hexerei_count           min
        party_element_types     full (distinct element types in the party for the full effect; Lynette, Yun Jin)
    reactions: {owns: [], enables: [], requires: [], aura_supplied: [], aura_consumed: []}   reaction keys / auras
    sources: {id: description}
    provenance: {<field path> | "*": {source, span, confidence: high | medium | low, method: manual | derived |
                 llm_extracted | measured, reviewed: human | claude | pending}}

"unknown" is a valid value wherever a value is uncertain: nothing is guessed into a field.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from gtc import KNOWLEDGE_DIR

KITS_DIR = KNOWLEDGE_DIR / "kits"
SCHEMA = 3
UNKNOWN = "unknown"
ELEMENTS = ("Pyro", "Hydro", "Electro", "Cryo", "Anemo", "Geo", "Dendro")
WEAPONS = ("sword", "claymore", "polearm", "bow", "catalyst")
_WEAPON_ALIAS = {"sword_one_hand": "sword", "pole": "polearm"}   # game-data spellings
ROLES = ("on_field_carry", "off_field_sub_dps", "driver", "buffer", "debuffer", "healer", "shielder", "applier",
         "enabler", "swirl_support", "battery", "grouping")
LEVELS = ("high", "medium", "low", "minimal")
DAMAGE_TYPES = ("normal", "charged", "plunge", "skill", "burst", "summon", "reaction")
STATS = ("atk", "hp", "def", "em", "er", "crit")
EFFECT_KINDS = ("atk", "atk_pct", "flat_dmg", "dmg_bonus", "elemental_dmg_bonus", "crit_rate", "crit_dmg", "em",
                "reaction_bonus", "reaction_base", "reaction_conversion", "res_shred", "def_shred", "dmg_taken",
                "energy", "cooldown", "infusion", "interruption", "heal", "shield", "other")
TARGETS = ("self", "active", "party", "party_others", "enemy", "matching_element_members")
CONDITION_TYPES = ("party_element_count", "party_elements_only", "party_elements_forbidden", "reaction_required",
                   "aura_required", "teammate_role_required", "reaction_trigger_count", "character_state", "hexerei_count",
                   "party_element_types")
CONFIDENCE = ("high", "medium", "low")
METHODS = ("manual", "derived", "llm_extracted", "measured")
REVIEWED = ("human", "claude", "pending")
REQUIRED = ("schema", "element", "weapon", "roles", "behavior", "effects", "conditions", "reactions", "sources", "provenance")
DESCRIBED = ("roles", "behavior", "scaling", "effects", "conditions", "reactions")


def _ok(v, allowed) -> bool:
    return v == UNKNOWN or v in allowed


def _condition_errors(c, where: str) -> list[str]:
    from gtc.reactions import BY_KEY

    errs = []
    t = c.get("type")
    if t not in CONDITION_TYPES:
        return [f"{where}: condition type {t!r} not in the vocabulary"]
    if t in ("party_element_count", "party_elements_only", "party_elements_forbidden"):
        if not c.get("elements") or not set(c["elements"]) <= set(ELEMENTS):
            errs.append(f"{where}: {t} needs elements")
        if t == "party_element_count" and not isinstance(c.get("full"), int):
            errs.append(f"{where}: party_element_count needs an integer `full`")
    if t == "party_element_types" and not isinstance(c.get("full"), int):
        errs.append(f"{where}: party_element_types needs an integer `full`")
    if t == "reaction_required" and not (c.get("reactions") and all(r in BY_KEY for r in c["reactions"])):
        errs.append(f"{where}: reaction_required needs known reaction keys")
    if t == "teammate_role_required" and not (c.get("roles") and set(c["roles"]) <= set(ROLES)):
        errs.append(f"{where}: teammate_role_required needs roles")
    if not c.get("text"):
        errs.append(f"{where}: condition needs the kit text it paraphrases (`text`)")
    return errs


def validate(name: str, kit: dict) -> list[str]:
    """Every problem with a schema-3 kit (empty when valid)."""
    from gtc.reactions import BY_KEY

    errs = []
    if not isinstance(kit, dict):
        return [f"{name}: not a mapping"]
    errs += [f"missing `{f}`" for f in REQUIRED if f not in kit]
    if kit.get("schema") != SCHEMA:
        errs.append(f"schema must be {SCHEMA}")
    if kit.get("element") not in ELEMENTS:
        errs.append("element not in the vocabulary")
    if kit.get("weapon") not in WEAPONS:
        errs.append("weapon not in the vocabulary")
    for r in kit.get("roles") or []:
        if r not in ROLES:
            errs.append(f"role {r!r} not in the vocabulary")
    b = kit.get("behavior") or {}
    if not _ok(b.get("field_time"), LEVELS):
        errs.append("behavior.field_time must be high | medium | low | minimal | unknown")
    if b.get("on_field_damage") not in (True, False, UNKNOWN):
        errs.append("behavior.on_field_damage must be true, false or unknown")
    if not _ok(b.get("off_field"), ("none", "some", "strong")):
        errs.append("behavior.off_field must be none | some | strong | unknown")
    if b.get("driver") not in (True, False, UNKNOWN):
        errs.append("behavior.driver must be true, false or unknown")
    if not _ok(b.get("damage_ownership"), ("carry", "sub_dps", "incidental", "none")):
        errs.append("behavior.damage_ownership must be carry | sub_dps | incidental | none | unknown")
    dmg = b.get("damage") or {}
    if dmg and (dmg.get("element") not in ELEMENTS + ("Physical", UNKNOWN) or not all(_ok(t, DAMAGE_TYPES) for t in dmg.get("types") or [])):
        errs.append("behavior.damage needs an element and damage types from the vocabulary")
    for a in b.get("application") or []:
        if a.get("element") not in ELEMENTS or a.get("mode") not in ("on_field", "off_field") or not _ok(a.get("strength"), ("high", "medium", "low")):
            errs.append(f"behavior.application entry {a!r} invalid")
    e = b.get("energy") or {}
    if e and not _ok(e.get("dependency"), ("high", "medium", "low")):
        errs.append("behavior.energy.dependency invalid")
    s = b.get("sustain") or {}
    if not (_ok(s.get("heal"), ("none", "low", "medium", "high")) and _ok(s.get("shield"), ("none", "weak", "strong"))):
        errs.append("behavior.sustain needs heal and shield levels")
    for i, sc in enumerate(kit.get("scaling") or []):
        if not _ok(sc.get("stat"), STATS) or sc.get("for") not in ("damage", "buff", "heal", "shield", UNKNOWN):
            errs.append(f"scaling {i + 1} invalid")
    for i, ef in enumerate(kit.get("effects") or []):
        w = f"effect {i + 1}"
        if ef.get("kind") not in EFFECT_KINDS:
            errs.append(f"{w}: kind {ef.get('kind')!r} not in the vocabulary")
        if ef.get("target") not in TARGETS:
            errs.append(f"{w}: target {ef.get('target')!r} not in the vocabulary")
        aff = ef.get("affects") or {}
        if not set(aff.get("elements") or []) <= set(ELEMENTS + ("Physical", "all")):
            errs.append(f"{w}: affects.elements invalid")
        if not all(_ok(t, DAMAGE_TYPES + ("all",)) for t in aff.get("damage_types") or []):
            errs.append(f"{w}: affects.damage_types invalid")
        if not all(r in BY_KEY or r == "all" for r in aff.get("reactions") or []):
            errs.append(f"{w}: affects.reactions must be reaction keys")
        if "amount" not in ef:
            errs.append(f"{w}: amount missing (use unknown)")
        for c in ef.get("conditions") or []:
            errs += _condition_errors(c, w)
        if not ef.get("source"):
            errs.append(f"{w}: needs its source talent")
    for i, c in enumerate(kit.get("conditions") or []):
        errs += _condition_errors(c, f"condition {i + 1}")
    rx = kit.get("reactions") or {}
    for part in ("owns", "enables", "requires"):
        for r in rx.get(part) or []:
            if r not in BY_KEY:
                errs.append(f"reactions.{part}: unknown reaction {r!r}")
    sources = kit.get("sources") or {}
    prov = kit.get("provenance") or {}
    default = prov.get("*")
    for f in DESCRIBED:
        p = prov.get(f, default)
        if p is None:
            errs.append(f"no provenance for `{f}`")
            continue
        if p.get("source") not in sources:
            errs.append(f"provenance of `{f}`: source {p.get('source')!r} not in sources")
        if p.get("confidence") not in CONFIDENCE or p.get("method") not in METHODS or p.get("reviewed") not in REVIEWED:
            errs.append(f"provenance of `{f}`: needs confidence, method and reviewed from the vocabulary")
    return [f"{name}: {x}" for x in errs]


_KITS: dict | None = None


def reviewed_kits() -> dict:
    """knowledge/kits/*.yaml (files starting with "_" skipped)."""
    global _KITS
    if _KITS is None:
        _KITS = {}
        if KITS_DIR.exists():
            for path in sorted(KITS_DIR.glob("*.yaml")):
                if not path.name.startswith("_"):
                    _KITS.update(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
    return _KITS


_DERIVED: dict = {}


def derived_kit(name: str) -> dict | None:
    """A schema-3 kit derived from what the engine measured, for characters without a reviewed kit. Behaviour comes
    from the measured capability profile (field share, damage share, application per element, off-field share,
    healing, shield rate), roles from the placement roles, conditions from knowledge/kit_conditions.yaml. Effects
    are not derivable from measurements, so they are left empty ("unknown"), and every field says method derived."""
    if name in _DERIVED:
        return _DERIVED[name]
    from gtc import gamedata
    from gtc.capabilities import load as load_caps
    from gtc.knowledge import load as load_kb

    g = gamedata.load_characters().get(name)
    if g is None:
        return None
    caps = load_caps()
    c = caps.get(name)
    info = load_kb().characters.get(name)
    roles = {r: q for r, q in (info.roles if info else {}).items()}
    out_roles = []
    if roles.get("buffer_anemo", 0) >= 2:
        out_roles += ["swirl_support", "grouping"]
    if roles.get("healer", 0) >= 3:
        out_roles.append("healer")
    if roles.get("shield", 0) >= 3:
        out_roles.append("shielder")
    if any(roles.get(r, 0) >= 3 for r in ("buffer_atk", "buffer_general", "buffer_cryo", "em_share", "buffer_lunar")):
        out_roles.append("buffer")
    if roles.get("offfield_app", 0) >= 3:
        out_roles.append("applier")
    if roles.get("res_shred", 0) >= 3 or roles.get("def_shred", 0) >= 3:
        out_roles.append("debuffer")
    behavior = {"field_time": UNKNOWN, "on_field_damage": UNKNOWN, "off_field": UNKNOWN, "driver": UNKNOWN,
                "damage_ownership": UNKNOWN, "damage": {"element": g.get("element"), "types": []},
                "application": [], "energy": {"burst_cost": UNKNOWN, "dependency": UNKNOWN},
                "sustain": {"heal": "medium" if roles.get("healer", 0) >= 3 else UNKNOWN,
                            "shield": "strong" if roles.get("shield", 0) >= 4 else UNKNOWN}}
    if c is not None and c.n:
        fs, ds = c.field_share, c.damage_share
        behavior["field_time"] = "high" if fs >= 0.45 else "medium" if fs >= 0.25 else "low" if fs >= 0.12 else "minimal"
        behavior["damage_ownership"] = "carry" if ds >= 0.45 else "sub_dps" if ds >= 0.2 else "incidental" if ds >= 0.05 else "none"
        behavior["on_field_damage"] = bool(ds >= 0.3 and fs >= 0.35 and c.offfield_share < 0.5)
        behavior["off_field"] = "strong" if c.offfield_share >= 0.6 and ds >= 0.15 else "some" if c.offfield_share >= 0.3 else "none"
        behavior["driver"] = bool(fs >= 0.4 and ds < 0.2)
        for k, v in (c.apply or {}).items():
            el, _, mode = k.partition(".")
            if el in ELEMENTS and v >= 0.5:
                behavior["application"].append({"element": el, "mode": "on_field" if mode == "on" else "off_field",
                                                 "strength": "high" if v >= 3 else "medium" if v >= 1.5 else "low"})
        if behavior["damage_ownership"] == "carry" and behavior["on_field_damage"]:
            out_roles.insert(0, "on_field_carry")
        elif behavior["damage_ownership"] in ("carry", "sub_dps") and behavior["off_field"] != "none":
            out_roles.insert(0, "off_field_sub_dps")
        if behavior["driver"]:
            out_roles.append("driver")
    from gtc.kit_conditions import legacy_conditions

    kit = {"schema": SCHEMA, "element": g.get("element"), "weapon": _WEAPON_ALIAS.get(g.get("weapon"), g.get("weapon")), "roles": sorted(set(out_roles)),
           "behavior": behavior, "scaling": [], "effects": [], "conditions": legacy_conditions(name),
           "reactions": {"owns": [], "enables": [], "requires": [], "aura_supplied": [], "aura_consumed": []},
           "sources": {"engine": "Measured capability profile and placement roles (gtc/capabilities.py, knowledge)"},
           "provenance": {"*": {"source": "engine", "span": "capabilities.json", "confidence": "low", "method": "derived",
                                "reviewed": "pending"}},
           "derived": True}
    _DERIVED[name] = kit
    return kit


_COMPILED: dict | None = None


def compiled_kits() -> dict:
    """knowledge/kits_compiled/*.yaml: LLM-extracted kits that passed gtc/kitcompile.py's checks, not human-reviewed."""
    global _COMPILED
    if _COMPILED is None:
        _COMPILED = {}
        d = KNOWLEDGE_DIR / "kits_compiled"
        if d.exists():
            for path in sorted(d.glob("*.yaml")):
                if not path.name.startswith("_"):
                    _COMPILED.update(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
    return _COMPILED


def kit(name: str) -> dict | None:
    """The reviewed kit when one exists, else the compiled one (LLM-extracted, checked), else the derived one."""
    return reviewed_kits().get(name) or compiled_kits().get(name) or derived_kit(name)
