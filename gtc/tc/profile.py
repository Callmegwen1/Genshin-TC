"""A team's damage profile: who deals what kind of damage, with which stats.

Built from a gcsim run. gcsim reports damage per ability per character and each character's
stat snapshot, which is exactly what a theorycrafter needs to reason about a swap: the swap
changes multipliers on these damage sources, and the formulas say by how much.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

# gcsim's stat order (pkg/core/attributes/stats.go).
SNAP = {"def": 2, "hp": 3, "atk": 5, "er": 7, "em": 8, "cr": 9, "cd": 10,
        "Pyro": 12, "Hydro": 13, "Cryo": 14, "Electro": 15, "Anemo": 16, "Geo": 17, "Dendro": 18, "Physical": 19, "dmg_pct": 21,
        "base_hp": 23, "base_atk": 24, "base_def": 25}
ELEMENTS = ["Pyro", "Hydro", "Electro", "Cryo", "Anemo", "Geo", "Dendro"]


@dataclass
class Unit:
    """One character as the calculator sees them: totals before dynamic team buffs."""
    name: str
    element: str
    level: int = 90
    cons: int = 0
    stats: dict[str, float] = field(default_factory=dict)  # atk, hp, def, em, cr, cd, dmg_pct, <Element> DMG%
    sets: dict[str, int] = field(default_factory=dict)  # set display name to piece count


@dataclass
class Source:
    owner: str
    name: str
    kind: str  # direct, lunar_charged_direct, lunar_charged_reaction, swirl
    element: str
    dps: float


@dataclass
class Profile:
    lineup: list[str]
    lead: str
    units: dict[str, Unit]
    sources: list[Source]
    origin: str = ""

    @property
    def dps(self) -> float:
        return sum(s.dps for s in self.sources)

    def by_owner(self, name: str) -> float:
        return sum(s.dps for s in self.sources if s.owner == name)


def classify(source: str, owner: str, kits: dict) -> tuple[str, str | None]:
    """Damage kind and element for a gcsim source name, using the owner's kit when it names the ability."""
    kit = kits.get(owner) or {}
    kind = (kit.get("abilities") or {}).get(source)
    if source.startswith("swirl-"):
        return "swirl", source.split("-", 1)[1].capitalize()
    if source == "lunarcharged":
        return "lunar_charged_reaction", "Electro"
    if kind is None and "lunar-charged" in source.lower():
        return "lunar_charged_direct", "Electro"  # Lunar-Charged damage counts as Electro
    return kind or "direct", ("Electro" if kind == "lunar_charged_direct" else None)


def from_gcsim(raw_path, names, kits: dict, game: dict, sets_lookup=None, lead: str | None = None, origin: str = "") -> Profile:
    d = json.loads(raw_path.read_text(encoding="utf-8"))
    units, keys = {}, []
    for c in d["character_details"]:
        name = names.character(c["name"]) or c["name"]
        keys.append(name)
        snap = c.get("snapshot") or []
        stats = {k: (snap[i] if i < len(snap) else 0.0) for k, i in SNAP.items()}
        sets = {}
        for k, n in (c.get("sets") or {}).items():
            sets[(sets_lookup(k) if sets_lookup else None) or k] = n
        units[name] = Unit(name, (c.get("element") or game.get(name, {}).get("element", "")).capitalize(),
                           c.get("level", 90), c.get("cons", 0) if isinstance(c.get("cons"), int) else 0, stats, sets)
    sources = []
    for i, entry in enumerate(d["statistics"].get("source_dps") or []):
        owner = keys[i]
        for src, v in (entry.get("sources") or {}).items():
            kind, element = classify(src, owner, kits)
            if v["mean"] > 0:
                sources.append(Source(owner, src, kind, element or units[owner].element, v["mean"]))
    if lead is None:
        lead = max(keys, key=lambda n: sum(s.dps for s in sources if s.owner == n and s.kind != "lunar_charged_reaction"))
    return Profile(keys, lead, units, sources, origin)
