"""Team validity (phase 9; split from candidate generation in model 6.3).

Two different questions, kept apart:
  candidate generation  what the automatic team generator searches: the archetype templates' slots, required roles
                        and element patterns (gtc/teams.fill_template). Failing them means "this lineup cannot
                        perform that archetype's mechanic" (no Hyperbloom without Electro), never "this team is
                        invalid".
  mechanical validity   whether four characters form a legal team at all (`mechanical`): four distinct, known
                        characters, at most one Traveler. Any legal team can be evaluated (AccountModel.assess_lineup),
                        whether or not a template would generate it.
A legal team is then classified by how well its number is supported (`support`):
  well_supported   its own simulations, or the pair model next to a simulated lineup with nothing unusual
  unusual          extrapolated far, atypical, a mechanic the evidence never covered, a provisional kit, role rules,
                   or no number at all
Off-meta never means invalid.

Before phase 9 three learned rules also rejected compositions: elements never seen in an archetype's simulated
teams, too many on-field characters, too little application, a carry without the teammate elements of 95% of
their teams, and a predicted damage owner who could not hold the template's first slot. They described how
unusual a team is, not whether it works, and they threw out functional teams (Neuvillette with Pyro supports,
Raiden with Cryo supports, Clorinde with Lunar supports). They are now typicality (gtc/typicality.py), which widens
the uncertainty of extrapolated estimates; the owner check became identity (gtc/identity.py).

No hand-written composition rule rejects teams either. Skirk "locked to Hydro and Cryo teammates" was checked in
phase 9: 10 of her 139 simulated lineups have other teammates and they work (Skirk / Escoffier / Navia / Xilonen
85k, Skirk / Chiori / Yelan / Zhongli 64k, against about 131k for her best), so it is a team-building preference
that typicality and power express, not a mechanical failure.

What this module still learns, for typicality: per carry, the teammate elements present in at least
CARRY_ELEMENT_SHARE of the simulated teams whose damage they own (Skirk: Cryo and Hydro in 131 of 133).
Written to knowledge/generated/validity.yaml by `python -m gtc derive`.
"""
from __future__ import annotations

from collections import defaultdict

import yaml

from gtc import KNOWLEDGE_DIR, params

VALIDITY_PATH = KNOWLEDGE_DIR / "generated" / "validity.yaml"
MIN_LINEUPS = params.get("validity.min_lineups")  # a carry needs this many own simulated teams for a teammate rule
CARRY_ELEMENT_SHARE = params.get("validity.carry_element_share")  # teammate element present in at least this share


def learn_carries(db: dict, universe: dict) -> dict:
    """Per carry: teammate elements present in at least CARRY_ELEMENT_SHARE of the simulated teams whose measured
    damage they own."""
    rows: dict[str, list[set[str]]] = defaultdict(list)
    for e in db.values():
        st = (e.get("profile") or {}).get("structure") or {}
        if st.get("type") in ("hypercarry", "dual_carry") and st.get("owners") and len(e["lineup"]) == 4:
            c = st["owners"][0]
            rows[c].append({universe[m].element for m in e["lineup"] if m != c and m in universe})
    out = {}
    for c, teams in rows.items():
        if len(teams) < MIN_LINEUPS:
            continue
        need = sorted(el for el in {x for t in teams for x in t} if sum(el in t for t in teams) / len(teams) >= CARRY_ELEMENT_SHARE)
        if need:
            out[c] = {"lineups": len(teams), "teammate_elements": need}
    return out


MANUAL_ID = "manual"  # the template id of a team entered by hand that no archetype generates


def mechanical(lineup, known) -> list[str]:
    """Why these characters cannot form a team (empty when they can)."""
    names = list(lineup)
    out = []
    if len(names) != 4:
        out.append(f"a team has 4 characters, not {len(names)}")
    if len(set(names)) != len(names):
        out.append("the same character appears twice")
    unknown = sorted(m for m in set(names) if m not in known)
    if unknown:
        out.append("unknown character: " + ", ".join(unknown))
    if sum(1 for m in set(names) if m.startswith("Traveler")) > 1:
        out.append("only one Traveler can be in a team")
    return out


def support(route: str, tier: str, findings: list, coverage_status: str | None, quality: str = "",
            quality_reasons=()) -> tuple[str, list[str]]:
    """("well_supported" | "unusual", reasons) for a legal team's number. Community simulations of poor quality
    (model 6.4: submitters disagree badly, or the rotation does not play the team as intended) are not "well
    supported" just because they exist."""
    why = []
    if route in ("exact_personal", "exact_community"):
        if quality == "poor":
            return "unusual", ["community simulations of poor quality: " + "; ".join(quality_reasons)]
        return "well_supported", []
    if route == "pair_model":
        if tier != "C":
            why.append("predicted by the pair model far from any simulated lineup")
    elif route == "provisional_kit":
        why.append("a member has only a provisional kit")
    elif route == "role_rules":
        why.append("only template role rules (no simulation or pair-model prediction)")
    else:
        why.append("no number: no simulations and nothing to predict from")
    why += [f.split(":", 1)[1].strip() if ":" in f else f for f in findings or []]
    if coverage_status and coverage_status != "complete":
        why.append(f"mechanics coverage {coverage_status}")
    return ("well_supported" if not why else "unusual"), why


_CARRIES: dict | None = None


def set_carry_rules(rules: dict) -> None:
    global _CARRIES
    _CARRIES = rules


def carry_rules() -> dict:
    global _CARRIES
    if _CARRIES is None:
        _CARRIES = load().get("_carries", {})
    return _CARRIES


def write(rules: dict) -> None:
    header = "# GENERATED by `python -m gtc derive` from simulated teams. Do not edit.\n"
    VALIDITY_PATH.write_text(header + yaml.safe_dump(rules, sort_keys=True), encoding="utf-8")


def load() -> dict:
    if not VALIDITY_PATH.exists():
        return {}
    return yaml.safe_load(VALIDITY_PATH.read_text(encoding="utf-8")) or {}
