"""Timeline effects (FM-3, FM-4): every kit effect becomes instances with a start, an end, an amount and a state, so
the model can answer "does this effect apply to this damage event?".

Sources: the structured kits (gtc/kits.py: reviewed > compiled > derived) for WHAT an effect is (kind, target,
affected elements / damage types / reactions, conditions), knowledge/forward/annotations.yaml for HOW to resolve it
(trigger, duration, amount from talent tables, quota), and the rotation for WHEN (the caster's actions, swirls).

Condition states (FM-4): met | partial | unmet | unknown. Unknown never earns credit: an effect whose condition,
amount, trigger or duration cannot be resolved is excluded from damage and listed with the reason, which widens the
uncertainty. Partial (a party-count condition below full) earns the partial amount (the kit's by-count schedule when
it has one, else the linear share).

Universal effects added here: elemental resonance (two or more members of an element), and Furina's Fanfare from a
party-HP model (Salon members drain HP, healing restores it, and every 1% of HP changed is one Fanfare).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

from gtc import KNOWLEDGE_DIR
from gtc.forward import data as D

ANNOTATIONS = KNOWLEDGE_DIR / "forward" / "annotations.yaml"
ACTION_TRIGGER = {"skill": "skill", "burst": "burst", "attack": "normal", "charge": "charged", "high_plunge": "plunge",
                  "low_plunge": "plunge", "plunge": "plunge", "dash": "dash", "aim": "charged"}
SALON = {"Usher": 0.024, "Chevalmarin": 0.016, "Crabaletta": 0.036}   # Furina skill table at level 9 (HP consumption)


@dataclass
class Instance:
    start: float
    end: float
    element: str | None = None  # the swirled element (element_from: swirl)


@dataclass
class TimedEffect:
    id: str
    caster: str
    kind: str
    target: str
    affects: dict
    amount: float | None
    state: str                       # met | partial | unmet | unknown
    instances: list[Instance] = field(default_factory=list)
    quota: int | None = None
    special: str = ""                # fanfare
    per_burst_cost: bool = False
    element_from: str = ""
    source: str = ""
    why: str = ""                    # reason when excluded or approximated
    dynamic: list = field(default_factory=list)   # per-hit conditions on the caster's state / resources (kit language)
    amount_resource: dict | None = None           # {resource, rate}: amount = rate x resource value at the hit
    gear: bool = False                            # a weapon or artifact-set effect (gtc/forward/gear.py)
    stack_max: int | None = None                  # stacking effects: amount x stacks at the hit
    stack_mode: str = "shared"                    # shared (each trigger refreshes all) | independent
    stack_duration: float = 0.0
    trigger_times: list = field(default_factory=list)
    stack_steps: list | None = None               # value by stack level (Mistsplitter 8/16/28%) instead of x stacks
    stack_sources: list = field(default_factory=list)   # [[Instance...], ...]: each active source is one stack level
    stack_threshold: int | None = None            # applies only at >= this many stacks (Kagura's 3-stack bonus)
    scale_stat: str | None = None                 # amount from the caster's stat: chained with buffs on the caster

    @property
    def active(self) -> bool:
        return self.state in ("met", "partial") and self.amount is not None and bool(self.instances)

    def at(self, t: float, element: str | None = None) -> Instance | None:
        """The instance active at t; for per-element effects (a swirled element), the one for `element`."""
        for i in self.instances:
            if i.start <= t < i.end and (element is None or i.element is None or i.element == element):
                return i
        return None


@lru_cache(maxsize=1)
def annotations() -> dict:
    return yaml.safe_load(ANNOTATIONS.read_text(encoding="utf-8")) if ANNOTATIONS.exists() else {}


@lru_cache(maxsize=256)
def factions(name: str) -> frozenset:
    """Faction / group membership from the official talent names: Moonsign (Nod-Krai) for a "Moonsign Benediction"
    passive, Hexerei for a "Witch's Eve Rite" passive. Overrides in annotations._factions."""
    out = set()
    try:
        names = [t["name"] for t in D.talent_entries(name)]
    except KeyError:
        names = []
    if any(n.startswith("Moonsign Benediction") for n in names):
        out.add("moonsign")
    if any(n.startswith("Witch's Eve Rite") for n in names):
        out.add("hexerei")
    for f, members in ((annotations().get("_factions") or {}) or {}).items():
        if name in (members or []):
            out.add(f)
    return frozenset(out)


def snapshot_types(name: str) -> set[str]:
    return set((annotations().get("_snapshot") or {}).get(name) or [])


def _patch(name: str, eff: dict) -> dict:
    for p in annotations().get(name) or []:
        if str(eff.get("source", "")).startswith(p["match"]) and (not p.get("kind") or p["kind"] == eff.get("kind")):
            return p
    return {}


def _table_value(name: str, spec: dict, level: int) -> float | None:
    kind, label = spec["table"]
    return D.value(name, kind, label, level, spec.get("index", 0))


def _caster_stat(build, stat: str) -> float:
    if stat == "base_atk":
        return build.stats.get("base_atk", 0.0)
    return build.total(stat)


_NUM = re.compile(r"([\d.]+)%\s+of\s+[\w' ]+?'s\s+(ATK|Max HP|HP|DEF|Elemental Mastery|EM|Energy Recharge)", re.I)
STAT_WORD = {"atk": "atk", "max hp": "hp", "hp": "hp", "def": "def", "elemental mastery": "em", "em": "em",
             "energy recharge": "er"}


def resolve_amount(name: str, eff: dict, patch: dict, build) -> tuple[float | None, str]:
    """(amount, note). Numbers stand; annotation specs are computed with the caster's build; simple text ("50% of
    Aino's Elemental Mastery") is parsed; anything else is unknown."""
    spec = patch.get("amount", eff.get("amount"))
    level = (build.talents or {}).get((spec or {}).get("table", ["skill"])[0], 9) if isinstance(spec, dict) and "table" in spec else 9
    if isinstance(spec, bool):
        return None, "amount unknown"
    if isinstance(spec, (int, float)):
        return float(spec), ""
    if isinstance(spec, dict):
        if "table" in spec:
            v = _table_value(name, spec, level)
            if v is None:
                return None, f"table value {spec['table']} not found"
            if spec.get("of"):
                v *= _caster_stat(build, spec["of"])
            if spec.get("cap_of"):   # e.g. Hu Tao's ATK increase, at most 400% of her base ATK
                v = min(v, spec["cap_of"]["rate"] * _caster_stat(build, spec["cap_of"]["of"]))
            return v, ""
        if "of" in spec:
            st = _caster_stat(build, spec["of"]) - spec.get("above", 0.0)
            v = max(st, 0.0) / spec.get("per", 1) * spec["rate"]
            return (min(v, spec["cap"]) if "cap" in spec else v), ""
    if isinstance(spec, str):
        m = _NUM.search(spec)
        if m:
            st = STAT_WORD.get(m.group(2).lower())
            return float(m.group(1)) / 100 * _caster_stat(build, st), "parsed from the kit text"
    return None, "amount not given as a number"


def _duration(name: str, eff: dict, patch: dict, build) -> float | str | None:
    d = patch.get("duration", eff.get("duration"))
    if isinstance(d, dict) and "table" in d:
        return _table_value(name, d, (build.talents or {}).get(d["table"][0], 9))
    if isinstance(d, (int, float)):
        return float(d)
    if isinstance(d, str) and d.lower() in ("permanent", "instant"):
        return d.lower()
    return None


def _triggers(name: str, eff: dict, patch: dict) -> list[str] | None:
    if patch.get("trigger"):
        return list(patch["trigger"])
    if str(eff.get("duration", "")).lower() == "permanent":
        return ["always"]
    kind = D.talent_kind(name, str(eff.get("source", "")))
    if kind in ("skill", "burst"):
        return [kind]
    src = str(eff.get("source", ""))
    entries = D.talent_entries(name)
    for t in entries:  # "(after <talent>)" in the source names the triggering talent
        if t["kind"] in ("skill", "burst") and t["name"] and t["name"].lower() in src.lower():
            return [t["kind"]]
    # a passive whose own text starts from a Skill or Burst ("After using the Elemental Burst Scoring Cuts, ...")
    own = next((t for t in entries if t["kind"] == "passive" and t["name"] and src.lower().startswith(t["name"].lower())), None)
    if own:
        text = re.sub(r"<[^>]+>|\{[^}]*\}", "", own["description"] or "")
        head = text.split(".")[0].lower()
        found = [t["kind"] for t in entries if t["kind"] in ("skill", "burst") and t["name"] and t["name"].lower() in head]
        if found:
            return found[:1]
        if "elemental burst" in head:
            return ["burst"]
        if "elemental skill" in head:
            return ["skill"]
    return None


DYNAMIC = ("state_active", "resource_at_least", "enemy_aura", "on_field")   # per hit


def state_at(rot, who: str, t: float) -> str | None:
    for m, name, a, b, *_ in (getattr(rot, "timeline", None) or {}).get("states", []):
        if m == who and a <= t < b:
            return name
    return None


def resource_at(rot, who: str, res: str, t: float):
    """The resource value at t (None when unknown or never set)."""
    v = None
    for tt, val in (getattr(rot, "timeline", None) or {}).get("resources", {}).get(f"{who}:{res}", []):
        if tt > t:
            break
        v = val
    return v


def dynamic_ok(e, rot, t: float) -> str:
    """met | unmet | unknown for an effect's per-hit conditions."""
    from gtc.forward.library import load_hand

    for c in e.dynamic:
        if c["type"] in ("enemy_aura", "on_field"):
            continue          # need the hit itself: checked in model.evaluate
        if c["type"] == "state_active":
            if state_at(rot, e.caster, t) != c["state"]:
                return "unmet"
        elif c["type"] == "resource_at_least":
            v = resource_at(rot, e.caster, c["resource"], t)
            if v is None:
                return "unknown"
            need = c.get("value")
            if need is None and "fraction" in c:
                lib = load_hand(e.caster)
                mx = ((lib.resources if lib else {}).get(c["resource"]) or {}).get("max")
                if not isinstance(mx, (int, float)):
                    return "unknown"
                need = c["fraction"] * mx
            if v < float(need):
                return "unmet"
    return "met"


def condition_state(cond: dict, lineup: list[str], rot) -> tuple[str, str]:
    """(state, note) for one effect condition, using the lineup and what the rotation shows."""
    from gtc.mechanics import element_of
    from gtc.team_mechanics import _effect_condition, _hexerei

    t = cond.get("type")
    if t == "faction_count":
        n = sum(cond["faction"] in factions(m) for m in lineup)
        return ("met" if n >= cond.get("min", 2) else "unmet"), f"{n} {cond['faction']} member(s)"
    if t == "hexerei_count":
        n = sum("hexerei" in factions(m) or m in _hexerei() for m in lineup)
        return ("met" if n >= cond.get("min", 2) else "unmet"), f"{n} Hexerei member(s)"
    if t == "reaction_required":
        want = cond.get("reactions") or []
        seen = {(h.reaction or h.amp or h.cata).lower() for h in rot.hits}
        if any(r in seen for r in want):
            return "met", "the reaction occurs in the rotation"
        els = {element_of(m) for m in lineup}
        if {"freeze"} & set(want) and {"Cryo", "Hydro"} <= els:
            return "met", "Cryo and Hydro both applied (Freeze estimated, not traced)"
        s = _effect_condition(cond, lineup, els - {None}, set())
        return ("met" if s == "met" else "unmet"), ("possible in this lineup (estimated)" if s == "met" else "the reaction cannot occur")
    s = _effect_condition(cond, lineup, {element_of(m) for m in lineup} - {None}, _hexerei())
    return s, ""


def _count(lineup, elements) -> int:
    from gtc.mechanics import element_of

    return sum(element_of(m) in elements for m in lineup)


def build_timeline(rot, builds: dict) -> list[TimedEffect]:
    """All effects of the lineup on this rotation."""
    from gtc.kits import kit

    lineup = rot.lineup
    out: list[TimedEffect] = []
    for name in lineup:
        k = kit(name) or {}
        b = builds[name]
        for i, eff in enumerate(k.get("effects") or []):
            patch = _patch(name, eff)
            te = TimedEffect(f"{name}:{i}", name, patch.get("kind", eff.get("kind")), patch.get("target", eff.get("target")),
                             patch.get("affects", eff.get("affects") or {}), None, "met", source=str(eff.get("source", "")),
                             special=patch.get("special", ""), per_burst_cost=bool((patch.get("amount") or {}).get("per_burst_cost")
                                                                                 if isinstance(patch.get("amount"), dict) else False),
                             element_from=patch.get("element_from", ""))
            # conditions
            notes, states = [], []
            for c in patch.get("conditions", eff.get("conditions") or []):
                if c.get("type") in DYNAMIC:
                    te.dynamic.append(c)      # resolved per hit from the rotation's state / resource timeline
                    continue
                s, note = condition_state(c, lineup, rot)
                states.append(s)
                if note:
                    notes.append(note)
            if "unmet" in states:
                te.state = "unmet"
            elif "unknown" in states:
                te.state = "unknown"
            elif "partial" in states:
                te.state = "partial"
            # amount
            if patch.get("by_count"):
                bc = patch["by_count"]
                n = _count(lineup, bc["elements"])
                te.amount = bc["values"][n - 1] if n >= 1 else 0.0
                te.state = "met" if n >= len(bc["values"]) else ("partial" if n else "unmet")
                notes.append(f"{n} of {len(bc['values'])} {'/'.join(bc['elements'])} members")
            elif isinstance(patch.get("amount"), dict) and "resource" in patch["amount"]:
                te.amount_resource = dict(patch["amount"])
                te.amount = float(patch["amount"].get("rate", 0.0))   # scaled per hit by the resource value
            elif te.special == "fanfare":
                te.amount = D.value(name, "burst", "Fanfare to DMG Increase Conversion Ratio", b.talents.get("burst", 9))
            else:
                te.amount, note = resolve_amount(name, eff, patch, b)
                if note:
                    notes.append(note)
                spec = patch.get("amount", eff.get("amount"))
                if isinstance(spec, dict) and spec.get("of") in ("atk", "hp", "def", "em") and not spec.get("cap_of") \
                        and "above" not in spec and "cap" not in spec:
                    te.scale_stat = spec["of"]   # Shenhe's Quill from her ATK: Bennett's buff on her counts
            if te.state == "partial" and not patch.get("by_count") and te.amount is not None:
                te.why = "partial condition"
            # quota
            q = patch.get("quota")
            if isinstance(q, dict):
                te.quota = int(_table_value(name, q, b.talents.get(q["table"][0], 9)) or 0) or None
            elif isinstance(q, int):
                te.quota = q
            # timing
            trig = _triggers(name, eff, patch)
            dur = _duration(name, eff, patch, b)
            if trig is None:
                te.state, notes = ("unknown" if te.state == "met" else te.state), notes + ["trigger unknown"]
            elif "always" in trig or dur == "permanent":
                te.instances = [Instance(0.0, rot.duration + 1)]
            else:
                if dur is None or dur == "instant":
                    te.state = "unknown" if te.state in ("met", "partial") else te.state
                    notes.append("duration unknown")
                else:
                    te.instances = _instances(rot, name, trig, float(dur), float(patch.get("delay", 0.0)))
            if te.amount is None and te.state in ("met", "partial"):
                te.state = "unknown"
            te.why = "; ".join(x for x in [te.why] + notes if x)
            out.append(te)
    out += resonance(rot, builds)
    from gtc.forward.gear import timeline as gear_timeline

    out += gear_timeline(rot, builds)       # weapon and artifact-set effects (phase H)
    return out


def trigger_starts(rot, name: str, trig: list[str], delay: float = 0.0) -> list[tuple[float, str | None]]:
    """When an effect of `name` starts, for each trigger kind:
        skill / burst / normal / charged / plunge   the caster's actions (Skill and Burst when the ability lands)
        swirl                                       the caster's swirls (per swirled element)
        reaction:<kind|kind>                        any occurrence of those reactions in the party
        reaction_own:<kind|kind|any>                reactions the caster triggers
        hit:<ability prefix>                        the caster's hits of that ability
        hittype:<normal|charged|...|elemental|any>  the caster's hits of those damage types (gear "on hit")"""
    starts: list[tuple[float, str | None]] = []
    for a in rot.actions:
        kind = ACTION_TRIGGER.get(a.action)
        if a.char == name and kind in trig:
            # a Skill or Burst effect starts when the ability lands (its first hit within 3 s of the cast), not at
            # the button press: Shenhe's field exists from the Burst's first hit
            land = a.t
            if kind in ("skill", "burst"):
                land = next((h.t for h in rot.hits if h.char == name and h.damage_type == kind and a.t <= h.t <= a.t + 3), a.t)
            starts.append((land + delay, None))
    if "swirl" in trig:
        for h in rot.hits:
            if h.char == name and h.reaction.startswith("swirl-"):
                starts.append((h.t, h.reaction.split("-", 1)[1].capitalize()))
    for tr in trig:
        if tr.startswith("reaction:") or tr.startswith("reaction_own:"):
            own = tr.startswith("reaction_own:")
            kinds = tr.split(":", 1)[1].split("|")
            for h in rot.hits:
                k = h.reaction or h.amp or h.cata
                if k and (not own or h.char == name) and ("any" in kinds or any(k.startswith(x) for x in kinds)):
                    starts.append((h.t + delay, None))
        if tr.startswith("hit:"):
            prefix = tr[4:]
            for h in rot.hits:
                if h.char == name and h.abil.startswith(prefix):
                    starts.append((h.t + delay, None))
        if tr.startswith("hittype:"):
            kinds = tr[8:].split("|")
            for h in rot.hits:
                if h.char != name or h.reaction:
                    continue
                if "any" in kinds or h.damage_type in kinds or ("elemental" in kinds and h.element not in ("Physical", "")):
                    starts.append((h.t + delay, None))
    if "swap_in" in trig or "swap_out" in trig:
        for i, (x, y, w) in enumerate(rot.segments):
            if "swap_in" in trig and w == name:
                starts.append((x + delay, None))
            if "swap_out" in trig and w == name and i + 1 < len(rot.segments):
                starts.append((y + delay, None))     # the next character takes the field (TTDS)
    starts.sort()
    return starts


def _instances(rot, name: str, trig: list[str], dur: float, delay: float, icd: float | None = None) -> list[Instance]:
    starts = trigger_starts(rot, name, trig, delay)
    out: list[Instance] = []
    last = -1e9
    for s, el in starts:  # a re-trigger refreshes (no stacking); a different swirled element is its own instance
        if icd and s - last < icd - 1e-9:
            continue
        last = s
        same = [i for i in out if i.element == el and i.start <= s < i.end]
        if same:
            same[-1].end = s + dur
        else:
            out.append(Instance(s, s + dur, el))
    return out


def resonance(rot, builds: dict) -> list[TimedEffect]:
    from collections import Counter

    from gtc.mechanics import element_of

    els = Counter(element_of(m) for m in rot.lineup)
    whole = [Instance(0.0, rot.duration + 1)]
    first_cryo = next((h.t for h in rot.hits if h.element == "Cryo" and h.mult), None)
    out = []
    if els["Pyro"] >= 2:
        out.append(TimedEffect("resonance:pyro", "resonance", "atk_pct", "party", {}, 0.25, "met", whole, source="Fervent Flames"))
    if els["Hydro"] >= 2:
        out.append(TimedEffect("resonance:hydro", "resonance", "hp_pct", "party", {}, 0.25, "met", whole, source="Soothing Water"))
    if els["Cryo"] >= 2:
        # +15% CRIT Rate against Cryo-affected or Frozen enemies: per hit, from the simulated aura when it lands
        out.append(TimedEffect("resonance:cryo", "resonance", "crit_rate", "party", {}, 0.15, "met",
                               [Instance(0.0, rot.duration + 1)], source="Shattering Ice",
                               dynamic=[{"type": "enemy_aura", "any": ["Cryo", "Frozen"]}],
                               why="against Cryo-affected or Frozen enemies (simulated aura per hit)"))
    if els["Dendro"] >= 2:
        out.append(TimedEffect("resonance:dendro", "resonance", "em", "party", {}, 50.0, "met", whole, source="Sprawling Greenery",
                               why="30 EM always, 20 after a Dendro reaction (assumed)"))
    # Moonsign (Nod-Krai): with 2+ Moonsign members the party is in Ascendant Gleam, and the best non-Moonsign member
    # adds a Lunar reaction DMG bonus from their stats (rule table: knowledge/kits.yaml _rules, Prydwen; gcsim applies
    # it too)
    moon = [m for m in rot.lineup if "moonsign" in factions(m)]
    if len(moon) >= 2:
        from gtc.tc.engine import load_kits

        rule = ((load_kits(generated=False).get("_rules") or {}).get("ascendant_gleam_non_moonsign") or {})
        best, who = 0.0, None
        for m in rot.lineup:
            if m in moon:
                continue
            spec = (rule.get("per_element") or {}).get(element_of(m))
            if spec:
                v = builds[m].total(spec["of"]) / spec.get("per", 1) * spec["rate"]
                v = min(v, rule.get("cap", 1.0))
                if v > best:
                    best, who = v, m
        if who:
            out.append(TimedEffect("moonsign:gleam", who, "reaction_bonus", "party", {"reactions": ["lunarcharged"]}, best,
                                   "met", whole, source="Ascendant Gleam (non-Moonsign member)",
                                   why=f"{len(moon)} Moonsign members; {who} contributes"))
    if els["Geo"] >= 2:
        out.append(TimedEffect("resonance:geo", "resonance", "dmg_bonus", "party", {}, 0.15, "unknown", whole,
                               source="Enduring Rock", why="needs a shield: not tracked yet"))
    return out


# ---------- Furina's Fanfare: a party-HP model ----------

def fanfare_curve(rot, builds: dict, timeline: list[TimedEffect]) -> list[tuple[float, float, int]]:
    """[(t, fanfare, members above 50% HP)] over the rotation. Salon members drain 2.4% / 1.6% / 3.6% of Max HP from every
    member above 50% HP per attack; heals in the timeline restore HP; each 1% of Max HP changed is one Fanfare, up
    to the table maximum. Fanfare resets at each Burst. HP persists across windows (no healer: the party sits at
    50% and the Salon stops draining)."""
    furina = next((e for e in timeline if e.special == "fanfare"), None)
    if furina is None:
        return []
    cap = D.value("Furina", "burst", "Maximum Fanfare", builds["Furina"].talents.get("burst", 9)) or 300
    hp = {m: 1.0 for m in rot.lineup}
    heals = [e for e in timeline if e.kind == "heal" and e.active]
    events: list[tuple[float, str, object]] = []
    for h in rot.hits:
        if h.char == "Furina":
            for k, pct in SALON.items():
                if k in h.abil:
                    events.append((h.t, "drain", pct))
    for e in heals:
        for inst in e.instances:
            t = inst.start
            while t < inst.end:
                events.append((t, "heal", e))
                t += 1.0
    # Fanfare starts from zero at every cast of the Burst (overlapping casts are merged into one timeline instance, so
    # the resets come from the casts themselves)
    casts = [a.t for a in rot.actions if a.char == "Furina" and a.action == "burst"]
    for t0 in (casts or [inst.start for inst in furina.instances]):
        events.append((t0, "reset", None))
    events.sort(key=lambda x: (x[0], x[1] != "reset"))
    fan, out = 0.0, []
    for t, kind, payload in events:
        if kind == "reset":
            fan = 0.0
        elif kind == "drain":
            for m in hp:
                if hp[m] > 0.5:
                    d = min(payload, hp[m] - 0.5 + 1e-9)
                    hp[m] -= d
                    fan += d * 100
        else:
            e = payload
            for m in hp:
                if e.target in ("party", "active") or m == e.caster:
                    restore = min(1.0 - hp[m], (e.amount or 0) / max(builds[m].total("hp"), 1.0))
                    hp[m] += restore
                    fan += restore * 100
        fan = min(fan, cap)
        out.append((t, fan, sum(v > 0.5 for v in hp.values())))
    return out


def fanfare_at(curve, t: float) -> float:
    v = 0.0
    for tt, f, _ in curve:
        if tt > t:
            break
        v = f
    return v


def above_half_at(curve, t: float, members: int = 4) -> int:
    """Party members above 50% HP at t (Salon Solitaire scales its members' damage 110% to 140% with this)."""
    v = members
    for tt, _, n in curve:
        if tt > t:
            break
        v = n
    return v
