"""Shared helpers for scenario tests: build hypothetical accounts from game data."""
from __future__ import annotations

from functools import lru_cache

from gtc import SNAPSHOT_DIR, gamedata, knowledge
from gtc.account import AccountModel
from gtc.report import analyze
from gtc.snapshot import Snapshot, latest_snapshot
from gtc.teams import Member


@lru_cache(maxsize=1)
def engine() -> AccountModel:
    kb = knowledge.load()
    an = analyze(Snapshot.load(latest_snapshot(SNAPSHOT_DIR)), kb)
    return AccountModel(an, kb)


def account(names: list[str], cons: dict[str, int] | None = None) -> list[Member]:
    """A hypothetical roster. Unlisted constellations: C0 for 5-stars, C6 for 4-stars."""
    am = engine()
    game = gamedata.load_characters()
    out = []
    for n in names:
        c = (cons or {}).get(n, 6 if game[n]["rarity"] == 4 else 0)
        roles = {**am.kb.characters[n].roles_at(c), **am.ev.faction_roles(n)}
        out.append(Member(n, game[n]["element"], 1.0, roles, c))
    return out


def ranked_values(roster: list[Member], pool: list[str] | None = None):
    am = engine()
    base, cands = am.plan(roster)
    owned = {m.key for m in roster}
    names = pool or [n for n in am.universe if n not in owned]
    vals = [v for n in names if (v := am.value_of(n, roster, base, cands))]
    return base, cands, sorted(vals, key=lambda v: -v.gain)
