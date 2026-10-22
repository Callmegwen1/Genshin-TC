"""Mechanical reasoning about a lineup (phase M4): what each kit supplies, what the team lacks, which buffs reach
which damage, which kits compete or undo each other, and which kit conditions hold. Deterministic, from the
structured kits (gtc/kits.py) and the universal mechanics (gtc/mechanics.py). It produces no power and never
changes one: it is representation the advisor reads (gtc/advisor.py) and explanations show.

    supplied_functions     function -> members providing it (on-field damage, off-field damage, driver, sustain,
                           swirl support, grouping, battery, buffs, debuffs, <element> application)
    missing_functions      what a team needs and nobody supplies: a damage dealer, someone to stay on field, the
                           elements its central mechanics need; sustain is reported but soft
    synergies              buff edges (giver -> receiver, the effect reaches that receiver's damage by target, element
                           and damage type) and enabler edges (an aura one member applies that a central mechanic or
                           another member's reaction needs)
    conflicts              active harm or risk: two kits whose own damage needs field time (field_time); a member
                           whose element removes the auras a central mechanic relies on (aura: harm for a strong
                           applier that is not the on-field carry, else a caution); a buffer whose
                           buffs reach no damage dealer here (buff_wasted, a caution); a broken `only` condition
                           (condition, harm)
    conditions             kit conditions satisfied and failed (gtc/kit_conditions.status)
    reaction_dependencies  reactions a kit needs (kit reactions.requires, and reaction_required on its effects) and
                           whether this lineup can produce them
    opportunity_losses     value a kit leaves unused without being hurt: a `count` condition below full (Escoffier's
                           shred with fewer Hydro/Cryo members), an effect whose reaction this team cannot trigger
    kit_coverage           which members have reviewed kits, compiled ones (LLM-extracted, review pending) or
                           derived ones; a derived kit (measured profile, no effects) supports
                           function and field-time reasoning but no buff or condition reasoning, so its buffs are
                           "unknown", never assumed absent

Severity: "harm" (the team works against itself), "caution" (worth saying, does not change advice alone).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from gtc import mechanics as M

DEALERS = ("carry", "sub_dps")
STAY_ON_FIELD = ("high", "medium")
BUFF_KINDS = {"atk", "atk_pct", "flat_dmg", "dmg_bonus", "elemental_dmg_bonus", "crit_rate", "crit_dmg", "em",
              "reaction_bonus", "reaction_base", "res_shred", "def_shred", "dmg_taken"}
STRENGTH = {"low": 1, "medium": 2, "high": 3}


@dataclass
class TeamMechanics:
    lineup: tuple
    central: list = field(default_factory=list)
    supplied_functions: dict = field(default_factory=dict)
    missing_functions: list = field(default_factory=list)
    synergies: list = field(default_factory=list)
    conflicts: list = field(default_factory=list)
    conditions_satisfied: list = field(default_factory=list)
    conditions_failed: list = field(default_factory=list)
    field_time: dict = field(default_factory=dict)
    buff_coverage: list = field(default_factory=list)
    reaction_dependencies: list = field(default_factory=list)
    opportunity_losses: list = field(default_factory=list)
    kit_coverage: dict = field(default_factory=dict)

    def harms(self) -> list:
        return [c for c in self.conflicts if c["severity"] == "harm"]

    def conflict_keys(self) -> set:
        return {c["key"] for c in self.conflicts}

    def as_dict(self) -> dict:
        return asdict(self)


_HEXEREI: set | None = None


def _hexerei() -> set:
    global _HEXEREI
    if _HEXEREI is None:
        from gtc.tc.engine import load_kits

        _HEXEREI = {n for n, k in load_kits(generated=False).items() if isinstance(k, dict) and k.get("hexerei")}
    return _HEXEREI


def _receiver(k: dict) -> dict:
    d = (k.get("behavior") or {}).get("damage") or {}
    return {"element": d.get("element") or k.get("element"), "types": d.get("types") or []}


def _is_dealer(k: dict) -> bool:
    return (k.get("behavior") or {}).get("damage_ownership") in DEALERS


def _applied(k: dict) -> dict:
    """{element: strongest application} of one kit."""
    out = {}
    for a in (k.get("behavior") or {}).get("application") or []:
        out[a["element"]] = max(out.get(a["element"], 0), STRENGTH.get(a.get("strength"), 0))
    return out


def default_central(lineup, kits) -> list:
    """Mechanics the team plausibly runs on when no identity says so: reactions the members' applied elements can
    produce that involve a damage dealer's element (Swirl and Crystallize are support reactions, not cores)."""
    applied = {e for k in kits.values() for e in _applied(k)}
    dealer_els = {_receiver(k)["element"] for k in kits.values() if _is_dealer(k)}
    out = []
    for r in sorted(M.possible_reactions(applied)):
        x = M.BY_KEY[r]
        if x.channel == "swirl" or x.cls == "crystallize" or r in ("overload", "spread"):
            continue
        if set(x.elements) & dealer_els:
            out.append(r)
    return out


def _reaction_possible(reaction: str, elements: set) -> bool:
    if reaction in ("freeze", "melt", "vaporize", "quicken", "crystallize"):
        r = M.BY_KEY[reaction]
        return set(r.elements) <= elements if reaction != "crystallize" else "Geo" in elements and len(elements) > 1
    r = M.BY_KEY.get(reaction)
    if r is None:
        return False
    if r.channel == "swirl":
        return "Anemo" in elements and r.elements[1] in elements
    return set(M.mechanic_elements(reaction)) <= elements


def _effect_condition(c: dict, lineup, elements: set, hexerei: set) -> str:
    """met | unmet | unknown for one effect-level condition."""
    t = c.get("type")
    if t == "reaction_required":
        return "met" if any(_reaction_possible(r, elements) for r in c.get("reactions") or []) else "unmet"
    if t == "party_element_types":
        n = len({M.element_of(m) for m in lineup} - {None})
        return "met" if n >= c.get("full", 4) else "partial"
    if t == "hexerei_count":
        return "met" if sum(m in hexerei for m in lineup) >= c.get("min", 2) else "unmet"
    if t in ("party_element_count", "party_elements_only", "party_elements_forbidden"):
        els = set(c.get("elements") or [])
        members = [M.element_of(m) for m in lineup]
        if t == "party_elements_only":
            ok = all(e in els for e in members) and (not c.get("each_required") or els <= set(members))
        elif t == "party_elements_forbidden":
            ok = not (set(members) & els)
        else:
            have = sum(e in els for e in members)
            return "met" if have >= c.get("full", len(lineup)) else "partial" if have else "unmet"
        return "met" if ok else "unmet"
    return "unknown"  # character_state, aura_required, reaction_trigger_count: depends on the rotation


def analyse(lineup, central=None) -> TeamMechanics:
    """TeamMechanics for a lineup. `central`: the team's central mechanics (the engine identity's), else derived."""
    from gtc import kits as K
    from gtc.kit_conditions import status

    lineup = tuple(lineup)
    kits = {m: K.kit(m) for m in lineup}
    kits = {m: k for m, k in kits.items() if k}
    tm = TeamMechanics(lineup=lineup)
    tm.kit_coverage = {"reviewed": sorted(m for m, k in kits.items() if not k.get("derived") and not k.get("compiled")),
                       "compiled": sorted(m for m, k in kits.items() if k.get("compiled")),
                       "derived": sorted(m for m, k in kits.items() if k.get("derived")),
                       "missing": sorted(set(lineup) - set(kits))}
    central = list(central) if central is not None else default_central(lineup, kits)
    tm.central = central
    elements = {M.element_of(m) for m in lineup} - {None}
    hexerei = _hexerei()
    B = {m: k.get("behavior") or {} for m, k in kits.items()}

    # ---- supplied and missing functions ----
    fn: dict[str, list] = {}

    def add(f, m):
        fn.setdefault(f, []).append(m)

    for m, k in kits.items():
        b, roles = B[m], set(k.get("roles") or [])
        if b.get("on_field_damage") is True:
            add("on-field damage", m)
        if _is_dealer(k) and b.get("off_field") in ("some", "strong") and not b.get("on_field_damage") is True:
            add("off-field damage", m)
        if b.get("driver") is True:
            add("driver", m)
        s = b.get("sustain") or {}
        if s.get("heal") not in (None, "none", "unknown") or s.get("shield") not in (None, "none", "unknown"):
            add("sustain", m)
        for r, f in (("swirl_support", "swirl support"), ("grouping", "grouping"), ("battery", "battery"),
                     ("buffer", "buffs"), ("debuffer", "debuffs")):
            if r in roles:
                add(f, m)
        for el in _applied(k):
            add(f"{el} application", m)
    tm.supplied_functions = fn
    missing = []
    if not any(_is_dealer(k) for k in kits.values()):
        missing.append("damage dealer")
    if not any(B[m].get("on_field_damage") is True or B[m].get("driver") is True or B[m].get("field_time") in STAY_ON_FIELD for m in kits):
        missing.append("someone to stay on field")
    for mech in central:
        for el in M.mechanic_elements(mech):
            if f"{el} application" not in fn:
                missing.append(f"{el} application ({M.mechanic_name(mech)})")
    if "sustain" not in fn:
        missing.append("sustain (soft)")
    tm.missing_functions = missing

    # ---- field time ----
    on_field = [m for m in kits if B[m].get("on_field_damage") is True]
    demand = {m: B[m].get("field_time", "unknown") for m in kits}
    tm.field_time = {"demand": demand, "on_field_dealers": on_field,
                     "total": round(sum(M.FIELD_TIME.get(v, 0) for v in demand.values()), 2)}
    if len(on_field) >= 2:
        share = sum(M.FIELD_TIME.get(demand[m], 0) for m in on_field)
        tm.conflicts.append({"key": "field_time:" + "+".join(sorted(on_field)), "kind": "field_time", "severity": "harm",
                             "members": sorted(on_field),
                             "text": f"{' and '.join(sorted(on_field))} both deal their damage on field and compete for "
                                     f"field time (needs about {share:.0%} of the rotation between them)",
                             "resolved_by": "a simulated rotation of this exact team"})

    # ---- buffs: who reaches whom ----
    dealers = [m for m, k in kits.items() if _is_dealer(k)]
    for g, k in kits.items():
        for eff in k.get("effects") or []:
            if eff.get("kind") not in BUFF_KINDS:
                continue
            conds = [(c, _effect_condition(c, lineup, elements, hexerei)) for c in eff.get("conditions") or []]
            state = ("unmet" if any(s == "unmet" for _, s in conds) else "partial" if any(s == "partial" for _, s in conds)
                     else "conditional" if conds else "always")
            reach, loose = [], []
            for r in dealers:
                rk = kits[r]
                rd = _receiver(rk)
                if eff.get("target") == "enemy":
                    els = (eff.get("affects") or {}).get("elements") or ["all"]
                    ok = "all" in els or rd["element"] in els
                elif eff.get("target") == "matching_element_members":
                    ok = rd["element"] in ((eff.get("affects") or {}).get("elements") or [])
                else:
                    ok = M.effect_applies(eff, rd, receiver_is_active=bool(B[r].get("on_field_damage") is True) or
                                          B[r].get("field_time") in STAY_ON_FIELD, same=(g == r))
                if ok:
                    reach.append(r)
                # the same test without the on-field requirement: an "active" buff still reaches a damage dealer who
                # swaps in to cast (Bennett's ATK snapshots on Xiangling's Pyronado), so it is not wasted
                if ok or (eff.get("target") == "active" and M.effect_applies(eff, rd, receiver_is_active=True, same=(g == r))):
                    loose.append(r)
            tm.buff_coverage.append({"giver": g, "effect": eff.get("source"), "kind": eff["kind"], "reaches": reach, "loose": loose,
                                     "state": state, "unmet": [c.get("text", c.get("type")) for c, s in conds if s == "unmet"]})
            for r in reach:
                if r != g and state != "unmet":
                    tm.synergies.append({"kind": "buff", "from": g, "to": r, "effect": eff.get("source"),
                                         "what": M.DAMAGE_BONUS.get(eff["kind"], eff["kind"]), "state": state})
            if (state != "unmet" and eff.get("target") not in ("self",) and _is_dealer(k) and reach == [g]
                    and any(r != g for r in dealers)):
                tm.opportunity_losses.append({"member": g, "kind": "self_only", "effect": eff.get("source"),
                                              "text": f"{g}'s {eff.get('source')} only boosts {g}'s own damage here; "
                                                      f"{', '.join(r for r in dealers if r != g)} "
                                                      f"{'deal' if len(dealers) > 2 else 'deals'} damage it does not cover"})
            if state == "unmet":
                tm.opportunity_losses.append({"member": g, "kind": "effect_inactive", "effect": eff.get("source"),
                                              "text": f"{g}'s {eff.get('source')} does not activate here: "
                                                      + "; ".join(c.get("text", c.get("type")) for c, s in conds if s == "unmet")})
    for g, k in kits.items():
        if k.get("derived") or "buffer" not in (k.get("roles") or []) and "debuffer" not in (k.get("roles") or []):
            continue
        rows = [c for c in tm.buff_coverage if c["giver"] == g]
        if rows and not any(set(c["loose"]) - {g} for c in rows) and not _is_dealer(k):
            tm.conflicts.append({"key": f"buff_wasted:{g}", "kind": "buff_wasted", "severity": "caution", "members": [g],
                                 "text": f"{g}'s buffs reach no damage dealer on this team",
                                 "resolved_by": "a damage dealer of the element or damage type the buffs need"})

    # ---- enablers: auras the central mechanics and kits need ----
    for mech in central:
        r = M.reaction_of(mech)
        for el in M.mechanic_elements(mech):
            givers = [m for m, k in kits.items() if el in _applied(k)]
            for g in givers:
                tm.synergies.append({"kind": "enabler", "from": g, "to": mech, "what": f"{el} for {M.mechanic_name(mech)}",
                                     "state": "always"})
        # aura consumption: a third element that reacts with this mechanic's auras removes them
        if r is not None and r.cls in ("control", "amplifying", "catalyze", "transformative") and r.channel != "swirl":
            for m, k in kits.items():
                for el, strength in _applied(k).items():
                    eaten = M.consumes_auras(el, mech)
                    other_core = [c for c in central if c != mech and el in M.mechanic_elements(c)]
                    if eaten and not other_core:
                        tm.conflicts.append({"key": f"aura:{m}:{mech}", "kind": "aura", "members": [m],
                                             # a strong off-field or support applier works against the
                                             # mechanic; an on-field carry's own element is what the team reacts with
                                             "severity": "harm" if strength >= 3 and B[m].get("on_field_damage") is not True
                                             else "caution",
                                             "text": f"{m}'s {el} removes the {' and '.join(eaten)} auras "
                                                     f"{M.mechanic_name(mech)} relies on",
                                             "resolved_by": f"a team built on the reaction {el} makes instead"})

    # ---- kit conditions ----
    for m in lineup:
        s = status(m, lineup)
        if s is None:
            continue
        row = {"member": m, **s}
        if s["met"]:
            tm.conditions_satisfied.append(row)
        elif s["rule"] == "only":
            tm.conditions_failed.append({**row, "severity": "harm"})
            tm.conflicts.append({"key": f"condition:{m}", "kind": "condition", "severity": "harm", "members": [m],
                                 "text": f"{m}'s kit condition is broken: {s['text']}",
                                 "resolved_by": "a lineup that meets the condition"})
        else:
            tm.conditions_failed.append({**row, "severity": "opportunity"})
            tm.opportunity_losses.append({"member": m, "kind": "partial_condition",
                                          "text": f"{m} works at {s['have']}/{s['need']} of full strength: {s['text']}"})

    # ---- reaction dependencies ----
    seen = set()
    for m, k in kits.items():
        for rx in (k.get("reactions") or {}).get("requires") or []:
            seen.add((m, rx))
            tm.reaction_dependencies.append({"member": m, "reaction": rx, "source": "kit",
                                             "met": _reaction_possible(rx, elements)})
        for eff in k.get("effects") or []:
            for c in eff.get("conditions") or []:
                if c.get("type") == "reaction_required" and (m, "/".join(c.get("reactions") or [])) not in seen:
                    seen.add((m, "/".join(c.get("reactions") or [])))
                    tm.reaction_dependencies.append({"member": m, "reaction": "/".join(c.get("reactions") or []),
                                                     "source": eff.get("source"),
                                                     "met": any(_reaction_possible(r, elements) for r in c.get("reactions") or [])})
    return tm


def critical_functions(tm: TeamMechanics, member: str) -> list[str]:
    """Functions `member` supplies that nobody else on the team does and the team depends on: on-field damage when
    they are the only one, application of a central mechanic's element, swirl support, sustain."""
    out = []
    for f, who in tm.supplied_functions.items():
        if who != [member]:
            continue
        if f == "on-field damage" or f in ("swirl support", "sustain"):
            out.append(f)
        elif f.endswith(" application"):
            el = f.split()[0]
            if any(el in M.mechanic_elements(c) for c in tm.central):
                out.append(f)
    return out
