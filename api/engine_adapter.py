"""The one place the cloud layer calls the theorycraft engine. Used by the worker and by the legacy synchronous route,
so both produce identical results. No engine logic lives here: it calls gtc.forward.blind.theorycraft unchanged and
shapes its output for JSON.
"""
from __future__ import annotations

from pathlib import Path

from gtc import KNOWLEDGE_DIR

KIT_DIR = KNOWLEDGE_DIR / "forward" / "actions"


class UnsupportedCharacter(ValueError):
    def __init__(self, names: list[str]):
        super().__init__(f"unsupported character(s): {', '.join(names)}")
        self.names = names


def supported_characters() -> list[str]:
    """Characters with a hand-written kit file; names keep the exact case of the files (Linux is case-sensitive)."""
    return sorted(p.stem for p in Path(KIT_DIR).glob("*.yaml"))


def run_team(lineup: list[str]) -> dict:
    """ForwardModel r8 blind theorycraft for one team (neutral profile). Raises UnsupportedCharacter instead of letting
    the engine fall back to gcsim for a character without a kit file."""
    from gtc.forward import FORWARD_VERSION
    from gtc.forward.blind import theorycraft
    from gtc.forward.decompose import _label
    from gtc.forward.library import load_hand

    missing = [m for m in lineup if load_hand(m) is None]
    if missing:
        raise UnsupportedCharacter(missing)

    r = theorycraft(list(lineup), profile="neutral")
    ev = r["evaluation"]
    search = r.get("search") or {}
    return {
        "lineup": list(lineup),
        "engine_version": FORWARD_VERSION,
        "dps": round(ev.dps),
        "total_damage": round(ev.total_damage),
        "rotation_seconds": round(ev.rotation_duration, 2),
        "strategy": _label(r["plan"]),
        "per_character_dps": {k: round(v) for k, v in ev.per_character.items()},
        "damage_share": {k: round(v, 4) for k, v in ev.damage_share.items()},
        "per_reaction": {k: round(v) for k, v in ev.per_reaction.items()},
        "top_buffs": dict(sorted(((k, round(v, 4)) for k, v in ev.buff_contributions.items()),
                                 key=lambda kv: -kv[1])[:10]),
        "field_time": {k: round(v, 2) for k, v in ev.field_time.items()},
        "energy": ev.energy,
        "coverage": round(ev.coverage, 4),
        "uncertainty_relative_sd": round(ev.uncertainty, 4),
        "confidence": ev.confidence,
        "unknown": ev.unknown,
        "assumptions": ev.assumptions,
        "search": {
            "candidates_evaluated": search.get("evaluated"),
            "base_search_seconds": search.get("seconds"),
            "time_limit_seconds": search.get("time_limit_seconds"),
            "limit_hit": search.get("limit_hit"),            # "time", "plans" or null
            "ended_by_time_limit": search.get("limit_hit") == "time",
            "note": search.get("bounded") or None,
        },
    }
