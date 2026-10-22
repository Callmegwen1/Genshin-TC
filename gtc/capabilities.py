"""Measured capability profile per character, aggregated over every simulated lineup they appear in.

Each lineup in the synergy database carries what each member actually did (gtc.synergy.measure_profile).
Here those are averaged per character:

  damage_share       mean share of team damage
  field_share        mean share of rotation time on field
  apply              element applications per 10 s, keyed "Hydro.off", "Hydro.on"...
  triggers           reactions triggered per 10 s, keyed by reaction
  heal_per_s         healing output per second where gcsim logged any (conditional healers often show 0)
  team_reaction_share  mean share of team damage from reactions in the teams they appear in

Phase 6 adds, from the same per-hit attribution and logs (all continuous; categorical helpers are properties):
  reaction_damage    {reaction: mean share of team damage from reactions this member triggered (owned)}
  amplified_share    mean share of their own damage dealt by Vaporize or Melt hits
  offfield_share     mean share of their own damage dealt while another member is on field (off-field persistence)
  particles_per10    particles generated per 10 s; energy_to_team_per10: energy they give teammates per 10 s
  shield_rate        share of their lineups in which they shield the team
  buffs_marginal     mean marginal buff value to teammates (each buff removed alone), share of team damage
  buffs_shapley      mean fair (Shapley) split of the buffed damage, share of team damage
  enable_reaction    mean reaction damage their auras or Dendro cores made possible, share of team damage
  enable_amp         mean amplified part of Vaporize and Melt hits on their aura, share of team damage
  buff_effects       {buff kind: mean share of team damage it adds to teammates}, e.g. "res shred", "cryo%"
  buff_to_dealer     mean share of the buffs they give that lands on the lineup's top damage dealer
  conditional        {gcsim mod: mean share of eligible hits it applied to} for their conditional buffs
  conditional_damage mean share of team damage dealt on hits where one of their conditional buffs was active

Means rather than medians, so a lineup can be left out exactly when validating (leave-one-out).
"""
from __future__ import annotations

from gtc import params

import json
from collections import defaultdict
from dataclasses import dataclass, field

from gtc.sources import SOURCE_DIR

CAPS_PATH = SOURCE_DIR / "capabilities.json"
ONFIELD_SHARE = params.get("capabilities.onfield_share")  # a member on field at least this much of the rotation counts as an on-field character


@dataclass
class Capability:
    name: str
    n: int = 0
    damage_share: float = 0.0
    field_share: float = 0.0
    apply: dict[str, float] = field(default_factory=dict)
    triggers: dict[str, float] = field(default_factory=dict)
    heal_per_s: float = 0.0
    team_reaction_share: float = 0.0
    reaction_damage: dict[str, float] = field(default_factory=dict)
    amplified_share: float = 0.0
    offfield_share: float = 0.0
    particles_per10: float = 0.0
    energy_to_team_per10: float = 0.0
    shield_rate: float = 0.0
    buffs_marginal: float = 0.0
    buffs_shapley: float = 0.0
    enable_reaction: float = 0.0
    enable_amp: float = 0.0
    buff_effects: dict[str, float] = field(default_factory=dict)
    buff_to_dealer: float = 0.0
    conditional: dict[str, float] = field(default_factory=dict)
    conditional_damage: float = 0.0

    @property
    def driver_like(self) -> bool:
        """On field a lot while dealing little: the measured definition the structure rules use."""
        from gtc.synergy import STRUCTURE_RULES

        return self.field_share >= STRUCTURE_RULES["driver_field"] and self.damage_share < STRUCTURE_RULES["driver_damage"]

    def vector(self) -> dict[str, float]:
        """Every continuous measurement as one flat dict (features for structure and identity models)."""
        out = {"damage_share": self.damage_share, "field_share": self.field_share, "heal_per_s": self.heal_per_s,
               "team_reaction_share": self.team_reaction_share, "amplified_share": self.amplified_share,
               "offfield_share": self.offfield_share, "particles_per10": self.particles_per10,
               "energy_to_team_per10": self.energy_to_team_per10, "shield_rate": self.shield_rate,
               "buffs_marginal": self.buffs_marginal, "buffs_shapley": self.buffs_shapley,
               "enable_reaction": self.enable_reaction, "enable_amp": self.enable_amp,
               "buff_to_dealer": self.buff_to_dealer, "conditional_damage": self.conditional_damage}
        out.update({f"apply.{k}": v for k, v in self.apply.items()})
        out.update({f"trigger.{k}": v for k, v in self.triggers.items()})
        out.update({f"reaction.{k}": v for k, v in self.reaction_damage.items()})
        out.update({f"buff.{k}": v for k, v in self.buff_effects.items()})
        return out

    def applies(self, element: str) -> float:
        return self.apply.get(f"{element}.on", 0.0) + self.apply.get(f"{element}.off", 0.0)

    def applies_off(self, element: str) -> float:
        return self.apply.get(f"{element}.off", 0.0)

    @property
    def onfield(self) -> bool:
        return self.field_share >= ONFIELD_SHARE


SCALARS = ("amplified_share", "offfield_share", "particles_per10", "energy_to_team_per10")  # per-member profile values
VIEWS = ("buffs_marginal", "buffs_shapley", "enable_reaction", "enable_amp")  # per-member attribution views of an entry


def aggregate(db: dict, exclude: frozenset | None = None) -> dict[str, Capability]:
    def blank():
        return {"n": 0, "damage_share": 0.0, "field_share": 0.0, "heal": 0.0, "rs": 0.0, "shield": 0.0, "to_dealer": 0.0,
                "to_dealer_n": 0, "cond_dmg": 0.0, "apply": defaultdict(float), "triggers": defaultdict(float),
                "reaction": defaultdict(float), "effects": defaultdict(float), "cond": defaultdict(float),
                "cond_n": defaultdict(int), **{k: 0.0 for k in SCALARS + VIEWS}}

    sums: dict[str, dict] = defaultdict(blank)
    for e in db.values():
        prof = e.get("profile")
        if not prof or (exclude is not None and frozenset(e["lineup"]) == exclude):
            continue
        members = prof["members"]
        dealer = max(members, key=lambda x: (members[x]["damage_share"], x)) if members else None
        cond_by_owner: dict[str, float] = defaultdict(float)
        for key, c in (prof.get("conditional_mods") or {}).items():
            cond_by_owner[c["owner"]] = max(cond_by_owner[c["owner"]], c["damage"])
        for m, c in members.items():
            s = sums[m]
            s["n"] += 1
            s["damage_share"] += c["damage_share"]
            s["field_share"] += c["field_share"]
            s["heal"] += c.get("heal_per_s", 0.0)
            s["rs"] += prof.get("reaction_share", 0.0)
            s["shield"] += 1.0 if c.get("shields") else 0.0
            for k, v in c["apply"].items():
                s["apply"][k] += v
            for k, v in c["triggers"].items():
                s["triggers"][k] += v
            for k, v in (c.get("reaction_damage") or {}).items():
                s["reaction"][k] += v
            for k in SCALARS:
                s[k] += c.get(k, 0.0)
            for k in VIEWS:
                s[k] += (e.get(k) or {}).get(m, 0.0)
            given = (e.get("detail") or {}).get(m) or {}
            for key, v in given.items():
                s["effects"][key.split("|", 1)[1]] += v
            total_given = sum(given.values())
            if total_given > 0 and dealer and dealer != m:
                s["to_dealer"] += sum(v for key, v in given.items() if key.split("|", 1)[0] == dealer) / total_given
                s["to_dealer_n"] += 1
            for key, c2 in (prof.get("conditional_mods") or {}).items():
                if c2["owner"] == m:
                    s["cond"][key] += c2["active"]
                    s["cond_n"][key] += 1
            s["cond_dmg"] += cond_by_owner.get(m, 0.0)
    out = {}
    for m, s in sums.items():
        n = s["n"]
        out[m] = Capability(
            m, n, s["damage_share"] / n, s["field_share"] / n,
            {k: v / n for k, v in s["apply"].items()}, {k: v / n for k, v in s["triggers"].items()},
            s["heal"] / n, s["rs"] / n,
            reaction_damage={k: v / n for k, v in s["reaction"].items()},
            **{k: s[k] / n for k in SCALARS + VIEWS},
            shield_rate=s["shield"] / n,
            buff_effects={k: v / n for k, v in s["effects"].items()},
            buff_to_dealer=s["to_dealer"] / s["to_dealer_n"] if s["to_dealer_n"] else 0.0,
            conditional={k: v / s["cond_n"][k] for k, v in s["cond"].items()},
            conditional_damage=s["cond_dmg"] / n,
        )
    return out


def build() -> int:
    from gtc.synergy import load_database

    caps = aggregate(load_database())
    CAPS_PATH.write_text(json.dumps({k: vars(v) for k, v in sorted(caps.items())}, indent=1), encoding="utf-8")
    return len(caps)


_CAPS: dict[str, Capability] | None = None


def load() -> dict[str, Capability]:
    global _CAPS
    if _CAPS is None:
        _CAPS = {k: Capability(**v) for k, v in json.loads(CAPS_PATH.read_text(encoding="utf-8")).items()} if CAPS_PATH.exists() else {}
        # Hand-written capabilities for characters without simulations (knowledge/kits_custom/, kits_provisional/):
        # the midpoints of the kit's ranges (gtc/kit_schema.py) stand in until simulations exist.
        from gtc import kit_schema
        from gtc.knowledge import custom_kits

        for name, kit in custom_kits().items():
            if isinstance(kit, dict) and kit_schema.described(kit) and name not in _CAPS:
                c = kit_schema.capability_fields(kit)
                _CAPS[name] = Capability(name, 0, c["damage_share"], c["field_share"], c["apply"], {}, c["heal_per_s"], 0.0)
    return _CAPS


def team_profile(members: list[str], caps: dict[str, Capability]) -> dict:
    """Predicted team totals from members' average capabilities."""
    from gtc import timing

    key = (tuple(members), id(caps))
    hit = _PROFILE_CACHE.get(key)
    if hit is not None:
        timing.count("team_profile_hit")
        return hit
    timing.count("team_profile_miss")
    _PROFILE_CACHE[key] = out = _team_profile(members, caps)
    return out


_PROFILE_CACHE: dict = {}


def _team_profile(members: list[str], caps: dict[str, Capability]) -> dict:
    elements = ("Pyro", "Hydro", "Electro", "Cryo", "Anemo", "Geo", "Dendro")
    known = [caps[m] for m in members if m in caps]
    return {
        "apply": {el: sum(c.applies(el) for c in known) for el in elements},
        "apply_off": {el: sum(c.applies_off(el) for c in known) for el in elements},
        "onfield": sum(1 for c in known if c.onfield),
        "unknown": [m for m in members if m not in caps],
    }


NEIGHBOUR_BASE = params.get("capabilities.neighbour_base")  # weight of a simulated lineup grows by this factor per shared teammate


class Neighbours:
    """Members' behaviour in the simulated lineups most like a given one. A lineup sharing k teammates with the
    target weighs NEIGHBOUR_BASE**k, so the closest lineups dominate and the overall average is the fallback.
    Global averages flatten damage shares (carries look weaker, supports stronger than in any one team); on
    held-out lineups this predicts the top damage dealer 86% of the time with a per-member share error of
    about 5 points, against 65% for plain averages."""

    def __init__(self, db: dict):
        # Sums of (count, damage share, field share, team reaction share) for member m over the lineups that
        # contain m and every teammate in S, for each subset S of up to three teammates. The weight base**k of
        # a lineup sharing k teammates equals the sum over subsets S of those k of (base - 1)**|S|, so weighted
        # sums for any lineup come from these totals without scanning lineups.
        from itertools import combinations

        self.sums: dict[tuple[str, frozenset], list[float]] = {}
        self.entries: dict[frozenset, dict] = {}
        for e in db.values():
            prof = e.get("profile")
            if not prof:
                continue
            names = frozenset(e["lineup"])
            self.entries[names] = prof
            for m in e["lineup"]:
                c = prof["members"][m]
                v = (1.0, c["damage_share"], c["field_share"], prof["reaction_share"])
                others = [x for x in e["lineup"] if x != m]
                for k in range(len(others) + 1):
                    for S in combinations(others, k):
                        acc = self.sums.setdefault((m, frozenset(S)), [0.0, 0.0, 0.0, 0.0])
                        for i in range(4):
                            acc[i] += v[i]

    def profile(self, members: list[str], exclude: frozenset | None = None) -> tuple[dict, float] | None:
        from itertools import combinations

        lineup = frozenset(members)
        shares, fields = {}, {}
        rs = total_w = 0.0
        b1 = NEIGHBOUR_BASE - 1
        for m in members:
            others = [x for x in members if x != m]
            tot = [0.0, 0.0, 0.0, 0.0]
            for k in range(len(others) + 1):
                f = b1 ** k
                for S in combinations(others, k):
                    acc = self.sums.get((m, frozenset(S)))
                    if acc:
                        for i in range(4):
                            tot[i] += f * acc[i]
            if exclude is not None and exclude in self.entries and m in exclude:
                prof = self.entries[exclude]
                w = NEIGHBOUR_BASE ** (len(lineup & exclude) - 1)
                c = prof["members"][m]
                for i, v in enumerate((1.0, c["damage_share"], c["field_share"], prof["reaction_share"])):
                    tot[i] -= w * v
            if tot[0] <= 1e-9:
                return None
            shares[m], fields[m] = tot[1] / tot[0], tot[2] / tot[0]
            rs += tot[3]
            total_w += tot[0]
        norm = sum(shares.values()) or 1.0
        return {m: {"damage_share": shares[m] / norm, "field_share": fields[m]} for m in members}, rs / total_w


_NEIGHBOURS: Neighbours | None = None


def neighbours() -> Neighbours | None:
    global _NEIGHBOURS
    if _NEIGHBOURS is None:
        from gtc.synergy import DB_PATH, load_database

        if DB_PATH.exists():
            _NEIGHBOURS = Neighbours(load_database())
    return _NEIGHBOURS


def predict_structure(members: list[str], caps: dict[str, Capability] | None = None,
                      nb: Neighbours | None = None, exclude: frozenset | None = None) -> dict:
    """Damage structure for an unsimulated lineup, as a distribution (gtc/structure.py): from the most similar
    simulated lineups when every member has been simulated, otherwise from members' average damage shares
    renormalised to the team, with the measured prediction error propagated into class probabilities."""
    from gtc import structure, timing

    timing.count("predict_structure")
    return structure.predict(members, nb, caps, exclude)
