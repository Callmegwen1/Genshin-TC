"""Load and validate the curated knowledge files."""
from __future__ import annotations

from gtc import params

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from gtc import KNOWLEDGE_DIR

NON_PREFERRED_FACTOR = params.get("knowledge.non_preferred_factor")
GENERATED_EXTRAS = {"healer", "shield", "res_shred", "def_shred"}
MAX_QUALITY = 5.0
ELEMENTS = {"Pyro", "Hydro", "Electro", "Cryo", "Anemo", "Geo", "Dendro"}


@dataclass
class Note:
    text: str
    templates: list[str] | None = None  # None means the note applies in every archetype


@dataclass
class CharacterInfo:
    key: str
    roles: dict[str, int]
    key_talents: list[str] = field(default_factory=lambda: ["skill", "burst"])
    constellation_roles: dict[int, dict[str, int]] = field(default_factory=dict)
    notes: list[Note] = field(default_factory=list)
    review: bool = False
    generated: bool = False  # only known from generated data, not hand-written
    custom_kit: bool = False  # placed by a hand-written kit in knowledge/kits_custom/
    provisional: bool = False  # described only by a provisional kit (knowledge/kits_provisional/, phase 6.5)

    def roles_at(self, constellation: int) -> dict[str, int]:
        """Roles including any unlocked by constellations. Higher constellations override lower ones."""
        roles = dict(self.roles)
        for con in sorted(self.constellation_roles):
            if constellation >= con:
                roles.update(self.constellation_roles[con])
        return roles


@dataclass
class Slot:
    name: str
    roles: list[str]
    elements: list[str] | None = None
    core: bool = False
    min_quality: int = 1
    weight: float = 1.0
    prefers: list[str] | None = None  # other roles count at NON_PREFERRED_FACTOR quality
    # Optional value formula. When set, slot quality = base + sum(weight * role quality), capped at 5,
    # so a character is credited for everything they bring, not just the role that got them in.
    value: dict[str, float] | None = None


@dataclass
class Template:
    id: str
    label: str
    slots: list[Slot]
    ceiling: float = 1.0
    allowed_elements: list[str] | None = None
    requires: list[dict] = field(default_factory=list)
    bonuses: list[dict] = field(default_factory=list)
    pair_bonuses: list[dict] = field(default_factory=list)
    sustain_penalty: float | None = None  # overrides scoring.no_sustain_penalty
    compare: str = "lead"  # composition baseline: best team with the same lead, or best "archetype" team overall
    signature: dict | None = None  # element pattern used to recognise simulations: require, forbid, only
    validity: dict | None = None  # rules learned from simulated teams (gtc/validity.py); checked before scoring


@dataclass
class Knowledge:
    characters: dict[str, CharacterInfo]
    templates: dict[str, Template]
    scoring: dict
    my_teams: list[list[str]]


def _read(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _character(key: str, v: dict) -> CharacterInfo:
    return CharacterInfo(
        key=key, roles=v.get("roles", {}), key_talents=v.get("key_talents", ["skill", "burst"]),
        constellation_roles={int(c): r for c, r in (v.get("constellation_roles") or {}).items()},
        notes=[Note(**n) if isinstance(n, dict) else Note(text=n) for n in v.get("notes", [])],
        review=v.get("review", False),
    )


def custom_kits(directory: Path = KNOWLEDGE_DIR) -> dict:
    """knowledge/kits_custom/*.yaml and knowledge/kits_provisional/*.yaml (files starting with "_" are skipped).
    Provisional kits carry `provisional: true`; a kits_custom entry for the same character wins."""
    out = {}
    for sub in ("kits_provisional", "kits_custom"):
        folder = directory / sub
        if folder.exists():
            for path in sorted(folder.glob("*.yaml")):
                if not path.name.startswith("_"):
                    out.update(_read(path))
    return out


def provisional_kits(directory: Path = KNOWLEDGE_DIR) -> dict:
    """The provisional kits only (phase 6.5)."""
    return {k: v for k, v in custom_kits(directory).items() if isinstance(v, dict) and v.get("provisional")}


def _apply_custom_kits(directory: Path, chars: dict, templates: dict) -> None:
    """Place characters described by hand in knowledge/kits_custom/ into teams. `expected_archetypes` maps an
    archetype id to carry or support (with an optional quality, default 4): carry gives the role of the
    archetype's first slot, support the role of its teammate slots. `roles` are taken as written. These are
    judgments, not measurements, so their teams are evidence tier E until simulations exist."""
    for name, kit in custom_kits(directory).items():
        if not isinstance(kit, dict) or not (kit.get("expected_archetypes") or kit.get("roles")):
            continue
        roles: dict[str, int] = {}
        for tid, spec in (kit.get("expected_archetypes") or {}).items():
            t = templates.get(tid)
            if t is None:
                raise ValueError(f"kits_custom: {name} names unknown archetype {tid}")
            spec = spec if isinstance(spec, dict) else {"as": spec}
            q = int(spec.get("quality", 4))
            if spec.get("as", "carry") == "carry":
                roles[t.slots[0].roles[0]] = q
            else:
                for slot in t.slots[1:]:
                    roles.setdefault(slot.roles[0], q)
        roles.update(kit.get("roles") or {})
        info = chars.get(name)
        if info is None:
            chars[name] = info = _character(name, {"roles": {}})
        info.roles = {r: v for r, v in info.roles.items() if r != "carry_unsimulated"}
        info.roles.update(roles)
        info.custom_kit = True
        info.provisional = bool(kit.get("provisional"))


def load(directory: Path = KNOWLEDGE_DIR, generated: bool = True) -> Knowledge:
    """Hand-written knowledge, plus generated knowledge for everything it does not cover
    (python -m gtc derive). A hand-written role or template always wins."""
    curated = _read(directory / "characters.yaml")
    auto_roles = _read(directory / "generated" / "auto_roles.yaml") if generated else {}
    merged = {}
    for key in set(curated) | set(auto_roles):
        v = dict(curated.get(key) or {})
        roles = dict((auto_roles.get(key) or {}).get("roles") or {})
        if key in curated:
            # For hand-written characters, only take what data adds on top of judgment: archetype carry and
            # teammate ratings from simulations, and sustain or shred read from talent text.
            roles = {r: q for r, q in roles.items() if r.startswith(("carry_", "support_")) or r in GENERATED_EXTRAS}
        roles.update(v.get("roles") or {})
        v["roles"] = roles
        if key not in curated:
            v["generated"] = True
        merged[key] = v
    chars = {key: _character(key, v) for key, v in merged.items()}
    for key, v in merged.items():
        chars[key].generated = bool(v.get("generated"))
    templates = {}
    template_docs = dict(_read(directory / "templates.yaml"))
    if generated:
        for tid, t in _read(directory / "generated" / "auto_templates.yaml").items():
            template_docs.setdefault(tid, t)
    for tid, t in template_docs.items():
        templates[tid] = Template(
            id=tid, label=t.get("label", tid), ceiling=t.get("ceiling", 1.0),
            slots=[Slot(**s) for s in t["slots"]], allowed_elements=t.get("allowed_elements"),
            requires=t.get("requires", []), bonuses=t.get("bonuses", []), pair_bonuses=t.get("pair_bonuses", []),
            sustain_penalty=t.get("sustain_penalty"), compare=t.get("compare", "lead"), signature=t.get("signature"),
        )
    if generated:
        _apply_custom_kits(directory, chars, templates)
    my_teams_path = directory / "my_teams.yaml"
    my_teams = _read(my_teams_path).get("teams", []) if my_teams_path.exists() else []
    kb = Knowledge(characters=chars, templates=templates, scoring=_read(directory / "scoring.yaml"), my_teams=my_teams)
    problems = validate(kb)
    if problems:
        raise ValueError("Knowledge base problems:\n  " + "\n  ".join(problems))
    return kb


def validate(kb: Knowledge) -> list[str]:
    """Catch typos early: every role a template mentions must exist on some character."""
    known_roles = {r for c in kb.characters.values() for r in c.roles}
    known_roles |= {r for c in kb.characters.values() for rs in c.constellation_roles.values() for r in rs}
    problems = []
    for c in kb.characters.values():
        all_roles = list(c.roles.items()) + [kv for rs in c.constellation_roles.values() for kv in rs.items()]
        for r, q in all_roles:
            if not 1 <= q <= 5:
                problems.append(f"{c.key}: role {r} quality {q} is outside 1-5")
        for t in c.key_talents:
            if t not in ("normal", "skill", "burst"):
                problems.append(f"{c.key}: unknown key talent {t}")
        for n in c.notes:
            for tid in n.templates or []:
                if tid not in kb.templates:
                    problems.append(f"{c.key}: note refers to unknown template {tid}")
    for t in kb.templates.values():
        for s in t.slots:
            for r in list(s.roles) + [r for r in (s.value or {}) if r != "base"]:
                if r not in known_roles:
                    problems.append(f"template {t.id}, slot {s.name}: no character has role '{r}'")
            for e in s.elements or []:
                if e not in ELEMENTS:
                    problems.append(f"template {t.id}, slot {s.name}: unknown element {e}")
    return problems
