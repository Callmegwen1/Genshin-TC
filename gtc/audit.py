"""Data audit: every character in the game, checked for contradictions between game data, roles, simulations
and the teams the engine can form. `python -m gtc audit` writes reports/audit-<date>.md.

Each finding says what is inconsistent and why, so nothing is silently dropped. A character the engine
cannot place in any valid team is traced to the reason: no roles, no slot that takes them, or a validity rule
that rejects every lineup (with that rule's own message).
"""
from __future__ import annotations

from gtc import params

from collections import Counter, defaultdict
from dataclasses import dataclass, field

from gtc import gamedata, knowledge


@dataclass
class CharacterAudit:
    name: str
    element: str
    rarity: int
    roles: list[str] = field(default_factory=list)
    sims: int = 0
    carried: int = 0  # simulated lineups whose measured damage they own
    prydwen: str = ""
    archetypes: list[str] = field(default_factory=list)  # archetypes with a valid team containing them
    led: list[str] = field(default_factory=list)  # archetypes with a valid team they lead
    findings: list[str] = field(default_factory=list)  # unexplained contradictions: something to fix
    notes: list[str] = field(default_factory=list)  # explained gaps, such as no simulations yet


def _why_no_team(name: str, universe: list, kb) -> str:
    """Why no archetype forms a valid team with this character: the first obstacle found."""
    from gtc import validity
    from gtc.capabilities import load as load_caps
    from gtc.teams import elements_fit, fill_template, slot_candidates

    me = next(m for m in universe if m.key == name)
    slots = [(t, s) for t in kb.templates.values() for s in t.slots if any(c[0].key == name for c in slot_candidates(s, t, [me]))]
    if not slots:
        return f"no archetype slot accepts their roles ({', '.join(sorted(me.roles)) or 'none'})"
    reasons = Counter()
    for t in {t.id: t for t, _ in slots}.values():
        raw = fill_template(t, universe, kb, limit=1, must=name, rank_by="potential")
        if not raw:
            reasons[f"{t.label}: no full lineup (another slot, a required role or the element pattern cannot be filled)"] += 1
    return "; ".join(r for r, _ in reasons.most_common(4))


def _why_no_lead(name: str, universe: list, kb) -> str:
    """Why no archetype forms a valid team led by this character."""
    from gtc import validity
    from gtc.capabilities import load as load_caps
    from gtc.teams import fill_template

    reasons = []
    for t in kb.templates.values():
        if t.slots and not fill_template(t, universe, kb, limit=1, lead=name, rank_by="potential"):
            reasons.append(f"{t.label}: no full lineup with them leading")
    return "; ".join(reasons[:3]) if reasons else "no archetype's carry slot accepts them"


def run() -> list[CharacterAudit]:
    from gtc.capabilities import load as load_caps
    from gtc.pairmodel import load as load_pairs
    from gtc.report import build_universe, load_evidence
    from gtc.synergy import table
    from gtc.teams import fill_template

    kb = knowledge.load()
    game = gamedata.load_characters()
    ev = load_evidence(kb)
    universe = build_universe(kb, ev)
    in_universe = {m.key for m in universe}
    tbl = table()
    caps = load_caps()
    pm = load_pairs()
    carried: Counter = Counter()
    if tbl:
        for e in tbl.by_lineup.values():
            st = (e.get("profile") or {}).get("structure") or {}
            if st.get("type") in ("hypercarry", "dual_carry") and st.get("owners"):
                carried[st["owners"][0]] += 1
    sims: Counter = Counter()
    for s in ev.standard:
        for n in s.names:
            sims[n] += 1
    # Which archetypes form a valid team with each character, and which they lead.
    archetypes: dict[str, set[str]] = defaultdict(set)
    led: dict[str, set[str]] = defaultdict(set)
    for t in kb.templates.values():
        for team in fill_template(t, universe, kb, limit=60, rank_by="potential"):
            for m in team.members:
                archetypes[m].add(t.label)
            led[team.lead].add(t.label)
    # Characters who appear in no top lineup still might fit: ask per character.
    out = []
    for name in sorted(game):
        g = game[name]
        info = kb.characters.get(name)
        a = CharacterAudit(name, g.get("element", "?"), g.get("rarity", 0))
        a.roles = sorted(info.roles) if info else []
        a.sims, a.carried = sims[name], carried[name]
        tiers = ev.prydwen.get("tiers", {}).get(name, [])
        a.prydwen = "/".join(f"{e['overall']} {e['category']}" for e in tiers if e.get("overall"))
        if name in in_universe and name not in archetypes:
            for t in kb.templates.values():
                if fill_template(t, universe, kb, limit=1, must=name, rank_by="potential"):
                    archetypes[name].add(t.label)
        a.archetypes, a.led = sorted(archetypes.get(name, ())), sorted(led.get(name, ()))
        carry_roles = [r for r in a.roles if r.startswith("carry_") and r != "carry_unsimulated"]
        dps_rated = any(e.get("category") == "DPS" and e.get("overall") for e in tiers)
        unsimulated = info is not None and set(info.roles) <= {"carry_unsimulated"} | {r for r in info.roles if r.startswith("faction_")}
        if not info:
            (a.findings if a.sims else a.notes).append(
                "no roles at all: neither hand-written nor generated" + (f", although simulated in {a.sims} lineups" if a.sims else ""))
        elif name in in_universe and not a.archetypes:
            if unsimulated:
                a.notes.append("cannot evaluate (tier F): no simulations and no kit numbers yet; describe the kit in "
                               "knowledge/kits_provisional/ (or kits_custom/) to place them in teams")
            else:
                a.findings.append("appears in no valid team: " + _why_no_team(name, universe, kb))
        if carry_roles and info and name in in_universe and not a.led:
            for t in kb.templates.values():
                if fill_template(t, universe, kb, limit=1, lead=name, rank_by="potential"):
                    a.led.append(t.label)
            if not a.led:
                a.findings.append(f"has carry roles ({', '.join(carry_roles)}) but leads no valid team: "
                                  + _why_no_lead(name, universe, kb))
        if dps_rated and not carry_roles and info and not unsimulated:
            c = caps.get(name)
            if c and c.field_share >= 0.4 and c.damage_share < 0.3:
                a.notes.append(f"Prydwen rates them as DPS ({a.prydwen}); simulations show an on-field driver "
                               f"(on field {c.field_share:.0%} of the time, {c.damage_share:.0%} of team damage), so they lead no carry archetype")
            else:
                a.findings.append(f"Prydwen rates them as DPS ({a.prydwen}) but they have no carry role")
        if info is not None and getattr(info, "provisional", False):
            from gtc import kit_schema
            from gtc.provisional import kits

            kit = kits().get(name) or {}
            for problem in kit_schema.validate(name, kit, pm.chars if pm is not None else ()):
                a.findings.append("provisional kit invalid: " + problem.split(": ", 1)[1])
            if pm is not None and name in pm.chars:
                a.findings.append(f"provisional kit is stale: now simulated ({a.sims} lineups), so measured routes value them; "
                                  f"delete knowledge/kits_provisional/{name.lower()}.yaml")
            elif a.sims:
                # Better evidence exists, but the kit is still in use: the pair model has not been rebuilt with it.
                a.findings.append(f"provisional kit still in use although {a.sims} simulated lineups now exist; run "
                                  f"`python -m gtc derive` so the measured routes (simulation, interpolation) take over")
            else:
                a.notes.append(f"provisional kit (schema {kit.get('schema', 1)}, {kit.get('role', 'carry')}, analogue "
                               f"{kit.get('analogue')}): kit-model evidence, tier E")
        if a.sims >= 5 and name not in caps:
            a.findings.append("simulated but has no measured capability profile")
        if a.sims >= 5 and pm is not None and name not in pm.chars:
            a.findings.append("simulated but missing from the pair model")
        if carry_roles and a.sims >= 20 and a.carried == 0:
            a.findings.append(f"has carry roles but owns the damage in none of their {a.sims} simulated lineups")
        if not a.sims and info and not a.findings and not a.notes:
            a.notes.append("no simulations: judged from role rules only (evidence tier E)")
        out.append(a)
    return out


def render(audits: list[CharacterAudit]) -> str:
    flagged = [a for a in audits if a.findings]
    noted = [a for a in audits if a.notes and not a.findings]
    out = ["# Data audit", "", f"Engine model {params.version()} ({params.fingerprint()}).", "",
           f"{len(audits)} characters checked: {len(flagged)} with unexplained findings, {len(noted)} with explained gaps.", ""]
    if flagged:
        out += ["## Findings to fix", "",
                "| Character | Element | Simulated lineups | Owns damage in | Prydwen | Findings |", "|---|---|---|---|---|---|"]
        out += [f"| {a.name} | {a.element} | {a.sims} | {a.carried} | {a.prydwen or 'unrated'} | {' '.join(f'{f}.' for f in a.findings + a.notes)} |"
                for a in flagged]
        out.append("")
    else:
        out += ["No unexplained findings.", ""]
    if noted:
        out += ["## Explained gaps", "",
                "| Character | Element | Simulated lineups | Prydwen | Note |", "|---|---|---|---|---|"]
        out += [f"| {a.name} | {a.element} | {a.sims} | {a.prydwen or 'unrated'} | {' '.join(f'{n}.' for n in a.notes)} |" for a in noted]
    return "\n".join(out) + "\n"
