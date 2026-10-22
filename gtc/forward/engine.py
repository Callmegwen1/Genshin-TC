"""The kit-language event simulation (phase A): EVENT -> RESOURCE -> STATE -> CONDITION -> EFFECT -> DAMAGE.

A character's kit file (knowledge/forward/actions/<Name>.yaml, loaded by gtc/forward/library.py) declares, besides its
actions and hits:

    resources  {name: {max: number | unknown, start: number}}              stacks, counters, gauges
    states     {name: {duration: number | {table: [...]} | unknown,         temporary states / stances
                       ends_on_swap: bool, extend_on: {action: seconds},
                       on_enter: [ops], on_exit: [ops]}}
    rules      - {on: {event: action | hit | reaction | swap_in | swap_out | state_end,
                       action / types / elements / reactions / state filters,
                       by: self | party | party_others | active, while_state: name},
                  icd: seconds, do: [ops]}
               - {when: {resource: name, at_least: number}, do: [ops]}  thresholds
    summons    {name: {start_on: action, first, interval, count | duration,  periodic hits (Oz, Pyronado, DoTs)
                       ends_on_swap: bool, hits: [...]}}
    procs      {name: {on: {event: hit, by: active, types: [...]}, requires: {summon | state}, icd, hits: [...]}}
                                                                            hits triggered by others (Rain Swords)
    ops        gain {resource, amount: number | unknown | {per_burst_cost: rate}}, consume {resource, amount | all},
               enter {state}, exit {state}, extend {state, seconds}

Actions may require a state or a resource level, have uses per state instance, run ops, and have state-specific
variants ("attack#2@masterstroke"). Hits may add multiplier from a resource ({add_mult: {resource, per}}).

Unknown amounts propagate: a resource that received an unknown gain has value None from then on, and every effect or
multiplier depending on it is reported unknown (no credit), never guessed.

The simulation records a timeline the forward model reads per hit: state intervals and resource values over time.
"""
from __future__ import annotations

from gtc.forward import data as D
from gtc.forward.trace import Action, Hit

UNKNOWN = "unknown"


def _num(name: str, spec, level: int = 9):
    """A number from a literal or a talent table reference; None when unknown."""
    if spec is None or spec == UNKNOWN:
        return None
    if isinstance(spec, (int, float)):
        return float(spec)
    if isinstance(spec, dict) and "table" in spec:
        t = spec["table"]
        return D.value(name, t[0], t[1], level, t[2] if len(t) > 2 else 0)
    return None


class KitMixin:
    """Event machinery added to the generator's simulator (gtc/forward/generator._Sim)."""

    def _kit_init(self):
        self.res: dict[tuple, float | None] = {}
        self.res_log: dict[str, list] = {}
        self.state_log: list[tuple] = []
        self.rule_last: dict[tuple, float] = {}
        self.summons: list[dict] = []
        for m in [x for x in self.lineup if x in self.libs]:
            for r, spec in (self.libs[m].resources or {}).items():
                self._set_res(m, r, float(spec.get("start", 0) or 0), 0.0)

    # ---------- resources ----------
    def _set_res(self, who: str, r: str, v, t: float):
        self.res[(who, r)] = v
        self.res_log.setdefault(f"{who}:{r}", []).append((round(t, 3), v))

    def _cap(self, who: str, r: str, v):
        if v is None:
            return None
        mx = (self.libs[who].resources.get(r) or {}).get("max")
        mx = _num(who, mx)
        return min(v, mx) if mx is not None else v

    def run_ops(self, who: str, ops: list, t: float, ctx: dict | None = None):
        for op in ops or []:
            if "gain" in op:
                g = op["gain"]
                amt = g.get("amount")
                if isinstance(amt, dict) and "per_burst_cost" in amt:
                    amt = (ctx or {}).get("burst_cost", 0.0) * float(amt["per_burst_cost"])
                else:
                    amt = _num(who, amt)
                cur = self.res.get((who, g["resource"]), 0.0)
                self._set_res(who, g["resource"], None if (amt is None or cur is None) else self._cap(who, g["resource"], cur + amt), t)
                self._check_thresholds(who, t)
            elif "consume" in op:
                c = op["consume"]
                cur = self.res.get((who, c["resource"]), 0.0)
                if c.get("amount") == "all" or cur is None:
                    self._set_res(who, c["resource"], 0.0 if c.get("amount") == "all" else None, t)
                else:
                    self._set_res(who, c["resource"], max(0.0, cur - float(c.get("amount", 0))), t)
            elif "enter" in op:
                self.enter_state(who, op["enter"], t)
            elif "exit" in op:
                self.exit_state(who, op["exit"], t)
            elif "extend" in op:
                st = self.state(who, t)
                if st and st["name"] == op["extend"]["state"]:
                    st["end"] += float(op["extend"]["seconds"])
            elif "energy" in op:      # flat energy (ignores ER), e.g. Raiden's Musou Isshin restoration
                e = op["energy"]
                st = self.state(who, t)
                if e.get("max_per_state") and st:
                    n = st["uses"].get("_energy", 0)
                    if n >= e["max_per_state"]:
                        continue
                    st["uses"]["_energy"] = n + 1
                amt = _num(who, e.get("amount")) or 0.0
                to = e.get("to", "party")
                for m in self.lineup:
                    if to == "party_others" and m == who or to == "self" and m != who:
                        continue
                    self.energy[m] = min(self.cost[m], self.energy[m] + amt)
                    self.energy_log.append({"t": t, "char": m, "kind": "flat", "amount": amt, "source": who})
            elif "copy" in op:        # remember a resource's value (Resolve consumed by Raiden's Burst)
                c = op["copy"]
                self._set_res(who, c["to"], self.res.get((who, c["from"]), 0.0), t)
            elif "distinct" in op:    # resource = distinct event kinds seen in a window (Neuvillette's Glories)
                d = op["distinct"]
                hist = self.__dict__.setdefault("_distinct", {}).setdefault((who, d["resource"]), [])
                kind = str((ctx or {}).get("reaction", "")).split("-")[0]
                hist.append((t, kind))
                win = float(d.get("window", 30))
                kinds = {k for tt, k in hist if t - tt <= win}
                self._set_res(who, d["resource"], self._cap(who, d["resource"], float(len(kinds))), t)

    def _check_thresholds(self, who: str, t: float):
        for rule in self.libs[who].rules or []:
            w = rule.get("when")
            if not w:
                continue
            v = self.res.get((who, w["resource"]))
            if v is not None and v >= float(w["at_least"]):
                self.run_ops(who, rule.get("do"), t)

    # ---------- states ----------
    def enter_state(self, who: str, name: str, t: float):
        sd = (self.libs[who].states or {}).get(name) or {}
        dur = _num(who, sd.get("duration"))
        if dur is not None:
            dur += float(sd.get("lead", 0) or 0)      # the state runs from the end of the action that started it
        cur = next((s for s in self.states[who] if s["name"] == name and s["start"] <= t < s["end"]), None)
        if cur:
            cur["end"] = t + (dur if dur is not None else 999.0)
            return
        self.states[who].append({"name": name, "start": t, "end": t + (dur if dur is not None else 999.0), "uses": {},
                                 "nominal_end": t + (dur if dur is not None else 999.0),
                                 "unknown_duration": dur is None})
        self.run_ops(who, sd.get("on_enter"), t)

    def exit_state(self, who: str, name: str, t: float):
        st = next((s for s in self.states[who] if s["name"] == name and s["start"] <= t < s["end"]), None)
        if st:
            st["end"] = t
            self.run_ops(who, ((self.libs[who].states or {}).get(name) or {}).get("on_exit"), t)

    def swap_out(self, who: str, t: float):
        if who not in self.libs:
            return
        for name, sd in (self.libs[who].states or {}).items():
            if sd.get("ends_on_swap"):
                self.exit_state(who, name, t)
        for s in self.summons:
            if s["owner"] == who and s["spec"].get("ends_on_swap") and s["end"] > t:
                s["end"] = t
        self.dispatch({"event": "swap_out", "char": who, "t": t})

    # ---------- events ----------
    def dispatch(self, ev: dict):
        """Run every rule in the party matching this event (rules filter on who caused it)."""
        for m in [x for x in self.lineup if x in self.libs]:
            for i, rule in enumerate(self.libs[m].rules or []):
                on = rule.get("on")
                if not on or on.get("event") != ev["event"]:
                    continue
                by = on.get("by", "self")
                src = ev.get("char")
                if by == "self" and src != m or by == "party_others" and src == m:
                    continue
                if by == "active" and src != self.on_field:
                    continue
                if on.get("action") and ev.get("action") not in ([on["action"]] if isinstance(on["action"], str) else on["action"]):
                    continue
                if on.get("types") and ev.get("damage_type") not in on["types"]:
                    continue
                if on.get("elements") and ev.get("element") not in on["elements"]:
                    continue
                if on.get("reactions") and not any(str(ev.get("reaction", "")).startswith(r) for r in on["reactions"]):
                    continue
                if on.get("while_state") and on["while_state"] not in self.active_states(m, ev["t"]):
                    continue
                icd = float(rule.get("icd", 0) or 0)
                if icd and ev["t"] - self.rule_last.get((m, i), -99.0) < icd:
                    continue
                self.rule_last[(m, i)] = ev["t"]
                self.run_ops(m, rule.get("do"), ev["t"], ev)

    def _proc_list(self, on_action: bool) -> list:
        """The lineup's procs on actions (True) or on hits (False), in lineup order: computed once per simulation
        (the loops run on every action and every hit)."""
        key = "_procs_action" if on_action else "_procs_hit"
        v = self.__dict__.get(key)
        if v is None:
            v = [(m, name, p) for m in self.lineup if m in self.libs for name, p in (self.libs[m].procs or {}).items()
                 if ((p.get("on") or {}).get("event") == "action") == on_action]
            self.__dict__[key] = v
        return v

    def _has_action_procs(self) -> bool:
        """Whether any member has a proc on actions (cached: most lineups have none, and this runs on every action)."""
        v = self.__dict__.get("_action_procs")
        if v is None:
            v = any((p.get("on") or {}).get("event") == "action"
                    for m in self.lineup if m in self.libs for p in (self.libs[m].procs or {}).values())
            self._action_procs = v
        return v

    def _procs_sustained(self, upto: float):
        """Close the previous action's sustained window at `upto` (the next action's start, or the rotation end):
        an ICD that ran out while it was still being performed triggers then."""
        w = self.__dict__.pop("_sustain", None)
        while w:                        # a long action can span several ICDs
            n = len(self.hits)
            self._procs_on_action(*w, end=min(w[2] + w[3], upto))
            if len(self.hits) == n:
                break

    def _procs_on_action(self, who: str, action: str, t: float, dur: float = 0.0, end: float | None = None):
        """Procs on an action being PERFORMED (event: action), not on its hits landing: Xingqiu's Rain Swords and
        Yelan's Exquisite Throw fire when the active character performs a Normal Attack (Raiden's Musou attacks
        included), whether or not and whenever its hits land. `on.delay` is the measured action-start-to-trigger
        time; the ICD runs from the trigger. `on.sustained`: the action keeps qualifying for its whole duration, so
        an ICD that ends mid-action triggers right then (waves exactly one ICD apart while the attacks continue;
        measured: the modal wave spacing of both Rain Swords and Exquisite Throw in other teams' sims is 1.00 s).
        The window ends when the action does or the next one starts, whichever is first, so it is resolved then
        (end=...); at the action's start only the immediate trigger is checked."""
        if not self._has_action_procs():
            return
        if end is None:
            self._sustain = (who, action, t, dur)
        for m, name, p in self._proc_list(True):
            if True:
                on = p.get("on") or {}
                by = on.get("by", "active")
                if by in ("active", "self") and who != (self.on_field if by == "active" else m) or by == "party_others" and who == m:
                    continue
                if on.get("actions") and action not in on["actions"]:
                    continue
                delay = float(on.get("delay", 0) or 0)
                tt = t + delay
                key = (m, f"proc:{name}")
                if end is not None:
                    if not on.get("sustained"):
                        continue
                    tt = max(tt, self.rule_last.get(key, -99.0) + float(p.get("icd", 0) or 0))
                    if tt - delay >= end - 1e-6:
                        continue
                req = p.get("requires") or {}
                if req.get("summon") and not any(s["owner"] == m and s["name"] == req["summon"] and s["start"] <= tt < s["end"]
                                                 for s in self.summons):
                    continue
                if req.get("state") and req["state"] not in self.active_states(m, tt):
                    continue
                if tt - self.rule_last.get(key, -99.0) < float(p.get("icd", 0) or 0) - 1e-6:
                    continue
                self.rule_last[key] = tt
                specs = p.get("hits") or []
                if p.get("hits_cycle"):
                    n = self.__dict__.setdefault("_cycle", {}).get(key, 0)
                    specs = p["hits_cycle_t"][n % len(p["hits_cycle_t"])]
                    self._cycle[key] = n + 1
                for h in self._hits_from(m, specs, tt, name):
                    self.emit(h, proc=True)

    def _proc_icd(self, owner: str, p: dict, t: float) -> float:
        """A proc's interval, shortened while one of the owner's summons is active and the party has an element
        (Nahida's Shrine of Maya with an Electro teammate: Tri-Karma interval minus the Burst table's decrease)."""
        icd = float(p.get("icd", 0) or 0)
        r = p.get("icd_reduce")
        if r:
            live = any(s["owner"] == owner and s["name"] == r.get("summon") and s["start"] <= t < s["end"] for s in self.summons)
            has = not r.get("party_element") or any(self.el.get(m) == r["party_element"] for m in self.lineup if m != owner)
            if live and has:
                v = _num(owner, r.get("by")) or 0.0
                icd = max(0.0, icd - v)
        return icd

    def _procs_on_hit(self, hit: Hit):
        """Procs: hits other characters' kits add when this hit lands (Razor's Soul Companion on the active hit),
        with their own ICD and requirements. Procs on actions being performed are _procs_on_action."""
        for m, name, p in self._proc_list(False):
            if True:
                on = p.get("on") or {}
                by = on.get("by", "active")
                if by == "active" and hit.char != self.on_field or by == "self" and hit.char != m:
                    continue
                if by == "party_others" and hit.char == m:
                    continue
                if on.get("types") and hit.damage_type not in on["types"]:
                    continue
                if on.get("actions") and hit.from_action not in on["actions"]:
                    continue        # Rain Swords key on Normal Attack actions, including Raiden's Musou attacks
                req = p.get("requires") or {}
                if req.get("summon") and not any(s["owner"] == m and s["name"] == req["summon"] and s["start"] <= hit.t < s["end"]
                                                 for s in self.summons):
                    continue
                if req.get("state") and req["state"] not in self.active_states(m, hit.t):
                    continue
                key = (m, f"proc:{name}")
                if hit.t - self.rule_last.get(key, -99.0) < self._proc_icd(m, p, hit.t):
                    continue
                self.rule_last[key] = hit.t
                specs = p.get("hits") or []
                if p.get("hits_cycle"):
                    n = self.__dict__.setdefault("_cycle", {}).get(key, 0)
                    specs = p["hits_cycle_t"][n % len(p["hits_cycle_t"])]
                    self._cycle[key] = n + 1
                for h in self._hits_from(m, specs, hit.t, name, trigger=hit):
                    self.hits.append(h)

    def start_summon(self, who: str, name: str, t: float):
        spec = self.libs[who].summons[name]
        dur = _num(who, spec.get("duration"))
        count = spec.get("count")
        interval = float(spec.get("interval", 1.0))
        end = t + (dur if dur is not None else (float(spec.get("first", 0)) + interval * (int(count or 1) - 1) + 0.01))
        # a re-cast replaces the running instance; summons of one group replace each other (Fischl's Oz from the
        # Skill or from the Burst: one Oz)
        grp = spec.get("group")
        cap = spec.get("max_instances")
        if cap:
            # several instances at once (Yae's Sesshou Sakura, up to 3): past the cap the oldest one ends
            live = sorted((s for s in self.summons if s["owner"] == who and s["name"] == name and s["end"] > t),
                          key=lambda s: s["start"])
            for s in live[: max(0, len(live) - int(cap) + 1)]:
                s["end"] = t
        else:
            for s in self.summons:
                if s["owner"] == who and (s["name"] == name or grp and s["spec"].get("group") == grp) and s["end"] > t:
                    s["end"] = t
        self.summons.append({"owner": who, "name": name, "start": t, "end": end, "spec": spec, "next": t + float(spec.get("first", 0))})

    def tick_summons(self, upto: float):
        for s in self.summons:
            while s["next"] <= upto and s["next"] < s["end"]:
                lt = s["spec"].get("level_table")
                for h in self._hits_from(s["owner"], s["spec"].get("hits") or [], s["next"], s["name"], offset_base=True):
                    if lt:
                        # the strike's level is the number of instances present (Sesshou Sakura Level 1-3)
                        from gtc.forward import data as D

                        n = sum(1 for o in self.summons if o["owner"] == s["owner"] and o["name"] == s["name"]
                                and o["start"] <= s["next"] < o["end"])
                        lvl = int((getattr(self.builds.get(s["owner"]), "talents", None) or {}).get(lt[0], 9))
                        v = D.value(s["owner"], lt[0], lt[1].format(n=max(1, n)), lvl)
                        if v:
                            h.mult = v
                    self.hits.append(h)
                s["next"] += float(s["spec"].get("interval", 1.0))

    def _hits_from(self, who: str, specs: list, t: float, label: str, offset_base: bool = False, trigger=None) -> list[Hit]:
        from gtc.forward.library import HitTemplate

        out = []
        for hs in specs:
            h = hs if isinstance(hs, HitTemplate) else self.libs[who]._template(hs, label)
            ht = t + h.offset
            hit = self._make_hit(who, h, ht, t)
            if trigger is not None and getattr(h, "scale_trigger", False):
                hit.mult *= trigger.mult        # a share of the triggering hit (Razor's Soul Companion)
            out.append(hit)
        return out

    def _make_hit(self, who: str, h, ht: float, start: float) -> Hit:
        lib = self.libs[who]
        element = h.element or self.el[who]
        if element == "absorb":
            element = self._aura(ht) or self.el[who]
        infusing = {n: s["infuse"] for n, s in (lib.states or {}).items() if s.get("infuse")}
        if infusing and h.damage_type in ("normal", "charged", "plunge"):
            # kit language: an infusing state (Hu Tao's Paramita Papilio: Pyro) decides the element of Normal,
            # Charged and Plunging hits; outside it they are Physical (a measured kit bakes in the usual element)
            on = [n for n in self.active_states(who, ht) if n in infusing]
            element = infusing[on[-1]] if on else "Physical"
        gauge = self._gauge(who, h, ht) if (lib.hand or getattr(h, "icd", "")) else h.gauge
        if element == "Physical":
            gauge = 0.0
        mult = self._mult(who, h, ht) if lib.hand else h.mult
        add = getattr(h, "add_mult", None)
        unknown = False
        if add:
            v = self.res.get((who, add["resource"]))
            per = _num(who, add.get("per"))
            if v is None or per is None:
                unknown = True
            else:
                mult += v * per
        hit = Hit(t=ht, char=who, abil=h.abil, damage_type=h.damage_type, element=element, mult=mult,
                  scaling=h.scaling, action_t=start, ignore_def=h.ignore_def, gauge=gauge)
        tbl = getattr(h, "table", ()) or ()
        if lib.hand and tbl and getattr(h, "expand", False):
            # a row with several distinct stats (ATK + EM): the other terms, at the build's talent level
            from gtc.forward import data as D

            lvl = int((getattr(self.builds.get(who), "talents", None) or {}).get(tbl[0], 9))
            tm = D.terms(who, tbl[0], tbl[1], lvl)
            if len({s for _, s in tm if s}) > 1:
                idx = tbl[2] if len(tbl) > 2 else 0
                hit.extra = tuple((v, s) for j, (v, s) in enumerate(tm) if j != idx and s and s != h.scaling)
        if unknown:
            hit.abil += " [resource bonus unknown]"
        if element in ("Pyro", "Hydro", "Electro", "Cryo"):
            self.last_applied.append((ht, element))
        return hit

    def post_reactions(self, hits: list) -> None:
        """Rules on reaction events run after the reaction model has decided the rotation's reactions (they feed
        resources such as Neuvillette's Draconic Glories; actions never depend on them)."""
        for h in sorted(hits, key=lambda x: x.t):
            kind = h.reaction or h.amp or h.cata
            if kind:
                self.dispatch({"event": "reaction", "char": h.char, "t": h.t, "reaction": kind})

    def timeline(self) -> dict:
        # (member, state, start, end, nominal end): a swap that ends a state early leaves end < nominal end
        states = [(m, s["name"], round(s["start"], 3), round(s["end"], 3), round(s.get("nominal_end", s["end"]), 3))
                  for m in self.lineup for s in self.states[m]]
        return {"states": states, "resources": dict(self.res_log)}
