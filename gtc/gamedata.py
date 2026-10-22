"""Static game data generated from community datasets. Never edit the generated files by hand.

Source: Project Amber (gi.yatta.moe), which mirrors datamined game data.
"""
from __future__ import annotations

import json
import urllib.request

from gtc import KNOWLEDGE_DIR

GAME_CHARACTERS = KNOWLEDGE_DIR / "generated" / "game_characters.json"
GAME_WEAPONS = KNOWLEDGE_DIR / "generated" / "game_weapons.json"
GAME_SETS = KNOWLEDGE_DIR / "generated" / "game_artifact_sets.json"
AMBER_SET_URL = "https://gi.yatta.moe/api/v2/en/reliquary"
AMBER_URL = "https://gi.yatta.moe/api/v2/en/avatar"
AMBER_WEAPON_URL = "https://gi.yatta.moe/api/v2/en/weapon"
ELEMENT_NAMES = {"Ice": "Cryo", "Wind": "Anemo", "Water": "Hydro", "Fire": "Pyro", "Electric": "Electro", "Grass": "Dendro", "Rock": "Geo"}


def fetch_characters() -> dict[str, dict]:
    """Every released character with a fixed element. Traveler and Manekin are skipped
    because their element depends on the player."""
    req = urllib.request.Request(AMBER_URL, headers={"User-Agent": "genshin-theorycraft-personal/0.1"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        items = json.load(resp)["data"]["items"].values()
    out = {}
    for it in items:
        element = ELEMENT_NAMES.get(it["element"])
        if element is None or it["name"] == "Traveler":
            continue
        out[it["name"]] = {"id": it["id"], "element": element, "rarity": it["rank"], "weapon": it["weaponType"].removeprefix("WEAPON_").lower()}
    return dict(sorted(out.items()))


def fetch_weapons() -> dict[str, dict]:
    """Weapon name to rarity and type (sword_one_hand, claymore, pole, bow, catalyst)."""
    req = urllib.request.Request(AMBER_WEAPON_URL, headers={"User-Agent": "genshin-theorycraft-personal/0.1"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        items = json.load(resp)["data"]["items"].values()
    return dict(sorted(((it["name"], {"rarity": it["rank"], "type": it["type"].removeprefix("WEAPON_").lower()}) for it in items), key=lambda x: x[0]))


def fetch_sets() -> dict[str, dict]:
    """Artifact set name to its highest rarity and set-bonus texts."""
    req = urllib.request.Request(AMBER_SET_URL, headers={"User-Agent": "genshin-theorycraft-personal/0.1"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        items = json.load(resp)["data"]["items"].values()
    return {it["name"]: {"rarity": max(it.get("levelList") or [5]), "effects": list((it.get("affixList") or {}).values())}
            for it in sorted(items, key=lambda x: x["name"])}


def update() -> int:
    chars = fetch_characters()
    GAME_CHARACTERS.parent.mkdir(parents=True, exist_ok=True)
    GAME_CHARACTERS.write_text(json.dumps(chars, ensure_ascii=False, indent=1), encoding="utf-8")
    GAME_WEAPONS.write_text(json.dumps(fetch_weapons(), ensure_ascii=False, indent=1), encoding="utf-8")
    GAME_SETS.write_text(json.dumps(fetch_sets(), ensure_ascii=False, indent=1), encoding="utf-8")
    return len(chars)


def load_characters() -> dict[str, dict]:
    if not GAME_CHARACTERS.exists():
        raise FileNotFoundError("Game data missing. Run: python -m gtc gamedata")
    return json.loads(GAME_CHARACTERS.read_text(encoding="utf-8"))


def load_weapons() -> dict[str, dict]:
    if not GAME_WEAPONS.exists():
        raise FileNotFoundError("Weapon data missing. Run: python -m gtc gamedata")
    return json.loads(GAME_WEAPONS.read_text(encoding="utf-8"))


def load_sets() -> dict[str, dict]:
    if not GAME_SETS.exists():
        raise FileNotFoundError("Artifact set data missing. Run: python -m gtc gamedata")
    return json.loads(GAME_SETS.read_text(encoding="utf-8"))


def names():
    """A name matcher covering every character, weapon and artifact set in the game."""
    from gtc.sources.names import Names

    return Names(load_characters().keys(), {k: v["rarity"] for k, v in load_weapons().items()},
                 list(load_sets()) if GAME_SETS.exists() else [])
