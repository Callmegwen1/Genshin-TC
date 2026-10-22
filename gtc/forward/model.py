"""The forward damage model (FM-1, FM-10): expected damage for every event of a rotation, from builds and timeline
effects, with the game formulas of gtc/tc/formulas.py. Deterministic: crit is the expected value 1 + CR x CD.

Per damage event:
    stat      = base x (1 + stat% from build and buffs) + flat            (the hit's scaling stat)
    base dmg  = talent multiplier x stat + flat additive damage            (Icy Quill, Aggravate / Spread)
    direct    = base dmg x (1 + DMG%) x DEF multiplier x RES multiplier x crit x amplifier (Melt / Vaporize)
    swirl and other transformative: coefficient x level base x (1 + EM bonus + reaction bonus) x RES (no crit, no DEF)
    Lunar-Charged reaction: per contributor (Hydro and Electro members) by gtc/tc/formulas.lunar_reaction_hit,
                            weighted by the contributor weights (largest first)
    Lunar direct (DEF ignored in the trace): formulas.lunar_direct_hit

Buffs on buffs (Bennett buffing Shenhe's ATK before her Quill) are not chained: effect amounts use the caster's
build. Weapon passives and artifact sets are not in the house build by design.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from gtc.forward import data as D
from gtc.forward.build import ENEMY_RES, meta_standard
from gtc.forward.effects import (SALON, TimedEffect, above_half_at, build_timeline, dynamic_ok, fanfare_at, fanfare_curve,
                                 resource_at, snapshot_types)
from gtc.reactions import BY_KEY, LUNAR_MULT
from gtc.tc import formulas as F

ELEMENTS = ("Pyro", "Hydro", "Electro", "Cryo", "Anemo", "Geo", "Dendro", "Physical")
AMP = {("melt", "Pyro"): 2.0, ("melt", "Cryo"): 1.5, ("vaporize", "Hydro"): 2.0, ("vaporize", "Pyro"): 1.5}
CATA = {"aggravate": 1.15, "spread": 1.25}
STAT_KINDS = {"atk": "atk", "atk_pct": "atk_pct", "hp_pct": "hp_pct", "def_pct": "def_pct", "em": "em",
              "crit_rate": "cr", "crit_dmg": "cd"}


@dataclass
class EventResult:
    t: float
    char: str
    abil: str
    element: str
    damage_type: str
    reaction: str
    pre_mitigation: float
    damage: float
    buffs: list[str]
    debuffs: list[str]
    gcsim_damage: float
    detail: dict = field(default_factory=dict, repr=False)  # dmg_bonus, cr, cd, flat, res, stat (diagnostics)


@dataclass
class ForwardTeamEvaluation:
    lineup: list[str]
    rotation_source: str
    rotation_duration: float
    total_damage: float
    dps: float
    per_character: dict[str, float]
    damage_share: dict[str, float]
    per_reaction: dict[str, float]
    buff_contributions: dict[str, float]        # effect -> share of team damage lost without it
    condition_states: list[dict]
    field_time: dict[str, float]
    energy: dict[str, dict]
    unknown: list[str]
    coverage: float                             # share of damage from fully modelled events
    uncertainty: float                          # relative sd
    assumptions: list[str]
    events: list[EventResult] = field(default_factory=list, repr=False)
    confidence: str = ""                        # High / Medium / Low (phase L)
    uncertainty_detail: dict = field(default_factory=dict)

    def summary(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if k != "events"}


def _active_at(rot, t: float) -> str | None:
    for a, b, who in rot.segments:
        if a <= t < b:
            return who
    return rot.segments[-1][2] if rot.segments else None


def _was_active(rot, who: str, start: float, t: float) -> bool:
    """Was `who` on field at some point between start and t?"""
    return any(w == who and a < t and b > start for a, b, w in rot.segments)


def _receives(e: TimedEffect, receiver: str, active: str | None, rot=None, inst=None, t: float = 0.0) -> bool:
    if e.target in ("party", "matching_element_members"):
        return True
    if e.target == "party_others":
        return receiver != e.caster
    if e.target == "self":
        return receiver == e.caster
    if e.target == "active":
        # a buff on the on-field character stays on them as a status for the rest of the instance after they swap
        # out (how gcsim models Shenhe's field bonus and Bennett's ATK); in-game some fields drop it sooner
        return receiver == active or (rot is not None and inst is not None and _was_active(rot, receiver, inst.start, t))
    return False


def _filters(e: TimedEffect, element: str, damage_type: str, reaction: str, receiver_element: str | None) -> bool:
    aff = e.affects or {}
    els = aff.get("elements") or ["all"]
    if e.target == "matching_element_members":
        if receiver_element not in els:
            return False
    elif "all" not in els and element not in els:
        return False
    types = aff.get("damage_types") or ["all"]
    dt = "skill" if damage_type in ("skill",) else damage_type
    if "all" not in types:
        norm = {("summon" if t == "summon" else t) for t in types}
        if dt not in norm and not (dt == "skill" and "summon" in norm) and not (dt == "burst" and "summon" in norm):
            return False
    rx = aff.get("reactions")
    if rx and reaction and reaction not in rx and not any(reaction.startswith(r) for r in rx):
        return False
    return True


def _lunar_state(m: str, t: float, b, usable: list, rot) -> dict:
    """A Lunar-Charged contributor's EM, crit and Lunar bonuses at t, with the buffs active on them."""
    st = {"em": b.stats.get("em", 0.0), "cr": b.stats.get("cr", 0.0), "cd": b.stats.get("cd", 0.0), "react": 0.0, "base": 0.0}
    active = _active_at(rot, t)
    for e in usable:
        inst = e.at(t)
        if inst is None or not _receives(e, m, active, rot, inst, t):
            continue
        rx = (e.affects or {}).get("reactions")
        if e.kind == "em":
            st["em"] += e.amount
        elif e.kind == "crit_rate":
            st["cr"] += e.amount
        elif e.kind == "crit_dmg":
            st["cd"] += e.amount
        elif e.kind in ("reaction_bonus", "reaction_base") and (not rx or "lunarcharged" in rx):
            st["react" if e.kind == "reaction_bonus" else "base"] += e.amount
    return st


def evaluate(rot, builds: dict | None = None, exclude: frozenset = frozenset(), info: dict | None = None) -> ForwardTeamEvaluation:
    from gtc.mechanics import element_of

    if builds is None:
        from gtc.forward.build import house_builds

        builds = house_builds(rot.lineup, (info or {}).get("er_added"))
    from gtc.forward.reactions import annotate_auras

    annotate_auras(rot.hits, list(rot.lineup))        # traced rotations: aura per hit from the aura simulation
    timeline = build_timeline(rot, builds)
    fan = fanfare_curve(rot, builds, timeline)
    usable = [e for e in timeline if e.active and e.id not in exclude]
    chain_cache: dict = {}
    quota_left: dict[tuple, int] = {}
    quota_epoch: dict[tuple, float] = {}
    elements_of = {m: element_of(m) for m in rot.lineup}
    events: list[EventResult] = []
    unknown_dmg, approx_dmg = 0.0, 0.0
    dyn_unknown: set = set()
    for h in rot.hits:
        b = builds.get(h.char)
        if b is None:
            continue
        # a snapshotting hit sees the buffs (and the on-field character) of its owner's cast, not of the moment it lands
        t_eff = h.action_t if (h.action_t is not None and h.damage_type in snapshot_types(h.char)) else h.t
        active = _active_at(rot, t_eff)
        s = dict(b.stats)
        dmg_bonus = s.get(h.element, 0.0) + s.get("dmg_pct", 0.0)
        res = {el: ENEMY_RES for el in ELEMENTS}
        flat, react_bonus, base_bonus, def_shred = 0.0, 0.0, 0.0, 0.0
        base_mult = 1.0
        used_buffs, used_debuffs = [], []
        shared_seen: set = set()     # the same gear effect from two wearers (two Noblesse, two VV) does not stack
        for e in usable:
            if e.gear and e.target in ("party", "party_others", "enemy", "active"):
                gkey = (e.source, e.kind, tuple((e.affects or {}).get("elements") or ()), e.element_from)
                inst0 = e.at(h.t if e.kind in ("res_shred", "def_shred") else t_eff,
                             (h.element if e.element_from == "swirl" else None))
                if inst0 is not None:
                    if gkey in shared_seen:
                        continue
                    shared_seen.add(gkey)
            # only stats snapshot: enemy debuffs, flat additive damage and quota-limited effects apply when the hit lands
            when = h.t if (e.kind in ("res_shred", "def_shred", "dmg_taken", "flat_dmg") or e.quota) else t_eff
            want_el = None
            if e.element_from == "swirl":
                want_el = elements_of.get(h.char) if e.target == "matching_element_members" else h.element
            inst = e.at(when, want_el)
            if inst is None:
                continue
            if e.dynamic:
                hit_ok = True
                for c in e.dynamic:
                    if c["type"] == "enemy_aura":       # "against opponents affected by Cryo" (aura when the hit lands)
                        if h.auras is None:
                            if not h.reaction:          # reaction damage has no aura state of its own: not applicable
                                dyn_unknown.add(e.id)
                            hit_ok = False
                        elif not set(c["any"]) & set(h.auras):
                            hit_ok = False
                    elif c["type"] == "on_field":       # Golden Troupe's off-field bonus, Aubade's off-field Lunar bonus
                        if (_active_at(rot, h.t) == e.caster) != bool(c.get("value", True)):
                            hit_ok = False
                if not hit_ok:
                    continue
                ok = dynamic_ok(e, rot, when)
                if ok == "unknown":
                    dyn_unknown.add(e.id)
                if ok != "met":
                    continue
            el_ok = h.element
            if e.element_from == "swirl" and inst.element:
                if e.kind in ("elemental_dmg_bonus",) and h.element != inst.element:
                    continue
                if e.target == "matching_element_members" and elements_of.get(h.char) != inst.element:
                    continue
            if e.kind in ("res_shred", "def_shred"):
                if e.kind == "def_shred":
                    def_shred += e.amount
                else:
                    els = (e.affects or {}).get("elements") or ["all"]
                    for el in (ELEMENTS if "all" in els else els):
                        res[el] -= e.amount
                used_debuffs.append(e.id)
                continue
            if e.kind == "dmg_taken" and e.target == "enemy":  # Omen: the enemy takes more damage from every hit
                if not h.reaction:
                    dmg_bonus += e.amount
                    used_debuffs.append(e.id)
                continue
            if not _receives(e, h.char, active, rot, inst, t_eff):
                continue
            if e.kind in ("reaction_bonus", "reaction_base"):
                if h.reaction or h.ignore_def or h.amp or h.cata:
                    if _filters(e, el_ok, h.damage_type, h.reaction or h.amp or h.cata, elements_of.get(h.char)):
                        if e.kind == "reaction_bonus":
                            react_bonus += e.amount
                        else:
                            base_bonus += e.amount
                        used_buffs.append(e.id)
                continue
            if h.reaction and e.kind not in ("em",):
                continue
            if not _filters(e, el_ok, h.damage_type, "", elements_of.get(h.char)):
                continue
            if e.quota:
                key = (e.id, h.char)
                if quota_epoch.get(key) != inst.start:
                    quota_epoch[key], quota_left[key] = inst.start, e.quota
                if quota_left[key] <= 0:
                    continue
                quota_left[key] -= 1
            amount = e.amount
            if e.scale_stat and amount:
                amount *= _chain(e, inst.start, usable, builds, rot, chain_cache)
            if e.amount_resource:
                v = resource_at(rot, e.caster, e.amount_resource["resource"], when)
                if v is None:
                    dyn_unknown.add(e.id)
                    continue
                steps = e.amount_resource.get("steps")
                if steps:     # stack-indexed values (Neuvillette's 110% / 125% / 160%)
                    amount = steps[min(int(v), len(steps)) - 1] if v >= 1 else 0.0
                else:
                    amount = e.amount * v
            if e.stack_max or e.stack_sources or e.stack_threshold:
                from gtc.forward.gear import amount_at

                amount = amount_at(e, when)
                if amount is None:
                    continue
            if e.special == "fanfare":
                amount = e.amount * fanfare_at(fan, h.t)
            if e.per_burst_cost:
                from gtc.forward.trace import burst_cost

                amount = e.amount * (burst_cost(h.char) or 0.0)
            if e.kind in STAT_KINDS:
                key = STAT_KINDS[e.kind]
                s[key] = s.get(key, 0.0) + amount
            elif e.kind == "atk":
                s["atk"] = s.get("atk", 0.0) + amount
            elif e.kind in ("dmg_bonus", "elemental_dmg_bonus", "dmg_taken"):
                dmg_bonus += amount
            elif e.kind == "flat_dmg":
                flat += amount
            elif e.kind == "base_multiplier":
                base_mult *= amount if amount else 1.0
            else:
                continue
            used_buffs.append(e.id)
        stat_total = {st: s.get(f"base_{st}", 0.0) * (1 + s.get(f"{st}_pct", 0.0)) + s.get(st, 0.0) for st in ("atk", "hp", "def")}
        stat_total["em"] = s.get("em", 0.0)
        em = s.get("em", 0.0)
        cr, cd = s.get("cr", 0.0), s.get("cd", 0.0)
        r_el = res.get(h.element, ENEMY_RES)
        reaction = h.reaction or h.amp or h.cata
        if h.reaction.startswith("swirl-"):
            el = h.reaction.split("-", 1)[1].capitalize()
            pre = BY_KEY[h.reaction].coefficient * F.reaction_base(90) * (1 + F.em_transformative(em) + react_bonus)
            dmg = pre * F.res_mult(res.get(el, ENEMY_RES))
        elif h.reaction in ("lunarcharged",):
            # every Hydro and Electro member contributes with their own EM, crit and Lunar bonuses at this moment;
            # contributions are weighted largest first (formulas.LUNAR_CONTRIBUTOR_WEIGHTS). Tier-4 approximation:
            # the per-contributor scale does not yet match gcsim (Moonsign level mechanics), so it counts as unknown
            parts = []
            for m in rot.lineup:
                if elements_of[m] not in ("Hydro", "Electro"):
                    continue
                st = _lunar_state(m, h.t, builds[m], usable, rot)
                parts.append(F.lunar_reaction_hit(90, st["em"], st["react"], st["base"], st["cr"], st["cd"], r_el))
            parts.sort(reverse=True)
            dmg = sum(w * p for w, p in zip(F.LUNAR_CONTRIBUTOR_WEIGHTS, parts))
            pre = dmg
            approx_dmg += dmg  # contributor set and weights approximated (validated within ~10% on the Flins team)
        elif h.reaction:
            key = h.reaction.split("-")[0]
            coef = BY_KEY.get(key).coefficient if BY_KEY.get(key) else 0.0
            pre = coef * F.reaction_base(90) * (1 + F.em_transformative(em) + react_bonus)
            dmg = pre * F.res_mult(r_el)
            if not coef:
                unknown_dmg += h.gcsim_damage
        elif h.ignore_def:
            stat = stat_total.get(h.scaling, 0.0)
            dmg = F.lunar_direct_hit(h.mult, stat, em, react_bonus, base_bonus, cr, cd, r_el)
            pre = dmg / F.res_mult(r_el) / F.crit_avg(cr, cd)
        else:
            stat = stat_total.get(h.scaling, 0.0)
            mult = h.mult
            if h.char == "Furina" and any(k in h.abil for k in SALON):
                # Salon Solitaire: members' DMG is 100% + 10% per party member above 50% HP (from the party-HP model)
                mult *= 1 + 0.1 * above_half_at(fan, h.t, len(rot.lineup))
            base = (mult * stat + sum(m * stat_total.get(s, 0.0) for m, s in (getattr(h, "extra", ()) or ()))) * base_mult + flat
            if h.cata in CATA:
                base += CATA[h.cata] * F.reaction_base(90) * (1 + F.em_additive(em) + react_bonus)
            pre = base * (1 + dmg_bonus)
            amp = 1.0
            if h.amp:
                amp = AMP.get((h.amp, h.element), 1.5) * (1 + F.em_amplifying(em) + react_bonus)
            dmg = pre * F.def_mult(90, def_shred=def_shred) * F.res_mult(r_el) * F.crit_avg(cr, cd) * amp
        events.append(EventResult(h.t, h.char, h.abil, h.element, h.damage_type, reaction, pre, dmg, used_buffs,
                                  used_debuffs, h.gcsim_damage,
                                  {"dmg_bonus": dmg_bonus, "cr": cr, "cd": cd, "flat": flat, "res": r_el,
                                   "stat": stat_total.get(h.scaling, 0.0), "em": em}))
    # steady state (generated rotations): damage landing between the second and the last cycle start, over that time
    win = rot.steady_window() if hasattr(rot, "steady_window") else None
    scored = [e for e in events if win[0] <= e.t < win[1]] if win else events
    total = sum(e.damage for e in scored)
    per_char: dict[str, float] = defaultdict(float)
    per_react: dict[str, float] = defaultdict(float)
    for e in scored:
        per_char[e.char] += e.damage
        if e.reaction:
            per_react[e.reaction] += e.damage
    unknown = [f"{e.caster}: {e.source} ({e.state}{'; ' + e.why if e.why else ''})" for e in timeline
               if not e.active and e.kind not in ("heal", "shield", "interruption", "infusion", "other", "cooldown", "energy")]
    others = [f"{e.caster}: {e.source} (kind '{e.kind}' not modelled)" for e in timeline
              if e.kind == "other" and e.state != "unmet"]
    others += [f"{e.caster}: {e.source} (depends on a state or resource whose value is unknown: no credit)"
               for e in timeline if e.id in dyn_unknown]
    unknown_hits = sum(1 for h in rot.hits if "[resource bonus unknown]" in h.abil)
    if unknown_hits:
        others.append(f"{unknown_hits} hits carry a resource-scaled multiplier whose resource is unknown (counted without it)")
    cond = [{"effect": e.id, "caster": e.caster, "source": e.source, "kind": e.kind, "state": e.state,
             "amount": None if e.amount is None else round(e.amount, 4), "note": e.why} for e in timeline]
    dur = max((win[1] - win[0]) if win else rot.duration, 1e-6)
    coverage = 1 - unknown_dmg / total if total else 0.0
    sd = 0.05 + 0.02 * len(unknown) + 0.01 * len(others) + 0.25 * (1 - coverage) + 0.10 * (approx_dmg / total if total else 0)
    out = ForwardTeamEvaluation(
        list(rot.lineup), rot.source, round(dur, 2), total, total / dur, dict(per_char),
        {k: v / total for k, v in per_char.items()} if total else {}, dict(per_react), {}, cond,
        {k: round(v, 1) for k, v in rot.field_time().items()}, _energy(info, builds), unknown + others,
        round(coverage, 3), round(min(sd, 0.6), 3),
        ["META_STANDARD builds (Favonius weapons, no sets, KQM-style substats, ER to requirement + 10%)",
         "enemy level 100, 10% RES, single target", "talents 9/9/9, C0",
         "rotation and reaction outcomes taken from the gcsim trace; stats, buffs, conditions and damage computed here",
         "buffs on buffs chained one level (a caster's buffed stat when the effect starts)"],
        events)
    from gtc.forward.uncertainty import assess

    detail = assess(rot, out)
    out.uncertainty, out.confidence, out.uncertainty_detail = detail["sd"], detail["confidence"], detail
    if any(getattr(b, "choice", None) is not None for b in builds.values()):
        from gtc.forward.standard import ASSUMPTIONS

        out.assumptions = ASSUMPTIONS + out.assumptions[2:]
    return out


def _chain(e: TimedEffect, t: float, usable: list, builds: dict, rot, cache: dict) -> float:
    """Buffs on buffs: the caster's stat when the effect starts, with the stat buffs active on the caster then
    (Bennett's ATK on Shenhe before her Quill), over the build stat the amount was computed from. One level deep."""
    key = (e.id, round(t, 3))
    if key in cache:
        return cache[key]
    b = builds.get(e.caster)
    if b is None:
        return 1.0
    stat = e.scale_stat
    s = dict(b.stats)
    active = _active_at(rot, t)
    for f in usable:
        if f is e or f.scale_stat or f.dynamic or f.stack_max or f.stack_sources or f.special:
            continue
        if f.kind not in STAT_KINDS and f.kind != "atk":
            continue
        aff = f.affects or {}
        if aff.get("damage_types") or (aff.get("elements") and "all" not in aff["elements"]):
            continue
        inst = f.at(t)
        if inst is None or not _receives(f, e.caster, active, rot, inst, t) or f.amount is None:
            continue
        k = STAT_KINDS.get(f.kind, "atk")
        s[k] = s.get(k, 0.0) + f.amount
    if stat == "em":
        now, base = s.get("em", 0.0), b.stats.get("em", 0.0)
    else:
        now = s.get(f"base_{stat}", 0.0) * (1 + s.get(f"{stat}_pct", 0.0)) + s.get(stat, 0.0)
        base = b.total(stat)
    cache[key] = now / base if base else 1.0
    return cache[key]


def _energy(info: dict | None, builds: dict) -> dict:
    from gtc.forward.energy import status

    out = {}
    for m, r in ((info or {}).get("energy") or {}).items():
        er = builds[m].total("er") if m in builds else None
        out[m] = {**r, "er": round(er, 3) if er else None, "status": status(r.get("required_er"), er or 0.0)}
    return out


def contributions(rot, builds: dict | None = None, info: dict | None = None) -> tuple[ForwardTeamEvaluation, dict[str, float]]:
    """The evaluation plus each active effect's contribution: the share of team damage lost when it is removed."""
    if builds is None:
        from gtc.forward.build import house_builds

        builds = house_builds(rot.lineup, (info or {}).get("er_added"))
    base = evaluate(rot, builds, info=info)
    tl = build_timeline(rot, builds)
    out = {}
    for e in tl:
        if e.active:
            without = evaluate(rot, builds, exclude=frozenset({e.id}), info=info).total_damage
            if base.total_damage:
                out[f"{e.caster}: {e.source}"] = round(1 - without / base.total_damage, 4)
    base.buff_contributions = dict(sorted(out.items(), key=lambda kv: -kv[1]))
    return base, base.buff_contributions
