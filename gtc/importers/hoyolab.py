"""Import the full roster from the HoYoLAB battle chronicle using your own cookie."""
from __future__ import annotations

import asyncio
import os
import re
from datetime import datetime, timezone

import genshin
from dotenv import load_dotenv

from gtc import ROOT
from gtc.snapshot import Artifact, Character, Snapshot, Talents, Weapon
from gtc.stats import HOYOLAB_IDS

# Stat ids as reported by HoYoLAB's property_map.
STAT_IDS = {2000: "hp", 2001: "atk", 2002: "def", 20: "crit_rate", 22: "crit_dmg", 23: "energy_recharge", 28: "elemental_mastery"}
_TAG = re.compile(r"<[^>]+>|\{LINK#[^}]*\}|\{/LINK\}")
_BOOST = re.compile(r"Increases the Level of (?:the (?:Elemental Skill|Elemental Burst|Normal Attack) )?(.+?) by (\d+)")


def _num(value: str) -> float:
    return float(value.replace("%", "").replace(",", "") or 0)


def _talents(entry: dict) -> Talents:
    """Active talents are ordered Normal, Skill, [alternate sprint], Burst.

    HoYoLAB reports levels including constellation boosts, so we read each
    unlocked constellation's text to subtract them and recover the base level.
    """
    active = [s for s in entry["skills"] if s["skill_type"] == 1]
    normal, skill, burst = active[0], active[1], active[-1]
    bonus = {"normal": 0, "skill": 0, "burst": 0}
    for con in entry["constellations"]:
        if not con["is_actived"]:
            continue
        m = _BOOST.search(_TAG.sub("", con["effect"]))
        if not m:
            continue
        target = m.group(1).strip()
        for slot, talent in (("normal", normal), ("skill", skill), ("burst", burst)):
            if talent.get("name", "").strip() == target:
                bonus[slot] += int(m.group(2))
    return Talents(
        normal=normal["level"] - bonus["normal"], skill=skill["level"] - bonus["skill"], burst=burst["level"] - bonus["burst"],
        normal_bonus=bonus["normal"], skill_bonus=bonus["skill"], burst_bonus=bonus["burst"],
    )


def _artifact(r: dict, holder: str) -> Artifact:
    main = r["main_property"]
    return Artifact(
        slot=r["pos"], set_name=r["set"]["name"], rarity=r["rarity"], level=r["level"],
        main_stat=HOYOLAB_IDS.get(main["property_type"], str(main["property_type"])), main_value=_num(main["value"]),
        substats=[{"key": HOYOLAB_IDS.get(sp["property_type"], str(sp["property_type"])), "value": _num(sp["value"]),
                   "rolls": sp.get("times", 0) + 1} for sp in r.get("sub_property_list", [])],
        location=holder,
    )


def _character(entry: dict) -> Character:
    base, w = entry["base"], entry["weapon"]
    props = entry["selected_properties"] + entry["base_properties"] + entry["extra_properties"]
    stats = {STAT_IDS[p["property_type"]]: _num(p["final"]) for p in props if p["property_type"] in STAT_IDS}
    return Character(
        id=base["id"], name=base["name"], element=base["element"], rarity=base["rarity"],
        level=base["level"], constellation=base["actived_constellation_num"], talents=_talents(entry),
        weapon=Weapon(name=w["name"], rarity=w["rarity"], level=w["level"], refinement=w["affix_level"], type=w["type"],
                      ascension=w.get("promote_level")),
        artifacts=[_artifact(r, base["name"]) for r in entry["relics"]],
        stats=stats,
    )


async def _fetch() -> tuple[int, dict]:
    load_dotenv(ROOT / ".env")
    cookies = {k.lower(): os.environ[k] for k in ("LTUID_V2", "LTOKEN_V2", "LTMID_V2")}
    client = genshin.Client(cookies, game=genshin.Game.GENSHIN)
    uid = int(os.environ["UID"])
    basic = await client.get_genshin_characters(uid)
    raw = await client.get_genshin_detailed_characters(uid, characters=[c.id for c in basic], return_raw_data=True)
    return uid, raw


def import_snapshot() -> Snapshot:
    uid, raw = asyncio.run(_fetch())
    chars = [_character(e) for e in raw["list"]]
    return Snapshot(uid=uid, source="hoyolab", taken_at=datetime.now(timezone.utc).isoformat(timespec="seconds"), characters=chars)
