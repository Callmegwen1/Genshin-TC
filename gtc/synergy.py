"""Measured synergy: how much of each character's damage comes from each teammate's buffs.

gcsim's sample log records, for every hit, the full damage calculation and every buff and RES shred active
on it, with its source and value. For each hit and each buff we recompute the hit without that buff using
the game formulas; the difference is that buff's contribution. Summing contributions by the character who
provides each buff gives typed, measured synergy:

    "Sucrose's buffs supply 14% of this team's damage: Elemental Mastery on Flins's Lunar hits 9%,
     Electro RES shred 5%."

Contributions are marginal (each buff removed alone), the standard way theorycrafters value a buff. They do
not add up exactly to the team total when buffs multiply each other; the difference is small and reported.

Reaction bonuses and Lunar base-damage bonuses appear in the log only as totals per hit. They are split
between their known sources using knowledge/kits.yaml; whatever cannot be placed is reported as unattributed.
"""
from __future__ import annotations

from gtc import params

import hashlib
import json
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field

from gtc.sim import GCSIM, SIM_DIR, ensure_binary
from gtc.sources.names import norm
from gtc.tc.formulas import crit_avg, em_additive, em_amplifying, em_lunar, em_transformative, reaction_base, res_mult
from gtc.tc.profile import SNAP

STAT_RE = re.compile(r"^\s*([a-z%]+):\s*(-?[\d.]+)\s*$")
LUNAR_DIRECT_TAGS = {29, 30, 31}  # gcsim attack tags for direct Lunar damage (checked against logs)

# Reaction facts come from gtc/reactions.py. Transformative damage is logged as one flat figure:
# multiplier x level base x (1 + 16 EM / (2000 + EM) + reaction bonus), so the bonus can be solved for.
from gtc.reactions import AMP_AURA, CATALYZE, CORE_REACTIONS, REACTION_AURAS, TRANSFORMATIVE  # noqa: E402

# Enablement: the aura a reaction consumes. Amplifying hits credit the amplified part (1 - 1/multiplier) to
# whoever applied the aura. Transformative and catalyze reactions credit ENABLE_SHARE of the reaction damage to
# the aura's appliers (the trigger keeps the rest); Hyperbloom and Burgeon credit it to whoever made the core.
ENABLE_SHARE = params.get("synergy.enable_share")

# Flat damage added to hits is logged only as a total. Known providers, and which hits they add to.
FLAT_DMG_PROVIDERS = {"Shenhe": {"element": "cryo"}, "Yun Jin": {"attack_tags": {1}}}
NORMAL_ATTACK_TAG = 1

# Set buffs that act on teammates, by gcsim mod key prefix, mapped to the set whose holder provides them.
TEAM_SET_KEYS = {
    "gleaming-moon-devotion": "Silken Moon's Serenade",
    "gleaming-moon-intent": "Night of the Sky's Unveiling",
    "nob": "Noblesse Oblige", "noblesse": "Noblesse Oblige",
    "tom": "Tenacity of the Millelith", "millelith": "Tenacity of the Millelith",
    "instructor": "Instructor", "archaic": "Archaic Petra", "petra": "Archaic Petra",
    "deepwood": "Deepwood Memories", "dm": "Deepwood Memories", "scroll": "Scroll of the Hero of Cinder City",
    "cinder": "Scroll of the Hero of Cinder City", "songofdayspast": "Song of Days Past", "sodp": "Song of Days Past",
    "vv": "Viridescent Venerer",
}


@dataclass
class Contribution:
    owner: str
    target: str
    kind: str  # stat name such as em, atk%, cr, cryo%, or "res shred"
    damage: float


@dataclass
class TeamSynergy:
    lineup: list[str]
    total: float
    own: dict[str, float]  # each member's own damage
    contributions: list[Contribution] = field(default_factory=list)
    unattributed: float = 0.0
    profile: dict = field(default_factory=dict)  # measured capabilities, see Attributor.measure_profile
    shapley: dict[str, float] = field(default_factory=dict)  # each member's fair share of buffs given (sums exactly)
    enablement: list[Contribution] = field(default_factory=list)  # reactions their auras or cores made possible

    # Attribution views, kept apart because they answer different questions (phase 6):
    #   ownership     own[m]: damage m's hits dealt
    #   marginal      buff_share(m): what teammates' hits lose when m's buffs alone are removed (overlapping buffs
    #                 each count fully, so marginal shares can add to more than the buffed damage)
    #   Shapley       shapley_share(m): m's fair split of the buffed damage, which sums exactly over givers
    #   enablement    enable_share(m, "enablement"): reaction damage m's auras or Dendro cores made possible
    #   amplification enable_share(m, "amplification"): the amplified part of Vaporize and Melt hits on m's aura
    # Enablement and amplification overlap with the triggering member's ownership; they never add to it.
    def enable_share(self, owner: str, kind: str | None = None) -> float:
        return sum(c.damage for c in self.enablement if c.owner == owner and c.target != owner
                   and (kind is None or c.kind == kind)) / self.total if self.total else 0.0

    def shapley_share(self, owner: str) -> float:
        return self.shapley.get(owner, 0.0) / self.total if self.total else 0.0

    def buff_share(self, owner: str) -> float:
        return sum(c.damage for c in self.contributions if c.owner == owner and c.target != owner) / self.total if self.total else 0.0

    def own_share(self, name: str) -> float:
        return self.own.get(name, 0.0) / self.total if self.total else 0.0

    def breakdown(self, owner: str) -> dict[tuple[str, str], float]:
        """(target, kind) -> share of team damage, for buffs `owner` gives teammates."""
        out: dict[tuple[str, str], float] = defaultdict(float)
        for c in self.contributions:
            if c.owner == owner and c.target != owner:
                out[(c.target, c.kind)] += c.damage / self.total
        return dict(out)


def run_sample(text: str, keep: bool = True) -> dict:
    """gcsim -sample for a config. Logs are about 3 MB each, so batch runs pass keep=False and delete them."""
    ensure_binary()
    SIM_DIR.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha1(text.encode()).hexdigest()[:16]
    cfg, out = SIM_DIR / f"{h}.txt", SIM_DIR / f"{h}.sample.json"
    if not out.exists():
        cfg.write_text(text, encoding="utf-8")
        proc = subprocess.run([str(GCSIM), "-c", str(cfg), "-sample", str(out)], capture_output=True, text=True, timeout=300)
        if proc.returncode != 0 or not out.exists():
            raise RuntimeError((proc.stdout + proc.stderr)[-400:])
    data = json.loads(out.read_text(encoding="utf-8"))
    if not keep:
        out.unlink(missing_ok=True)
        cfg.unlink(missing_ok=True)
    return data


def _stats(entries) -> list[tuple[str, float]]:
    out = []
    if not isinstance(entries, list) or not any("status: added" in str(x) for x in entries):
        return out
    for x in entries:
        m = STAT_RE.match(str(x))
        if m and m.group(1) not in ("expiry_frame",):
            out.append((m.group(1), float(m.group(2))))
    return out


class Attributor:
    def __init__(self, sample: dict, names, kits: dict):
        self.names, self.kits = names, kits
        self.members = []
        self.sets: dict[str, dict[str, int]] = {}
        for c in sample["character_details"]:
            name = names.character(c["name"]) or c["name"]
            self.members.append(name)
            self.sets[name] = {(names.artifact_set(k) or k): n for k, n in (c.get("sets") or {}).items()}
        self.norm_members = {norm(m): m for m in self.members}
        self.logs = sample["logs"]
        self.cons = {}
        self.stats = {}
        for c in sample["character_details"]:
            name = names.character(c["name"]) or c["name"]
            self.cons[name] = c.get("cons") or 0
            snap = c.get("snapshot") or []
            self.stats[name] = {k: (snap[i] if i < len(snap) else 0.0) for k, i in SNAP.items()}
        self.weapon_holder: dict[str, str] = {}
        aliases = _weapon_aliases()
        for c in sample["character_details"]:
            name = names.character(c["name"]) or c["name"]
            wname = norm((c.get("weapon") or {}).get("name", ""))
            canon = aliases.get(wname, wname)
            for alias, target in aliases.items():
                if target == canon:
                    self.weapon_holder[alias] = name
            self.weapon_holder[wname] = name
        moonsign = sum((kits.get(m) or {}).get("moonsign", 0) for m in self.members)
        self.lunar_sources = {m: self._lunar_sources(m, moonsign) for m in self.members}

    def _lunar_sources(self, target: str, moonsign: int) -> list[tuple[str, str, float]]:
        """Known reaction and base-damage bonuses on `target`'s Lunar damage, from kits: (owner, react|base, value)."""
        out = []

        def take(spec, caster):
            if spec.get("kind") not in ("react_bonus", "base_bonus"):
                return
            if spec.get("applies_to") and not set(spec["applies_to"]) & {"lunar_charged_direct", "lunar_charged_reaction"}:
                return
            when = spec.get("when") or {}
            if moonsign < when.get("moonsign_at_least", 0) or self.cons.get(caster, 0) < spec.get("constellation", 0):
                return
            tgt = spec.get("target", "party")
            if tgt == "self" and caster != target or tgt == "others" and caster == target:
                return
            val = spec["value"]
            if isinstance(val, dict):
                stat = self.stats.get(caster, {}).get(val["of"], 0.0)
                val = min(stat / val.get("per", 1) * val["rate"], val.get("cap", 1e9))
            out.append((caster, "react" if spec["kind"] == "react_bonus" else "base", float(val) * spec.get("uptime", 1.0)))

        for m in self.members:
            for spec in (self.kits.get(m) or {}).get("effects", []):
                take(spec, m)
            for set_name, n in self.sets.get(m, {}).items():
                if n >= 4:
                    for spec in (self.kits.get("_sets") or {}).get(set_name, []):
                        take(spec, m)
        return out

    def _lunar_bonus_contribs(self, target: str, dmg: float, em: float, react: float, base: float) -> list[Contribution]:
        """Split a Lunar hit's reaction and base-damage bonus totals among their known sources."""
        out = []
        srcs = self.lunar_sources.get(target, [])
        for kind, total in (("react", react), ("base", base)):
            mine = [(o, v) for o, k, v in srcs if k == kind]
            expected = sum(v for _, v in mine)
            if not mine or total <= 0:
                continue
            scale = min(1.0, total / expected) if expected else 0.0
            for owner, v in mine:
                v *= scale
                if kind == "react":
                    ratio = (1 + em_lunar(em) + react - v) / (1 + em_lunar(em) + react)
                else:
                    ratio = (1 + base - v) / (1 + base)
                out.append(Contribution(owner, target, "Lunar reaction bonus" if kind == "react" else "Lunar base DMG", dmg * (1 - ratio)))
        return out

    def _member(self, token: str) -> str | None:
        """A character from a gcsim key token: a display name, or one of gcsim's short aliases ("chev",
        "xq", "esco", "kaz"). Missing the aliases credited those characters' buffs to the attacker."""
        token = norm(token)
        if token in self.norm_members:
            return self.norm_members[token]
        name = self.names.character(token) or self.names.character(_char_aliases().get(token, ""))
        return name if name in self.members else None

    def owner_of(self, key: str, attacker: str) -> str:
        """Who provides a buff, from its gcsim key: '<character>-...', '<weapon>-<holder>', or a team set."""
        parts = key.split("-")
        if len(parts) > 1 and self._member(parts[-1]):
            return self._member(parts[-1])
        if self._member(parts[0]):
            return self._member(parts[0])
        for k in (norm(key), norm(parts[0])):
            if k in self.weapon_holder:
                return self.weapon_holder[k]
        for prefix, set_name in TEAM_SET_KEYS.items():
            if norm(key).startswith(norm(prefix)):
                holders = [m for m in self.members if self.sets.get(m, {}).get(set_name, 0) >= 4]
                if holders:
                    return attacker if attacker in holders else holders[0]
        return attacker

    def resist_owner(self, key: str, attacker: str) -> str:
        if key.startswith("vv"):
            holders = [m for m in self.members if self.sets.get(m, {}).get("Viridescent Venerer", 0) >= 4]
            if holders:
                return holders[0]
        return self.owner_of(key, attacker)

    def attribute(self) -> TeamSynergy:
        calcs = {}
        for l in self.logs:
            if l.get("event") == "calc":
                calcs.setdefault((l["frame"], l["char_index"], l["logs"].get("abil")), []).append(l["logs"])
        own: dict[str, float] = defaultdict(float)
        contributions: list[Contribution] = []
        unattributed = 0.0
        total = 0.0
        last_mods: dict[str, dict] = {}
        last_resist: dict[str, list] = {}
        contributors: dict[int, list[dict]] = defaultdict(list)
        self.react_mods: list[tuple[int, int, str, int]] = []  # (frame added, receiver index, key, expiry frame)
        # Logged reaction-bonus values per hit: "<abil> [React Bonus]" carries {key: value} for the attacker.
        self.react_values: dict[tuple[int, int, str], dict[str, float]] = {}
        for l in self.logs:
            if l.get("event") == "pre_damage_mods" and str(l.get("msg", "")).endswith("[React Bonus]") and l.get("logs"):
                abil = str(l["msg"])[: -len(" [React Bonus]")]
                vals = {k: float(v) for k, v in l["logs"].items() if isinstance(v, (int, float))}
                if vals:
                    self.react_values[(l["frame"], l.get("char_index", -1), abil)] = vals
        self.shapley: dict[str, float] = defaultdict(float)
        self.enable: list[Contribution] = []
        self.aura: dict[int, dict[str, dict[str, float]]] = defaultdict(dict)  # target -> element -> applier -> durability
        self.cores: dict[int, dict[str, float]] = {}  # dendro core source frame -> creator shares
        core_queue: dict[int, list[int]] = defaultdict(list)  # trigger index -> core sources, oldest first
        for l in self.logs:
            if l.get("msg") == "react bonus mod added":
                exp = (l.get("logs") or {}).get("expiry", -1)
                self.react_mods.append((l["frame"], l.get("char_index", -1), (l.get("logs") or {}).get("key", ""), exp))
            if l.get("event") == "element" and str(l.get("msg", "")).startswith("lunarcharged contributor"):
                c = dict(l["logs"])
                c["who"] = self.members[l["char_index"]] if 0 <= l.get("char_index", -1) < len(self.members) else "?"
                contributors[l["frame"]].append(c)
        for l in self.logs:
            ev = l.get("event")
            if ev == "element":
                msg = str(l.get("msg", ""))
                if msg == "application":
                    self._track_aura(l)
                elif msg == "dendro core spawned":
                    self._spawn_core(l)
                elif msg.endswith("triggered") and (l.get("logs") or {}).get("dendro_core_src") is not None:
                    core_queue[l.get("char_index", -1)].append(l["logs"]["dendro_core_src"])
                continue
            if ev != "damage":
                continue
            lg = l["logs"]
            dmg = float(lg.get("damage") or 0)
            if dmg <= 0:
                continue
            attacker = self.members[l["char_index"]] if 0 <= l.get("char_index", -1) < len(self.members) else "?"
            total += dmg
            own[attacker] += dmg
            if isinstance(lg.get("resist_mods"), list) and lg.get("ele"):
                last_resist[str(lg["ele"]).lower()] = lg["resist_mods"]
            if lg.get("abil") == "lunarcharged" and contributors.get(l["frame"]):
                got = self._lunar_charged_hit(dmg, contributors[l["frame"]], last_mods, last_resist.get("electro"))
                for c in got:
                    if c.owner != c.target:
                        self.shapley[c.owner] += c.damage
                contributions += got
                continue
            calc_list = calcs.get((l["frame"], l["char_index"], lg.get("abil"))) or []
            abil = str(lg.get("abil", ""))
            if abil in TRANSFORMATIVE or abil in CORE_REACTIONS:
                self._enable_reaction(attacker, abil, dmg, int(lg.get("target", 1) or 1), core_queue.get(l["char_index"]))
            if abil in TRANSFORMATIVE and calc_list:
                got = self._transformative_hit(attacker, abil, calc_list.pop(0), dmg, last_mods, l["frame"], l["char_index"])
                for c in got:
                    if c.owner != attacker:
                        self.shapley[c.owner] += c.damage  # few, independent sources: marginal = fair share
                contributions += got
                continue
            mods_here = {k: v for k, v in lg.items() if isinstance(v, list) and k not in ("resist_mods", "pre_damage_mods")}
            if mods_here:
                last_mods[attacker] = mods_here
            calc = calc_list.pop(0) if calc_list else None
            if calc and calc.get("melt_vape"):
                self._enable_amp(attacker, lg, calc, dmg)
            for c in self._hit(attacker, lg, calc, dmg, l["frame"], l["char_index"]):
                if c.owner == attacker and c.kind != "res shred":
                    continue  # self-buffs are part of the character's own damage
                contributions.append(c)
        syn = TeamSynergy(self.members, total, dict(own), contributions, unattributed)
        syn.profile = self.measure_profile(own, total)
        syn.shapley = dict(self.shapley)
        syn.enablement = self.enable
        return syn

    # ---------- enablement ----------
    @staticmethod
    def _gauge(entries) -> dict[str, float]:
        out = {}
        for x in entries or []:
            if ":" in str(x):
                k, v = str(x).split(":", 1)
                try:
                    out[k.strip().lower()] = float(v)
                except ValueError:
                    pass
        return out

    def _track_aura(self, l: dict) -> None:
        """Keep who supplied each aura's durability: existing contributions are scaled to the logged durability
        (decay and consumption), and the applier is credited with what their application added."""
        lg = l.get("logs") or {}
        target = int(lg.get("target", 1) or 1)
        who = self.members[l["char_index"]] if 0 <= l.get("char_index", -1) < len(self.members) else None
        existing, after = self._gauge(lg.get("existing")), self._gauge(lg.get("after"))
        applied = str(lg.get("applied_ele", "")).lower()
        state = self.aura[target]
        for ele in list(state):
            if ele not in existing and ele not in after:
                del state[ele]
        for ele, dur in after.items():
            contrib = state.get(ele, {})
            before = existing.get(ele, 0.0)
            tot = sum(contrib.values())
            contrib = {k: v * before / tot for k, v in contrib.items()} if tot > 0 and before > 0 else {}
            added = dur - before
            if ele == applied and who and added > 0:
                contrib[who] = contrib.get(who, 0.0) + added
            elif not contrib and who and dur > 0:
                contrib = {who: dur}  # a reaction product such as Quicken, made by this application
            tot = sum(contrib.values())
            if tot > 0:
                state[ele] = {k: v * dur / tot for k, v in contrib.items()}
            else:
                state.pop(ele, None)

    def _aura_shares(self, target: int, elements) -> dict[str, float]:
        tot: dict[str, float] = defaultdict(float)
        for ele in elements:
            for k, v in self.aura.get(target, {}).get(ele, {}).items():
                tot[k] += v
        s = sum(tot.values())
        return {k: v / s for k, v in tot.items()} if s > 0 else {}

    def _spawn_core(self, l: dict) -> None:
        """A Dendro core: half to the character whose hit made the Bloom, half to the Hydro and Dendro auras' owners."""
        lg = l.get("logs") or {}
        who = self.members[l["char_index"]] if 0 <= l.get("char_index", -1) < len(self.members) else None
        auras = self._aura_shares(int(lg.get("target", 1) or 1), ("hydro", "dendro"))
        shares: dict[str, float] = {}
        if who:
            shares[who] = ENABLE_SHARE if auras else 1.0
        for k, v in auras.items():
            shares[k] = shares.get(k, 0.0) + (1 - ENABLE_SHARE if who else 1.0) * v
        self.cores[lg.get("src", l["frame"])] = shares

    def _enable_amp(self, attacker: str, lg: dict, calc: dict, dmg: float) -> None:
        mult = calc.get("amp_mult_total") or 0.0
        aura = AMP_AURA.get((str(lg.get("amp", "")).lower(), str(lg.get("ele", "")).lower()))
        if mult <= 1 or not aura:
            return
        enabled = dmg * (1 - 1 / mult)
        for who, share in self._aura_shares(int(lg.get("target", 1) or 1), (aura,)).items():
            if who != attacker:
                self.enable.append(Contribution(who, attacker, "amplification", enabled * share))

    def _enable_reaction(self, attacker: str, abil: str, dmg: float, target: int, queue: list[int] | None) -> None:
        if abil in CORE_REACTIONS:
            shares = self.cores.get(queue.pop(0)) if queue else None
        else:
            shares = self._aura_shares(target, REACTION_AURAS.get(abil, ()))
        for who, share in (shares or {}).items():
            if who != attacker:
                self.enable.append(Contribution(who, attacker, "enablement", ENABLE_SHARE * dmg * share))

    # ---------- fair shares (Shapley) ----------
    def _shapley_hit(self, attacker: str, effects: list[tuple[str, str, float]], ctx: dict, dmg: float) -> None:
        """Exact Shapley values over the teammates whose buffs touched this hit. The hit is recomputed with
        every subset of their buffs removed (at most 2^3 subsets), and each teammate gets their average marginal
        contribution over all orderings. The shares sum exactly to the hit minus the hit without any teammate buff."""
        owners = sorted({o for o, _, _ in effects if o != attacker})
        if not owners:
            return
        from itertools import combinations
        from math import factorial

        n = len(owners)
        value: dict[frozenset, float] = {}
        for k in range(n + 1):
            for S in combinations(owners, k):
                present = frozenset(S)
                removed = [(st, v) for o, st, v in effects if o != attacker and o not in present]
                value[present] = dmg * hit_factor(ctx, removed)
        for i in owners:
            others = [o for o in owners if o != i]
            phi = 0.0
            for k in range(n):
                w = factorial(k) * factorial(n - k - 1) / factorial(n)
                for S in combinations(others, k):
                    S = frozenset(S)
                    phi += w * (value[S | {i}] - value[S])
            self.shapley[i] += phi

    def measure_profile(self, own: dict[str, float], total: float) -> dict:
        """What each member actually did in this simulation, per 10 seconds where it is a rate:
        element applications on and off field, field time, reaction triggers, healing, shields, damage share.
        Plus the team's reaction-damage share and its damage structure (see classify_structure)."""
        last_frame = max((l.get("frame", 0) for l in self.logs), default=1) or 1
        seconds = last_frame / 60
        per10 = 10 / seconds if seconds else 0.0
        active, active_since = None, 0
        field: dict[str, float] = defaultdict(float)
        app: dict[str, dict[str, float]] = {m: defaultdict(float) for m in self.members}
        trig: dict[str, dict[str, float]] = {m: defaultdict(float) for m in self.members}
        heal: dict[str, float] = defaultdict(float)
        shield: dict[str, float] = defaultdict(float)
        abil_owner: dict[str, str] = {}
        for l in self.logs:
            if l.get("event") == "damage" and 0 <= l.get("char_index", -1) < len(self.members):
                abil_owner.setdefault(str((l.get("logs") or {}).get("abil", "")), self.members[l["char_index"]])
        for l in self.logs:
            ev, idx, frame = l.get("event"), l.get("char_index", -1), l.get("frame", 0)
            who = self.members[idx] if 0 <= idx < len(self.members) else None
            lg = l.get("logs") or {}
            if ev == "action" and who:
                if active is not None:
                    field[active] += frame - active_since
                active, active_since = who, frame
            elif ev == "element" and l.get("msg") == "application" and who:
                ele = str(lg.get("applied_ele", "")).capitalize()
                if ele in ("Pyro", "Hydro", "Electro", "Cryo", "Anemo", "Geo", "Dendro"):
                    app[who][f"{ele}.{'on' if who == active else 'off'}"] += 1
            elif ev == "damage" and who:
                abil = str(lg.get("abil", ""))
                if abil in TRANSFORMATIVE or abil == "lunarcharged" or abil in ("aggravate", "spread"):
                    trig[who][abil.split("-")[0]] += 1
                elif lg.get("amp"):
                    trig[who][str(lg["amp"])] += 1
            elif ev == "heal":
                msg = str(l.get("msg", ""))
                source = abil_owner.get(msg.replace(" Healing", "").strip())
                if source is None:  # heal events are named after the ability, often with a suffix
                    source = next((o for a, o in abil_owner.items() if a and (msg.startswith(a) or a.startswith(msg.split(" (")[0]))), who)
                if source:
                    heal[source] += float(lg.get("final amount") or lg.get("received amount") or 0)
            elif ev == "shield" and who and "add" in str(l.get("msg", "")).lower():
                shield[who] += 1
        if active is not None:
            field[active] += last_frame - active_since
        members = {}
        for m in self.members:
            members[m] = {
                "damage_share": own.get(m, 0.0) / total if total else 0.0,
                "field_share": field.get(m, 0.0) / last_frame,
                "apply": {k: round(v * per10, 3) for k, v in app[m].items()},
                "triggers": {k: round(v * per10, 3) for k, v in trig[m].items()},
                "heal_per_s": round(heal.get(m, 0.0) / seconds, 1) if seconds else 0.0,
                "shields": shield.get(m, 0.0) > 0,
            }
        x = self.measure_lineup(total)
        for m in self.members:
            members[m].update(x["members"].get(m, {}))
        # Every reaction's own damage counts, Lunar-Bloom and Lunar-Crystallize included (before phase 6 only
        # transformative reactions and Lunar-Charged did).
        reaction_share = sum(x["reaction_damage"].values())
        return {"members": members, "reaction_share": round(reaction_share, 4),
                "structure": classify_structure(members, reaction_share),
                **{k: v for k, v in x.items() if k != "members"}}

    # ---------- lineup measurements (phase 6) ----------
    def _aura_timeline(self) -> dict[int, list[tuple[int, set, set]]]:
        """Per target: (frame, auras just before, auras just after) at every element application. gcsim logs the
        state before each application already decayed, so between two applications an aura is known at both ends."""
        out: dict[int, list[tuple[int, set, set]]] = defaultdict(list)
        for l in self.logs:
            if l.get("event") == "element" and l.get("msg") == "application":
                lg = l.get("logs") or {}
                before = {k for k, v in self._gauge(lg.get("existing")).items() if v > 0}
                after = {k for k, v in self._gauge(lg.get("after")).items() if v > 0}
                out[int(lg.get("target", 1) or 1)].append((l.get("frame", 0), before, after))
        return out

    @staticmethod
    def _present(timeline: list[tuple[int, set, set]], frames: list[int], frame: int, aura: str) -> bool:
        """Was `aura` on the target at `frame`? Present after one application and still present just before the
        next: on throughout. Present after but gone before the next: assumed to expire halfway between."""
        import bisect

        i = bisect.bisect_right(frames, frame) - 1
        if i < 0:
            return False
        f0, _, after = timeline[i]
        if aura not in after:
            return False
        if i + 1 >= len(timeline):
            return True
        f1, before_next, _ = timeline[i + 1]
        return aura in before_next or frame <= (f0 + f1) / 2

    def measure_lineup(self, total: float) -> dict:
        """Reaction, amplification, aura, conditional-buff, off-field and energy measurements for one sample:
          reaction_damage    {reaction: share of team damage}, Swirl grouped (gtc.reactions.kind_of)
          amplified          {vaporize|melt: share of team damage dealt by amplified hits}
          catalyzed          {aggravate|spread: share of team damage dealt by catalyzed hits}
          aura_uptime        {aura: share of the rotation it is on the main target}, Frozen and Quicken included
          aura_at_hit        {aura: share of team damage dealt while it was on the target}
          conditional_mods   {mod: owner, share of eligible hits it applied to, share of team damage on those hits},
                             for buffs gcsim rejected at least once ("conditions not met")
        and per member: reaction_damage (by reaction), amplified_share and offfield_share of their own damage,
        particles and energy_to_team per 10 s."""
        from gtc.reactions import is_reaction_damage, kind_of

        last_frame = max((l.get("frame", 0) for l in self.logs), default=1) or 1
        per10 = 600 / last_frame
        timeline = self._aura_timeline()
        frames = {t: [x[0] for x in tl] for t, tl in timeline.items()}
        main = min(timeline, key=lambda t: (-len(timeline[t]), t)) if timeline else 1
        react: dict[str, float] = defaultdict(float)
        amp: dict[str, float] = defaultdict(float)
        cata: dict[str, float] = defaultdict(float)
        at_hit: dict[str, float] = defaultdict(float)
        m_react: dict[str, dict[str, float]] = {m: defaultdict(float) for m in self.members}
        m_own: dict[str, float] = defaultdict(float)
        m_amp: dict[str, float] = defaultdict(float)
        m_off: dict[str, float] = defaultdict(float)
        particles: dict[str, float] = defaultdict(float)
        energy: dict[str, float] = defaultdict(float)
        seen_drops: set = set()
        mods: dict[str, dict] = {}
        auras_seen = sorted({a for tl in timeline.values() for _, b, af in tl for a in (b | af)})
        active = None
        for l in self.logs:
            ev, idx = l.get("event"), l.get("char_index", -1)
            who = self.members[idx] if 0 <= idx < len(self.members) else None
            lg = l.get("logs") or {}
            if ev == "action" and who:
                active = who
            elif ev == "energy" and l.get("msg") == "particle":
                src = self._member(norm(str(lg.get("source", ""))))
                if src:
                    drop = (l.get("frame"), src, lg.get("ele"))
                    if drop not in seen_drops:
                        seen_drops.add(drop)
                        particles[src] += float(lg.get("count") or 0)
                    if who and who != src and float(lg.get("ER") or 0) > 0:
                        energy[src] += float(lg.get("amt") or 0) / float(lg["ER"])
            elif ev == "damage" and who:
                dmg = float(lg.get("damage") or 0)
                if dmg <= 0:
                    continue
                abil = str(lg.get("abil", ""))
                m_own[who] += dmg
                if is_reaction_damage(abil):
                    react[kind_of(abil)] += dmg
                    m_react[who][kind_of(abil)] += dmg
                a = str(lg.get("amp") or "").lower()
                if a in ("vaporize", "melt"):
                    amp[a] += dmg
                    m_amp[who] += dmg
                c = str(lg.get("cata") or "").lower()
                if c in ("aggravate", "spread"):
                    cata[c] += dmg
                if who != active:
                    m_off[who] += dmg
                tgt = int(lg.get("target", main) or main)
                tl, fr = timeline.get(tgt, []), frames.get(tgt, [])
                for aura in auras_seen:
                    if self._present(tl, fr, l.get("frame", 0), aura):
                        at_hit[aura] += dmg
                entries = [(k, v) for k, v in lg.items() if isinstance(v, list) and k not in ("resist_mods", "pre_damage_mods")]
                pre = lg.get("pre_damage_mods")
                if isinstance(pre, list):
                    entries += [(pre[i], pre[i + 1]) for i in range(0, len(pre) - 1, 2) if isinstance(pre[i], str)]
                for key, ent in entries:
                    text = " ".join(str(x) for x in ent) if isinstance(ent, list) else str(ent)
                    st = mods.get(key)
                    if st is None:
                        st = mods[key] = {"owner": self.owner_of(key, who), "on": 0, "off": 0, "dmg": 0.0}
                    if "status: rejected" in text:
                        st["off"] += 1
                    elif "status: added" in text:
                        st["on"] += 1
                        st["dmg"] += dmg
        # Uptime on the main target: walk the intervals between applications.
        uptime: dict[str, float] = {}
        tl = timeline.get(main, [])
        for aura in auras_seen:
            on = 0.0
            for i, (f0, _, after) in enumerate(tl):
                if aura not in after:
                    continue
                f1 = tl[i + 1][0] if i + 1 < len(tl) else last_frame
                still = i + 1 >= len(tl) or aura in tl[i + 1][1]
                on += (f1 - f0) if still else (f1 - f0) / 2
            uptime[aura] = round(on / last_frame, 4)

        def share(d):
            return {k: round(v / total, 4) for k, v in sorted(d.items()) if total and v / total >= 0.0005}

        members = {}
        for m in self.members:
            members[m] = {
                "reaction_damage": share(m_react[m]),
                "amplified_share": round(m_amp[m] / m_own[m], 4) if m_own[m] else 0.0,
                "offfield_share": round(m_off[m] / m_own[m], 4) if m_own[m] else 0.0,
                "particles_per10": round(particles[m] * per10, 3),
                "energy_to_team_per10": round(energy[m] * per10, 3),
            }
        conditional = {k: {"owner": v["owner"], "active": round(v["on"] / (v["on"] + v["off"]), 4),
                           "damage": round(v["dmg"] / total, 4) if total else 0.0}
                       for k, v in sorted(mods.items()) if v["off"] > 0}
        return {"members": members, "reaction_damage": share(react), "amplified": share(amp), "catalyzed": share(cata),
                "aura_uptime": uptime, "aura_at_hit": share(at_hit), "conditional_mods": conditional}

    def _lunar_charged_hit(self, dmg: float, contribs: list[dict], last_mods: dict, resist) -> list[Contribution]:
        """A Lunar-Charged reaction hit: each contributor's weighted share, scored with their EM, reaction and
        base-damage bonuses, and the buffs they had on their most recent hit. RES shred from recent Electro hits."""
        out = []
        weights = [(c, float(c.get("damage", 0)) * float(c.get("mult", 0))) for c in contribs]
        total_w = sum(w for _, w in weights) or 1.0
        for c, w in weights:
            who, share = c["who"], dmg * w / total_w
            em, react, base = float(c.get("em", 0)), float(c.get("react", 0)), float(c.get("base damage bonus", 0))
            cr, cd = min(float(c.get("cr", 0)), 1.0), float(c.get("cd", 0))
            for key, entries in (last_mods.get(who) or {}).items():
                for stat, v in _stats(entries):
                    ratio = 1.0
                    if stat == "em":
                        ratio = (1 + em_lunar(em - v) + react) / (1 + em_lunar(em) + react)
                    elif stat in ("cr", "cd"):
                        ratio = crit_avg(max(0.0, cr - v) if stat == "cr" else cr, cd - v if stat == "cd" else cd) / crit_avg(cr, cd)
                    owner = self.owner_of(key, who)
                    if ratio < 1.0 and owner != who:
                        out.append(Contribution(owner, who, stat, share * (1 - ratio)))
            out += [x for x in self._lunar_bonus_contribs(who, share, em, react, base) if x.owner != who]
        if isinstance(resist, list):
            for i in range(0, len(resist) - 1, 2):
                key, info = resist[i], resist[i + 1]
                if isinstance(info, list) and "status: added" in info:
                    amount = next((float(x.split(":")[1]) for x in info if str(x).startswith("amount")), 0.0)
                    ratio = res_mult(0.1 + amount - amount) / res_mult(0.1 + amount)
                    out.append(Contribution(self.resist_owner(key, "?"), contribs[0]["who"], "res shred", dmg * (1 - ratio)))
        return out

    def _react_sources(self, frame: int, receiver_index: int, receiver: str) -> list[str]:
        """Owners of the reaction-bonus mods active on this character at this frame."""
        owners = []
        for added, idx, key, exp in self.react_mods:
            if idx == receiver_index and added <= frame and (exp in (-1, None) or frame < exp):
                owners.append(self.owner_of(key, receiver))
        return owners

    def _react_bonus_contribs(self, receiver: str, owners: list[str], dmg: float, total_bonus: float, em_term: float,
                              label: str, values: dict[str, float] | None = None) -> list[Contribution]:
        """Credit teammates for a hit's reaction bonus. gcsim logs each source's value with the hit
        ("<abil> [React Bonus]"), so the split is exact; without that record, equal among the active sources."""
        out = []
        if values:
            for key, v in values.items():
                owner = self.owner_of(key, receiver)
                if owner == receiver or v <= 0:
                    continue
                ratio = (1 + em_term + total_bonus - v) / (1 + em_term + total_bonus)
                out.append(Contribution(owner, receiver, label, dmg * (1 - ratio)))
            return out
        if total_bonus <= 0 or not owners:
            return out
        share = total_bonus / len(owners)
        for owner in owners:
            if owner == receiver:
                continue
            ratio = (1 + em_term + total_bonus - share) / (1 + em_term + total_bonus)
            out.append(Contribution(owner, receiver, label, dmg * (1 - ratio)))
        return out

    def _transformative_hit(self, attacker: str, abil: str, calc: dict, dmg: float, last_mods: dict,
                            frame: int, index: int) -> list[Contribution]:
        """Hyperbloom, Bloom, Swirl, Electro-Charged, Overloaded...: the triggerer's EM buffs (from their most recent
        hit) and teammates' reaction bonuses, plus RES shred (handled from the damage line)."""
        out = []
        em = calc.get("em") or 0.0
        base = reaction_base(int(calc.get("char_lvl") or 90)) * TRANSFORMATIVE[abil]
        flat = calc.get("flat_dmg") or 0.0
        em_term = em_transformative(em)
        bonus = max(0.0, flat / base - 1 - em_term) if base else 0.0
        for key, entries in (last_mods.get(attacker) or {}).items():
            for stat, v in _stats(entries):
                if stat == "em":
                    owner = self.owner_of(key, attacker)
                    if owner != attacker:
                        ratio = (1 + em_transformative(em - v) + bonus) / (1 + em_term + bonus)
                        out.append(Contribution(owner, attacker, "em", dmg * (1 - ratio)))
        out += self._react_bonus_contribs(attacker, self._react_sources(frame, index, attacker), dmg, bonus, em_term, "reaction bonus",
                                          self.react_values.get((frame, index, abil)))
        return out

    def _hit(self, attacker: str, lg: dict, calc: dict | None, dmg: float, frame: int = 0, index: int = -1) -> list[Contribution]:
        out = []
        res = calc.get("res") if calc else None
        # RES shred: every hit, reactions included.
        rm = lg.get("resist_mods")
        if isinstance(rm, list):
            for i in range(0, len(rm) - 1, 2):
                key, info = rm[i], rm[i + 1]
                if not isinstance(info, list) or "status: added" not in info:
                    continue
                amount = next((float(x.split(":")[1]) for x in info if str(x).startswith("amount")), 0.0)
                ele = next((x.split(":")[1].strip() for x in info if str(x).startswith("ele")), "")
                if ele and ele.lower() != str(lg.get("ele", "")).lower():
                    continue
                r = res if res is not None else 0.1 + amount
                ratio = res_mult(r - amount) / res_mult(r) if res_mult(r) else 1.0
                out.append(Contribution(self.resist_owner(key, attacker), attacker, "res shred", dmg * (1 - ratio)))
        if not calc:
            return out
        lunar = calc.get("ignore_def") == 1 and int(lg.get("attack-tag", 0)) in LUNAR_DIRECT_TAGS
        amp = bool(calc.get("melt_vape"))
        scaling = "hp" if calc.get("use_hp") else "def" if calc.get("use_def") else "em" if calc.get("use_em") else "atk"
        S = calc.get("total_scaling") or 0.0
        em = calc.get("em") or 0.0
        react = calc.get("react_bonus") or 0.0
        cr, cd = min(calc.get("cr") or 0.0, 1.0), calc.get("cd") or 0.0
        bonus = calc.get("bonus_dmg") or 0.0
        ele = str(lg.get("ele", "")).lower()
        base_total = calc.get("base_dmg") or 0.0
        catalyze_flat = 0.0
        if calc.get("catalyzed") and base_total:
            # The catalyze bonus is the flat part of base damage (minus any other flat damage such as quills).
            reaction = "spread" if ele == "dendro" else "aggravate"
            catalyze_flat = reaction_base(int(calc.get("char_lvl") or 90)) * CATALYZE[reaction] * (1 + em_additive(em) + react)
            catalyze_flat = min(catalyze_flat, calc.get("flat_dmg") or catalyze_flat)
        mods = [(k, v) for k, v in lg.items() if k not in ("resist_mods", "pre_damage_mods") and isinstance(v, list)]
        pdm = lg.get("pre_damage_mods")
        if isinstance(pdm, list):
            mods += [(pdm[i], pdm[i + 1]) for i in range(0, len(pdm) - 1, 2) if isinstance(pdm[i], str)]
        for key, entries in mods:
            for stat, v in _stats(entries):
                ratio = 1.0
                if stat in ("atk", "atk%", "hp", "hp%", "def", "def%") and scaling == stat.rstrip("%"):
                    base = calc.get(f"base_{scaling}") or 0.0
                    delta = v if not stat.endswith("%") else base * v
                    ratio = (S - delta) / S if S else 1.0
                elif stat == "em":
                    if scaling == "em":
                        ratio = (S - v) / S if S else 1.0
                    elif lunar:
                        ratio = (1 + em_lunar(em - v) + react) / (1 + em_lunar(em) + react)
                    elif amp:
                        ratio = (1 + em_amplifying(em - v) + react) / (1 + em_amplifying(em) + react)
                    elif catalyze_flat > 0:
                        # Aggravate / Spread: EM raises only the added flat damage.
                        new_flat = catalyze_flat * (1 + em_additive(em - v) + react) / (1 + em_additive(em) + react)
                        ratio = (base_total - catalyze_flat + new_flat) / base_total if base_total else 1.0
                elif stat in ("cr", "cd"):
                    cr2, cd2 = (max(0.0, cr - v), cd) if stat == "cr" else (cr, cd - v)
                    ratio = crit_avg(cr2, cd2) / crit_avg(cr, cd)
                elif stat.endswith("%") and not lunar and stat[:-1] in (ele, "dmg", "dmgp"):
                    ratio = (1 + bonus - v) / (1 + bonus)
                if ratio < 1.0:
                    out.append(Contribution(self.owner_of(key, attacker), attacker, stat, dmg * (1 - ratio)))
        flat, base_dmg = calc.get("flat_dmg") or 0.0, calc.get("base_dmg") or 0.0
        if flat > 0 and base_dmg > flat and not calc.get("catalyzed"):
            tag = int(lg.get("attack-tag", 0))
            provider = next((m for m, rule in FLAT_DMG_PROVIDERS.items() if m in self.members and m != attacker
                             and (rule.get("element") == ele or tag in rule.get("attack_tags", set()))), None)
            if provider:
                out.append(Contribution(provider, attacker, "flat DMG", dmg * flat / base_dmg))
        if lunar:
            out += self._lunar_bonus_contribs(attacker, dmg, em, react, calc.get("react_base_dmg_bonus") or 0.0)
        elif amp and react > 0:
            amp_dmg_share = 1.0  # the whole hit scales with the amplifying multiplier
            out += self._react_bonus_contribs(attacker, self._react_sources(frame, index, attacker), dmg * amp_dmg_share,
                                              react, em_amplifying(em), "reaction bonus",
                                              self.react_values.get((frame, index, str(lg.get("abil", "")))))
        elif catalyze_flat > 0 and react > 0 and base_total:
            out += self._react_bonus_contribs(attacker, self._react_sources(frame, index, attacker), dmg * catalyze_flat / base_total,
                                              react, em_additive(em), "reaction bonus",
                                              self.react_values.get((frame, index, str(lg.get("abil", "")))))
        if catalyze_flat > 0 and base_total:
            for who, share in self._aura_shares(int(lg.get("target", 1) or 1), ("quicken",)).items():
                if who != attacker:
                    self.enable.append(Contribution(who, attacker, "enablement", ENABLE_SHARE * dmg * catalyze_flat / base_total * share))
        # Fair shares over every teammate buff on this hit, recomputed jointly.
        effects = [(self.owner_of(k, attacker), st, v) for k, entries in mods for st, v in _stats(entries)]
        if isinstance(rm, list):
            for i in range(0, len(rm) - 1, 2):
                key, info = rm[i], rm[i + 1]
                if isinstance(info, list) and "status: added" in info:
                    amount = next((float(x.split(":")[1]) for x in info if str(x).startswith("amount")), 0.0)
                    ele_r = next((x.split(":")[1].strip() for x in info if str(x).startswith("ele")), "")
                    if not ele_r or ele_r.lower() == ele:
                        effects.append((self.resist_owner(key, attacker), "res shred", amount))
        for c in out:
            if c.kind in ("flat DMG", "reaction bonus"):
                effects.append((c.owner, c.kind, c.damage / dmg if dmg else 0.0))
        ctx = {"scaling": scaling, "S": S, "base": calc.get(f"base_{scaling}") or 0.0, "em": em, "react": react, "cr": cr,
               "cd": cd, "bonus": bonus, "res": res if res is not None else 0.1, "lunar": lunar, "amp": amp,
               "catalyze_flat": catalyze_flat, "base_total": base_total}
        self._shapley_hit(attacker, effects, ctx, dmg)
        return out


def hit_factor(ctx: dict, removed: list[tuple[str, float]]) -> float:
    """A hit's damage with these (stat, value) buffs removed, relative to the logged hit. Terms combine as in the
    damage formula: scaling stat, EM (through the hit's reaction), crit, DMG bonus and RES multiply; flat damage
    and reaction-bonus shares (already fractions of the hit) subtract."""
    scaling, S = ctx["scaling"], ctx["S"]
    d_scale = d_em = d_cr = d_cd = d_bonus = d_res = 0.0
    frac = 0.0
    for st, v in removed:
        if st in ("atk", "atk%", "hp", "hp%", "def", "def%") and scaling == st.rstrip("%"):
            d_scale += v if not st.endswith("%") else ctx["base"] * v
        elif st == "em":
            if scaling == "em":
                d_scale += v
            else:
                d_em += v
        elif st == "cr":
            d_cr += v
        elif st == "cd":
            d_cd += v
        elif st == "res shred":
            d_res += v
        elif st in ("flat DMG", "reaction bonus"):
            frac += v
        elif st.endswith("%") and not ctx["lunar"]:
            d_bonus += v
    f = (S - d_scale) / S if S else 1.0
    em, react = ctx["em"], ctx["react"]
    if d_em:
        if ctx["lunar"]:
            f *= (1 + em_lunar(em - d_em) + react) / (1 + em_lunar(em) + react)
        elif ctx["amp"]:
            f *= (1 + em_amplifying(em - d_em) + react) / (1 + em_amplifying(em) + react)
        elif ctx["catalyze_flat"] > 0 and ctx["base_total"]:
            cf = ctx["catalyze_flat"]
            new = cf * (1 + em_additive(em - d_em) + react) / (1 + em_additive(em) + react)
            f *= (ctx["base_total"] - cf + new) / ctx["base_total"]
    if d_cr or d_cd:
        cr, cd = ctx["cr"], ctx["cd"]
        f *= crit_avg(max(0.0, cr - d_cr), cd - d_cd) / crit_avg(cr, cd)
    if d_bonus:
        f *= (1 + ctx["bonus"] - d_bonus) / (1 + ctx["bonus"])
    if d_res:
        r = ctx["res"]
        f *= res_mult(r - d_res) / res_mult(r) if res_mult(r) else 1.0
    return max(0.0, f - frac)


# ---------- team structure ----------

STRUCTURE_RULES = params.get("synergy.structure_rules")


def classify_structure(members: dict[str, dict], reaction_share: float, rules: dict | None = None) -> dict:
    """Where a team's damage comes from, from measured shares. Returns the structure and its damage owners.
      hypercarry     one member deals at least 55%
      dual_carry     two members each deal at least 25%
      reaction_core  reactions deal at least half the team's damage
      driver         the member with the most field time deals under 25% (others' damage does the work)
      distributed    none of these"""
    rules = rules or STRUCTURE_RULES
    by_dmg = sorted(members, key=lambda m: -members[m]["damage_share"])
    top = by_dmg[0] if by_dmg else None
    if top and members[top]["damage_share"] >= rules["hypercarry"]:
        return {"type": "hypercarry", "owners": [top]}
    if len(by_dmg) > 1 and members[by_dmg[1]]["damage_share"] >= rules["dual_carry"]:
        return {"type": "dual_carry", "owners": by_dmg[:2]}
    if reaction_share >= rules["reaction_core"]:
        return {"type": "reaction_core", "owners": []}
    onfield = max(members, key=lambda m: members[m]["field_share"]) if members else None
    if onfield and members[onfield]["field_share"] >= rules["driver_field"] and members[onfield]["damage_share"] < rules["driver_damage"]:
        return {"type": "driver", "owners": [m for m in by_dmg[:2] if m != onfield][:1]}
    return {"type": "distributed", "owners": []}


# ---------- database over every standard gcsim lineup ----------

from gtc.sources import SOURCE_DIR  # noqa: E402

DB_PATH = SOURCE_DIR / "synergy.json"


def build_database(progress=print, workers: int = 14) -> int:
    """Attribute every distinct standard lineup's best simulation, gcsim runs in parallel.
    Results are saved as they come in, so an interrupted build resumes where it stopped."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from gtc import gamedata
    from gtc.sim import Config, Keys, _raw_entries, render
    from gtc.sources import gcsim_db
    from gtc.tc.engine import load_kits

    names, kits, keys = gamedata.names(), load_kits(), Keys()
    canonical = keys.char_canonical
    groups: dict[frozenset, list] = defaultdict(list)
    for t in gcsim_db.load():
        if gcsim_db.is_standard(t):
            groups[t.names].append(t)
    best: dict[frozenset, gcsim_db.SimTeam] = {}
    stats: dict[frozenset, dict] = {}
    values = gcsim_db.lineup_values()
    for lineup, sims in groups.items():
        sims.sort(key=lambda x: x.dps)
        best[lineup] = sims[len(sims) // 2]  # the median submission is the lineup's representative for attribution
        stats[lineup] = value_stats(values[lineup], [x.dps for x in sims])
    raw = _raw_entries()
    out = json.loads(DB_PATH.read_text(encoding="utf-8")) if DB_PATH.exists() else {}
    todo = []
    for lineup, t in best.items():
        e = raw.get(t.id)
        if t.id in out or not e:
            continue
        char_keys = {}
        for line in e["config"].splitlines():
            m = re.match(r"\s*([a-z0-9]+)\s+char\s", line)
            if m:
                display = names.character(m.group(1)) or names.character(canonical.get(m.group(1), ""))
                if display:
                    char_keys[display] = m.group(1)
        text, _ = render(Config(e["config"], t.id, t.dps, char_keys), {}, keys, iterations=1)
        todo.append((lineup, t, text))

    def work(item):
        lineup, t, text = item
        try:
            syn = Attributor(run_sample(text, keep=False), names, kits).attribute()
        except Exception as exc:  # a config gcsim cannot run any more
            return t.id, {"error": str(exc)[:200]}
        return t.id, {
            "lineup": sorted(lineup), "dps": stats[lineup]["median"], "dps_stats": stats[lineup], "total": syn.total,
            "profile": syn.profile,
            "own": {k: v / syn.total for k, v in syn.own.items()} if syn.total else {},
            "buffs_marginal": {m: syn.buff_share(m) for m in syn.lineup},
            "buffs_shapley": {m: round(syn.shapley_share(m), 5) for m in syn.lineup},
            "enable_reaction": {m: round(syn.enable_share(m, "enablement"), 5) for m in syn.lineup},
            "enable_amp": {m: round(syn.enable_share(m, "amplification"), 5) for m in syn.lineup},
            "detail": {m: {f"{tgt}|{kind}": round(v, 5) for (tgt, kind), v in syn.breakdown(m).items() if v >= 0.002} for m in syn.lineup},
        }

    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for fut in as_completed([pool.submit(work, item) for item in todo]):
            tid, result = fut.result()
            out[tid] = result
            done += 1
            if done % 200 == 0:
                DB_PATH.write_text(json.dumps(out), encoding="utf-8")
                progress(f"{len(out)} of {len(best)} lineups attributed")
    DB_PATH.write_text(json.dumps(out), encoding="utf-8")
    return len(out)


def value_stats(v, sims_dps: list[float]) -> dict:
    """Stored per lineup: the robust value (median of per-submitter medians) as "median", plus the spread."""
    out = lineup_stats(sims_dps)
    out.update({"median": v.value, "n_submitters": v.n_submitters, "submitter_spread": round(v.spread, 4)})
    return out


def refresh_values() -> int:
    """Rewrite each stored lineup's value from gcsim_db.lineup_values() without re-running any simulation."""
    from gtc.sources import gcsim_db

    db = load_database()
    groups: dict[frozenset, list[float]] = defaultdict(list)
    for t in gcsim_db.load():
        if gcsim_db.is_standard(t):
            groups[t.names].append(t.dps)
    values = gcsim_db.lineup_values()
    changed = 0
    for e in db.values():
        if "lineup" not in e:
            continue
        k = frozenset(e["lineup"])
        if k in values:
            if e.get("dps") != values[k].value:
                changed += 1
            e["dps"] = values[k].value
            e["dps_stats"] = value_stats(values[k], groups[k])
    DB_PATH.write_text(json.dumps(db), encoding="utf-8")
    global _TABLE
    _TABLE = None
    return changed


def lineup_stats(values: list[float]) -> dict:
    """Median, spread and count of a lineup's simulations. With five or more, also a 20% trimmed mean."""
    v = sorted(values)
    n = len(v)
    med = v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2
    mean = sum(v) / n
    sd = (sum((x - mean) ** 2 for x in v) / (n - 1)) ** 0.5 if n > 1 else 0.0
    out = {"median": med, "n": n, "sd": sd, "min": v[0], "max": v[-1]}
    if n >= 5:
        k = int(n * 0.2)
        out["trimmed_mean"] = sum(v[k:n - k]) / (n - 2 * k)
    return out


def load_database() -> dict:
    db = json.loads(DB_PATH.read_text(encoding="utf-8")) if DB_PATH.exists() else {}
    for e in db.values():
        _migrate(e)
    return db


def _migrate(e: dict) -> None:
    """Entries written before phase 6 named the attribution views "buffs", "shapley" and "enable" (enablement and
    amplification together). Rename them in place so every reader uses the phase 6 names."""
    if "buffs" in e and "buffs_marginal" not in e:
        e["buffs_marginal"] = e.pop("buffs")
        e["buffs_shapley"] = e.pop("shapley", {})
        e["enable_reaction"] = e.pop("enable", {})
        e["enable_amp"] = {}


def enabled(e: dict, member: str) -> float:
    """Reaction enablement plus amplification credited to `member` in a database entry."""
    return (e.get("enable_reaction") or {}).get(member, 0.0) + (e.get("enable_amp") or {}).get(member, 0.0)


# ---------- pair table: what each teammate is worth to each carry ----------

@dataclass
class PairStat:
    carry: str
    mate: str
    n: int
    value: float  # mean share of team damage: own damage, buffs to teammates and reactions they enable
    own: float
    buffs: float
    to_carry: float  # buffs aimed at the carry specifically
    kinds: dict[str, float]  # buff type -> mean share of team damage
    enable: float = 0.0  # reactions their auras or Dendro cores make possible

    def explain(self, top: int = 3) -> str:
        parts = [f"{k} {v:.0%}" for k, v in sorted(self.kinds.items(), key=lambda x: -x[1])[:top] if v >= 0.01]
        own = f"own damage {self.own:.0%}" if self.own >= 0.01 else ""
        enable = f"enables reactions {self.enable:.0%}" if self.enable >= 0.01 else ""
        return ", ".join(p for p in [own, enable] + parts if p) or "little measurable effect"




class SynergyTable:
    """Measured synergy from the database, keyed by the carry gcsim's lineup was built around."""

    def __init__(self, db: dict, categories: dict[str, set[str]]):
        from gtc.evidence import assign_carry

        self.by_lineup: dict[frozenset, dict] = {}
        obs: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for entry in db.values():
            if "lineup" not in entry:
                continue
            lineup = frozenset(entry["lineup"])
            self.by_lineup[lineup] = entry
            st = (entry.get("profile") or {}).get("structure")
            if st is not None:  # the measured damage owner; teams without a single carry have no pair carry
                carry = st["owners"][0] if st["type"] in ("hypercarry", "dual_carry") and st["owners"] else None
            else:
                carry = assign_carry(lineup, categories)
            if not carry:
                continue
            for m in lineup:
                if m == carry:
                    continue
                kinds: dict[str, float] = defaultdict(float)
                to_carry = 0.0
                for key, v in (entry["detail"].get(m) or {}).items():
                    tgt, kind = key.split("|", 1)
                    kinds[kind] += v
                    if tgt == carry:
                        to_carry += v
                obs[(carry, m)].append({"own": entry["own"].get(m, 0.0), "buffs": entry["buffs_marginal"].get(m, 0.0),
                                        "enable": enabled(entry, m),
                                        "to_carry": to_carry, "kinds": dict(kinds), "lineup": lineup})
        self.obs = obs
        self.pairs: dict[tuple[str, str], PairStat] = {}
        for (carry, m), rows in obs.items():
            n = len(rows)
            kinds: dict[str, float] = defaultdict(float)
            for r in rows:
                for k, v in r["kinds"].items():
                    kinds[k] += v / n
            own = sum(r["own"] for r in rows) / n
            buffs = sum(r["buffs"] for r in rows) / n
            enable = sum(r["enable"] for r in rows) / n
            self.pairs[(carry, m)] = PairStat(carry, m, n, own + buffs + enable, own, buffs, sum(r["to_carry"] for r in rows) / n,
                                              dict(kinds), enable)

    def pair(self, carry: str, mate: str, exclude: frozenset | None = None) -> PairStat | None:
        """Average over simulated teams; `exclude` leaves one lineup out (no lineup is estimated from itself)."""
        if exclude is None:
            return self.pairs.get((carry, mate))
        rows = [r for r in self.obs.get((carry, mate), []) if r["lineup"] != exclude]
        if not rows:
            return None
        n = len(rows)
        kinds: dict[str, float] = defaultdict(float)
        for r in rows:
            for k, v in r["kinds"].items():
                kinds[k] += v / n
        own, buffs = sum(r["own"] for r in rows) / n, sum(r["buffs"] for r in rows) / n
        enable = sum(r["enable"] for r in rows) / n
        return PairStat(carry, mate, n, own + buffs + enable, own, buffs, sum(r["to_carry"] for r in rows) / n, dict(kinds), enable)

    def best_mates(self, carry: str, top: int = 8, min_n: int = 2) -> list[PairStat]:
        return sorted((p for (c, _), p in self.pairs.items() if c == carry and p.n >= min_n), key=lambda p: -p.value)[:top]


_TABLE: SynergyTable | None = None


def table() -> SynergyTable | None:
    global _TABLE
    if _TABLE is None:
        db = load_database()
        if not db:
            return None
        from gtc.evidence import role_categories
        from gtc.sources import prydwen

        _TABLE = SynergyTable(db, role_categories(prydwen.load()))
    return _TABLE


_CHAR_ALIASES: dict[str, str] | None = None


def _char_aliases() -> dict[str, str]:
    """gcsim character aliases ("chev" -> "chevreuse")."""
    global _CHAR_ALIASES
    if _CHAR_ALIASES is None:
        from gtc.sim import Keys

        try:
            _CHAR_ALIASES = {norm(a): c for a, c in Keys().char_canonical.items()}
        except Exception:  # gcsim key data not downloaded
            _CHAR_ALIASES = {}
    return _CHAR_ALIASES


_WEAPON_ALIASES: dict[str, str] | None = None


def _weapon_aliases() -> dict[str, str]:
    """gcsim weapon shortcut to canonical key, normalised: 'ttds' -> 'thrillingtalesofdragonslayers'."""
    global _WEAPON_ALIASES
    if _WEAPON_ALIASES is None:
        from gtc.sim import KEYS_PATH

        data = json.loads(KEYS_PATH.read_text(encoding="utf-8"))
        _WEAPON_ALIASES = {alias: norm(canon) for alias, canon in data["weapon"]}
    return _WEAPON_ALIASES
