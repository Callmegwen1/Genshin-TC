"""Rotation generator (rotation step 2): build plausible rotations for a lineup from its kits and action libraries,
with no access to that lineup's own simulations, and let the forward model score them.

The theorycrafter's template, generalised:
    1. Supports set up: each casts their Skill and Burst (in the order their library shows they prefer, follow-ups
       included: Kazuha's plunge after his Skill), respecting cooldowns and energy.
    2. Carry window: the carry casts Skill and Burst (both orders are candidates), then repeats their filler unit
       (their usual on-field action string), re-casting their Skill whenever it is off cooldown, until the period ends.
    3. Optional refresh: supports whose Skill is off cooldown mid-window re-cast it once (a candidate flag).
    The cycle repeats; the period is the team's longest Burst cooldown among on-field damage dealers (at least 15 s).

Candidates: every order of the supports x carry Skill/Burst order x refresh on/off x the carry's filler strings.
No ordering rule is imposed (the forward model's score decides; Swirl supports may go first and swirl the previous
cycle's aura, as theorycrafters often play them). Each is generated
over CYCLES cycles and evaluated by gtc/forward/model.py; the best is returned with the others.

Energy: particles per Skill from the library (same element 3 / other 1 energy, x0.6 off field, the receiver's ER),
plus the house enemy drop (one neutral particle every 10 s) and Favonius procs (expected 1.8 particles per 12 s per
holder). A Burst that is not affordable waits for energy (the rotation gets longer), as a player would.

Reactions here: Swirl and Anemo absorption take the most recent swirlable element applied by the team (an aura
rule; the full reaction model is step 4). Amplifying and catalyze reactions are not generated yet.
"""
from __future__ import annotations

import os
import time
from functools import lru_cache
from dataclasses import replace, dataclass
from itertools import permutations

from gtc.forward import data as D
from gtc.forward.trace import Action, Hit, Rotation

CYCLES = 6               # generated cycles; the score is steady state over cycles 2..5 (Rotation.steady_window)
SWAP_DELAY = 0.2         # seconds per character swap (12 frames: the swap_delay of the community gcsim configs)
ER_BUFFER, ER_CAP = 1.1, 2.6   # build ER = 1.1 x requirement; above 2.6 ER a rotation is not realistic
SWIRLABLE = ("Pyro", "Hydro", "Electro", "Cryo")
DROP_EVERY, FAV_EVERY = 12.0, 12.0   # random enemy drops (gcsim: every 480-720 f): the slowest interval, so a
                                     # planned Burst never depends on a lucky drop
FAV_ICD = [12.0, 10.5, 9.0, 7.5, 6.0]          # Favonius proc cooldown by refinement (Amber text)
FAV_CHANCE = [0.6, 0.7, 0.8, 0.9, 1.0]         # proc chance by refinement: 3 particles x chance per proc


@lru_cache(maxsize=None)
def _chain_length(char: str) -> int:
    import re as _re

    return sum(1 for k in D.table(char, "normal") if _re.match(r"^\d+-Hit DMG", k))


def _stamina_delay() -> float:
    from gtc.forward import frames as FR

    return FR.stamina_regen_delay(STAMINA_DELAY)


def favonius(build) -> tuple[float, float] | None:
    """(cooldown, chance) of a member's Favonius procs (Amber text: "CRIT Hits have a 60% chance to generate a small
    amount of Elemental Particles ... once every 12s", by refinement): the neutral house build wears Favonius R1; a
    standard build only when its weapon is a Favonius weapon; otherwise None."""
    gear = getattr(build, "gear", None) or {}
    if not gear:
        return FAV_ICD[0], FAV_CHANCE[0]
    if not str(gear.get("weapon", "")).startswith("Favonius"):
        return None
    i = max(0, min(5, int(gear.get("refine", 1))) - 1)
    return FAV_ICD[i], FAV_CHANCE[i]


FAV_PARTICLES = 3        # elementless particles per proc (6 Energy on field)
STAMINA_MAX = 240.0      # party stamina pool
STAMINA_REGEN = 25.0     # per second (gcsim stam_post: 25/s)
STAMINA_DELAY = 1.5      # fallback; the measured delay from the stamina action's start (frames.stamina_regen_delay)
DASH_STAMINA = 18.0


def stamina_cost(char: str, action: str) -> float:
    """Stamina an action uses: the Charged Attack cost from the Amber talent table, a dash 18; else nothing."""
    if action == "dash":
        return DASH_STAMINA
    if action == "charge":
        v = D.value(char, "normal", "Charged Attack Stamina Cost")
        return float(v) if v else 0.0
    return 0.0


@dataclass
class Plan:
    supports: tuple
    carry_first: str      # "skill" | "burst" (which opens the window) | "skill_only" (the carry's Burst is not used)
    refresh: str          # "" (none) | "mid" (halfway through the window) | "after_burst" (while the carry's Burst works)
    filler: tuple = ()
    carries: tuple = ()   # one carry, or two: each gets their own field window in turn (a dual-carry plan)
    period: float = 0.0   # the cycle length when chosen explicitly (0: the team's default cycle)
    bursts: tuple = ()    # per-member Burst schedule ((member, every), ...): 1 every cycle, 2 every second cycle,
                          # 0 never; members not listed Burst every cycle (when funded)
    support_policy: str = "wait"   # "event": supports are called in from the timeline's state (Skill ready and its
                          # effect over, Burst due and funded); otherwise: "wait" for a cooldown (up to 3 s), "defer" one that is
                          # not ready and cast it inside the carry window when it is, "recast" every support Skill
                          # whenever ready inside the carry window (between the carry's strings)
    protect_state: bool = False   # keep the driver on field while a state of theirs that a swap would end is
                          # running (Raiden's Musou Isshin): the window extends and support visits wait
    family: str = "standard"   # "quickswap": no long driver - each member takes a short turn in order

    def burst_on(self, member: str, cycle: int) -> bool:
        every = dict(self.bursts).get(member, 1)
        return bool(every) and cycle % every == 0


def _cd(name: str, kind: str) -> float:
    tab = D.table(name, kind)
    for label in ("CD", "Press CD", "Skill CD"):
        if label in tab and tab[label]:
            return float(tab[label][0])
    return 15.0 if kind == "burst" else 8.0


def on_field_dealers(lineup: list[str]) -> list[str]:
    """Members whose own damage needs them on field (kit behaviour), largest damage role first."""
    from gtc.kits import kit

    rank = {"carry": 3, "sub_dps": 2, "incidental": 1, "none": 0}
    xs = [m for m in lineup if (kit(m) or {}).get("behavior", {}).get("on_field_damage") is True]
    return sorted(xs, key=lambda m: -rank.get((kit(m) or {}).get("behavior", {}).get("damage_ownership"), 0))


def roles(lineup: list[str]) -> tuple[str, list[str]]:
    """(carry, supports) from the kits: the on-field damage dealer with the largest damage role."""
    from gtc.kits import kit

    rank = {"carry": 3, "sub_dps": 2, "incidental": 1, "none": 0}
    best = max(lineup, key=lambda m: ((kit(m) or {}).get("behavior", {}).get("on_field_damage") is True,
                                      rank.get((kit(m) or {}).get("behavior", {}).get("damage_ownership"), 0)))
    return best, [m for m in lineup if m != best]


def _support_key(m: str) -> int:
    """Swirl supports last (they swirl the aura the others applied), everyone else first."""
    from gtc.kits import kit

    return 1 if "swirl_support" in ((kit(m) or {}).get("roles") or []) else 0


from gtc.forward.engine import KitMixin


class _Sim(KitMixin):
    def __init__(self, lineup, libs, builds):
        from gtc.mechanics import element_of

        self.lineup, self.libs, self.builds = lineup, libs, builds
        self.el = {m: element_of(m) for m in lineup}
        self.t = 0.0
        self.energy = {m: D.value(m, "burst", "Energy Cost") or 0.0 for m in lineup}   # start full (as gcsim)
        self.cost = dict(self.energy)
        self.ready = {(m, k): 0.0 for m in lineup for k in ("skill", "burst")}
        self.actions: list[Action] = []
        self.hits: list[Hit] = []
        self.energy_log: list[dict] = []
        self.segments: list[tuple] = []
        self.last_applied: list[tuple[float, str]] = []
        self.fav = {m: favonius(builds[m]) for m in lineup}
        self.next_drop = DROP_EVERY
        self.fav_ready = {m: 0.0 for m in lineup}
        self.last_swap = -1e9
        self.stamina, self.stamina_t, self.stamina_used = STAMINA_MAX, 0.0, -1e9
        self.stamina_waited = 0.0
        self.fav_none = {m: 1.0 for m in lineup}       # chance no proc happened since the cooldown ended
        self.fav_deferred: list = []
        self.fav_half: dict = {}
        self.waited = 0.0
        self.chain = {m: 0 for m in lineup}       # next Normal Attack in the chain
        self.states: dict[str, list] = {m: [] for m in lineup}   # [{name, start, end, uses}]
        self.icd: dict[tuple, list] = {}          # (char, group) -> [hits counted, timer start]
        self.level_until: dict[str, float] = {}   # talent-level bonus window end per character
        self.pending: list[tuple] = []            # particles in flight: (land time, owner, count, element, spawn time)
        self.on_field = lineup[0]
        for m in [x for x in lineup if x in libs]:
            for attr in ("resources", "rules", "summons", "procs"):
                if not hasattr(libs[m], attr):
                    setattr(libs[m], attr, {} if attr != "rules" else [])
        self._kit_init()

    def _aura(self, t: float) -> str | None:
        """The element a Swirl or an Anemo absorption takes at t. Stopgap aura rule until the reaction model: Cryo
        and Hydro both applied in the last 6 s means a Frozen enemy, which swirls as Cryo; else the latest element."""
        recent = {el for tt, el in self.last_applied if t - 6.0 <= tt <= t}
        if {"Cryo", "Hydro"} <= recent:
            return "Cryo"
        for tt, el in reversed(self.last_applied):
            if tt <= t:
                return el
        return None

    def _particles(self, owner: str, n: float, element: str | None, t: float, receiver_active: str,
                   spawn: float | None = None):
        for m in self.lineup:
            base = (3.0 if element and self.el[m] == element else 1.0 if element else 2.0) * n
            base *= 1.0 if m == receiver_active else 0.6
            er = self.builds[m].total("er")
            self.energy[m] = min(self.cost[m], self.energy[m] + base * er)
            self.energy_log.append({"t": t, "char": m, "kind": "particle", "amount": base * er, "er": er,
                                    "ele": element or "neutral", "active": m == receiver_active, "spawn": spawn,
                                    "count": n, "source": owner})

    def _tick_passive_energy(self, upto: float, active: str):
        while self.next_drop <= upto:
            self._particles("drop", 1.0, None, self.next_drop, active)
            self.next_drop += DROP_EVERY


    def state(self, who: str, t: float):
        """The most recent active state (characters can hold several at once)."""
        act = [s for s in self.states.get(who, []) if s["start"] <= t < s["end"]]
        return act[-1] if act else None

    def active_states(self, who: str, t: float) -> list[str]:
        return [s["name"] for s in self.states.get(who, []) if s["start"] <= t < s["end"]]

    def _key(self, who: str, key: str) -> str:
        """The variant key for an action: "burst@symphony" while that state is active (latest state first)."""
        lib = self.libs[who]
        for name in reversed(self.active_states(who, self.t)):
            k = f"{key}@{name}"
            if lib.entry(k):
                cap = (lib.action_meta.get(k) or {}).get("uses_per_state")
                st = self._state_obj(who, name)
                if cap is not None and st is not None and st["uses"].get(k, 0) >= int(cap):
                    continue        # the state's variant is spent (Thunderous Symphony once per window)
                return k
        return key

    def _frame_key(self, a) -> str:
        """The measured-frames name of a performed action: a reduced-cost Burst variant has its own frames."""
        v = getattr(a, "variant", "") or ""
        if a.action == "burst" and "@" in v:
            meta = self.libs[a.char].action_meta.get(v) or {}
            if "energy_cost" in meta and float(meta["energy_cost"]) < self.cost.get(a.char, 0.0) - 1e-6:
                return "burst~partial"
        return a.action

    def _state_obj(self, who: str, name: str):
        return next((s for s in reversed(self.states.get(who, [])) if s["name"] == name and s["start"] <= self.t < s["end"]),
                    None)

    def _entry(self, who: str, key: str):
        """The library entry for an action, using the state-specific variant ("attack#2@masterstroke") while the
        character is in that state."""
        return self.libs[who].entry(self._key(who, key))

    def cost_of(self, who: str, action: str) -> float:
        meta = self.libs[who].action_meta.get(self._key(who, action)) or {}
        return float(meta["energy_cost"]) if "energy_cost" in meta else self.cost[who]

    def can(self, who: str, action: str) -> bool:
        key = self._key(who, action)
        meta = self.libs[who].action_meta.get(key) or self.libs[who].action_meta.get(action) or {}
        for other, secs in ((meta.get("unavailable_after") or {}).items()):
            last = next((a.t for a in reversed(self.actions) if a.char == who and a.action == other), None)
            if last is not None and self.t < last + float(secs) - 1e-6:
                return False
        need = meta.get("requires_state")
        if need:
            st = next((s for s in self.states.get(who, []) if s["name"] == need and s["start"] <= self.t < s["end"]), None)
            if not st or st["uses"].get(action, 0) >= meta.get("uses_per_state", 99):
                return False
        if action in ("skill", "burst") and self.libs[who].hand:
            if (self.ready.get((who, key), 0.0) if key != action else self.ready[(who, action)]) > self.t + 1e-6:
                return False
            if action == "burst" and self.energy[who] < self.cost_of(who, action) - 1e-6:
                return False
        rr = meta.get("requires_resource")
        if rr:
            v = self.res.get((who, rr["resource"]))
            if v is None or v < float(rr.get("at_least", 0)):
                return False
        return self._entry(who, action) is not None

    def emit(self, hit, proc: bool = False):
        """Every hit goes through here: recorded, then hit events and procs are dispatched."""
        self.hits.append(hit)
        self._favonius(hit)
        if hit.damage_type in ("normal", "charged") and hit.mult and not hit.reaction and hit.char == self.on_field:
            from gtc.forward import frames as FR

            r = FR.naca_energy(hit.char)       # measured flat energy per Normal / Charged hit (gcsim core rule)
            if r:
                self.energy[hit.char] = min(self.cost[hit.char], self.energy[hit.char] + r)
                self.energy_log.append({"t": hit.t, "char": hit.char, "kind": "flat", "amount": r,
                                        "source": "na-ca-on-hit", "ele": None, "active": True, "spawn": hit.t})
        self.dispatch({"event": "hit", "char": hit.char, "t": hit.t, "damage_type": hit.damage_type, "element": hit.element})
        if not proc:
            n = len(self.hits)
            self._procs_on_hit(hit)
            for extra in self.hits[n:]:
                self.dispatch({"event": "hit", "char": extra.char, "t": extra.t, "damage_type": extra.damage_type,
                               "element": extra.element})

    def _stamina_regen(self, t: float) -> None:
        start = max(self.stamina_t, self.stamina_used + _stamina_delay())
        if t > start:
            self.stamina = min(STAMINA_MAX, self.stamina + STAMINA_REGEN * (t - start))
        self.stamina_t = max(self.stamina_t, t)

    def _favonius(self, hit) -> None:
        """Favonius from the wearer's own damaging hits: after the cooldown each hit crits with the build's CRIT
        Rate and then procs with the refinement's chance; the expected proc lands at the hit where the chance of
        having procced passes one half. 3 elementless particles, about a second later."""
        f = self.fav.get(hit.char)
        if not f or not hit.mult or hit.reaction:
            return
        # resolved when the hit LANDS, in time order: a summon's later ticks are not on-field hits
        self.fav_deferred.append(hit)

    def _flush_favonius(self, upto: float) -> None:
        """Favonius for hits that landed up to `upto`: gcsim procs it only while the wearer is the active character
        (4396 of 4396 logged procs), on a crit (build CRIT Rate x refinement chance, expected at the half-way hit)."""
        due = sorted((h for h in self.fav_deferred if h.t <= upto), key=lambda h: h.t)
        if not due:
            return
        self.fav_deferred = [h for h in self.fav_deferred if h.t > upto]
        for hit in due:
            f = self.fav[hit.char]
            if hit.t < self.fav_ready[hit.char] or self._active_at(hit.t) != hit.char:
                continue
            self._favonius_roll(hit, f)

    def _active_at(self, t: float) -> str:
        for a, b, w in reversed(self.segments):
            if a <= t:
                return w
        return self.on_field

    def _favonius_roll(self, hit, f) -> None:
        """Expected value: each eligible hit adds its share of the proc probability as particles; the window closes
        once the proc is near certain (95%), its cooldown counted from the hit where it passed one half."""
        w = hit.char
        p = min(1.0, self.builds[w].stats.get("cr", 0.05)) * f[1]
        before = 1 - self.fav_none[w]
        self.fav_none[w] *= (1 - p)
        after = 1 - self.fav_none[w]
        self.pending.append((hit.t + 1.0, f"favonius-{w}", FAV_PARTICLES * (after - before), None, hit.t))
        if before < 0.5 <= after:
            self.fav_half[w] = hit.t
        if after >= 0.95:
            # a closed window means the proc happened: credit the remaining probability so every closed window yields
            # exactly one proc (found by the metamorphic test: more CRIT Rate closed windows earlier with less credit)
            self.pending.append((hit.t + 1.0, f"favonius-{w}", FAV_PARTICLES * (1 - after), None, hit.t))
            self.fav_ready[w] = self.fav_half.get(w, hit.t) + f[0]
            self.fav_none[w] = 1.0

    def _gauge(self, who: str, h, t: float) -> float:
        if not h.icd or h.icd == "none":
            return h.gauge
        k = (who, h.icd)          # "standard", or a named group with the same 3-hit / 2.5 s rule (a summon's own)
        n, t0 = self.icd.get(k, [0, -99.0])
        if t - t0 >= 2.5:
            n, t0 = 0, t
        g = 1.0 if n % 3 == 0 else 0.0
        self.icd[k] = [n + 1, t0]
        return g

    def _mult(self, who: str, h, t: float) -> float:
        """The hit's multiplier at the build's talent level for its table (kit files store level 9), plus a temporary
        level bonus while active (Lohen's When the Mood Strikes)."""
        if not h.table:
            return h.mult
        level = int((getattr(self.builds.get(who), "talents", None) or {}).get(h.table[0], 9))
        lb = self.libs[who].level_bonus
        if lb and h.table[0] == lb.get("table") and t < self.level_until.get(who, -1):
            level += int(lb.get("amount", 0))
        if level == 9:
            return h.mult
        v = D.value(who, h.table[0], h.table[1], level, h.table[2] if len(h.table) > 2 else 0)
        return v or h.mult

    def act(self, who: str, action: str) -> bool:
        lib = self.libs[who]
        if lib.hand and not self.can(who, action if action != "attack" else f"attack#{self.chain[who]}"):
            if action != "attack" or not self.can(who, "attack#0"):
                return False
        if action == "attack":
            e = self._entry(who, f"attack#{self.chain[who]}")
            if e is None:
                self.chain[who] = 0
                e = self._entry(who, "attack#0")
        else:
            e = self._entry(who, action)
        if e is None:
            return False
        if action in ("high_plunge", "low_plunge"):
            # legality: a plunge needs the character airborne, i.e. right after the action whose kit follow-up it is
            prev = self.actions[-1] if self.actions else None
            if not prev or prev.char != who or self.libs[who].follow.get(prev.action) != action:
                return False
        kind = action if action in ("skill", "burst") else None
        vkey = self._key(who, action) if kind else action
        used_key = self._key(who, action)          # the variant actually performed (counted against its state)
        # measured execution timing (gtc/forward/frames.py): the previous action's lock depends on what follows it
        # (an attack can be cancelled into a dash sooner than into another attack), hitlag included
        t_trans = None
        if self.actions:
            from gtc.forward import frames as FR

            prev = self.actions[-1]
            lk = None if getattr(prev, "own_duration", False) else FR.lock(prev.char, prev.action, action if who == prev.char else "swap")
            if who == prev.char and not getattr(prev, "own_duration", False):
                # same character: the measured executed-to-executed gap of this exact transition (for attacks, by
                # chain position); a transition never observed falls back to the kit's own (chain-hit) duration,
                # never to a faster generic median
                run = 0
                for a_ in reversed(self.actions):
                    if a_.char != who or a_.action != "attack":
                        break
                    run += 1
                seg_burst = False             # Burst used since this character swapped in (a Burst state's strings)
                for a_ in reversed(self.actions):
                    if a_.char != who:
                        break
                    if a_.action == "burst":
                        seg_burst = True
                        break
                # the Normal Attack string cycles (N5 is followed by N1 again): a long run of attacks maps back onto
                # the measured chain positions by the string's length (the Amber table's "N-Hit DMG" rows)
                n_chain = _chain_length(who)
                pos = ((run - 1) % n_chain) + 1 if (run and n_chain) else run
                lk = FR.gap(who, self._frame_key(prev), pos, action, burst_segment=seg_burst)
                if lk is None and self._frame_key(prev) != prev.action:
                    lk = None if prev.end is None else max(0.0, prev.end - prev.t)    # the variant's own duration
                if lk is None:
                    # unobserved transition: never faster than the evidence allows (the measured queue lock with
                    # hitlag, or the kit duration, whichever is longer)
                    lq = FR.lock(prev.char, prev.action, action)
                    lk = max(lq or 0.0, (prev.end or prev.t) - prev.t)
            if lk is not None:
                t_trans = prev.t + lk
                if self.t <= (prev.end or prev.t) + 1e-6:      # no idle since: the transition sets the start
                    self.t = prev.t + lk
                else:
                    self.t = max(self.t, prev.t + lk)
            else:
                t_trans = prev.end or prev.t
        if kind:
            wait = max(0.0, (self.ready.get((who, vkey), 0.0) if vkey != kind else self.ready[(who, kind)]) - self.t)
            if kind == "burst" and self.energy[who] < self.cost_of(who, kind) - 1e-6:
                return False
            if wait > 0:
                if wait > 3.0:
                    return False
                self.t += wait
                self.waited += wait
        if action == "dash" and getattr(self.libs.get(who), "hand", False) is not None:
            from gtc.forward import frames as FR

            rule = FR.dash_rule()
            ds = [a.t for a in self.actions if a.char == who and a.action == "dash" and a.t > self.last_swap - 1e-6]
            if rule and len(ds) >= 2 and ds[-1] - ds[-2] <= rule[0] and self.t < ds[-1] + rule[1]:
                # two dashes close together lock the next one out (measured in gcsim: refused with stamina left)
                wait = ds[-1] + rule[1] - self.t
                if wait > 3.0:
                    return False
                self.t += wait
                self.waited += wait
        cost = stamina_cost(who, action)
        if cost:
            self._stamina_regen(self.t)
            if self.stamina < cost:           # not enough stamina: wait for it, as the game (and gcsim) does
                need = (cost - self.stamina) / STAMINA_REGEN + max(0.0, self.stamina_used + _stamina_delay() - self.t)
                if need > 6.0:
                    return False
                self.t += need
                self.stamina_waited += need
                self._stamina_regen(self.t)
        if who != self.on_field and self.actions:
            from gtc.forward import frames as FR

            self.t = max(self.t, self.last_swap + FR.swap_cd())    # swap cooldown
            if t_trans is not None:
                t_trans = max(t_trans, self.last_swap + FR.swap_cd())   # gcsim enforces it itself: not idle
            self.t += SWAP_DELAY
            self.last_swap = self.t        # the cooldown runs from the swap's completion (gcsim: 60 f after it executes)
        start = self.t
        self._flush_favonius(start)
        if cost:
            self.stamina -= cost
            self.stamina_used = start
            self.stamina_t = start
        self._procs_sustained(start)       # the previous action's window closes as this one starts
        self.tick_summons(start)
        if who != self.on_field:
            self.swap_out(self.on_field, start)
        if action in ("skill", "burst"):
            # a re-cast replaces what the previous cast left running (Escoffier's Mek, Furina's Salon, Ineffa's
            # Birgitta, a Stele, a field): its lingering hits still scheduled after this cast are cancelled
            prev_t = next((a.t for a in reversed(self.actions) if a.char == who and a.action == action), None)
            if prev_t is not None:
                ent = self.libs[who].entry(self._key(who, action)) or self.libs[who].entry(action)
                linger = (ent.duration if ent else 0.0) + 0.5
                self.hits = [h for h in self.hits if not (h.char == who and h.from_action == action
                                                           and abs((h.action_t or -1) - prev_t) < 1e-6
                                                           and h.t > start and h.t - prev_t > linger)]
        self.actions.append(Action(start, who, action if action != "attack" else "attack"))
        # hitlag: the character's own hits freeze them, and gcsim extends every timed status of theirs by the frozen
        # frames ("mod extended"): Raiden's Musou Isshin outlasts its 7 s by the hitlag of her attacks
        from gtc.forward import frames as FR

        hl = FR.hitlag(who, action)
        if hl > 0:
            for st_ in self.states.get(who, []):
                if st_["start"] <= start < st_["end"] and st_["end"] - st_["start"] < 60:
                    st_["end"] += hl
                    st_["nominal_end"] = st_.get("nominal_end", st_["end"] - hl) + hl
        self.actions[-1].variant = used_key
        # the transition the generator used, so the gcsim translation emits exactly the idle inserted on top of it
        self.actions[-1].earliest = t_trans + (SWAP_DELAY if self.actions[:-1] and self.actions[-2].char != who else 0.0)             if t_trans is not None else None
        # particles land on whoever is on field when they arrive: the character acting now
        self.on_field = who
        dur = e.duration
        dbr = ((lib.action_meta.get(vkey) or lib.action_meta.get(action) or {}).get("duration_by_resource")
               if lib.hand else None)
        if dbr:
            # kit language: an action whose duration depends on a resource it consumes (Neuvillette's Charged Attack
            # charges faster with Sourcewater Droplets absorbed); durations measured in gcsim
            have = self.res.get((who, dbr["resource"])) or 0.0
            k = int(min(dbr.get("consume", 1), have))
            table_ = {int(x): float(v) for x, v in dbr["durations"].items()}
            dur = table_.get(k, table_[min(table_, key=lambda x: abs(x - k))])
            self._set_res(who, dbr["resource"], have - k, start)
        for p in [p for p in self.pending if p[0] <= start + dur]:
            self.pending.remove(p)
            self._particles(p[1], p[2], p[3], p[0], who, spawn=p[4] if len(p) > 4 else None)
        for h in e.hits:
            ht = start + h.offset
            if h.reaction == "swirl":
                continue          # Swirl is decided by the reaction model from the auras, not copied from a source team
            element = h.element
            if self.el[who] == "Anemo" and element in SWIRLABLE:     # absorbed element follows the aura
                element = self._aura(ht) or element
            if lib.hand:
                hit = self._make_hit(who, h, ht, start)
                hit.from_action = action
            else:
                hit = Hit(t=ht, char=who, abil=h.abil, damage_type=h.damage_type, element=element, mult=h.mult,
                          scaling=h.scaling, action_t=start, ignore_def=h.ignore_def, gauge=h.gauge, from_action=action)
                if element in SWIRLABLE and element != "Anemo":
                    self.last_applied.append((ht, element))
            self.emit(hit)
            self.last_applied.sort()
        self.segments.append((start, start + dur, who))
        self.actions[-1].end = start + dur
        self.actions[-1].own_duration = bool(dbr)    # its own duration overrides the measured cancel frames
        self.t = start + dur
        if kind == "skill" and e.particles:
            from gtc.forward import frames as FR

            sched = FR.particle_schedule(who)
            if sched:          # measured arrival schedule of this character's own particles after a Skill
                for off, cnt in sched:
                    self.pending.append((start + off, who, cnt, self.el[who], start))
            else:
                travel = FR.particle_delay(who) or 1.0            # measured Skill-to-arrival time
                self.pending.append((start + travel, who, e.particles, self.el[who], start))
        if lib.hand:
            meta = lib.action_meta.get(action) or {}
            if meta.get("state"):
                sd = lib.states.get(meta["state"]) or {}
                dur = sd.get("duration")
                if isinstance(dur, dict):
                    dur = D.value(who, dur["table"][0], dur["table"][1])
                # lead: the state's own duration runs from the end of the action's animation (Raiden's Musou Isshin: gcsim
                # status 518 f from the cast = 420 f table + 98 f Burst animation)
                lead = float(sd.get("lead", 0) or 0)
                self.states[who].append({"name": meta["state"], "start": start, "end": start + lead + float(dur or 0),
                                         "uses": {}, "nominal_end": start + lead + float(dur or 0)})
            if meta.get("requires_state"):
                st = self.state(who, start)
                if st:
                    st["uses"][action] = st["uses"].get(action, 0) + 1
            if "@" in used_key:
                st = self._state_obj(who, used_key.split("@", 1)[1])
                if st is not None:
                    st["uses"][used_key] = st["uses"].get(used_key, 0) + 1
            for sname, sd in lib.states.items():
                ext = (sd.get("extend_on") or {}).get(action)
                st = self.state(who, start)
                if ext and st and st["name"] == sname:
                    st["end"] += float(ext)
            lb = lib.level_bonus
            if lb and lb.get("trigger") == action:
                self.level_until[who] = start + float(lb.get("duration", 0))
        if lib.hand:
            meta = lib.action_meta.get(vkey) or lib.action_meta.get(action) or {}
            self.run_ops(who, meta.get("do"), start)
            for sname, sd in (lib.summons or {}).items():
                if sd.get("start_on") == action:
                    self.start_summon(who, sname, start)
        self.dispatch({"event": "action", "char": who, "t": start, "action": action,
                       "burst_cost": self.cost.get(who, 0.0) if kind == "burst" else 0.0})
        self._procs_on_action(who, action, start, dur)
        if action == "attack":
            self.chain[who] += 1
        elif action not in ("wait",):
            self.chain[who] = 0
        if kind:
            vmeta = (lib.action_meta.get(vkey) or {}) if lib.hand else {}
            cd = vmeta.get("cd") or ((lib.action_meta.get(action) or {}).get("cd") if lib.hand else None)
            if vkey != kind:
                self.ready[(who, vkey)] = start + (float(cd) if cd else 0.0)   # the variant's own cooldown
            else:
                from gtc.forward import frames as FR

                hold = any(FR.is_hold(h.abil) for h in e.hits)      # the variant the kit file measured
                bd = FR.burst_duration(who)
                own = next((a.t for a in reversed(self.actions[:-1]) if a.char == who and a.action == "burst"), None)
                # a Burst field's effect reaches the character on its tick: only after about a second on field
                # (gcsim: Bennett's reduced Skill cooldown in 15% of casts within 0.5 s of swapping in, ~100% after 1 s)
                seg_start = start
                for a_ in reversed(self.actions):
                    if a_.char != who:
                        break
                    seg_start = a_.t                     # the first action of this field segment (swap-in)
                on_for = start - seg_start
                inside = bool(bd and own is not None and start - own <= bd and on_for >= FIELD_TICK) if kind == "skill" else False
                self.ready[(who, kind)] = start + (float(cd) if cd else (FR.cooldown(who, kind, hold, inside)
                                                                          or _cd(who, kind)))
            if kind == "burst":
                self.energy[who] = max(0.0, self.energy[who] - self.cost_of(who, kind)) if vkey != kind else 0.0
        self._tick_passive_energy(self.t, who)
        follow = self.libs[who].follow.get(action)
        if follow and follow not in ("skill", "burst"):
            self.act(who, follow)
        return True


def _window(sim, carry: str, plan: Plan, end_t: float, cycle_start: float, period: float) -> None:
    """One carry's field window: buff openers, Skill and Burst in the plan's order (with the refresh timing), then
    their filler string until end_t, re-casting Skill when ready and a missed Burst as soon as it is funded."""
    libs = sim.libs
    skip = plan.carry_first == "skill_only" or not plan.burst_on(carry, getattr(sim, "cycle", 0))
    order = (["skill"] if skip else
             ["skill", "burst"] if plan.carry_first == "skill" else ["burst", "skill"])
    for a in _buff_openers(carry, libs[carry]):
        sim.act(carry, a)
    refreshed = False
    for a in order:
        sim.act(carry, a)
        if a == "burst" and plan.refresh == "after_burst":
            _refresh(sim, plan, cycle_start)   # supports re-cast while the carry's Burst keeps working
            refreshed = True
    skill_refused = False
    burst_done = skip or \
        any(a.char == carry and a.action == "burst" and a.t >= cycle_start for a in sim.actions)
    while sim.t < end_t:
        # every branch either acts or lets time pass: a refused action never loops in place
        special = next((sp for sp in libs[carry].specials if sim.can(carry, sp)), None)
        if special and sim.act(carry, special):   # limited-use specials (Lohen's Etched) whenever available
            continue
        if not burst_done and sim.ready[(carry, "burst")] <= sim.t and sim.energy[carry] >= sim.cost[carry] - 1e-6:
            burst_done = sim.act(carry, "burst")   # a Burst missed at the slot is cast as soon as it is funded
            if burst_done:
                continue
            burst_done = True                      # refused (state, schedule): not retried this window
        if sim.ready[(carry, "skill")] <= sim.t and not skill_refused:
            if sim.act(carry, "skill"):
                continue
            skill_refused = True
        if plan.refresh == "mid" and not refreshed and sim.t > cycle_start + period / 2:
            _refresh(sim, plan, cycle_start)
            refreshed = True
            continue
        if plan.support_policy == "event":
            if not _protected(sim, carry, plan) and _visit_events(sim, plan):
                continue
        elif plan.support_policy != "wait" and not _protected(sim, carry, plan) and _visit_ready(sim, plan):
            continue
        unit = list(plan.filler) or libs[carry].filler or ["attack"]
        moved = False
        for a in unit:
            if sim.t >= end_t:
                moved = True          # the window ends mid-string: the next cycle starts on time
                break
            moved |= sim.act(carry, a)
        if not moved:
            sim.t += 0.5
    # state protection: a state of the driver's that a swap would end is played out before anyone swaps in
    limit = end_t + 12.0
    while plan.protect_state and _protected(sim, carry, plan) and sim.t < limit:
        moved = False
        for a in (list(plan.filler) or libs[carry].filler or ["attack"]):
            if not _protected(sim, carry, plan):
                break
            moved |= sim.act(carry, a)
        if not moved:
            break


def _protected(sim, carry: str, plan) -> bool:
    """The driver is in a state a swap would end, with more than a moment of it left (and the plan protects it)."""
    if not plan.protect_state:
        return False
    sd = sim.libs[carry].states or {}
    for s in sim.states.get(carry, []):
        if s["start"] <= sim.t < s["end"] - 0.3 and s["end"] < sim.t + 60 and (sd.get(s["name"]) or {}).get("ends_on_swap"):
            return True
    return False


def _quickswap_cycle(sim, plan, cycle_start: float, period: float) -> None:
    """Quickswap family: no long driver. Each member in turn: Skill when ready, Burst when funded (and scheduled), a
    short attack string; rounds repeat until the cycle ends."""
    libs = sim.libs
    order = list(plan.supports)
    while sim.t < cycle_start + period:
        moved = False
        for m in order:
            if sim.t >= cycle_start + period:
                break
            if sim.ready[(m, "skill")] <= sim.t + 1e-6 and sim.act(m, "skill"):
                moved = True
            if (plan.burst_on(m, getattr(sim, "cycle", 0)) and sim.ready[(m, "burst")] <= sim.t + 1e-6
                    and sim.energy[m] >= sim.cost_of(m, "burst") - 1e-6 and sim.act(m, "burst")):
                moved = True
            for a in (list(plan.filler) or ["attack", "attack"]):
                if libs[m].entry("attack#0") or libs[m].entry("attack"):
                    moved |= sim.act(m, a)
        if not moved:
            sim.t += 0.5


def _reaction_procs(sim, hits: list, lineup: list[str], libs: dict) -> list:
    """Kit procs on reaction events (Fischl's A4: when the ACTIVE character triggers an Electro-related reaction
    while Oz is on the field). The window opens at the listed actions for the given duration; an optional cooldown."""
    out = []
    for m in lineup:
        for rp in (getattr(libs.get(m), "reaction_procs", None) or {}).values():
            w = rp.get("window") or {}
            d = w.get("duration")
            if isinstance(d, dict):
                d = D.value(m, d["table"][0], d["table"][1])
            windows = [(a.t, a.t + float(d or 0)) for a in sim.actions if a.char == m and a.action in (w.get("after") or [])]
            last = -1e9
            for h in sorted(hits, key=lambda x: x.t):
                k = h.reaction or h.amp or h.cata
                if not k or not any(k.startswith(x) for x in rp.get("kinds") or []):
                    continue
                if rp.get("by") == "active" and sim._active_at(h.t) != h.char:
                    continue
                if windows and not any(a <= h.t < b for a, b in windows):
                    continue
                if h.t - last < float(rp.get("icd") or 0.0):
                    continue
                last = h.t
                for tmpl in rp.get("hits_t") or []:
                    hit = sim._make_hit(m, tmpl, h.t + tmpl.offset, h.t)
                    hit.from_action = "reaction_proc"
                    out.append(hit)
    return out


def _clip_field_states(hits: list, segments: list, lineup: list[str]) -> list:
    """Kits whose Burst is an on-field state (Raiden's Musou Isshin, Razor's Lightning Fang: the talent table names
    the state's duration) lose that state's hits while they are off field."""
    from gtc.forward.rotation import WINDOW_ROWS

    state = {m for m in lineup if WINDOW_ROWS.get(m, ("", ""))[0] == "burst"}

    def on_field(m, t):
        return any(a <= t < b and w == m for a, b, w in segments)

    return [h for h in hits if not (h.char in state and h.damage_type in ("burst", "normal", "charged")
                                    and not on_field(h.char, h.t))]


def _effect_over(sim, s: str) -> bool:
    """The support's last Skill effect has run out: no summon of theirs is live, and the hits their last cast left
    lingering are over (a Mek, a Salon, a Stele)."""
    if any(x["owner"] == s and x["end"] > sim.t for x in sim.summons):
        return False
    last = next((a.t for a in reversed(sim.actions) if a.char == s and a.action == "skill"), None)
    if last is None:
        return True
    ent = sim.libs[s].entry("skill")
    span = max((h.offset for h in (ent.hits if ent else [])), default=0.0)
    return sim.t >= last + span


def _visit_events(sim, plan) -> bool:
    """Event-driven support visits (support_policy "event"), from the timeline's current state rather than fixed
    visit points: a support whose Skill is ready and whose last effect has run out recasts it; a support whose
    Burst is due this cycle and now funded casts it. The driver resumes after. True when someone was visited."""
    went = False
    cyc = getattr(sim, "cycle", 0)
    for s in plan.supports:
        if sim.ready[(s, "skill")] <= sim.t + 1e-6 and _effect_over(sim, s) and sim.can(s, "skill") and sim.act(s, "skill"):
            went = True
        if (plan.burst_on(s, cyc) and sim.ready[(s, "burst")] <= sim.t + 1e-6
                and not any(a.char == s and a.action == "burst" and a.t >= getattr(sim, "cycle_start", 0.0) for a in sim.actions)
                and sim.energy[s] >= sim.cost_of(s, "burst") - 1e-6 and sim.act(s, "burst")):
            went = True
    return went


def _visit_ready(sim, plan) -> bool:
    """Support policy inside the carry window: a support whose Skill is ready (deferred at setup, or any support
    under "recast") swaps in and casts it; the carry resumes after. True when someone was visited."""
    went = False
    for s in plan.supports:
        if s not in getattr(sim, "deferred", set()) and plan.support_policy != "recast":
            continue
        if sim.ready[(s, "skill")] <= sim.t + 1e-6 and sim.can(s, "skill") and sim.act(s, "skill"):
            getattr(sim, "deferred", set()).discard(s)
            went = True
    return went


def _refresh(sim, plan, cycle_start: float) -> None:
    for s in plan.supports:
        if sim.ready[(s, "skill")] <= sim.t:
            sim.act(s, "skill")
        if (plan.burst_on(s, getattr(sim, "cycle", 0))
                and not any(a.char == s and a.action == "burst" and a.t >= cycle_start for a in sim.actions)
                and sim.ready[(s, "burst")] <= sim.t and sim.energy[s] >= sim.cost[s] - 1e-6):
            sim.act(s, "burst")   # a support Burst missed at setup is cast at the refresh


class _Scheduled:
    """A scheduled but not yet finalized rotation (no reaction model): what the energy iteration needs (actions,
    energy log, duration), and the scheduler state to finalize it once the build is settled."""

    def __init__(self, sim, cycles, dur, lineup, libs, plan, period, carry):
        self.sim, self.cycles, self.duration = sim, cycles, dur
        self.lineup, self.actions, self.energy, self.segments = list(lineup), sim.actions, sim.energy_log, sim.segments
        self._args = (libs, plan, period, carry)

    def finalize(self) -> Rotation:
        return _finalize(self.sim, self.cycles, self.duration, self.lineup, *self._args)


def generate(lineup: list[str], libs: dict, builds: dict, plan: Plan, period: float, finalize: bool = True):
    carry, _ = roles(lineup)
    sim = _Sim(lineup, libs, builds)
    sim.deferred = set()
    order_carry = ["skill", "burst"] if plan.carry_first == "skill" else ["burst", "skill"]
    cycles = []
    for c in range(CYCLES):
        cycle_start = sim.t
        cycles.append((sim.t, len(sim.actions)))
        sim.cycle = c
        sim.cycle_start = cycle_start
        if plan.family == "quickswap":
            _quickswap_cycle(sim, plan, cycle_start, period)
            continue
        for s in plan.supports:
            first = libs[s].first
            seq = [first, "burst" if first == "skill" else "skill"]
            if not plan.burst_on(s, c):
                seq = [x for x in seq if x != "burst"]
            for a in seq:
                if (a == "skill" and plan.support_policy != "wait"
                        and sim.ready[(s, "skill")] > sim.t + 0.3):          # (event: visited when ready)
                    sim.deferred.add(s)        # not ready: visited inside the carry window when it is
                    continue
                if a == "burst":
                    if sim.energy[s] < sim.cost[s] - 1e-6 and sim.ready[(s, "burst")] <= sim.t + 3:
                        # wait for energy a little (a player would), else skip this cycle's Burst
                        need = sim.cost[s] - sim.energy[s]
                        for _ in range(6):
                            sim._tick_passive_energy(sim.t + 1.0, carry)
                            sim.t += 1.0
                            sim.waited += 1.0
                            if sim.energy[s] >= sim.cost[s] - 1e-6:
                                break
                        del need
                sim.act(s, a)
        carries = plan.carries or (carry,)
        for i, cr in enumerate(carries):
            if len(carries) == 1:
                end_t = cycle_start + period
            else:   # dual plan: each carry gets the window their kit needs, one after the other
                from gtc.forward.rotation import field_profile

                end_t = sim.t + field_profile(cr).minimum_seconds + 1.5
            _window(sim, cr, plan if i == 0 else Plan(plan.supports, plan.carry_first, "", (), carries,
                                                      support_policy=plan.support_policy),
                    end_t, cycle_start, period)
    dur = sim.t
    sim._procs_sustained(dur)
    sim.tick_summons(dur)
    sched = _Scheduled(sim, cycles, dur, lineup, libs, plan, period, carry)
    return sched.finalize() if finalize else sched


def _finalize(sim, cycles, dur, lineup, libs, plan, period, carry) -> Rotation:
    """The reaction model, reaction procs and summaries on a scheduled rotation."""
    sim.hits.sort(key=lambda h: h.t)
    from gtc.forward.reactions import simulate

    base_hits = _clip_field_states(sim.hits, sim.segments, list(lineup))
    hits, rx = simulate(base_hits, list(lineup))
    if any(getattr(libs.get(m), "reaction_procs", None) for m in lineup):
        for _ in range(2):          # procs depend on reactions, and their hits react: settle in two passes
            procs = _reaction_procs(sim, hits, lineup, libs)
            hits, rx = simulate(base_hits + procs, list(lineup))
    sim.post_reactions(hits)
    carry_names = " then ".join(plan.carries or (carry,))
    rot = Rotation(list(lineup), sim.actions, hits, dur, sim.energy_log, sim.segments,
                   f"generated: supports {', '.join(plan.supports)}; carry {carry_names} {plan.carry_first} first, filler "
                   f"{' '.join(plan.filler or libs[carry].filler)}; "
                   f"refresh {plan.refresh or 'none'}; {CYCLES} cycles of {period:.0f} s")
    rot.notes.append(f"waited {sim.waited:.1f} s for energy or cooldowns")
    rot.cycles = cycles
    rot.timeline = sim.timeline()
    rot.notes.append("reactions: " + ", ".join(f"{k} {v}" for k, v in sorted(rx.items()) if not k.startswith("_")))
    from gtc.forward.reactions import summary as rx_summary

    rot.reactions = rx_summary(rx)
    return rot


def _buff_openers(name: str, lib) -> list[str]:
    """Carry actions that start one of the carry's own buffs (annotation triggers such as Ayaka's dash for her A4):
    used to open the carry window."""
    from gtc.forward.effects import annotations

    out = []
    for p in annotations().get(name) or []:
        for tr in p.get("trigger") or []:
            if tr in ("dash",) and lib.entry(tr) and tr not in out:
                out.append(tr)
    return out


def candidates(lineup: list[str], libs: dict | None = None) -> list[Plan]:
    """Single-carry plans for every on-field damage dealer as the carry (the others support: cast and leave), and,
    with two or more on-field damage dealers, dual plans where two carries each get their window in turn."""
    # with no on-field damage dealer (quickswap / off-field teams) someone still stays on field: every member is a
    # candidate driver and the forward model decides
    real = on_field_dealers(lineup)
    dealers = real or list(lineup)
    # any member who can act on field is a driver candidate (who stands on field is a decision, not a tag): members
    # the kit does not mark as on-field dealers get a smaller set of plan variants
    extra = [m for m in lineup if m not in dealers and libs and libs.get(m) is not None
             and (libs[m].entry("attack#0") or libs[m].entry("attack"))]
    choices = [(c,) for c in dealers + extra] + [(a, b) for a in real for b in real if a != b]
    out = []
    # quickswap family: no long driver; every order of the four members takes short turns
    for perm in permutations(lineup):
        out.append(Plan(tuple(perm), "skill", "", ("attack", "attack"), (), family="quickswap"))
    for carries in choices:
        sup = [m for m in lineup if m not in carries]
        lib = (libs or {}).get(carries[0])
        fills = [tuple(f) for f in (lib.fillers if lib else [])] or [()]
        for perm in permutations(sup):   # every order: the forward model decides (no ordering heuristic)
            # a carry whose Burst is worth less than the field time and energy it costs can skip it: the forward
            # model decides (single-carry plans)
            firsts = ("skill", "burst", "skill_only") if len(carries) == 1 else ("skill", "burst")
            minor = carries[0] in extra
            for first in (("skill", "burst") if minor else firsts):
                for refresh in (("", "mid") if minor else ("", "mid", "after_burst")):
                    if first == "skill_only" and refresh == "after_burst":
                        continue
                    for f in (fills[:2] if minor else fills):
                        out.append(Plan(tuple(perm), first, refresh, f, carries))
    return out


def best_rotation(lineup: list[str], libs: dict, builds: dict | None = None) -> dict:
    """Generate every candidate, evaluate each with the forward model, return the best and the ranking."""
    from gtc.forward.build import house_builds
    from gtc.forward.energy import requirements
    from gtc.forward.model import evaluate
    from gtc.forward.rotation import window_fit

    period = window_fit(lineup)["period"]
    costs = {m: D.value(m, "burst", "Energy Cost") for m in lineup}
    results = []
    base_period = period
    from gtc.forward.deps import graph, realisation, respects

    graphs = {}
    pruned = 0
    t_start = time.time()
    budget_note = ""
    limit_hit = None
    for i, plan in enumerate(candidates(lineup, libs)):
        if i >= MAX_PLANS or time.time() - t_start > SEARCH_SECONDS:
            budget_note = f"search bounded: {i} base plans evaluated (limits {MAX_PLANS} plans / {SEARCH_SECONDS:.0f} s)"
            limit_hit = "plans" if i >= MAX_PLANS else "time"
            break
        g = graphs.setdefault(plan.carries, graph(lineup, plan.carries, libs))
        if not respects(plan.supports, plan.carries, g):
            pruned += 1          # breaks a hard dependency (a stack builder after its consumer)
            continue
        results.append(_run_plan(lineup, libs, builds, plan, _period(plan, libs, base_period), costs))
        _lighten(results)
    # the cycle length is searched too: the best plans again at the cycles the kits suggest (the longest Burst
    # cooldown, a support's Skill cooldown, the carry's state plus setup); the forward model decides
    best_plans = []
    for r in sorted(results, key=lambda r: -r[0]):
        if r[1] not in best_plans:
            best_plans.append(r[1])
        if len(best_plans) >= 6:
            break
    for plan in best_plans:
        cur = _period(plan, libs, base_period)
        for p in _alt_periods(lineup, plan, libs):
            if abs(p - cur) < 0.75:
                continue
            alt = replace(plan, period=round(p, 2))
            results.append(_run_plan(lineup, libs, builds, alt, alt.period, costs))
    # Burst usage is decided by marginal value: for the best plans, each member's Burst schedule (every cycle, every
    # second cycle, never) is varied one member at a time and kept only when steady-state DPS rises
    decisions = _burst_search(lineup, libs, builds, results, base_period, costs)
    # level 2 (windows): the support policy of the best strategies - wait for a support's cooldown at setup, or
    # visit the support inside the carry window when its Skill is ready (once, or every time)
    _policy_search(lineup, libs, builds, results, base_period, costs)
    # a rotation that cannot loop (a member's energy requirement is unrealistic) is never preferred
    results.sort(key=lambda r: (any(v.get("status") == "unsustainable" for v in (r[3].energy or {}).values()), -r[0]))
    if not results[0][2].hits:      # the winner was lightened: regenerate it
        p = results[0][1]
        results[0] = _run_plan(lineup, libs, builds, p, _period(p, libs, base_period), costs)
    out = _finish(results, graphs, pruned)
    out["search"] = {"evaluated": len(results), "seconds": round(time.time() - t_start, 1), "bounded": budget_note,
                     "limit_hit": limit_hit, "time_limit_seconds": SEARCH_SECONDS}
    out["burst_decisions"] = [d for d in decisions if d["plan"] == out["plan"].__repr__()] or decisions[:8]
    return out


def _burst_search(lineup, libs, builds, results, base_period, costs, top: int = 4) -> list[dict]:
    def ok(r):
        return not any(v.get("status") == "unsustainable" for v in (r[3].energy or {}).values())

    seeds = []
    for r in sorted(results, key=lambda r: -r[0]):
        if ok(r) and r[1] not in [s[1] for s in seeds]:
            seeds.append(r)
        if len(seeds) >= top:
            break
    decisions = []
    for seed in seeds:
        cur = seed
        for m in lineup:
            if not (libs.get(m) and libs[m].entry("burst")):
                continue
            for every in (2, 0):
                sched = tuple(sorted({**dict(cur[1].bursts), m: every}.items()))
                alt = replace(cur[1], bursts=sched)
                r = _run_plan(lineup, libs, builds, alt, _period(alt, libs, base_period), costs)
                results.append(r)
                decisions.append({"plan": None, "member": m, "schedule": {2: "every second cycle", 0: "never"}[every],
                                  "dps_every_cycle": round(cur[0]), "dps_alternative": round(r[0]),
                                  "marginal_value_of_every_cycle": round(cur[0] - r[0])})
                if r[0] > cur[0] and ok(r):
                    cur = r
        for d in decisions:
            if d["plan"] is None:
                d["plan"] = cur[1].__repr__()
    return decisions


def _policy_search(lineup, libs, builds, results, base_period, costs, top: int = 8) -> None:
    """Level 2 (windows) over a diverse set of strategies: the overall best few, plus the best plan of every driver
    and opening, so a strategy that only shines with a different support policy or state protection is not lost
    because its plain version ranked low (diversity before local refinement)."""
    ranked = [r for r in sorted(results, key=lambda r: -r[0]) if r[1].support_policy == "wait" and not r[1].protect_state]
    seeds = []
    for r in ranked:
        if len(seeds) < top and r[1] not in seeds:
            seeds.append(r[1])
    per_group = {}
    for r in ranked:
        # the two best support orders of every driver x opening x refresh: a plain plan that ranks low can be the one
        # that wins once its windows change (no refresh only pays once the driver's state is protected)
        g = (r[1].carries, r[1].carry_first, r[1].refresh, r[1].family)
        if per_group.get(g, 0) < 2 and r[1] not in seeds:
            per_group[g] = per_group.get(g, 0) + 1
            seeds.append(r[1])
    staged = []
    for plan in seeds:
        if plan.family == "quickswap":
            continue
        # level 1 still varies with level 2: each cycle length the kits suggest, with each support policy and with
        # or without protecting the driver's state (a long state window only pays off with a cycle that fits it)
        cur = _period(plan, libs, base_period)
        periods = [cur] + [p for p in _alt_periods(lineup, plan, libs) if abs(p - cur) >= 0.75]
        prot = (False, True) if _has_swap_state(libs.get(plan.carries[0]) if plan.carries else None) else (False,)
        for per in periods:
            for pol in ("wait", "defer", "recast", "event"):
                for protect in prot:
                    if per == cur and pol == "wait" and not protect:
                        continue          # the seed itself
                    alt = replace(plan, support_policy=pol, protect_state=protect,
                                  period=round(per, 2) if per != cur else plan.period)
                    r = _run_plan(lineup, libs, builds, alt, alt.period or cur, costs)
                    results.append(r)
                    staged.append(r)
    # level 3 (action order): the driver's attack string for the best few - the kit's measured strings and a plain
    # repeated Normal Attack (repeat until the window or state ends)
    done, best_of = set(), {}
    for r in sorted(staged, key=lambda r: -r[0]):
        g = (r[1].carries, r[1].carry_first)
        if g not in best_of:
            best_of[g] = r            # diversity carries through: the best level-2 plan of every driver and opening
    for r in sorted(best_of.values(), key=lambda r: -r[0])[:6]:
        plan = r[1]
        lib = libs.get(plan.carries[0]) if plan.carries else None
        options = [tuple(f) for f in (lib.fillers[:3] if lib else [])] + [("attack",)]
        for f in options:
            if f == tuple(plan.filler) or (repr(plan), f) in done:
                continue
            done.add((repr(plan), f))
            alt = replace(plan, filler=f)
            results.append(_run_plan(lineup, libs, builds, alt, alt.period or _period(alt, libs, base_period), costs))


def _has_swap_state(lib) -> bool:
    return bool(lib and any((sd or {}).get("ends_on_swap") for sd in (lib.states or {}).values()))


def family_of(plan, base_period: float) -> str:
    """The cycle family a plan belongs to (reporting): quickswap, dual window, alternating (a Burst every second
    cycle), short / long (cycle length against the team's base cycle), else standard."""
    if plan.family == "quickswap":
        return "QUICKSWAP"
    if len(plan.carries) > 1:
        return "DUAL_WINDOW"
    if any(v == 2 for _, v in plan.bursts):
        return "ALTERNATING"
    if plan.period and base_period:
        if plan.period < 0.85 * base_period:
            return "SHORT"
        if plan.period > 1.15 * base_period:
            return "LONG"
    return "STANDARD"


def _alt_periods(lineup: list[str], plan, libs: dict) -> list[float]:
    """Cycle lengths the kits suggest: the longest Burst cooldown and the longest support Skill cooldown (plus a second
    of setup), and for a single carry with a timed state, the state plus the supports' setup."""
    out = []
    bursts = [_cd(m, "burst") for m in lineup]
    out.append(max(bursts) + 1.0)
    if plan.carries:
        # short family: just the driver's own Skill cycle (minimal setup), and long: the longest Burst cooldown
        # plus the driver's whole state
        out.append(max(_cd(plan.carries[0], "skill"), 8.0) + 1.0)
    sup = [m for m in lineup if m not in plan.carries]
    if sup:
        out.append(max(_cd(m, "skill") for m in sup) + 1.0)
    if len(plan.carries) == 1:
        lib = libs.get(plan.carries[0])
        for sd in ((lib.states or {}).values() if lib else []):
            d = sd.get("duration")
            if isinstance(d, dict):
                d = D.value(plan.carries[0], d["table"][0], d["table"][1])
            if d:
                out.append(float(d) + 2.5 * len(sup) + 2.0)
    return sorted({round(p, 1) for p in out if 8.0 <= p <= 40.0})


FIELD_TICK = 1.0       # seconds on field before a Burst field's effect applies to the character (measured)
MAX_PLANS = 900         # hard bounds on the base-plan search (deterministic order: carry choices, then supports)
# the cloud deployment lowers this with GTC_SEARCH_SECONDS; unset, it stays 120 s so r8 results are unchanged
SEARCH_SECONDS = float(os.environ.get("GTC_SEARCH_SECONDS", "120"))
KEEP_FULL = 24          # candidates kept with their full rotation and events; the rest keep score, plan and summary


def _lighten(results: list) -> None:
    """Memory: only the leading candidates keep hits and per-event results (the search holds hundreds of plans)."""
    if len(results) <= 2 * KEEP_FULL:
        return
    keep = {id(r) for r in sorted(results, key=lambda r: -r[0])[:KEEP_FULL]}
    for r in results:
        if id(r) not in keep and r[2].hits:
            r[2].hits = []
            r[2].energy = []
            r[2].timeline = {}
            r[3].events = []


def _run_plan(lineup, libs, builds, plan, period, costs):
    from gtc.forward.build import house_builds
    from gtc.forward.energy import requirements
    from gtc.forward.model import evaluate

    if builds is None:
        # schedule with ample energy, then require the build to meet the ER the rotation needs (+10%, KQM
        # convention, as for traced rotations); a requirement above ER_CAP is unrealistic: reschedule at the cap,
        # so Bursts are genuinely late or skipped
        from gtc.forward.build import meta_standard

        ample = house_builds(lineup, {m: 3.0 for m in lineup})
        rot = generate(lineup, libs, ample, plan, period, finalize=False)     # the intended schedule (energy only)
        req = requirements(rot, costs)
        added = {}
        for m, r in req.items():
            have = meta_standard(m).total("er")
            need = min(ER_BUFFER * (r.get("required_er") or 0), ER_CAP)
            if need > have:
                added[m] = round(need - have, 3)
        b = house_builds(lineup, added)
        # the scored rotation is always scheduled with the build it is scored with (an ample-energy schedule paired
        # with a lower-ER build made gcsim wait for Bursts the forward rotation had already cast). Energy that scales
        # with ER (Raiden's restoration) is inflated in the ample pass, so the requirement can fall short: members
        # whose Bursts come late against the intended schedule get +0.2 ER (cap 2.6) and the plan is scheduled again
        # - the same rule the reference's builds go through (trace.house_trace)
        from gtc.forward.trace import _burst_times, _late_bursts

        intended = _burst_times(rot)
        for i in range(5):
            rot = generate(lineup, libs, b, plan, period, finalize=False)       # always the build that is scored
            late = [n for n in _late_bursts(intended, _burst_times(rot))
                    if b[n].total("er") < ER_CAP - 1e-6]
            if not late or i == 4:
                break
            for n in late:
                added[n] = round(added.get(n, 0.0) + min(0.2, ER_CAP - b[n].total("er")), 3)
            b = house_builds(lineup, added)
        req = requirements(rot, costs)
        key = _schedule_key(rot, added)
        hit = _EVAL_MEMO.get(key)
        if hit is not None:
            return (hit[0], plan, hit[1], hit[2], b)    # an identical schedule (same actions, same build): same result
        rot = rot.finalize()          # the reaction model once, on the schedule that is scored
    else:
        b, added = builds, {}
        rot = generate(lineup, libs, b, plan, period)
        req = requirements(rot, costs)
        key = None
    ev = evaluate(rot, b, info={"energy": req, "er_added": added})
    if key is not None:
        if len(_EVAL_MEMO) > 4000:
            _EVAL_MEMO.clear()
        _EVAL_MEMO[key] = (ev.dps, rot, ev)
    return (ev.dps, plan, rot, ev, b)


_EVAL_MEMO: dict = {}


def _schedule_key(sched, added: dict) -> tuple:
    """Identity of a scheduled rotation for memoising its evaluation: the exact action sequence (who, what, when)
    and the build's ER additions. Plans that schedule identically (a support policy with nothing to defer) are
    scored once."""
    return (tuple(sched.lineup), tuple((a.char, a.action, getattr(a, "variant", ""), round(a.t, 4)) for a in sched.actions),
            tuple(sorted((k, round(v, 4)) for k, v in added.items())), round(sched.duration, 4))


def _finish(results, graphs, pruned):
    from gtc.forward.deps import realisation

    dps, plan, rot, ev, used = results[0]
    g = graphs.get(plan.carries) or {"hard": [], "soft": []}
    from gtc.forward.uncertainty import assess

    real = realisation(rot, ev, plan.carries)
    detail = assess(rot, ev, real, generated=True)
    ev.uncertainty, ev.confidence, ev.uncertainty_detail = detail["sd"], detail["confidence"], detail
    return {"plan": plan, "rotation": rot, "evaluation": ev, "graph": g, "pruned": pruned, "used_builds": used,
            "realisation": realisation(rot, ev, plan.carries),
            "ranking": [(round(r[0]), r[1].carries, r[1].supports, r[1].carry_first, r[1].refresh, r[1].filler)
                        for r in results],
            "by_carries": _best_by_carries(results)}


def _period(plan, libs: dict, base: float) -> float:
    """The cycle length: the team's Burst cycle, and, for a single carry whose kit has a timed state (Lohen's
    Masterstroke), long enough to play the whole state after setup, and no shorter than the Skill cooldown that opens
    it."""
    if plan.period:
        return plan.period
    if len(plan.carries) != 1:
        return base
    c = plan.carries[0]
    lib = libs.get(c)
    if not lib or not lib.states:
        return base
    longest = 0.0
    for sd in lib.states.values():
        d = sd.get("duration")
        if isinstance(d, dict):
            d = D.value(c, d["table"][0], d["table"][1])
        longest = max(longest, float(d or 0) + sum(float(v) for v in (sd.get("extend_on") or {}).values()))
    return max(base, _cd(c, "skill"), longest + 5.0)


def _best_by_carries(results) -> dict:
    """The best plan for each carry choice: how the team does with each carry alone and with both."""
    out = {}
    for dps, plan, rot, ev, *_ in results:
        k = " + ".join(plan.carries)
        if k not in out:
            out[k] = {"dps": round(dps), "rotation_s": round(rot.duration, 1),
                      "shares": {m: round(v, 3) for m, v in ev.damage_share.items()}}
    return out
