"""Identity v2: what a team is, independent of the template that generated it (phase 8).

Identity answers "whose team is it, and what does it run on", from measurements:
  primary actor   the most probable top damage dealer (gtc/structure.py), when the team is built around a carry
  structure       the most probable damage structure, plus its on-field / quickswap patterns
  systems         every mechanic with a centrality between 0 and 1 (multi-label), and the full signal vector behind it
  central         mechanics with centrality at least CENTRAL; incidental: present but below
  label           built from the above ("Raiden Shogun on-field · incidental Hyperbloom")

Centrality is not "reaction damage at least 35%". Each mechanic has measured signals, each normalised by a scale
(knowledge/model.yaml `identity.scales`), and the v1 aggregate is their maximum:
  reaction_damage    share of team damage the reaction deals (transformative and Lunar reactions)
  carry_amplified    share of the main damage dealer's own damage on amplified hits (Vaporize, Melt)
  team_amplified     share of team damage on amplified hits
  catalyzed          share of team damage on Aggravate / Spread hits
  aura_at_hit        share of team damage dealt while the aura is on the target (Frozen for Freeze, Quicken)
  conditioned_buffs  share of team damage from buffs that need the reaction (mechanics.conditioned_buffs: kit reactions.requires)
  trigger_rate       reactions triggered per 10 s, all members
So Freeze is central with no Freeze damage at all (Ayaka teams deal half their damage into Frozen targets), Vaporize
through the carry's amplified hits, and Chevreuse's Overloaded through her conditioned buffs. The signal vector is
stored whole, so the aggregate can become mechanic-specific later.

Simulated lineups use their own measurements. Unsimulated lineups get signals averaged over simulated lineups
that share at least two members (weight NEIGHBOUR_BASE per shared member), and a mechanic whose elements the team
lacks gets no signal at all.
"""
from __future__ import annotations

from collections import defaultdict
from itertools import combinations

from gtc import params

SCALES = params.get("identity.scales")
CENTRAL = params.get("identity.central")
INCIDENTAL = params.get("identity.incidental")
NEIGHBOUR_BASE = params.get("capabilities.neighbour_base")
AURA_MECHANICS = {"frozen": "freeze", "quicken": "quicken"}
STRUCTURE_WORDS = {"hypercarry": "hypercarry", "dual_carry": "dual carry", "driver": "driver", "reaction_core": "reaction core",
                   "distributed": "spread damage"}

_SIGNALS: dict[frozenset, dict] | None = None
_PAIR_INDEX: dict[frozenset, list] | None = None
_CACHE: dict = {}


def signals_from_profile(prof: dict, entry: dict | None = None) -> dict[str, dict[str, float]]:
    """{mechanic: {signal: raw value}} measured in one simulated lineup."""
    from gtc.mechanics import conditioned_buffs

    out: dict[str, dict[str, float]] = defaultdict(dict)
    for k, v in (prof.get("reaction_damage") or {}).items():
        out[k]["reaction_damage"] = v
    members = prof.get("members") or {}
    for amp, v in (prof.get("amplified") or {}).items():
        out[amp]["team_amplified"] = v
        dealers = [m for m, d in members.items() if d.get("damage_share", 0) >= 0.2]
        out[amp]["carry_amplified"] = max((members[m].get("amplified_share", 0.0) for m in dealers), default=0.0)
    for k, v in (prof.get("catalyzed") or {}).items():
        out[k]["catalyzed"] = v
    for aura, mech in AURA_MECHANICS.items():
        v = (prof.get("aura_at_hit") or {}).get(aura, 0.0)
        if v:
            out[mech]["aura_at_hit"] = v
    rates: dict[str, float] = defaultdict(float)
    for d in members.values():
        for k, v in (d.get("triggers") or {}).items():
            rates[k] += v
    from gtc.reactions import kind_of

    for k, v in rates.items():
        mech = kind_of(k) if k not in ("vaporize", "melt") else k
        out[mech]["trigger_rate"] = v
    if entry is not None:
        for m, mech in conditioned_buffs().items():
            if m in members:
                out[mech]["conditioned_buffs"] = (entry.get("buffs_shapley") or {}).get(m, 0.0)
    return {k: dict(v) for k, v in out.items()}


def _measured() -> dict[frozenset, dict]:
    global _SIGNALS, _PAIR_INDEX
    if _SIGNALS is None:
        from gtc.synergy import table

        tbl = table()
        _SIGNALS, _PAIR_INDEX = {}, defaultdict(list)
        for names, e in (tbl.by_lineup.items() if tbl else []):
            prof = e.get("profile")
            if prof and len(names) == 4:
                _SIGNALS[names] = signals_from_profile(prof, e)
                for pair in combinations(sorted(names), 2):
                    _PAIR_INDEX[frozenset(pair)].append(names)
    return _SIGNALS


def predicted_signals(lineup, elements: dict[str, str], exclude: frozenset | None = None) -> dict[str, dict[str, float]]:
    """Signals for an unsimulated lineup, mechanic by mechanic: the weighted mean over simulated lineups that share
    at least two members, can perform the mechanic, and use no character outside this lineup for its elements (a
    Raiden team with Yaoyao learns nothing about Hyperbloom from Raiden teams whose Dendro is Nahida). A mechanic
    whose elements the lineup lacks, or with no such neighbour, gets no signal."""
    from gtc.reactions import mechanic_elements

    measured = _measured()
    key = frozenset(lineup)
    near: dict[frozenset, int] = {}
    for pair in combinations(sorted(key), 2):
        for names in _PAIR_INDEX.get(frozenset(pair), []):
            if names != exclude and names != key:
                near[names] = len(names & key)
    if not near:
        return {}
    game = _element_of()

    def el(n):
        return elements.get(n) or game.get(n, "?")

    have = {el(m) for m in key}
    mechanics = {mech for names in near for mech in measured[names]}
    out = {}
    for mech in sorted(mechanics):
        need = ("Cryo", "Hydro") if mech == "freeze" else mechanic_elements(mech)
        if not need or not set(need) <= have:
            continue
        mine = {m for m in key if el(m) in need}
        totals: dict[str, float] = defaultdict(float)
        weight = 0.0
        for names, shared in near.items():
            holders = {m for m in names if el(m) in need}
            if not holders <= mine or not set(need) <= {el(m) for m in names}:
                continue  # an outside holder of a needed element, or a neighbour that cannot perform the mechanic
            w = NEIGHBOUR_BASE ** (shared - 2)
            weight += w
            for sname, v in measured[names].get(mech, {}).items():
                totals[sname] += w * v
        if weight:
            out[mech] = {sname: v / weight for sname, v in totals.items()}
    # No qualifying neighbour: the members' own average reaction ownership (capability profiles), gated the same way.
    from gtc.capabilities import load as load_caps

    caps = load_caps() or {}
    for mech in {k for m in key if m in caps for k in caps[m].reaction_damage}:
        if mech in out:
            continue
        need = mechanic_elements(mech)
        if need and set(need) <= have:
            v = sum(caps[m].reaction_damage.get(mech, 0.0) for m in key if m in caps)
            if v > 0:
                out[mech] = {"reaction_damage": v, "from_capabilities": 1.0}
    return out


OWNER_SHARE = params.get("identity.owner_share")


_MOONSIGN: dict[int, set] = {}
_ELEMENTS: dict[str, str] | None = None


def _element_of() -> dict[str, str]:
    global _ELEMENTS
    if _ELEMENTS is None:
        from gtc import gamedata

        _ELEMENTS = {k: v.get("element", "?") for k, v in gamedata.load_characters().items()}
    return _ELEMENTS


def moonsign(ev) -> set[str]:
    """Characters with Moonsign: from kit data and Prydwen's faction tags. Lunar reactions need one."""
    if id(ev) not in _MOONSIGN:
        from gtc.tc.engine import load_kits

        kits = load_kits()
        _MOONSIGN[id(ev)] = ({n for n, v in kits.items() if (v or {}).get("moonsign")}
                             | {n for n, tags in ev.factions.items() if "moonsign" in tags})
    return _MOONSIGN[id(ev)]


def system_owners(lineup, mech: str, prof: dict | None, ev) -> list[str]:
    """Whose mechanic it is. Lunar reactions belong to the Moonsign members who give the team access to them (a
    non-Moonsign carry such as Clorinde triggers Lunar-Charged but does not own it). Amplifying reactions belong to
    whoever's hits are amplified; other reactions to whoever triggers at least OWNER_SHARE of their damage. Auras
    (Freeze, Quicken) have no single owner."""
    from gtc.reactions import BY_KEY, channel_of

    r = next((x for x in BY_KEY.values() if mech in (x.key, channel_of(x))), None)
    if r is not None and r.cls == "lunar":
        return sorted(m for m in lineup if m in moonsign(ev))
    if prof is None:
        return []
    members = prof.get("members") or {}
    if mech in ("vaporize", "melt"):
        return sorted(m for m, d in members.items() if d.get("amplified_share", 0) >= OWNER_SHARE and d.get("damage_share", 0) >= 0.2)
    total = sum((d.get("reaction_damage") or {}).get(mech, 0.0) for d in members.values())
    if total <= 0:
        return []
    return sorted(m for m, d in members.items() if (d.get("reaction_damage") or {}).get(mech, 0.0) / total >= OWNER_SHARE)


def centrality(signals: dict[str, float]) -> float:
    """v1 aggregate: the largest normalised signal (1 = fully central)."""
    return max((min(1.0, v / SCALES[s]) for s, v in signals.items() if s in SCALES and SCALES[s] > 0), default=0.0)


def identify(lineup, ev, structure: dict | None = None, measured: bool | None = None) -> dict:
    """The team's identity."""
    from gtc.reactions import mechanic_name
    from gtc.structure import carry_probability

    key = frozenset(lineup)
    if key in _CACHE:
        return _CACHE[key]
    if structure is None:
        from gtc.evaluate import structure_of

        structure, measured = structure_of(key, ev)
    if measured is None:
        measured = key in _measured()
    sig = _measured().get(key) if measured else None
    if sig is None:
        elements = {m: _element_of().get(m, "?") for m in key}
        sig = predicted_signals(key, elements)
        source = "predicted"
    else:
        source = "measured"
    systems = {mech: round(centrality(s), 3) for mech, s in sig.items()}
    central = sorted((m for m, c in systems.items() if c >= CENTRAL), key=lambda m: -systems[m])
    incidental = sorted((m for m, c in systems.items() if INCIDENTAL <= c < CENTRAL), key=lambda m: -systems[m])
    st = structure or {}
    pc = carry_probability(st)
    primary = st.get("primary") or {}
    actor = max(primary, key=lambda m: (primary[m], m)) if primary else None
    actor = actor if actor and pc >= 0.5 and primary.get(actor, 0) >= 0.5 else None
    kind = st.get("type")
    pattern = st.get("patterns") or {}
    driver = st.get("owners", [None])[0] if kind == "driver" and st.get("owners") else None
    if actor:
        word = "on-field" if pattern.get("on_field_carry", 0) >= 0.5 else STRUCTURE_WORDS.get(kind, "")
        if kind == "dual_carry":
            second = sorted(primary, key=lambda m: -primary[m])[1] if len(primary) > 1 else None
            head = f"{actor} and {second}" if second and primary.get(second, 0) >= 0.2 else actor
            word = "dual carry"
        else:
            head = actor
    else:
        head, word = ("No single carry", STRUCTURE_WORDS.get(kind, "")) if kind else ("Team", "")
    parts = [f"{head} {word}".strip()]
    prof = ev.measured_profile(key) if source == "measured" else None
    owners = {m: system_owners(key, m, prof, ev) for m in central}
    if central:
        named = []
        for m in central:
            who = owners.get(m) or []
            if actor and who and actor not in who:
                named.append(f"{mechanic_name(m)} from {' and '.join(who)}")
            else:
                named.append(mechanic_name(m))
        parts.append(" + ".join(named))
    if incidental:
        parts.append("incidental " + ", ".join(mechanic_name(m) for m in incidental[:2]))
    out = {"primary_actor": actor, "primary_probability": round(primary.get(actor, 0.0), 3) if actor else 0.0,
           "driver": driver, "structure": kind, "carry_probability": round(pc, 3),
           "systems": systems, "signals": {m: {k: round(v, 4) for k, v in s.items()} for m, s in sig.items()},
           "central": central, "incidental": incidental, "owners": owners, "label": " · ".join(parts), "source": source}
    _CACHE[key] = out
    return out
