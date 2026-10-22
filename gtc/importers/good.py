"""Import inventory from a GOOD export (Genshin Open Object Description).

Scanners such as Inventory Kamera or Irminsul produce GOOD files. HoYoLAB already gives us every
character and what they have equipped, so here we only take what HoYoLAB cannot see: weapons and
artifacts sitting unequipped in the inventory.

GOOD shape, abridged:
  {"format": "GOOD", "version": 2,
   "weapons":   [{"key": "FavoniusSword", "level": 90, "ascension": 6, "refinement": 3, "location": ""}],
   "artifacts": [{"setKey": "GladiatorsFinale", "slotKey": "flower", "rarity": 5, "level": 20,
                  "mainStatKey": "hp", "substats": [{"key": "critRate_", "value": 3.9}], "location": ""}]}
"""
from __future__ import annotations

import json
from pathlib import Path

from gtc.snapshot import Artifact, Snapshot, Weapon
from gtc.stats import ROLL_VALUE

SLOT_KEYS = {"flower": 1, "plume": 2, "sands": 3, "goblet": 4, "circlet": 5}
# Main stat value at +20 for 5-star artifacts, and at +16 for 4-star. Enough for build checks.
MAIN_VALUE_5 = {"hp": 4780, "atk": 311, "hp_": 46.6, "atk_": 46.6, "def_": 58.3, "eleMas": 186.5, "enerRech_": 51.8,
                "critRate_": 31.1, "critDMG_": 62.2, "heal_": 35.9, "physical_dmg_": 58.3}


def _main_value(key: str, rarity: int, level: int) -> float:
    full = MAIN_VALUE_5.get(key, 46.6)  # elemental DMG goblets share the ATK% curve
    cap = 20 if rarity == 5 else 16
    scale = (0.25 + 0.75 * min(level, cap) / cap) * (1.0 if rarity == 5 else 0.75)
    return round(full * scale, 1)


def parse(path: Path, names, weapon_types: dict[str, dict]) -> tuple[list[Weapon], list[Artifact]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("format") != "GOOD":
        raise ValueError(f"{path} is not a GOOD export")
    weapons = []
    for w in data.get("weapons", []):
        if w.get("location"):
            continue
        name = names.weapon(w["key"]) or w["key"]
        info = weapon_types.get(name, {})
        weapons.append(Weapon(name=name, rarity=info.get("rarity", 0), level=w.get("level", 1), refinement=w.get("refinement", 1),
                              type=info.get("type", ""), ascension=w.get("ascension"), location=None))
    artifacts = []
    for a in data.get("artifacts", []):
        if a.get("location"):
            continue
        subs = []
        for sub in a.get("substats", []):
            if not sub.get("key"):
                continue
            rolls = max(1, round(sub["value"] / ROLL_VALUE[sub["key"]])) if sub["key"] in ROLL_VALUE else 1
            subs.append({"key": sub["key"], "value": sub["value"], "rolls": rolls})
        artifacts.append(Artifact(
            slot=SLOT_KEYS.get(a["slotKey"], 0), set_name=names.artifact_set(a["setKey"]) or a["setKey"],
            rarity=a.get("rarity", 5), level=a.get("level", 0), main_stat=a["mainStatKey"],
            main_value=_main_value(a["mainStatKey"], a.get("rarity", 5), a.get("level", 0)), substats=subs, location=None,
        ))
    return weapons, artifacts


def merge(snapshot: Snapshot, path: Path, names, weapon_types: dict[str, dict]) -> Snapshot:
    weapons, artifacts = parse(path, names, weapon_types)
    snapshot.spare_weapons, snapshot.spare_artifacts, snapshot.has_inventory = weapons, artifacts, True
    snapshot.source = f"{snapshot.source}+good"
    return snapshot
