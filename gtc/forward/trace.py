"""Rotations from gcsim (FM-2, rotation source A): a community rotation script, run by the local gcsim with house
builds, read back as an ordered list of actions, damage events, energy events and field segments.

What the trace supplies: the rotation itself (who acts when, swaps, how long it lasts), each hit's ability, timing,
element, damage type, talent multiplier and scaling stat, and which hits reacted (Melt, Vaporize, Aggravate...),
because gcsim simulated the auras. What it does NOT supply to the forward model: stats, buffs, debuffs, flat damage,
crit, DEF and RES. Those the forward model computes itself (gtc/forward/model.py). The same gcsim run's DPS is the
validation reference for that computation (gtc/forward/validate.py).

Approximation: hits that exist because of a teammate (Xingqiu's Rain Swords on Normal Attacks) or whose multiplier
already includes a stacking mechanic gcsim computed (Raiden's Resolve) are taken as they are in the trace; they are
flagged in `Rotation.notes` when known.
"""
from __future__ import annotations

import re
from collections import defaultdict, deque
from dataclasses import dataclass, field

FPS = 60
TAG = {1: "normal", 2: "charged", 3: "plunge", 4: "skill", 5: "skill", 6: "burst", 7: "weapon", 8: "burst", 9: "other"}
REACTION_ABIL = re.compile(r"^(swirl-|overload|superconduct|electrocharged|shatter|burning|bloom|hyperbloom|burgeon|"
                           r"lunarcharged|lunar|crystallize)", re.I)


@dataclass
class Action:
    t: float
    char: str
    action: str
    end: float = 0.0       # when the action's animation ends (generated rotations; 0 when unknown)
    earliest: float | None = None   # generated rotations: the start the measured transition allowed (before any wait)
    variant: str = ""               # generated rotations: the kit variant performed ("burst@symphony")


@dataclass
class Hit:
    t: float
    char: str
    abil: str
    damage_type: str          # normal | charged | plunge | skill | burst | weapon | reaction | other
    element: str              # Cryo, Hydro, ... Physical
    mult: float               # talent multiplier from the trace
    scaling: str              # atk | hp | def | em
    amp: str = ""             # melt | vaporize (the hit was amplified in the trace)
    cata: str = ""            # aggravate | spread
    reaction: str = ""        # transformative / lunar reaction damage (swirl-cryo, lunarcharged...)
    gcsim_damage: float = 0.0  # what gcsim dealt with its own stats and buffs (diagnostics only)
    ignore_def: bool = False   # Lunar direct damage and similar (DEF does not apply)
    gcsim_expected: float = 0.0  # gcsim's crit-averaged damage for this hit (diagnostics only)
    gauge: float = 0.0         # elemental units this hit applied (0: no application, e.g. inside its ICD)
    from_action: str = ""      # the action that produced it (attack, charge, skill, burst...): procs key on it
    gcsim_calc: dict = field(default_factory=dict, repr=False)  # gcsim's per-hit breakdown (diagnostics only)
    auras: tuple | None = None  # enemy auras present when the hit landed (the reaction simulator sets it; None: unknown)
    action_t: float | None = None  # when the owner's action that produced it started
    extra: tuple = ()          # further scaling terms ((mult, stat), ...): Nahida's Tri-Karma is ATK + EM


@dataclass
class Rotation:
    lineup: list[str]
    actions: list[Action]
    hits: list[Hit]
    duration: float
    energy: list[dict] = field(default_factory=list)
    segments: list[tuple[float, float, str]] = field(default_factory=list)   # (start, end, character on field)
    source: str = ""
    notes: list[str] = field(default_factory=list)
    timeline: dict = field(default_factory=dict)   # kit-language states and resources over time (engine.py)
    reactions: dict = field(default_factory=dict)  # reaction summary (reactions.summary) for generated rotations
    cycles: list = field(default_factory=list)     # generated rotations: (start time, first action index) per cycle

    def steady_window(self) -> tuple[float, float] | None:
        """Steady-state scoring window: from the second cycle's start to the last cycle's start (the first cycle
        starts with full energy and no buffs up; the last one's trailing damage has no time after it)."""
        if len(self.cycles) >= 3:
            return self.cycles[1][0], self.cycles[-1][0]
        return None

    def field_time(self) -> dict[str, float]:
        out: dict[str, float] = defaultdict(float)
        for a, b, who in self.segments:
            out[who] += b - a
        return dict(out)


def _element(s: str) -> str:
    s = (s or "").lower()
    return {"physical": "Physical", "": "Physical", "none": "Physical"}.get(s, s.capitalize())


def from_sample(sample: dict, key_to_name: dict[str, str], source: str = "") -> Rotation:
    """Parse a gcsim -sample log."""
    from gtc import gamedata

    names = gamedata.names()

    def resolve(n):
        return key_to_name.get(n) or names.character(n) or n

    members = [resolve(c["name"]) for c in sample["character_details"]]
    logs = sample["logs"]
    actions, hits, energy = [], [], []
    pending: dict[tuple, deque] = defaultdict(deque)
    applied: dict[tuple, deque] = defaultdict(deque)
    app_meta: dict[tuple, deque] = defaultdict(deque)
    for l in logs:
        if l.get("event") == "damage":
            lg = l["logs"]
            pending[(l.get("frame"), l.get("char_index"), lg.get("abil"))].append(lg)
        elif l.get("event") == "element" and l.get("msg") == "application":
            lg = l["logs"]
            applied[(l.get("frame"), l.get("char_index"), lg.get("abil"))].append(float(lg.get("dur") or 0) / 25.0)
            app_meta[(l.get("frame"), l.get("char_index"), lg.get("abil"))].append(
                (lg.get("applied_ele"), lg.get("attack_tag")))
    active, field_start, segments = None, 0.0, []
    last_action: dict[str, float] = {}
    end = 0.0
    for l in logs:
        ev, t = l.get("event"), (l.get("frame") or 0) / FPS
        idx = l.get("char_index", -1)
        who = members[idx] if 0 <= idx < len(members) else None
        end = max(end, t)
        if ev == "action" and who:
            act = l["logs"].get("action", "")
            if act == "swap":
                tgt = resolve(l["logs"].get("target"))
                if active is not None:
                    segments.append((field_start, t, active))
                active, field_start = tgt, t
                continue
            if active is None:
                active, field_start = who, t
            actions.append(Action(t, who, act))
            last_action[who] = t
            if act in ("skill", "burst"):
                last_action[(who, act)] = t
        elif ev == "calc" and who:
            lg = l["logs"]
            abil = lg.get("abil", "")
            q = pending.get((l.get("frame"), idx, abil))
            dmg = q.popleft() if q else {}
            tag = dmg.get("attack-tag")
            reaction = abil if REACTION_ABIL.match(abil) or (isinstance(tag, int) and tag >= 10) else ""
            lunar_direct = False
            if reaction and not REACTION_ABIL.match(abil) and float(lg.get("talent") or 0) > 0:
                # a reaction-tagged hit with its own talent multiplier is direct Lunar damage (Flins's Thunderous
                # Symphony, Ineffa's Birgitta A1): DEF ignored, it can crit, it scales with the talent
                reaction, lunar_direct = "", True
            scaling = "hp" if lg.get("use_hp") else "def" if lg.get("use_def") else "em" if lg.get("use_em") else "atk"
            hits.append(Hit(t=t, char=who, abil=abil,
                            damage_type="reaction" if reaction else ("lunar" if lunar_direct else TAG.get(tag, "other")),
                            element=_element(dmg.get("ele")), mult=float(lg.get("talent") or 0.0), scaling=scaling,
                            amp=str(dmg.get("amp") or ""), cata=str(dmg.get("cata") or ""), reaction=reaction,
                            gcsim_damage=float(lg.get("damage") or 0.0),
                            action_t=last_action.get((who, TAG.get(tag))) if TAG.get(tag) in ("skill", "burst") else last_action.get(who),
                            ignore_def=bool(lg.get("ignore_def")) and not reaction,
                            gcsim_expected=float((lg.get("avg_crit_dmg_react") if float(lg.get("react_mult") or 0) > 0
                                                  and lg.get("avg_crit_dmg_react") else lg.get("avg_crit_dmg"))
                                                 or lg.get("damage") or 0.0), gcsim_calc=lg,
                            gauge=(applied[(l.get("frame"), idx, abil)].popleft() if applied.get((l.get("frame"), idx, abil)) else 0.0)))
        elif ev == "energy" and who and l.get("msg") == "particle":
            lg = l["logs"]
            energy.append({"t": t, "char": who, "kind": "particle", "amount": float(lg.get("amt") or 0),
                           "count": float(lg.get("count") or 1),
                           "er": float(lg.get("ER") or 1.0), "source": lg.get("source"), "ele": _element(lg.get("ele")),
                           "active": bool(lg.get("is_active"))})
        elif ev == "energy" and who and l.get("msg") == "adding energy":
            lg = l["logs"]
            energy.append({"t": t, "char": who, "kind": "flat", "amount": float(lg.get("rec'd") or 0),
                           "source": lg.get("source")})
    if active is not None:
        segments.append((field_start, end, active))
    # applications without a damage event (Xingqiu's Rain Screen orbitals): zero-damage hits that apply their element,
    # so kits measured from traces keep them and the aura model sees them
    for (fr, idx, abil), q in applied.items():
        # damage hits consumed these applications from the front: the leftovers are the last entries
        meta = deque(list(app_meta.get((fr, idx, abil)) or [])[-len(q):]) if q else deque()
        who = members[idx] if isinstance(idx, int) and 0 <= idx < len(members) else None
        while q and who:
            units = q.popleft()
            ele, tag = meta.popleft() if meta else (None, None)
            if not units:
                continue
            hits.append(Hit(t=(fr or 0) / FPS, char=who, abil=str(abil), damage_type=TAG.get(tag, "other"),
                            element=_element(ele), mult=0.0, scaling="atk", gauge=units))
    hits.sort(key=lambda h: h.t)
    notes = _fill_table_multipliers(hits)
    rot = Rotation(members, actions, hits, end, energy, segments, source, notes)
    # idle as gcsim lived it: frames where the next action was refused (cooldown, energy, stamina, swap cooldown)
    # plus explicit waits - not inferred from gaps (a channelled Charged Attack is not idle)
    refused = {l.get("frame") for l in logs if l.get("event") == "sim" and str(l.get("msg", "")).startswith("could not execute")}
    waits = sum(float((l.get("logs") or {}).get("f") or 0) for l in logs
                if l.get("event") == "action" and l.get("msg") == "executed wait")
    rot.idle_s = round((len(refused) + waits) / FPS, 2)
    rot.idle_refused_s = round(len(refused) / FPS, 2)
    return rot


_WORDS = re.compile(r"[a-z]+")
_STOP = {"dmg", "damage", "of", "the", "a", "salon", "member", "skill", "hit"}


def _fill_table_multipliers(hits: list[Hit]) -> list[str]:
    """Some gcsim abilities carry their scaling inside flat damage (Furina's Salon members: talent multiplier 0, HP x
    ratio as flat damage). For those, the multiplier comes from the owner's Amber talent table: the label whose words
    all appear in the ability name ("Gentilhomme Usher DMG" for "Salon Member: Gentilhomme Usher"), with the kit's
    damage scaling stat. Unmatched hits keep multiplier 0 and are listed."""
    from gtc.forward import data as D
    from gtc.forward.build import scaling_stat

    notes, cache = [], {}
    for h in hits:
        if h.mult or h.reaction or not h.gcsim_damage:
            continue
        key = (h.char, h.abil)
        if key not in cache:
            words = set(_WORDS.findall(h.abil.lower())) - _STOP
            found = None
            for kind in ("skill", "burst", "normal"):
                for label, vals in D.table(h.char, kind).items():
                    lw = set(_WORDS.findall(label.lower())) - _STOP
                    if lw and lw <= words and vals:
                        found = (len(lw), vals[0]) if found is None or len(lw) > found[0] else found
            if found is None:  # an ability named after its talent ("Let the People Rejoice"): the first "... DMG" row
                for t in D.talent_entries(h.char):
                    if t["name"] and h.abil.startswith(t["name"]) and t["kind"] in ("skill", "burst"):
                        row = next((v for k, v in D.table(h.char, t["kind"]).items() if k.endswith("DMG") and v), None)
                        if row:
                            found = (0, row[0])
                            break
            cache[key] = found[1] if found else None
            if found is None:
                notes.append(f"{h.char}: {h.abil} has no talent multiplier in the trace or the tables")
        if cache[key]:
            h.mult = cache[key]
            h.scaling = scaling_stat(h.char) if h.scaling == "atk" else h.scaling
    return sorted(set(notes))


def house_config(lineup: list[str], er: dict[str, float] | None = None, builds: dict | None = None):
    """(gcsim text with house builds, key map, entry id) for a lineup's community rotation, or None when none
    exists. `er`: extra Energy Recharge per character on top of the house build (energy requirements). `builds`:
    META_STANDARD (realistic) builds to render instead of the neutral house build (weapons, refinements, sets)."""
    from gtc import gamedata
    from gtc.forward.build import gcsim_lines, meta_standard
    from gtc.sim import Keys, find_config, render

    cfg = find_config(lineup, gamedata.names())
    if cfg is None:
        return None
    text, _ = render(cfg, {}, Keys())
    keep = [l for l in text.splitlines() if not re.match(r"\s*\w+\s+(char|add)\b", l)]
    lines = []
    from dataclasses import replace as _replace

    from gtc.forward import standard as S

    for n, k in cfg.char_keys.items():
        if builds and n in builds and getattr(builds[n], "choice", None) is not None:
            b = _replace(builds[n])
            b.choice = builds[n].choice
            if er and er.get(n):
                b.artifacts = {**b.artifacts, "er": b.artifacts.get("er", 0.0) + er[n]}
            lines += S.gcsim_lines(k, b)
            continue
        b = meta_standard(n)
        if er and er.get(n):
            b.artifacts = {**b.artifacts, "er": b.artifacts.get("er", 0.0) + er[n]}
        lines += gcsim_lines(k, b)
    return "\n".join(lines + keep), cfg.char_keys, cfg.entry_id


ER_BUFFER = 1.1  # house ER target: 10% above the bare requirement (particle timing and Favonius are not exact)
AMPLE_ER = 3.0  # pass A: enough Energy Recharge that no Burst ever waits, so the rotation keeps its written shape


def house_trace(lineup: list[str], builds: dict | None = None) -> tuple[Rotation, dict] | None:
    """The community rotation for this lineup with house builds, in two passes (FM-7):
      A. run with ample ER: the rotation's shape and its particle schedule, from which each character's required
         ER follows (gtc/forward/energy.py);
      B. run with the house build plus the ER each character needs, with a 10% buffer (KQM convention: meet the
         requirement; the bare requirement stalls on particle timing):
         the rotation the forward model evaluates and the gcsim DPS it is validated against.
    Returns (rotation, info) with info = {"gcsim_dps", "gcsim_char_dps", "config", "energy", "er_added"}."""
    from gtc.forward.build import meta_standard
    from gtc.forward.energy import requirements
    from gtc.sim import run
    from gtc.synergy import run_sample

    hc = house_config(lineup, {n: AMPLE_ER for n in lineup})   # pass A: neutral builds (everyone on Favonius R1)
    if hc is None:
        return None
    text_a, keys, entry = hc
    inv = {v: k for k, v in keys.items()}
    rot_a = from_sample(run_sample(text_a, keep=True), inv)
    costs = {n: burst_cost(n) for n in lineup}
    req = requirements(rot_a, costs)
    added = {}
    if builds:
        # the same investment policy applied to this rotation: gear, main stats and substats re-chosen by the forward
        # model on the community rotation (traced with ample ER), every member meeting this rotation's ER need
        from gtc.forward.standard import optimise, refit

        from gtc.forward.standard import er_targets

        # independent of the blind builds: the same policy optimised from scratch on this rotation
        builds, _ = optimise(lineup, rot_a, None, None, passes=2, costs=costs)
        targets = er_targets(rot_a, builds, costs, ER_BUFFER)
        builds = refit(builds, targets)
        # energy that scales with ER (Raiden's restoration) is inflated in the ample-ER pass: when the realistic run is
        # slower than the rotation's shape, raise the ER of members whose Bursts came late, refit, and run again
        burst_a = _burst_times(rot_a)
        for _ in range(12):
            text, _, _ = house_config(lineup, None, builds)
            trial = from_sample(run_sample(text, keep=True), inv)
            if trial.duration <= 1.2 * rot_a.duration:
                break
            late = _late_bursts(burst_a, _burst_times(trial))
            if not late:
                break
            for n in late:
                targets[n] = min(2.6, max(targets.get(n) or builds[n].total("er"), builds[n].total("er")) + 0.2)
            builds = refit(builds, targets)
        text, _, _ = house_config(lineup, None, builds)
    else:
        for n in lineup:
            r = req.get(n, {}).get("required_er")
            have = meta_standard(n).total("er")
            if r and ER_BUFFER * r > have:
                added[n] = round(ER_BUFFER * r - have, 3)
        text, _, _ = house_config(lineup, added)
    rot = from_sample(run_sample(text, keep=True), inv, f"gcsim community rotation {entry} (house builds)")
    stalled = rot.duration > 1.2 * rot_a.duration      # the reference cannot keep its shape with these builds
    r = run(text)
    char_dps = {inv.get(k) or k: v for k, v in (r.character_dps or {}).items()}
    return rot, {"gcsim_dps": r.dps, "gcsim_dps_se": r.dps_se, "gcsim_char_dps": char_dps, "config": entry,
                 "error": r.error, "energy": req, "er_added": added, "builds": builds,
                 "reference_stalled": stalled, "shape_s": (round(rot_a.duration, 1), round(rot.duration, 1))}


def _burst_times(rot) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    for a in rot.actions:
        if a.action == "burst":
            out.setdefault(a.char, []).append(a.t)
    return out


def _late_bursts(ref: dict, trial: dict, tol: float = 1.0) -> list[str]:
    """Members whose k-th Burst comes later in `trial` than in `ref` by more than the team's overall slip plus
    `tol` seconds, the first to stall: everyone after them slips too, so the earliest delay names the culprit."""
    short = [n for n, ts in ref.items() if len(trial.get(n, [])) < len(ts)]
    first: dict[str, float] = {}
    for n, ts in ref.items():
        for k, t in enumerate(ts):
            if k < len(trial.get(n, [])) and trial[n][k] - t > tol:
                first[n] = min(first.get(n, 1e9), trial[n][k])
                break
            if k >= len(trial.get(n, [])):
                first[n] = min(first.get(n, 1e9), t)
                break
    if not first:
        return short
    earliest = min(first.values())
    return sorted(set(short) | {n for n, t in first.items() if t <= earliest + 2.0})


def burst_cost(name: str) -> float | None:
    from gtc.forward import data as D

    v = D.value(name, "burst", "Energy Cost")
    return float(v) if v else None
