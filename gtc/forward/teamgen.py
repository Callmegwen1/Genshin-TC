"""Team generation from a kit's needs (rotation step 6): character kit -> what it wants -> who in the pool supplies
it -> candidate teams -> mechanical screen (TeamMechanics) -> forward calculation (generated rotation) -> ranking ->
substitutions. The forward model decides; the needs only narrow the search.

Needs read from the carry's kit:
    buffs      teammates whose effects reach the carry's damage element and types (buffs, RES shred, DMG taken)
    reactions  teammates whose element triggers the reactions the carry's own conditions ask for (Lohen's A4 wants a
               teammate's Cryo reaction: Hydro / Pyro / Electro / Anemo teammates)
    factions   a faction-count condition (Hexerei: Secret Rite) wants more members of that faction
    sustain    soft: a healer or shielder
Teammates are scored by how many needs they cover (weighted); the top few per need plus the best overall form the
pool; every trio from the pool is a candidate; TeamMechanics removes harm (field-time competition with the carry,
broken conditions); the cheapest pre-score (needs covered) keeps a shortlist for the forward model.

Phase J additions:
    REQUIRES   reactions, factions, battery (the kit's energy dependency), sustain
    BENEFITS   buffs and RES shred from the kit AND from the gear a teammate would realistically wear (an Anemo
               support's Viridescent Venerer shreds the carry's element; a Noblesse support buffs ATK), reaction
               amplification (EM buffs for a reaction carry)
    AVOIDS     aura interference (a teammate whose element reacts with the carry's in a way the carry's kit does not
               ask for, when it asks for specific reactions), wasted buffs (a teammate whose buffs do not reach the
               carry), competing field time and broken party restrictions (TeamMechanics; the last two remove a team)
The pair model only orders teams with equal coverage; it never removes a teammate the community has not simulated.
"""
from __future__ import annotations

from itertools import combinations

from gtc import mechanics as M

REACTS_WITH = {"Cryo": {"Hydro": "freeze", "Pyro": "melt", "Electro": "superconduct", "Anemo": "swirl-cryo"},
               "Pyro": {"Hydro": "vaporize", "Cryo": "melt", "Electro": "overloaded", "Anemo": "swirl-pyro"},
               "Hydro": {"Pyro": "vaporize", "Cryo": "freeze", "Electro": "electrocharged", "Anemo": "swirl-hydro"},
               "Electro": {"Pyro": "overloaded", "Cryo": "superconduct", "Hydro": "electrocharged", "Anemo": "swirl-electro"}}
BUFF_KINDS = {"atk", "atk_pct", "flat_dmg", "dmg_bonus", "elemental_dmg_bonus", "crit_rate", "crit_dmg", "em",
              "res_shred", "def_shred", "dmg_taken"}


def needs(carry: str) -> dict:
    from gtc.forward.effects import factions
    from gtc.kits import kit

    k = kit(carry) or {}
    dmg = (k.get("behavior") or {}).get("damage") or {}
    el = dmg.get("element") or M.element_of(carry)
    out = {"element": el, "damage_types": dmg.get("types") or [], "reactions": set(), "factions": {}, "sustain": True}
    for e in k.get("effects") or []:
        for c in e.get("conditions") or []:
            if c.get("type") == "reaction_required":
                out["reactions"] |= set(c.get("reactions") or [])
            if c.get("type") == "hexerei_count":
                out["factions"]["hexerei"] = c.get("min", 2)
            if c.get("type") == "faction_count":
                out["factions"][c["faction"]] = c.get("min", 2)
    for c in k.get("conditions") or []:
        if c.get("type") == "hexerei_count":
            out["factions"]["hexerei"] = c.get("min", 2)
    out["reactions"] = sorted(out["reactions"])
    dep = ((k.get("behavior") or {}).get("energy") or {}).get("dependency")
    out["battery"] = dep in ("high", "medium")
    # elements whose reaction with the carry's element the kit does not ask for (only when it asks for some)
    if out["reactions"]:
        fam = {r.split("-")[0] for r in out["reactions"]}
        out["avoid_elements"] = sorted(e for e, r in REACTS_WITH.get(el, {}).items()
                                       if r.split("-")[0] not in fam and e != "Anemo")
    else:
        out["avoid_elements"] = []
    return out


GEAR_SET_KINDS = {"res_shred": 1.5, "dmg_taken": 1.5, "atk_pct": 1.0, "em": 0.7, "dmg_bonus": 1.0,
                  "elemental_dmg_bonus": 1.0, "crit_rate": 1.0, "crit_dmg": 1.0}


def gear_supply(member: str, carry_element: str) -> tuple[float, str | None]:
    """The best party-reaching 4-piece set this teammate could wear for the carry: (weight, set)."""
    from gtc.forward.gear import set_effects
    from gtc.forward.standard import SETS_4PC

    best, which = 0.0, None
    el = M.element_of(member)
    for s in SETS_4PC:
        w = 0.0
        for e in set_effects(s, 4):
            if e.get("state") != "met" or e.get("target", "self") not in ("party", "party_others", "enemy", "active"):
                continue
            if e["kind"] not in GEAR_SET_KINDS:
                continue
            if e.get("element_from") == "swirl":
                if el != "Anemo" or carry_element not in ("Pyro", "Hydro", "Electro", "Cryo"):
                    continue
            else:
                els = (e.get("affects") or {}).get("elements")
                if els and carry_element not in els:
                    continue
            w += GEAR_SET_KINDS[e["kind"]]
        if w > best:
            best, which = w, s
    return best, which


def supplies(member: str, need: dict) -> dict[str, float]:
    """What `member` brings to a carry with these needs (weights)."""
    from gtc.forward.effects import factions
    from gtc.kits import kit

    k = kit(member) or {}
    got: dict[str, float] = {}
    el = need["element"]
    for e in k.get("effects") or []:
        if e.get("kind") not in BUFF_KINDS or e.get("target") == "self":
            continue
        els = (e.get("affects") or {}).get("elements") or ["all"]
        if "all" in els or el in els:
            got["buffs"] = got.get("buffs", 0.0) + (1.5 if e.get("kind") in ("res_shred", "dmg_taken") else 1.0)
    rx = REACTS_WITH.get(el, {}).get(M.element_of(member))
    if rx and (not need["reactions"] or rx in need["reactions"]):
        app = max((1.0 if a.get("mode") == "off_field" else 0.5) for a in (k.get("behavior") or {}).get("application") or [{"mode": "on"}])
        got["reactions"] = app
    for f in need["factions"]:
        if f in factions(member):
            got[f"faction:{f}"] = 1.0
    gw, gset = gear_supply(member, el)
    if gw:
        got["gear"] = round(gw, 2)
    if need.get("battery") and M.element_of(member) == el:
        got["battery"] = 0.5
    s = (k.get("behavior") or {}).get("sustain") or {}
    if s.get("heal") not in (None, "none", "unknown") or s.get("shield") not in (None, "none", "unknown"):
        got["sustain"] = 0.5
    return got


def evaluable(m: str) -> bool:
    """A character the forward model can play: a hand-written kit, or community simulations to measure actions from."""
    from gtc.forward.library import load_hand, source_lineups

    return load_hand(m) is not None or bool(source_lineups(m, n=1))


def candidate_teams(carry: str, pool: list[str], keep: int = 14, per_need: int = 4) -> tuple[list[dict], list[str]]:
    """(shortlisted teams, pool members that cannot be evaluated)."""
    from gtc.forward.generator import on_field_dealers
    from gtc.team_mechanics import analyse

    need = needs(carry)
    unplayable = sorted(m for m in pool if m != carry and not evaluable(m))
    scored = {m: supplies(m, need) for m in pool if m != carry and m not in unplayable}
    chosen = set()
    leaders = set()
    for key in {k for v in scored.values() for k in v}:
        # the best suppliers OF THIS NEED (then overall): a strong RES-shred teammate is not crowded out by generalists
        best = sorted((m for m in scored if key in scored[m]), key=lambda m: (-scored[m][key], -sum(scored[m].values())))[:per_need]
        chosen |= set(best)
        leaders |= set(best[:2])
    top = sorted(scored, key=lambda m: -sum(scored[m].values()))[:8]
    chosen |= set(top)
    teams = []
    try:
        from gtc.pairmodel import load as _load_pm

        pm = _load_pm()
    except Exception:
        pm = None
    for trio in combinations(sorted(chosen), 3):
        lineup = [carry, *trio]
        if len(on_field_dealers(lineup)) > 1 and on_field_dealers(lineup)[0] != carry:
            continue      # another on-field carry would take the window (the dual-carry search covers that question)
        tm = analyse(lineup)
        if [c for c in tm.harms() if c["kind"] in ("field_time", "condition")]:
            continue
        cover: dict[str, float] = {}
        for m in trio:
            for k, v in scored[m].items():
                cover[k] = cover.get(k, 0.0) + v
        avoid = []
        for m in trio:
            if M.element_of(m) in need.get("avoid_elements", []):
                avoid.append(f"{m}: {M.element_of(m)} reacts with {need['element']} in a way {carry}'s kit does not ask for")
            if not scored[m].get("buffs") and not scored[m].get("gear") and _has_buffs(m):
                avoid.append(f"{m}: buffs do not reach {carry}'s {need['element']} damage")
        pre = round(sum(cover.values()) - 0.5 * len(avoid), 2)
        prior = pm.predict(lineup, carry) if pm is not None else None
        teams.append({"lineup": lineup, "pre": pre, "covers": cover, "avoids": avoid, "pair_prior": prior})
    # coverage first; the pair model only breaks ties (unknown pairs are not penalised)
    teams.sort(key=lambda t: (-t["pre"], -(t["pair_prior"] or 0.0)))
    # diversity: every top supplier appears in at least two shortlisted teams, so the forward model decides
    short = teams[:keep]
    for m in list(dict.fromkeys(top + sorted(leaders))):
        have = sum(m in t["lineup"] for t in short)
        for t in teams:
            if have >= 2:
                break
            if m in t["lineup"] and t not in short:
                short.append(t)
                have += 1
    return short, unplayable


def _has_buffs(m: str) -> bool:
    from gtc.kits import kit

    return any(e.get("kind") in BUFF_KINDS and e.get("target") != "self" for e in (kit(m) or {}).get("effects") or [])


def run(carry: str, pool: list[str], keep: int = 10) -> dict:
    """Generate, theorycraft and rank teams for `carry` from `pool` (forward model on generated rotations)."""
    from gtc.forward.blind import theorycraft

    results = []
    shortlist, unplayable = candidate_teams(carry, pool, keep)
    for c in shortlist:
        try:
            r = theorycraft(c["lineup"])
        except Exception as e:  # a teammate without a library (no simulations and no hand kit) cannot be evaluated
            results.append({**c, "error": f"{type(e).__name__}: {e}"})
            continue
        results.append({**c, "result": r})
    ok = [x for x in results if "result" in x]
    ok.sort(key=lambda x: -x["result"]["evaluation"].dps)
    return {"needs": needs(carry), "ranked": ok, "failed": [x for x in results if "error" in x],
            "cannot_evaluate": unplayable, "shortlist": [x["lineup"] for x in shortlist]}


def substitutions(best: list[str], pool: list[str], carry: str, limit: int = 8) -> list[dict]:
    """Replace each teammate of `best` by pool members that cover a need, and calculate the change."""
    from gtc.forward.blind import theorycraft
    from gtc.forward.model import contributions

    base = theorycraft(best)
    b_ev = base["evaluation"]
    _, b_contrib = contributions(base["rotation"], info={"energy": b_ev.energy, "er_added": {}})
    need = needs(carry)
    out = []
    for slot in [m for m in best if m != carry]:
        alts = sorted((m for m in pool if m not in best and supplies(m, need) and evaluable(m)),
                      key=lambda m: -sum(supplies(m, need).values()))[:3]
        for alt in alts:
            team = [alt if m == slot else m for m in best]
            try:
                r = theorycraft(team)
            except Exception:
                continue
            ev = r["evaluation"]
            _, contrib = contributions(r["rotation"], info={"energy": ev.energy, "er_added": {}})
            lost = {k: v for k, v in b_contrib.items() if k.startswith(slot) and v > 0.005}
            gained = {k: v for k, v in contrib.items() if k.startswith(alt) and v > 0.005}
            out.append({"out": slot, "in": alt, "before": round(b_ev.dps), "after": round(ev.dps),
                        "change": round(ev.dps / b_ev.dps - 1, 3),
                        "own_share_out": round(b_ev.damage_share.get(slot, 0), 3),
                        "own_share_in": round(ev.damage_share.get(alt, 0), 3),
                        "carry_share": (round(b_ev.damage_share.get(carry, 0), 3), round(ev.damage_share.get(carry, 0), 3)),
                        "buffs_lost": lost, "buffs_gained": gained, "rotation": r["rotation"].source})
            if len(out) >= limit:
                return out
    return out
