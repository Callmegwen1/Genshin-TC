"""Reaction model (phase B): an explicit, simplified aura simulation over a rotation's hits. Deterministic gauge
theory, not a frame-perfect emulator.

Gauge theory (game mechanics; gcsim implements the same):
    a hit that applies U units leaves an aura of 0.8 x U, decaying linearly over (2.5 x U + 7) s
    only hits that apply their element react (a hit inside its ICD neither reacts nor applies)
    Melt / Vaporize       forward (Pyro on Cryo, Hydro on Pyro): x2, consumes 2U; reverse: x1.5, consumes 0.5U
    Freeze                Cryo + Hydro: Frozen with 2 x min(trigger, aura) units, lasting 2*sqrt(5G+4)-4 s
    Shatter               a blunt hit (plunge, claymore, Geo) on a Frozen enemy: Shatter damage, Freeze removed
    Swirl                 Anemo on each swirlable aura present (Frozen counts as Cryo): consumes 0.5U each
    Crystallize           Geo on an aura: consumes 0.5U (shield, no damage)
    Overloaded, Superconduct   transformative damage, consume 1U
    Electro-Charged       Hydro and Electro coexist; a tick every 1 s consumes 0.4U of each. With a Lunar-Charged
                          conversion in the team (Flins, Ineffa kits) the ticks are Lunar-Charged, every 2.2 s
    Quicken               Electro + Dendro: a Quicken aura (gauge = the smaller one, lasting 12 x gauge + 6 s);
                          Electro hits on it Aggravate (+1.15 x level base, scaled by EM), Dendro hits Spread (x1.25);
                          the hit's own gauge refreshes Quicken
    Bloom                 Hydro + Dendro: a Dendro Core (at most 5; the oldest bursts when a 6th appears). A core
                          bursts after 6 s (Bloom, owned by whoever made it), or becomes Hyperbloom when an Electro hit
                          lands while it exists (owned by the Electro character), or Burgeon with Pyro
    Reaction damage cooldown   at most 2 instances of each transformative reaction kind per 0.5 s (gcsim's
                          reaction ICD groups, approximated)
Not modelled: multiple targets and aura tax, Burning, Lunar-Bloom / Lunar-Crystallize, Stellar reactions.

`simulate` returns (hits, counts). counts["_detail"] holds, per reaction: triggers, owners, which character's
application supplied the aura consumed, and per element the aura uptime (share of the rotation the aura existed).
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import replace

SWIRLABLE = ("Pyro", "Hydro", "Electro", "Cryo")
LUNAR_TICK, EC_TICK = 2.2, 1.0
CORE_LIFE, CORE_MAX = 6.0, 5
RX_ICD_WINDOW, RX_ICD_HITS = 0.5, 2
TRANSFORMATIVE_DAMAGE = ("swirl", "overloaded", "superconduct", "electrocharged", "shatter", "bloom", "hyperbloom",
                         "burgeon")


class Auras:
    def __init__(self):
        self.g: dict[str, float] = {}
        self.rate: dict[str, float] = {}
        self.by: dict[str, str] = {}       # who applied the current aura of an element
        self.t = 0.0
        self.uptime: dict[str, float] = defaultdict(float)

    def advance(self, t: float) -> None:
        dt = max(0.0, t - self.t)
        for el in list(self.g):
            life = self.g[el] / self.rate[el] if self.rate[el] > 0 else dt
            self.uptime[el] += min(dt, life)
            self.g[el] -= self.rate[el] * dt
            if self.g[el] <= 1e-6:
                self._drop(el)
        self.t = t

    def _drop(self, el):
        self.g.pop(el, None)
        self.rate.pop(el, None)
        self.by.pop(el, None)

    def apply(self, el: str, units: float, who: str = "") -> None:
        gauge = 0.8 * units
        dur = 2.5 * units + 7.0
        if self.g.get(el, 0.0) < gauge:
            self.g[el], self.rate[el] = gauge, gauge / dur
        self.by[el] = who

    def take(self, el: str, amount: float) -> None:
        if el in self.g:
            self.g[el] -= amount
            if self.g[el] <= 1e-6:
                self._drop(el)

    def freeze(self, amount: float, who: str = "") -> None:
        g = 2 * amount
        self.g["Frozen"] = max(self.g.get("Frozen", 0.0), g)
        self.rate["Frozen"] = self.g["Frozen"] / max(2 * math.sqrt(5 * self.g["Frozen"] + 4) - 4, 0.5)
        self.by["Frozen"] = who

    def quicken(self, amount: float, who: str = "") -> None:
        dur = 12 * amount + 6
        self.g["Quicken"] = max(self.g.get("Quicken", 0.0), amount)
        self.rate["Quicken"] = self.g["Quicken"] / dur
        self.by["Quicken"] = who

    def has(self, el: str) -> bool:
        return self.g.get(el, 0.0) > 1e-6


def _blunt(hit, weapon_of: dict) -> bool:
    return hit.damage_type == "plunge" or weapon_of.get(hit.char) == "claymore" or hit.element == "Geo"


def simulate(hits: list, lineup: list[str], lunar: bool | None = None) -> tuple[list, dict]:
    from gtc.forward.build import weapon_type
    from gtc.forward.trace import Hit

    if lunar is None:
        lunar = lunar_team(lineup)
    weapon_of = {m: weapon_type(m) for m in lineup}
    a = Auras()
    out: list = []
    counts: dict = {}
    owners: dict[str, Counter] = defaultdict(Counter)
    sources: dict[str, Counter] = defaultdict(Counter)
    suppressed: Counter = Counter()
    recent: dict[str, list[float]] = defaultdict(list)
    cores: list[dict] = []
    last_electro, next_tick = None, None
    ec_owner = None            # Electro-Charged belongs to whoever created or refreshed the Hydro + Electro coexistence

    def add(kind: str, owner: str, applier: str = ""):
        counts[kind] = counts.get(kind, 0) + 1
        owners[kind][owner] += 1
        if applier:
            sources[kind][applier] += 1

    def dmg(kind: str, t: float, owner: str, element: str, applier: str = "") -> None:
        fam = kind.split("-")[0]
        if fam in TRANSFORMATIVE_DAMAGE:
            r = [x for x in recent[kind] if t - x < RX_ICD_WINDOW]
            if len(r) >= RX_ICD_HITS:
                suppressed[kind] += 1
                recent[kind] = r
                return
            r.append(t)
            recent[kind] = r
        out.append(Hit(t=t, char=owner, abil=kind, damage_type="reaction", element=element, mult=0.0, scaling="em",
                       reaction=kind))
        add(kind, owner, applier)

    def burst_cores(upto: float):
        for c in [c for c in cores if c["t"] + CORE_LIFE <= upto]:
            cores.remove(c)
            dmg("bloom", c["t"] + CORE_LIFE, c["owner"], "Dendro", c["owner"])

    for h in sorted(hits, key=lambda x: x.t):
        if h.reaction:
            continue
        burst_cores(h.t)
        a.advance(h.t)
        while next_tick is not None and next_tick <= h.t:
            a.advance(next_tick)
            if a.has("Hydro") and a.has("Electro"):
                key = "lunarcharged" if lunar else "electrocharged"
                dmg(key, next_tick, ec_owner or last_electro or lineup[0], "Electro", a.by.get("Hydro", ""))
                if not lunar:
                    a.take("Hydro", 0.4)
                    a.take("Electro", 0.4)
                next_tick += LUNAR_TICK if lunar else EC_TICK
            else:
                next_tick = None
        a.advance(h.t)
        x = replace(h, amp="", cata="", reaction="", auras=tuple(sorted(k for k in list(a.g) if a.has(k))))
        el, u, who = h.element, h.gauge, h.char
        if a.has("Frozen") and _blunt(h, weapon_of):
            dmg("shatter", h.t, who, "Physical", a.by.get("Frozen", ""))
            a.take("Frozen", 1e9)
        # Dendro Cores react to Electro / Pyro hits that apply their element
        if u > 0 and cores and el in ("Electro", "Pyro"):
            # an Electro / Pyro application hits every Dendro Core present (gcsim: hyperbloom triggered for each);
            # the reaction damage cooldown still limits the damage instances
            while cores:
                c = cores.pop(0)
                dmg("hyperbloom" if el == "Electro" else "burgeon", h.t, who, "Dendro", c["owner"])
        if u <= 0 or el in ("Physical", ""):
            out.append(x)
            continue
        if el == "Anemo":
            # Swirl uses up the Anemo hit's durability as it reacts: each aura (Electro, Hydro, Pyro, Cryo, then
            # Frozen) loses half of what is left, and only what remains reaches the next one (gcsim aura logs: a 1U
            # hit on Cryo + Frozen takes 0.5U of Cryo and leaves Frozen untouched; a 2U hit empties a small Cryo and
            # takes the rest from Frozen)
            left = u
            for sw in ("Electro", "Hydro", "Pyro", "Cryo", "Frozen"):
                if left <= 1e-6 or not a.has(sw):
                    continue
                kind = "Cryo" if sw == "Frozen" else sw
                dmg(f"swirl-{kind.lower()}", h.t, who, kind, a.by.get(sw, ""))
                used = min(a.g[sw], 0.5 * left)
                a.take(sw, used)
                left -= 2 * used
            out.append(x)
            continue
        if el == "Geo":
            for e in ("Pyro", "Hydro", "Electro", "Cryo"):
                if a.has(e):
                    a.take(e, 0.5 * u)
                    add("crystallize", who, a.by.get(e, ""))
                    break
            out.append(x)
            continue
        if el == "Pyro":
            if a.has("Frozen") or a.has("Cryo"):
                x.amp = "melt"
                add("melt", who, a.by.get("Cryo") or a.by.get("Frozen", ""))
                a.take("Frozen" if a.has("Frozen") else "Cryo", 2 * u)
            elif a.has("Hydro"):
                x.amp = "vaporize"
                add("vaporize", who, a.by.get("Hydro", ""))
                a.take("Hydro", 0.5 * u)
            elif a.has("Electro"):
                dmg("overloaded", h.t, who, "Pyro", a.by.get("Electro", ""))
                a.take("Electro", u)
            elif a.has("Dendro") or a.has("Quicken"):
                add("burning-unmodelled", who)
                a.apply("Pyro", u, who)
            else:
                a.apply("Pyro", u, who)
        elif el == "Hydro":
            if a.has("Pyro"):
                x.amp = "vaporize"
                add("vaporize", who, a.by.get("Pyro", ""))
                a.take("Pyro", 2 * u)
            elif a.has("Cryo"):
                amt = min(u, a.g["Cryo"])
                applier = a.by.get("Cryo", "")
                a.take("Cryo", amt)
                a.freeze(amt, who)
                add("freeze", who, applier)
            elif a.has("Dendro") or a.has("Quicken"):
                src = "Dendro" if a.has("Dendro") else "Quicken"
                add("bloom-core", who, a.by.get(src, ""))
                a.take(src, 0.5 * u)    # Hydro on Dendro is the weak side: 0.5x (gcsim aura logs: 5299 of 5299)
                cores.append({"t": h.t, "owner": who})
                if len(cores) > CORE_MAX:
                    old = cores.pop(0)
                    dmg("bloom", h.t, old["owner"], "Dendro", old["owner"])
                if src == "Quicken" and a.has("Electro"):
                    # Hydro next to Electro: the two coexist and Electro-Charged runs (gcsim: EC owned by the Hydro unit)
                    a.apply("Hydro", u, who)
                    ec_owner = who
                    if next_tick is None:
                        next_tick = h.t + (LUNAR_TICK if lunar else EC_TICK) / 2
            else:
                a.apply("Hydro", u, who)
                if a.has("Electro"):
                    ec_owner = who
                if a.has("Electro") and next_tick is None:
                    next_tick = h.t + (LUNAR_TICK if lunar else EC_TICK) / 2
        elif el == "Cryo":
            if a.has("Pyro"):
                x.amp = "melt"
                add("melt", who, a.by.get("Pyro", ""))
                a.take("Pyro", 0.5 * u)
            elif a.has("Hydro"):
                amt = min(u, a.g["Hydro"])
                applier = a.by.get("Hydro", "")
                a.take("Hydro", amt)
                a.freeze(amt, who)
                add("freeze", who, applier)
            elif a.has("Electro"):
                dmg("superconduct", h.t, who, "Cryo", a.by.get("Electro", ""))
                a.take("Electro", u)
            else:
                a.apply("Cryo", u, who)
        elif el == "Electro":
            last_electro = who
            if a.has("Quicken"):
                # Aggravate does not consume Quicken; the Electro then reacts with a Dendro aura alongside (Quicken
                # refreshed) or stays as its own aura next to Quicken (gcsim logs: after = [electro, quicken])
                x.cata = "aggravate"
                add("aggravate", who, a.by.get("Quicken", ""))
                if a.has("Dendro"):
                    amt = min(u, a.g["Dendro"])
                    applier = a.by.get("Dendro", "")
                    a.take("Dendro", amt)
                    a.quicken(amt, who)
                    add("quicken", who, applier)
                else:
                    a.apply("Electro", u, who)
                    if a.has("Hydro"):
                        ec_owner = who
                    if a.has("Hydro") and next_tick is None:
                        next_tick = h.t + (LUNAR_TICK if lunar else EC_TICK) / 2
            elif a.has("Pyro"):
                dmg("overloaded", h.t, who, "Electro", a.by.get("Pyro", ""))
                a.take("Pyro", u)
            elif a.has("Cryo") or a.has("Frozen"):
                dmg("superconduct", h.t, who, "Cryo", a.by.get("Cryo") or a.by.get("Frozen", ""))
                a.take("Frozen" if a.has("Frozen") else "Cryo", u)
            elif a.has("Dendro"):
                amt = min(u, a.g["Dendro"])
                applier = a.by.get("Dendro", "")
                a.take("Dendro", amt)
                a.quicken(amt, who)
                add("quicken", who, applier)
            else:
                a.apply("Electro", u, who)
                if a.has("Hydro"):
                    ec_owner = who
                if a.has("Hydro") and next_tick is None:
                    next_tick = h.t + (LUNAR_TICK if lunar else EC_TICK) / 2
        elif el == "Dendro":
            if a.has("Quicken"):
                x.cata = "spread"
                add("spread", who, a.by.get("Quicken", ""))
                if a.has("Electro"):
                    amt = min(u, a.g["Electro"])
                    applier = a.by.get("Electro", "")
                    a.take("Electro", amt)
                    a.quicken(amt, who)
                    add("quicken", who, applier)
                elif a.has("Hydro"):
                    add("bloom-core", who, a.by.get("Hydro", ""))
                    a.take("Hydro", 2 * u)
                    cores.append({"t": h.t, "owner": who})
                    if len(cores) > CORE_MAX:
                        old = cores.pop(0)
                        dmg("bloom", h.t, old["owner"], "Dendro", old["owner"])
                else:
                    a.apply("Dendro", u, who)
            elif a.has("Hydro") or a.has("Electro"):
                # Dendro on Electro + Hydro (Electro-Charged): Quicken with the Electro first (1:1), then the rest of
                # the Dendro Blooms with the Hydro at 2x (gcsim aura logs: after = quicken, or quicken + leftover Hydro)
                left = u
                if a.has("Electro"):
                    amt = min(left, a.g["Electro"])
                    applier = a.by.get("Electro", "")
                    a.take("Electro", amt)
                    a.quicken(amt, who)
                    add("quicken", who, applier)
                    left -= amt
                if a.has("Hydro") and left > 1e-6:
                    add("bloom-core", who, a.by.get("Hydro", ""))
                    a.take("Hydro", 2 * left)    # Dendro on Hydro is the strong side: 2x
                    cores.append({"t": h.t, "owner": who})
                    if len(cores) > CORE_MAX:
                        old = cores.pop(0)
                        dmg("bloom", h.t, old["owner"], "Dendro", old["owner"])
            elif a.has("Pyro"):
                add("burning-unmodelled", who)
                a.apply("Dendro", u, who)
            else:
                a.apply("Dendro", u, who)
        out.append(x)
    end = max((h.t for h in hits), default=0.0)
    burst_cores(end + CORE_LIFE)
    a.advance(end)
    counts["_detail"] = {"owners": {k: dict(v) for k, v in owners.items()},
                         "aura_sources": {k: dict(v) for k, v in sources.items()},
                         "suppressed_by_reaction_icd": dict(suppressed),
                         "aura_uptime": {k: round(v / end, 3) for k, v in a.uptime.items()} if end else {},
                         "duration": end}
    return sorted(out, key=lambda x: x.t), counts


def annotate_auras(hits: list, lineup: list[str]) -> None:
    """Set `auras` on hits whose aura state is unknown (a traced rotation: gcsim supplied the reactions, not the aura
    timeline) by running the aura simulation over their element applications. Reactions are not changed."""
    todo = [h for h in sorted(hits, key=lambda x: x.t) if not h.reaction]
    if not todo or all(h.auras is not None for h in todo):
        return
    out, _ = simulate(todo, lineup)
    sim = [x for x in out if x.damage_type != "reaction" or not x.reaction]
    for h, x in zip(todo, sim):
        if h.auras is None:
            h.auras = x.auras


def lunar_team(lineup: list[str]) -> bool:
    """A team whose kits convert Electro-Charged into Lunar-Charged (a reaction_conversion effect to lunarcharged)."""
    from gtc.kits import kit

    for m in lineup:
        for e in (kit(m) or {}).get("effects") or []:
            if e.get("kind") == "reaction_conversion" and "lunarcharged" in ((e.get("affects") or {}).get("reactions") or []):
                return True
    return False


def summary(counts: dict) -> dict:
    """Per reaction: triggers, rate per second, owners, aura sources; aura uptime; ICD suppressions."""
    d = counts.get("_detail") or {}
    dur = d.get("duration") or 1.0
    out = {}
    for k, n in counts.items():
        if k.startswith("_"):
            continue
        out[k] = {"triggers": n, "per_second": round(n / dur, 3), "owners": d.get("owners", {}).get(k, {}),
                  "aura_from": d.get("aura_sources", {}).get(k, {})}
    return {"reactions": out, "aura_uptime": d.get("aura_uptime", {}),
            "suppressed_by_reaction_icd": d.get("suppressed_by_reaction_icd", {})}


_ENVELOPE: dict | None = None


def envelope() -> dict:
    """Community 99th-percentile reaction rates per second (all simulated lineups' trigger rates): the plausibility
    envelope for generated rotations. gcsim as examiner, never as an input to a team's numbers."""
    global _ENVELOPE
    if _ENVELOPE is None:
        from collections import defaultdict

        from gtc.synergy import load_database

        rates = defaultdict(list)
        for e in load_database().values():
            tot = defaultdict(float)
            for d in ((e.get("profile") or {}).get("members") or {}).values():
                for k, v in ((d or {}).get("triggers") or {}).items():
                    tot[k] += v
            for k, v in tot.items():
                rates[k].append(v / 10.0)      # the database stores triggers per 10 s
        _ENVELOPE = {("overloaded" if k == "overload" else k): sorted(v)[min(len(v) - 1, int(len(v) * 0.99))]
                     for k, v in rates.items() if len(v) >= 20}
    return _ENVELOPE


def plausibility(rates: dict) -> list[str]:
    """Flags for reaction rates above anything the community has simulated (99th percentile)."""
    env = envelope()
    out = []
    for k, v in rates.items():
        fam = "swirl" if k.startswith("swirl") else k
        lim = env.get(fam)
        if lim and v > lim:
            out.append(f"{k}: {v:.2f}/s is above the community 99th percentile ({lim:.2f}/s): check application and ICDs")
    return out
