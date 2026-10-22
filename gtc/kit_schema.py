"""Provisional kit schema v2 (phase 13): the deterministic description of a character with no simulations.

One YAML file per character in knowledge/kits_provisional/. Every field is in the normalised capability terms of
gtc/capabilities.py and gtc/reactions.py, so a provisional character enters structure, coverage, identity and the
pair model's neighbourhood like any other. Phase 14's offline compiler will write this same schema, so every field
carries provenance: which source it comes from, how confident the writer is, and how it was produced.

    schema: 2
    provisional: true
    role: carry | sub_dps | support         how the character is valued (gtc/provisional.py)
    element, weapon
    analogue: <simulated character>          the closest measured role: stands in for the character in the pair model
    field: {behaviour: on_field | off_field | quickswap, share: [lo, hi]}
    personal_damage: {tier: high | medium | low | minimal, share: [lo, hi]}   share of team damage
    application: {"<Element>.on" | "<Element>.off": [lo, hi]}                 applications per 10 s
    buffs: [{kind, target, condition, text}]  kind from BUFF_KINDS; target from TARGETS or "element:<E>"
    sustain: {heal: none | low | medium | high, shield: none | weak | strong}
    reactions: {owns: [reaction keys it triggers for its own damage], enables: [reaction keys its aura or
               application makes possible], converts: {reaction key: new reaction name}}
    preferred_systems: [reaction keys]       the team mechanics the kit is built around
    restrictions: [{rule, ..., why}]          machine-checked; a lineup that breaks one gets no number:
                   needs_element  {any_of: [elements]}   a teammate (not the character) of one of these elements
                   needs_count    {element, min}         at least `min` members of the element, the character included
    synergies: [{with: <character> | "element:<E>" | "system:<reaction key>", why}]   explanation only
    expected_archetypes / roles               placement into candidate teams (generators, never power)
    sources: {id: description}
    provenance: {field: {source: <id>, confidence: high | medium | low, method: manual | llm_extracted | derived}}
               every described field needs an entry; "*" sets the default for the rest

Ranges are [low, high] where the writer is unsure; the midpoint stands in until simulations exist.
"""
from __future__ import annotations

from gtc.reactions import BY_KEY, ELEMENTS

SCHEMA_VERSION = 2
ROLES = ("carry", "sub_dps", "support")
BEHAVIOURS = ("on_field", "off_field", "quickswap")
DAMAGE_TIERS = ("high", "medium", "low", "minimal")
HEAL = ("none", "low", "medium", "high")
SHIELD = ("none", "weak", "strong")
BUFF_KINDS = ("atk", "dmg_bonus", "crit", "em", "def", "hp", "res_shred", "def_shred", "reaction_base",
              "reaction_conversion", "energy", "moonsign", "interruption", "damage_scaling", "other")
TARGETS = ("self", "party", "active", "off_field", "reaction_trigger", "moonsign")
CONFIDENCE = ("high", "medium", "low")
METHODS = ("manual", "llm_extracted", "derived")
WEAPONS = ("sword", "claymore", "polearm", "bow", "catalyst")
# Fields that describe the character (and therefore need provenance).
DESCRIBED = ("role", "element", "weapon", "analogue", "field", "personal_damage", "application", "buffs", "sustain",
             "reactions", "preferred_systems", "restrictions", "synergies")
REQUIRED = ("schema", "provisional", "sources", "provenance") + DESCRIBED
RULES = ("needs_element", "needs_count")

# Where a number comes from (every PowerEstimate): the four evidence states of the phase 13 brief.
EVIDENCE_STATE = {
    "exact_personal": "simulation",
    "exact_community": "simulation",
    "pair_model": "interpolation",
    "provisional_kit": "kit-model",
    "role_rules": "rules-only",
    "none": "none",
}


def evidence_state(route: str) -> str:
    return EVIDENCE_STATE.get(route, "none")


def _range(v) -> bool:
    return (isinstance(v, (list, tuple)) and len(v) == 2 and all(isinstance(x, (int, float)) for x in v)
            and v[0] <= v[1]) or isinstance(v, (int, float))


def mid(v) -> float:
    return (float(v[0]) + float(v[1])) / 2 if isinstance(v, (list, tuple)) else float(v or 0.0)


def validate(name: str, kit: dict, known_characters=()) -> list[str]:
    """Every problem with a provisional kit, as readable findings (empty when the kit is valid)."""
    errs = []
    if not isinstance(kit, dict):
        return [f"{name}: not a mapping"]
    for f in REQUIRED:
        if f not in kit:
            errs.append(f"missing field `{f}`")
    if kit.get("schema") != SCHEMA_VERSION:
        errs.append(f"schema must be {SCHEMA_VERSION}")
    if kit.get("role") not in ROLES:
        errs.append(f"role must be one of {', '.join(ROLES)}")
    if kit.get("element") not in ELEMENTS:
        errs.append("element must be one of " + ", ".join(ELEMENTS))
    if kit.get("weapon") not in WEAPONS:
        errs.append("weapon must be one of " + ", ".join(WEAPONS))
    known = set(known_characters)
    if known and kit.get("analogue") not in known:
        errs.append(f"analogue {kit.get('analogue')!r} has no simulations")
    fld = kit.get("field") or {}
    if fld.get("behaviour") not in BEHAVIOURS or not _range(fld.get("share")):
        errs.append("field needs behaviour (" + ", ".join(BEHAVIOURS) + ") and a share range")
    pd = kit.get("personal_damage") or {}
    if pd.get("tier") not in DAMAGE_TIERS or not _range(pd.get("share")):
        errs.append("personal_damage needs tier (" + ", ".join(DAMAGE_TIERS) + ") and a share range")
    for k, v in (kit.get("application") or {}).items():
        el, _, where = str(k).partition(".")
        if el not in ELEMENTS or where not in ("on", "off") or not _range(v):
            errs.append(f"application {k!r}: use '<Element>.on|off': [lo, hi]")
    for i, b in enumerate(kit.get("buffs") or []):
        tgt = str(b.get("target", ""))
        if b.get("kind") not in BUFF_KINDS:
            errs.append(f"buff {i + 1}: kind {b.get('kind')!r} not in the vocabulary")
        if tgt not in TARGETS and not (tgt.startswith("element:") and tgt[8:] in ELEMENTS):
            errs.append(f"buff {i + 1}: target {tgt!r} not in the vocabulary")
        if not b.get("text"):
            errs.append(f"buff {i + 1}: needs the kit text it paraphrases")
    su = kit.get("sustain") or {}
    if su.get("heal") not in HEAL or su.get("shield") not in SHIELD:
        errs.append("sustain needs heal (" + ", ".join(HEAL) + ") and shield (" + ", ".join(SHIELD) + ")")
    rx = kit.get("reactions") or {}
    for part in ("owns", "enables"):
        for r in rx.get(part) or []:
            if r not in BY_KEY:
                errs.append(f"reactions.{part}: unknown reaction {r!r}")
    for r in (rx.get("converts") or {}):
        if r not in BY_KEY:
            errs.append(f"reactions.converts: unknown reaction {r!r}")
    for r in kit.get("preferred_systems") or []:
        if r not in BY_KEY:
            errs.append(f"preferred_systems: unknown reaction {r!r}")
    for i, r in enumerate(kit.get("restrictions") or []):
        rule = r.get("rule")
        if rule not in RULES:
            errs.append(f"restriction {i + 1}: rule must be one of {', '.join(RULES)}")
        elif rule == "needs_element" and (not r.get("any_of") or not set(r["any_of"]) <= set(ELEMENTS)):
            errs.append(f"restriction {i + 1}: needs_element needs any_of: [elements]")
        elif rule == "needs_count" and (r.get("element") not in ELEMENTS or not isinstance(r.get("min"), int)):
            errs.append(f"restriction {i + 1}: needs_count needs element and an integer min")
        if not r.get("why"):
            errs.append(f"restriction {i + 1}: needs a reason (why)")
    for i, s in enumerate(kit.get("synergies") or []):
        w = str(s.get("with", ""))
        if not w or not s.get("why"):
            errs.append(f"synergy {i + 1}: needs `with` and `why`")
        elif w.startswith("element:") and w[8:] not in ELEMENTS or w.startswith("system:") and w[7:] not in BY_KEY:
            errs.append(f"synergy {i + 1}: unknown target {w!r}")
    sources = kit.get("sources") or {}
    if not isinstance(sources, dict) or not sources:
        errs.append("sources must map an id to a description")
    prov = kit.get("provenance") or {}
    default = prov.get("*")
    for f in DESCRIBED:
        p = prov.get(f, default)
        if p is None:
            errs.append(f"no provenance for `{f}`")
            continue
        if p.get("source") not in sources:
            errs.append(f"provenance of `{f}`: source {p.get('source')!r} is not in sources")
        if p.get("confidence") not in CONFIDENCE:
            errs.append(f"provenance of `{f}`: confidence must be one of {', '.join(CONFIDENCE)}")
        if p.get("method") not in METHODS:
            errs.append(f"provenance of `{f}`: method must be one of {', '.join(METHODS)}")
    return [f"{name}: {e}" for e in errs]


def unmet_restrictions(name: str, kit: dict, lineup, element_of) -> list[str]:
    """The kit's restrictions this lineup breaks, as readable reasons."""
    out = []
    members = list(lineup)
    for r in kit.get("restrictions") or []:
        if r.get("rule") == "needs_element":
            mates = {element_of(m) for m in members if m != name}
            if not mates & set(r["any_of"]):
                els = " or ".join(r["any_of"])
                out.append(f"{name} needs {'an' if els[0] in 'AEIOU' else 'a'} {els} teammate: {r['why']}")
        elif r.get("rule") == "needs_count":
            n = sum(1 for m in members if element_of(m) == r["element"])
            if n < r["min"]:
                out.append(f"{name} needs {r['min']} {r['element']} members: {r['why']}")
    return out


def capability_fields(kit: dict) -> dict:
    """The capability values the kit declares (midpoints), in gtc.capabilities.Capability's terms."""
    if kit.get("schema") == SCHEMA_VERSION:
        # heal_per_s is measured HP per second; a categorical heal level has no number, so it stays 0 (unknown)
        # and the category is kept in the kit for explanation.
        return {"damage_share": mid((kit.get("personal_damage") or {}).get("share", 0.0)),
                "field_share": mid((kit.get("field") or {}).get("share", 0.0)),
                "apply": {k: mid(v) for k, v in (kit.get("application") or {}).items()},
                "heal_per_s": 0.0}
    c = kit.get("capabilities") or {}
    return {"damage_share": mid(c.get("damage_share", 0.0)), "field_share": mid(c.get("field_share", 0.0)),
            "apply": {k: mid(v) for k, v in (c.get("apply") or {}).items()}, "heal_per_s": mid(c.get("heal_per_s", 0.0))}


def described(kit: dict) -> bool:
    """Whether the kit declares any capability (old `capabilities` block or schema v2)."""
    return kit.get("schema") == SCHEMA_VERSION or bool(kit.get("capabilities"))
