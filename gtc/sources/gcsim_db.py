"""gcsim team database, hosted by Keqing Mains at db.kqm.gg.

Each entry is one simulated team: members with constellation, weapon and refinement,
plus damage per second per target. Submitters use very different assumptions (the same
Flins team ranges from about 140k DPS at C0 to 1.4M at C6 R5), so every comparison the
engine makes goes through `is_standard` or a like-for-like match. See docs/engine.md.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field

from gtc.sources import SOURCE_DIR
from gtc.sources.fetch import TOOL_UA

DB_URL = "https://db.kqm.gg/api/db"
RAW_PATH = SOURCE_DIR / "gcsim_db_raw.json"
TEAMS_PATH = SOURCE_DIR / "gcsim_teams.json"
PAGE = 100
ACCEPTED_TAGS = {1, 9}  # 1 = accepted by gcsim reviewers, 9 = guide simulations
TAG_NAMES = {1: "gcsim", 5: "itto simps", 6: "random delays", 7: "newbie", 8: "APL", 9: "guides"}


@dataclass
class SimMember:
    name: str
    rarity: int
    cons: int
    weapon: str
    weapon_rarity: int
    refine: int
    sets: dict = field(default_factory=dict)  # artifact set -> pieces, as submitted
    talents: tuple = ()  # (normal, skill, burst)

    @property
    def main_set(self) -> str:
        """The set with the most pieces (4pc or 2pc), or "" with none; ties go alphabetical."""
        if not self.sets:
            return ""
        return min(self.sets.items(), key=lambda kv: (-kv[1], kv[0]))[0]


@dataclass
class SimTeam:
    id: str
    date: int
    description: str
    targets: int
    dps: float
    tags: list[int]
    members: list[SimMember]
    submitter: str = ""  # gcsim's submitter id; "migrated" for entries carried over from the old database

    @property
    def names(self) -> frozenset[str]:
        cached = self.__dict__.get("_names")
        if cached is None:
            cached = self.__dict__["_names"] = frozenset(m.name for m in self.members)
        return cached

    def member(self, name: str) -> SimMember | None:
        return next((m for m in self.members if m.name == name), None)

    @property
    def build_key(self) -> tuple:
        """The build assumptions that change a lineup's damage materially: each member's constellation, weapon,
        refinement and main artifact set. Substats differ in every submission and are left out."""
        return tuple(sorted((m.name, m.cons, m.weapon, m.refine, m.main_set) for m in self.members))

    @property
    def accepted(self) -> bool:
        return bool(ACCEPTED_TAGS & set(self.tags))


def download() -> int:
    """Fetch every entry, 100 per request, half a second apart."""
    entries, skip = [], 0
    while True:
        q = urllib.parse.quote(json.dumps({"limit": PAGE, "skip": skip}))
        req = urllib.request.Request(f"{DB_URL}?q={q}", headers={"User-Agent": TOOL_UA})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.load(resp).get("data") or []
        if not data:
            break
        entries += data
        skip += PAGE
        time.sleep(0.5)
    RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
    RAW_PATH.write_text(json.dumps(entries), encoding="utf-8")
    return len(entries)


def normalize(names, game_chars: dict[str, dict]) -> tuple[int, int]:
    """Convert raw entries into SimTeams with display names and rarities. Returns (kept, skipped)."""
    raw = json.loads(RAW_PATH.read_text(encoding="utf-8"))
    teams, skipped = [], 0
    for e in raw:
        s = e.get("summary") or {}
        members = []
        for c in s.get("team") or []:
            name = names.character(c["name"])
            w = c.get("weapon") or {}
            wr = names.weapon_rarity(w.get("name", ""))
            if name is None or wr is None:
                break
            rarity = game_chars.get(name, {}).get("rarity", 5)  # Travelers are 5-star
            t = c.get("talents") or {}
            members.append(SimMember(name, rarity, c.get("cons", 0), w["name"], wr, w.get("refine", 1),
                                     dict(c.get("sets") or {}), (t.get("attack"), t.get("skill"), t.get("burst"))))
        if len(members) != len(s.get("team") or [0]) or not s.get("mean_dps_per_target"):
            skipped += 1
            continue
        teams.append(SimTeam(
            id=e["_id"], date=int(e.get("create_date") or 0), description=(e.get("description") or "")[:300],
            targets=s.get("target_count", 1), dps=s["mean_dps_per_target"], tags=e.get("accepted_tags") or [],
            members=members, submitter=str(e.get("submitter") or ""),
        ))
    TEAMS_PATH.write_text(json.dumps([asdict(t) for t in teams]), encoding="utf-8")
    return len(teams), skipped


@dataclass
class LineupValue:
    """A lineup's value from all its standard simulations, robust to who submitted them.

    Each submitter's runs collapse to their median, so re-submitting the same lineup many times is one vote;
    the lineup's value is the median of those per-submitter values. Entries without a known submitter
    ("migrated" from the old database, or blank) count together as one submitter. `n_submitters` is the
    number of independent votes and sets the uncertainty (gtc/estimate.py).

    Submissions also differ in their build assumptions (a Hu Tao on Deathmatch against one on Ballad of the Fjords).
    `by_build` keeps, for each distinct build (SimTeam.build_key), the median of its submitters' medians and how many
    submitters ran it, so the uncertainty can tell disagreement within one build from disagreement between builds.
    The value itself is unchanged by this."""
    value: float
    n_sims: int
    n_submitters: int
    by_submitter: dict[str, float]
    spread: float  # max minus min of the per-submitter values, relative to the value; 0 with one submitter
    by_build: dict = field(default_factory=dict)  # build_key -> (value, n_submitters)

    @property
    def n_builds(self) -> int:
        return len(self.by_build)

    @property
    def mixed_builds(self) -> bool:
        return len(self.by_build) > 1


def _median(v: list[float]) -> float:
    v = sorted(v)
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


def aggregate(sims: list[SimTeam]) -> LineupValue:
    groups: dict[str, list[float]] = {}
    builds: dict[tuple, dict[str, list[float]]] = {}
    for t in sims:
        who = t.submitter if t.submitter and t.submitter != "migrated" else "unknown"
        groups.setdefault(who, []).append(t.dps)
        builds.setdefault(t.build_key, {}).setdefault(who, []).append(t.dps)
    per = {who: _median(v) for who, v in groups.items()}
    value = _median(list(per.values()))
    spread = (max(per.values()) - min(per.values())) / value if value else 0.0
    by_build = {k: (_median([_median(v) for v in subs.values()]), len(subs)) for k, subs in builds.items()}
    return LineupValue(value, len(sims), len(per), per, spread, by_build)


_VALUES: dict[frozenset, LineupValue] | None = None


def lineup_values() -> dict[frozenset, LineupValue]:
    """Every standard lineup's robust value. The one place lineup values are computed."""
    global _VALUES
    if _VALUES is None:
        groups: dict[frozenset, list[SimTeam]] = {}
        for t in load():
            if is_standard(t):
                groups.setdefault(t.names, []).append(t)
        _VALUES = {k: aggregate(v) for k, v in groups.items()}
    return _VALUES


_LOADED: tuple[float, list] | None = None


def load() -> list[SimTeam]:
    """Every normalised simulation. Parsed once per file version (callers must not modify the records)."""
    global _LOADED
    if not TEAMS_PATH.exists():
        return []
    mtime = TEAMS_PATH.stat().st_mtime
    if _LOADED is None or _LOADED[0] != mtime:
        _LOADED = (mtime, [SimTeam(**{**t, "members": [SimMember(**m) for m in t["members"]]})
                           for t in json.loads(TEAMS_PATH.read_text(encoding="utf-8"))])
    return _LOADED[1]


def is_standard(t: SimTeam) -> bool:
    """Comparable across teams: every 5-star character at C0 with any 5-star weapon at R1,
    single target, accepted by reviewers. 4-star characters and weapons may be at any level,
    as in Keqing Mains' and Prydwen's own standards."""
    if t.targets != 1 or not t.accepted:
        return False
    return all((m.rarity < 5 or m.cons == 0) and (m.weapon_rarity < 5 or m.refine == 1) for m in t.members)
