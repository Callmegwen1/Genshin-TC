"""Derive game-wide knowledge from data, so the engine knows every character and archetype.

Writes two generated files that knowledge.load() merges under the hand-written ones:
  knowledge/generated/auto_roles.yaml      role tags for every character
  knowledge/generated/auto_templates.yaml  archetypes discovered in the gcsim database

Role tags come from:
  Prydwen's tier list   role category (On-Field DPS, Damage Support, Support), tier and tags (high app, CC)
  talent descriptions   healing, shields and RES/DEF shred, from Project Amber's datamined text
  gcsim simulations     which archetypes a character carries, and how well teams with each teammate perform

Archetypes come from the 4,800 standard gcsim simulations. Each simulation is assigned a carry (the one
member Prydwen rates purely as On-Field DPS, or the only one rated DPS at all) and a reaction family
(from the elements present). Families that match a hand-written template feed that template's carry
role. The rest become new templates.

Hand-written knowledge always wins: a role defined in knowledge/characters.yaml is never overwritten.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict

import yaml

from gtc import KNOWLEDGE_DIR, gamedata
from gtc.evidence import assign_carry, role_categories
from gtc.synergy import table as synergy_table
from gtc.sources import SOURCE_DIR, gcsim_db, prydwen
from gtc.sources.fetch import get

AUTO_ROLES = KNOWLEDGE_DIR / "generated" / "auto_roles.yaml"
AUTO_TEMPLATES = KNOWLEDGE_DIR / "generated" / "auto_templates.yaml"
FAMILY_LINEUPS = SOURCE_DIR / "family_lineups.json"
AMBER_DETAIL = "https://gi.yatta.moe/api/v2/en/avatar/{id}"
TIER_QUALITY = {"T0": 5, "T0.5": 5, "T1": 4, "T1.5": 4, "T2": 3, "T3": 2, "T4": 2, "T5": 1}
from gtc.reactions import HELPERS, reaction_between  # noqa: E402  (swirl and crystallize helpers define no family)

# Which partner element a carry's team is usually built around, in order (a judgment); the reaction each pair
# makes is a game fact from gtc/reactions.py.
PARTNER_ORDER = {
    "Pyro": ["Hydro", "Cryo", "Electro", "Dendro"],
    "Hydro": ["Pyro", "Electro", "Dendro", "Cryo"],
    "Cryo": ["Hydro", "Pyro", "Electro"],
    "Electro": ["Dendro", "Hydro", "Pyro", "Cryo"],
    "Dendro": ["Electro", "Hydro", "Pyro"],
}
PARTNER_PRIORITY = {el: [(p, reaction_between(el, p).family) for p in order] for el, order in PARTNER_ORDER.items()}
# (reaction, carry element) that a hand-written template already describes.
TEMPLATE_FOR = {
    ("Freeze", "Cryo"): "freeze", ("Melt", "Cryo"): "melt", ("Vaporize", "Pyro"): "vaporize_pyro",
    ("Vaporize", "Hydro"): "international", ("Quicken", "Electro"): "aggravate", ("Lunar-Charged", "Electro"): "lunar_charged",
}


def _q(ratio: float, cuts=(0.9, 0.75, 0.6, 0.45)) -> int:
    for q, cut in zip((5, 4, 3, 2), cuts):
        if ratio >= cut:
            return q
    return 1


def talent_texts(game: dict[str, dict]) -> dict[str, str]:
    """Skill, Burst and passive descriptions per character from Project Amber (cached for a month)."""
    out = {}
    for name, info in game.items():
        page = get(AMBER_DETAIL.format(id=info["id"]), "amber", max_age_days=30, delay=0.3, browser=False)
        if not page:
            continue
        data = json.loads(page).get("data") or {}
        texts = [t.get("description", "") for t in (data.get("talent") or {}).values()]
        out[name] = re.sub(r"<[^>]+>|\{[^}]*\}", " ", " ".join(texts))
    return out


def sustain_and_shred(text: str) -> dict[str, int]:
    roles = {}
    if re.search(r"restor\w* (?:\w+ )?HP|regenerat\w* HP|heal", text, re.I):
        roles["healer"] = 3
    if re.search(r"\bshield", text, re.I):
        roles["shield"] = 3
    if re.search(r"(?:RES|Resistance)\w* (?:is |are )?(?:decreased|reduced)|decreas\w+ \w+(?: \w+)? RES\b", text, re.I):
        roles["res_shred"] = 3
    if re.search(r"DEF (?:is )?(?:decreased|reduced)|decreas\w+ \w+(?: \w+)? DEF\b", text, re.I):
        roles["def_shred"] = 3
    return roles


def family_of(elements: list[str], carry_element: str, moonsign: bool) -> tuple[str, str | None, list[str]]:
    """(label, hand-written template id or None, required elements), named after the carry's own reaction.
    moonsign: the carry has a Moonsign kit (only then can the team be a Lunar family)."""
    reactive = set(elements) - HELPERS
    if carry_element in HELPERS:
        return f"{carry_element} carry", None, [carry_element]
    if moonsign and {"Electro", "Hydro"} <= reactive and carry_element in ("Electro", "Hydro"):
        reaction, need = "Lunar-Charged", ["Electro", "Hydro"]
    elif moonsign and {"Dendro", "Hydro"} <= reactive and carry_element in ("Dendro", "Hydro"):
        reaction, need = "Lunar-Bloom", ["Dendro", "Hydro"]
    elif {"Dendro", "Hydro", "Electro"} <= reactive and "Pyro" not in reactive and carry_element in ("Dendro", "Hydro", "Electro"):
        reaction, need = "Hyperbloom", ["Dendro", "Electro", "Hydro"]
    else:
        partner = next(((el, r) for el, r in PARTNER_PRIORITY.get(carry_element, []) if el in reactive), None)
        if partner is None:
            return f"Mono {carry_element}", None, [carry_element]
        reaction, need = partner[1], sorted({carry_element, partner[0]})
    return f"{reaction} ({carry_element} carry)", TEMPLATE_FOR.get((reaction, carry_element)), need


def discover(kb_templates: dict) -> dict:
    """Archetypes, carry ratings and teammate ratings from standard gcsim simulations."""
    game = gamedata.load_characters()
    pry = prydwen.load()
    tiers = pry.get("tiers", {})
    moonsign = {s["name"] for g in pry.get("characters", {}).values() for s in g.get("synergies", [])
                if (s.get("tag") or "").strip().lower() == "moonsign"}
    cats = role_categories(pry)
    rated = {n: {e["category"] for e in v if e.get("overall")} for n, v in tiers.items()}
    elem = lambda n: n[10:-1] if n.startswith("Traveler (") else game.get(n, {}).get("element", "?")

    fam_sims: dict[str, list] = defaultdict(list)
    fam_meta: dict[str, dict] = {}
    tbl = synergy_table()
    # One entry per lineup (its median submission, for the lineup and members), valued at the lineup's robust value:
    # the median of per-submitter medians (gcsim_db.lineup_values).
    groups: dict[frozenset, list] = defaultdict(list)
    for t in gcsim_db.load():
        if gcsim_db.is_standard(t):
            groups[t.names].append(t)
    values = gcsim_db.lineup_values()
    reps = []
    for lineup, sims in groups.items():
        sims.sort(key=lambda x: x.dps)
        reps.append(sims[len(sims) // 2])
    for t in reps:
        names = list(t.names)
        # The carry is the lineup's MEASURED top damage owner when it was simulated and attributed; teams without
        # a single carry (reaction cores, drivers, distributed) are not carry families. Otherwise Prydwen's categories.
        entry = tbl.by_lineup.get(t.names) if tbl else None
        st = (entry.get("profile") or {}).get("structure") if entry else None
        if st is not None:
            carry = st["owners"][0] if st["type"] in ("hypercarry", "dual_carry") and st["owners"] else None
        else:
            carry = assign_carry(names, cats)
        if not carry:
            continue
        # Lunar families need a Moonsign CARRY: Clorinde topping damage next to Ineffa and Columbina deals her own
        # Electro damage while Ineffa makes the Lunar-Charged, so that is a Clorinde team, not a Lunar-Charged one.
        label, template, core = family_of([elem(n) for n in names], elem(carry), carry in moonsign)
        fam_sims[label].append((carry, t))
        fam_meta[label] = {"template": template, "require": core}

    families = {}
    for label, sims in fam_sims.items():
        best_by_carry: dict[str, float] = defaultdict(float)
        for carry, t in sims:
            best_by_carry[carry] = max(best_by_carry[carry], values[t.names].value)
        top = max(best_by_carry.values())
        carries = {c: _q(v / top) for c, v in best_by_carry.items()}
        scores: dict[str, list[float]] = defaultdict(list)
        for carry, t in sims:
            for n in t.names:
                if n != carry:
                    scores[n].append(values[t.names].value / best_by_carry[carry])
        # Teammate ratings come from MEASURED synergy when available: each teammate's share of team damage
        # (own damage plus buffs, attributed hit by hit from gcsim logs) alongside this family's carries.
        # Without synergy data, from how their teams perform relative to the carry's best.
        # A character whose only rated role is On-Field DPS is not offered as a support option.
        supports = {}
        for n, v in scores.items():
            if len(v) < 2 or rated.get(n) == {"DPS"}:
                continue
            shares = [p.value for c in best_by_carry if (p := tbl.pair(c, n)) and p.n >= 1] if tbl else []
            if shares:
                supports[n] = _q(sum(shares) / len(shares), (0.30, 0.22, 0.15, 0.08))
            else:
                supports[n] = _q(sum(v) / len(v), (0.9, 0.8, 0.7, 0.55))
        families[label] = {**fam_meta[label], "sims": len(sims), "best_dps": round(top), "carries": carries, "supports": supports,
                           "lineups": sorted(sorted(t.names) for _, t in sims)}
    return families


def build(kb) -> tuple[dict, dict]:
    game = gamedata.load_characters()
    pry = prydwen.load()
    texts = talent_texts(game)
    families = discover(kb.templates)

    roles: dict[str, dict[str, int]] = defaultdict(dict)
    sources: dict[str, list[str]] = defaultdict(list)

    def give(name: str, role: str, q: int, why: str):
        if q > roles[name].get(role, 0):
            roles[name][role] = q
            sources[name].append(f"{role} {q}: {why}")

    for name, entries in pry.get("tiers", {}).items():
        el = game.get(name, {}).get("element")
        for e in entries:
            q = TIER_QUALITY.get(e.get("overall") or "", 2)
            tags = {t.split(" (")[0] for t in e.get("tags", [])}
            if e["category"] == "Sub-DPS":
                give(name, "offfield_dps", q, f"Prydwen Damage Support {e.get('overall')}")
                give(name, "offfield_app", min(5, q + (1 if "high app" in tags else 0)), "Prydwen Damage Support" + (", high app" if "high app" in tags else ""))
            elif e["category"] == "Support":
                give(name, "buffer_anemo" if el == "Anemo" else "buffer_general", q, f"Prydwen Support {e.get('overall')}")
                if "high app" in tags:
                    give(name, "offfield_app", q, "Prydwen high app tag")
            if "CC" in tags:
                give(name, "cc", 4, "Prydwen CC tag")
    for name, text in texts.items():
        for role, q in sustain_and_shred(text).items():
            give(name, role, q, "talent description")
    # Damage dealers no archetype family can place as a carry: known and rated, but no archetype can be inferred
    # yet. Some have no standard simulations at all; others appear only in a few lineups as a teammate.
    from gtc.sources import gcsim_db

    simulated_carries = {c for fam in families.values() for c in fam["carries"]}
    lineup_count: dict[str, int] = {}
    for names in gcsim_db.lineup_values():
        for n in names:
            lineup_count[n] = lineup_count.get(n, 0) + 1
    for name, entries in pry.get("tiers", {}).items():
        for e in entries:
            if e["category"] == "DPS" and name not in simulated_carries:
                n = lineup_count.get(name, 0)
                why = "no standard gcsim teams yet" if not n else f"in only {n} standard lineups, too few to infer an archetype"
                give(name, "carry_unsimulated", TIER_QUALITY.get(e.get("overall") or "", 2),
                     f"Prydwen On-Field DPS {e.get('overall')}, {why}")

    templates = {}
    family_lineups: dict[str, list] = {}
    for label, fam in families.items():
        if fam["template"] and fam["template"] in kb.templates:
            family_lineups.setdefault(fam["template"], []).extend(fam["lineups"])
            carry_role = kb.templates[fam["template"]].slots[0].roles[0]
            for c, q in fam["carries"].items():
                give(c, carry_role, q, f"carries {label} in {fam['sims']} gcsim sims")
            continue
        if fam["sims"] < 5:
            continue
        slug = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
        for c, q in fam["carries"].items():
            give(c, f"carry_{slug}", q, f"carries {label} in gcsim")
        for s, q in fam["supports"].items():
            give(s, f"support_{slug}", q, f"teams with them perform at quality {q} in {label} gcsim sims")
        family_lineups[f"auto_{slug}"] = fam["lineups"]
        templates[f"auto_{slug}"] = {
            "label": f"{label} (from gcsim data)",
            "ceiling": 1.0,
            "signature": {"require": fam["require"]},
            "slots": [
                {"name": f"{label} carry", "roles": [f"carry_{slug}"], "core": True, "weight": 2},
                {"name": "Teammate", "roles": [f"support_{slug}"], "weight": 1.5},
                {"name": "Teammate", "roles": [f"support_{slug}"]},
                {"name": "Flex", "roles": [f"support_{slug}", "healer", "shield", "buffer_general", "buffer_anemo"]},
            ],
            "generated": {"sims": fam["sims"], "best_dps": fam["best_dps"], "carries": sorted(fam["carries"], key=lambda c: -fam["carries"][c])},
        }

    role_doc = {n: {"roles": dict(sorted(r.items())), "why": sources[n]} for n, r in sorted(roles.items())}
    # Which simulated lineups each generated archetype was discovered from: its tier uses only these, so a
    # Bennett-led Lunar-Charged lineup does not rate Bennett's "Mono Pyro" archetype.
    FAMILY_LINEUPS.write_text(json.dumps(family_lineups), encoding="utf-8")
    return role_doc, templates


def write(kb) -> tuple[int, int]:
    roles, templates = build(kb)
    header = "# GENERATED by `python -m gtc derive`. Do not edit; override in knowledge/characters.yaml or templates.yaml.\n"
    AUTO_ROLES.write_text(header + yaml.safe_dump(roles, sort_keys=False, allow_unicode=True, width=200), encoding="utf-8")
    AUTO_TEMPLATES.write_text(header + yaml.safe_dump(templates, sort_keys=False, allow_unicode=True, width=200), encoding="utf-8")
    return len(roles), len(templates)
