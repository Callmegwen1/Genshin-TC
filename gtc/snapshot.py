"""Normalized account snapshot. Every importer converts into this shape.

Stat keys follow GOOD (see gtc/stats.py). Percent stats are in percent units.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

SLOT_NAMES = {1: "flower", 2: "plume", 3: "sands", 4: "goblet", 5: "circlet"}


@dataclass
class Weapon:
    name: str
    rarity: int
    level: int
    refinement: int
    type: int | str = 0
    ascension: int | None = None
    location: str | None = None  # character key holding it; None when unequipped (inventory only)


@dataclass
class Artifact:
    slot: int  # 1 flower, 2 plume, 3 sands, 4 goblet, 5 circlet
    set_name: str
    rarity: int
    level: int
    main_stat: str  # GOOD key
    main_value: float = 0.0
    substats: list[dict] = field(default_factory=list)  # [{"key": GOOD key, "value": float, "rolls": int}]
    location: str | None = None

    @property
    def slot_name(self) -> str:
        return SLOT_NAMES.get(self.slot, str(self.slot))


@dataclass
class Talents:
    """Talent levels. `base` is what you paid materials for; `effective` includes constellation bonuses."""
    normal: int
    skill: int
    burst: int
    normal_bonus: int = 0
    skill_bonus: int = 0
    burst_bonus: int = 0

    @property
    def effective(self) -> dict[str, int]:
        return {
            "normal": self.normal + self.normal_bonus,
            "skill": self.skill + self.skill_bonus,
            "burst": self.burst + self.burst_bonus,
        }


@dataclass
class Character:
    id: int
    name: str
    element: str
    rarity: int
    level: int
    constellation: int
    talents: Talents
    weapon: Weapon
    artifacts: list[Artifact] = field(default_factory=list)
    stats: dict[str, float] = field(default_factory=dict)

    @property
    def key(self) -> str:
        """Lookup key into the knowledge base. Traveler is keyed per element."""
        return f"Traveler ({self.element})" if self.name == "Traveler" else self.name

    def set_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for a in self.artifacts:
            counts[a.set_name] = counts.get(a.set_name, 0) + 1
        return counts

    def active_sets(self) -> dict[str, int]:
        """Sets with a 2-piece or 4-piece bonus active, as {set: 2 or 4}."""
        return {s: (4 if n >= 4 else 2) for s, n in self.set_counts().items() if n >= 2}


@dataclass
class Snapshot:
    uid: int
    source: str
    taken_at: str
    characters: list[Character]
    # Unequipped items, only known when a scanner export (GOOD) was imported.
    spare_weapons: list[Weapon] = field(default_factory=list)
    spare_artifacts: list[Artifact] = field(default_factory=list)
    has_inventory: bool = False

    @property
    def data_level(self) -> str:
        """"full" with a scanner export (spare weapons and artifacts known), "basic" from HoYoLAB alone
        (equipped items only). Anything that depends on the inventory says which it rests on."""
        return "full" if self.has_inventory else "basic"

    def by_key(self) -> dict[str, Character]:
        return {c.key: c for c in self.characters}

    def all_weapons(self) -> list[Weapon]:
        """Every weapon the account is known to own, with its current holder in `location`."""
        equipped = [Weapon(**{**asdict(c.weapon), "location": c.key}) for c in self.characters]
        return equipped + self.spare_weapons

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=1), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "Snapshot":
        raw = json.loads(path.read_text(encoding="utf-8"))
        chars = []
        for c in raw["characters"]:
            chars.append(Character(
                id=c["id"], name=c["name"], element=c["element"], rarity=c["rarity"],
                level=c["level"], constellation=c["constellation"],
                talents=Talents(**c["talents"]), weapon=Weapon(**c["weapon"]),
                artifacts=[Artifact(**a) for a in c["artifacts"]], stats=c["stats"],
            ))
        return cls(
            uid=raw["uid"], source=raw["source"], taken_at=raw["taken_at"], characters=chars,
            spare_weapons=[Weapon(**w) for w in raw.get("spare_weapons", [])],
            spare_artifacts=[Artifact(**a) for a in raw.get("spare_artifacts", [])],
            has_inventory=raw.get("has_inventory", False),
        )


def latest_snapshot(directory: Path) -> Path:
    files = sorted(directory.glob("*.json"))
    if not files:
        raise FileNotFoundError(f"No snapshots in {directory}. Run: python -m gtc import")
    return files[-1]
