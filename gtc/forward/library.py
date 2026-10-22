"""Per-character action libraries (rotation step 1): what each action of a character does, as character facts.

For every action type (skill, burst, attack, charge, dash, high_plunge, ...):
    duration   seconds from the action until the next action (animation, swap included): field time it costs
    hits       the damage it produces: offset from the cast, ability, element, damage type, talent multiplier,
               scaling stat; Swirl reactions are kept as element-agnostic templates ("swirl")
    particles  elemental particles generated per cast (the character's own particle events)
and per character a FILLER UNIT: the most common sequence of non-Skill / non-Burst actions they perform on field
between swaps (Ayaka: dash, attack, attack, charge), for the generator to repeat during a carry window.

Source: house-build traces (gtc/forward/trace.py) of community rotations of OTHER teams (behaviour evidence, the
examiner's data, never the team being evaluated): `build(name, exclude=[lineups])` skips any lineup in `exclude`,
so a blind test never sees its own team. Each entry keeps the median instance across all casts in the sources.
Multipliers are cross-checked against the Amber talent tables (`check`).

Approximations: hits a teammate triggers (Xingqiu's Rain Swords) are counted per cast as measured; hit counts that
depend on target size or on the source rotation are the median over sources.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from statistics import median

from gtc import ROOT

LIB_DIR = ROOT / "data" / "forward" / "library"
SOURCES_PER_CHAR = 4
FILLER_KINDS = ("attack", "charge", "dash", "high_plunge", "low_plunge", "aim", "jump", "walk")


@dataclass
class HitTemplate:
    offset: float
    abil: str
    element: str
    damage_type: str
    mult: float
    scaling: str
    reaction: str = ""          # "swirl" template or "" (amp / cata are decided by the reaction model, not here)
    ignore_def: bool = False
    gauge: float = 0.0          # elemental units applied (the kit's ICD and gauge, as gcsim implements them)
    table: tuple = ()           # hand-written kits: (talent, label, index) the multiplier comes from
    icd: str = ""               # hand-written kits: "standard" (1U on the 1st of every 3 hits or after 2.5 s)
    add_mult: dict | None = None  # {resource, per}: multiplier added per point of a resource (Raiden's Resolve)
    scale_trigger: bool = False   # proc hit: multiplier is a share of the triggering hit's (Razor's Soul Companion)
    source: str = ""            # provenance of this hit's structure (amber / hand / gcsim-calibrated)
    expand: bool = False        # the only hit of a multi-stat row in its group: the row's other terms are added


@dataclass
class ActionEntry:
    action: str
    duration: float
    hits: list[HitTemplate] = field(default_factory=list)
    particles: float = 0.0
    casts: int = 0


@dataclass
class Library:
    name: str
    actions: dict[str, ActionEntry]
    filler: list[str]
    sources: list[str]
    notes: list[str] = field(default_factory=list)
    follow: dict[str, str] = field(default_factory=dict)   # action -> the own action that usually follows it at once
    hand: bool = False                                      # hand-written prerelease kit (no gcsim input)
    states: dict = field(default_factory=dict)              # name -> {start, duration, extend_on}
    specials: list = field(default_factory=list)            # actions used whenever available in the carry window
    level_bonus: dict = field(default_factory=dict)         # {table, amount, trigger, duration}
    action_meta: dict = field(default_factory=dict)         # action -> {state, requires_state, uses_per_state}
    facts: dict = field(default_factory=dict)               # known / assumed / unknown
    resources: dict = field(default_factory=dict)           # kit language (gtc/forward/engine.py)
    rules: list = field(default_factory=list)
    summons: dict = field(default_factory=dict)
    procs: dict = field(default_factory=dict)
    reaction_procs: dict = field(default_factory=dict)   # procs on reaction events (applied after the reaction model)
    provenance: dict = field(default_factory=dict)
    status: dict = field(default_factory=dict)              # release_status, kit_version (phase I)

    def _template(self, h: dict, label: str = "") -> "HitTemplate":
        """A hit spec from a kit file: Amber table reference or literal multiplier."""
        from gtc.forward import data as D

        scaling = h.get("scaling")
        if "table" in h:
            kind, lab, idx = (list(h["table"]) + [0])[:3]
            mult = D.value(self.name, kind, lab, 9, idx) or 0.0
            abil, table, src = f"{lab} ({label})" if label else lab, (kind, lab, idx), "amber"
            if scaling is None:
                # the stat comes from the table row's own text ("3.6% Max HP"), not a per-character default
                tm = D.terms(self.name, kind, lab, 9)
                stats = {s for _, s in tm if s}
                if len(stats) == 1:
                    scaling = next(iter(stats))
                elif len(stats) > 1 and idx < len(tm) and tm[idx][1]:
                    scaling = tm[idx][1]
        else:
            mult, abil, table, src = float(h.get("mult", 0.0)), h.get("abil", label), (), h.get("source", "hand")
        # keyword arguments: a positional call once put the source string into scale_trigger, so every table-linked
        # proc hit was scaled by its trigger's multiplier
        return HitTemplate(offset=float(h.get("offset", 0.0)), abil=h.get("abil", abil), element=h.get("element", ""),
                           damage_type=h.get("type", "skill"), mult=mult, scaling=scaling or "atk", reaction="",
                           ignore_def=bool(h.get("ignore_def", False)), gauge=float(h.get("gauge", 0.0)), table=table,
                           icd=h.get("icd", ""), add_mult=h.get("add_mult"), scale_trigger=bool(h.get("scale_trigger", False)),
                           source=src)
    fillers: list[list[str]] = field(default_factory=list) # the most common on-field strings (the generator tries each)
    first: str = "skill"                                    # which of Skill / Burst they usually cast first on a turn

    def entry(self, action: str) -> ActionEntry | None:
        return self.actions.get(action)


def _owner_action(hit, actions_by_char: dict[str, list]) -> int | None:
    """Index of the owner's action that produced a hit: the latest action of the matching type (skill hits come
    from the last Skill, burst hits from the last Burst, ...), else the owner's latest action."""
    acts = actions_by_char.get(hit.char) or []
    want = {"skill": ("skill",), "burst": ("burst",), "normal": ("attack",), "charged": ("charge", "aim"),
            "plunge": ("high_plunge", "low_plunge", "plunge")}.get(hit.damage_type)
    best = None
    for i, a in enumerate(acts):
        if a.t > hit.t + 1e-6:
            break
        if want is None or a.action in want:
            best = i
    return best


def measure(rotations: list, name: str) -> Library:
    per: dict[str, list[dict]] = defaultdict(list)       # action -> list of instances {duration, hits, particles}
    fillers: Counter = Counter()
    follows: dict[str, Counter] = defaultdict(Counter)
    firsts: Counter = Counter()
    sources = []
    for rot in rotations:
        sources.append(rot.source)
        acts_all = sorted(rot.actions, key=lambda a: a.t)
        by_char: dict[str, list] = defaultdict(list)
        for a in acts_all:
            by_char[a.char].append(a)
        mine = by_char.get(name, [])
        inst = []
        for a in mine:
            nxt = next((b.t for b in acts_all if b.t > a.t + 1e-6), rot.duration)
            inst.append({"action": a.action or "wait", "t": a.t, "duration": nxt - a.t, "hits": [], "particles": 0.0})
        for h in rot.hits:
            if h.char != name:
                continue
            if h.reaction.startswith("swirl-"):
                i = next((j for j in range(len(mine) - 1, -1, -1) if mine[j].t <= h.t + 1e-6), None)
                if i is not None:
                    inst[i]["hits"].append(HitTemplate(round(h.t - mine[i].t, 3), "swirl", "", "reaction", 0.0, "em", "swirl"))
                continue
            if h.reaction:
                continue  # other reaction damage is decided by the reaction model
            if not h.mult and h.gauge and h.damage_type in ("other", "weapon"):
                # a damage-free application (Xingqiu's orbitals): a status from the latest Skill or Burst, within 30 s
                i = next((j for j in range(len(mine) - 1, -1, -1) if mine[j].action in ("skill", "burst")
                          and mine[j].t <= h.t + 1e-6 and h.t - mine[j].t <= 30.0), None)
            else:
                i = _owner_action(h, {name: mine})
            if i is None:
                continue
            inst[i]["hits"].append(HitTemplate(round(h.t - mine[i].t, 3), h.abil, h.element, h.damage_type, h.mult,
                                               h.scaling, "", h.ignore_def, h.gauge))
        for e in rot.energy:
            if e.get("kind") == "particle" and str(e.get("source", "")).replace(" ", "").lower() == name.replace(" ", "").lower():
                i = next((j for j in range(len(mine) - 1, -1, -1) if mine[j].action == "skill" and mine[j].t <= e["t"]), None)
                if i is not None and e["char"] == name:
                    inst[i]["particles"] += e.get("count", 1.0)
        for x in inst:
            per[x["action"]].append(x)
        for a, b in zip(acts_all, acts_all[1:]):
            if a.char == name:
                follows[a.action][b.action if b.char == name else "swap"] += 1
        prev = None
        for a in acts_all:
            if a.char == name and prev != name and a.action in ("skill", "burst"):
                firsts[a.action] += 1
            prev = a.char
        # filler units: runs of on-field non-Skill / non-Burst actions of this character between other characters' actions
        run: list[str] = []
        for a in acts_all:
            if a.char == name and a.action in FILLER_KINDS:
                run.append(a.action)
            else:
                if len(run) >= 2:
                    fillers[tuple(run)] += 1
                run = []
    actions = {}
    # Normal Attacks are a chain: key each attack by the chain position its hit names ("Normal 2" -> attack#2)
    import re as _re

    chain = defaultdict(list)
    for x in per.pop("attack", []):
        idx = next((int(m.group(1)) for h in x["hits"] for m in [_re.search(r"Normal (\d+)", h.abil)] if m), None)
        chain[f"attack#{idx if idx is not None else 0}"].append(x)
    per.update(chain)
    for act, xs in per.items():
        xs = [x for x in xs if x["duration"] < 10]  # waits for energy or cooldowns are not animation
        if not xs:
            continue
        n = median(len(x["hits"]) for x in xs)
        rep = min(xs, key=lambda x: (abs(len(x["hits"]) - n), x["duration"]))
        actions[act] = ActionEntry(act, round(median(x["duration"] for x in xs), 3), rep["hits"],
                                   round(median(x["particles"] for x in xs), 2), len(xs))
    filler = list(fillers.most_common(1)[0][0]) if fillers else (["attack"] * 3 if "attack#0" in actions else [])
    top = [list(f) for f, _ in fillers.most_common(3)] or ([filler] if filler else [])
    follow = {}
    for act, c in follows.items():
        nxt, k = c.most_common(1)[0]
        if nxt not in ("swap", "wait", "") and k >= 0.6 * sum(c.values()) and act not in FILLER_KINDS:
            follow[act] = nxt
    return Library(name=name, actions=actions, filler=filler, sources=sources, notes=[], follow=follow,
                   fillers=top, first=firsts.most_common(1)[0][0] if firsts else "skill")


def source_lineups(name: str, exclude: list | None = None, n: int = SOURCES_PER_CHAR, role: str | None = None) -> list[list[str]]:
    """Community lineups containing `name` to measure from, highest-DPS first, skipping excluded lineups. role
    "carry": only lineups where `name` deals the largest damage share (their carry actions: attack chains, charged
    attacks, windows); "support": lineups where they deal under 30%."""
    from gtc import gamedata
    from gtc.sim import find_config
    from gtc.synergy import load_database

    from gtc.forward.hidden import lineups as hidden_lineups

    skip = {frozenset(x) for x in (exclude or [])} | hidden_lineups()     # hidden validation teams are never sources
    seen, out = set(), []
    entries = sorted((e for e in load_database().values() if len(e.get("lineup") or []) == 4 and name in e["lineup"]),
                     key=lambda e: -e.get("dps", 0))
    names = gamedata.names()
    for e in entries:
        k = frozenset(e["lineup"])
        if k in skip or k in seen:
            continue
        shares = {m: (d or {}).get("damage_share", 0) for m, d in ((e.get("profile") or {}).get("members") or {}).items()}
        if role == "carry" and shares and max(shares, key=shares.get) != name:
            continue
        if role == "support" and shares.get(name, 0) >= 0.3:
            continue
        seen.add(k)
        if find_config(list(e["lineup"]), names) is None:
            continue
        out.append(list(e["lineup"]))
        if len(out) >= n:
            break
    return out


HAND_DIR = None


def load_hand(name: str, level: int = 9) -> Library | None:
    """A hand-written prerelease kit (knowledge/forward/prerelease/<name>.yaml): actions, hits as Amber table
    references, states, specials, level bonus, and the known / assumed / unknown facts. No gcsim input."""
    import yaml

    from gtc import KNOWLEDGE_DIR
    from gtc.forward import data as D

    path = KNOWLEDGE_DIR / "forward" / "actions" / f"{name}.yaml"
    if not path.exists():
        path = KNOWLEDGE_DIR / "forward" / "prerelease" / f"{name}.yaml"
    if not path.exists():
        return None
    spec = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get(name) or {}
    lib = Library(name=name, actions={}, filler=[], sources=["kit file"], notes=[], follow=dict(spec.get("follow") or {}),
                  fillers=[list(f) for f in spec.get("fillers") or []], first=spec.get("first", "skill"), hand=True,
                  states=spec.get("states") or {}, specials=list(spec.get("specials") or []),
                  level_bonus=spec.get("level_bonus") or {}, action_meta={}, facts=spec.get("facts") or {},
                  resources=spec.get("resources") or {}, rules=list(spec.get("rules") or []),
                  summons=spec.get("summons") or {}, procs=spec.get("procs") or {}, provenance=spec.get("provenance") or {},
                  reaction_procs=spec.get("reaction_procs") or {},
                  status=spec.get("status") or {})
    lib.filler = lib.fillers[0] if lib.fillers else []
    for rp in lib.reaction_procs.values():
        rp["hits_t"] = [lib._template(h) for h in rp.get("hits") or []]
    for act, a in (spec.get("actions") or {}).items():
        hits = [lib._template(h, act) for h in a.get("hits") or []]
        lib.actions[act] = ActionEntry(act, float(a.get("duration", 0.5)), hits, float(a.get("particles", 0.0)), 0)
        lib.action_meta[act] = {k: a[k] for k in ("state", "requires_state", "uses_per_state", "requires_resource",
                                                  "do", "summon", "cd", "energy_cost", "duration_by_resource") if k in a}
    # kit language: rules on measured actions that survive a re-freeze (Fischl's Skill is unavailable while the
    # Burst's Oz is out: unavailable_after {burst: seconds})
    for act, rules in (spec.get("action_rules") or {}).items():
        lib.action_meta.setdefault(act, {}).update(rules)
    for sname, s in lib.summons.items():
        s["hits"] = [lib._template(h, sname) for h in s.get("hits") or []]
    for pname, p in lib.procs.items():
        p["hits"] = [lib._template(h, pname) for h in p.get("hits") or []]
        if p.get("hits_cycle"):
            p["hits_cycle_t"] = [[lib._template(h, pname) for h in group] for group in p["hits_cycle"]]
    _fill_normal_chain(lib, name)
    # a multi-stat table row (ATK + EM) listed as one hit gets its other terms; a kit that lists each term as its
    # own hit (Nahida's Tri-Karma: index 0 and 1) does not, so nothing is counted twice
    groups = [e.hits for e in lib.actions.values()] + [s.get("hits") or [] for s in lib.summons.values()] +         [p.get("hits") or [] for p in lib.procs.values()] +         [g for p in lib.procs.values() for g in (p.get("hits_cycle_t") or [])]
    for hs in groups:
        rows = {}
        for h in hs:
            if h.table:
                rows.setdefault(tuple(h.table[:2]), set()).add(h.table[2] if len(h.table) > 2 else 0)
        for h in hs:
            if h.table and len(rows.get(tuple(h.table[:2]), ())) == 1:
                tm = D.terms(name, h.table[0], h.table[1], 9)
                h.expand = len({s for _, s in tm if s}) > 1
    return lib


def _fill_normal_chain(lib, name: str) -> None:
    """Every position of the Normal Attack string exists: a position the source rotations never played (Raiden's N3
    and N4) or measured without hits is built from the Amber "N-Hit DMG" row (one hit per value), with the element,
    gauge, ICD and timing of the nearest measured attack. A string that cycles past it is otherwise cut short."""
    import re as _re
    from dataclasses import replace as _replace

    from gtc.forward import data as D

    rows = {int(m.group(1)): k for k in D.table(name, "normal") if (m := _re.match(r"^(\d+)-Hit DMG", k))}
    if not rows:
        return
    measured = {k: e for k, e in lib.actions.items() if _re.fullmatch(r"attack#\d+", k) and e.hits}
    if not measured:
        return
    for pos in sorted(rows):
        key = f"attack#{pos - 1}"
        if key in measured:
            continue
        near = min(measured, key=lambda k: abs(int(k.split("#")[1]) - (pos - 1)))
        proto = measured[near].hits[0]
        vals = D.table(name, "normal")[rows[pos]]
        hits = [_replace(proto, offset=proto.offset + 0.1 * i, table=("normal", rows[pos], i), mult=v,
                         abil=f"{rows[pos]} (attack#{pos - 1})", source="amber (filled chain position)")
                for i, v in enumerate(vals)]
        old = lib.actions.get(key)
        dur = old.duration if old else measured[near].duration
        lib.actions[key] = ActionEntry(key, dur, hits, old.particles if old else 0.0, 0)
        lib.action_meta.setdefault(key, {})


def build(name: str, exclude: list | None = None, role: str | None = None, measured: bool = False) -> Library:
    """The character's action library: their kit file when one exists (no gcsim), else measured from other teams'
    simulations. measured=True forces measurement (used only by kitfreeze to write kit files)."""
    from gtc.forward.trace import house_trace

    hand = None if measured else load_hand(name)
    if hand is not None:   # a kit file is never re-measured from simulations
        return hand

    rots = []
    lineups = source_lineups(name, exclude, role=role) or source_lineups(name, exclude)
    failed = []
    known_bad = _failed_sources()
    for lu in lineups:
        key = " / ".join(sorted(lu))
        if key in known_bad:
            failed.append(f"source {key} skipped: failed before ({known_bad[key]})")
            continue
        try:
            tr = house_trace(lu)
        except Exception as e:  # a source gcsim cannot run (timeout, unsupported script) is skipped, listed, and
            failed.append(f"source {key} skipped: {type(e).__name__}")     # recorded so it is never retried
            _record_failed(key, type(e).__name__)
            continue
        if tr:
            rots.append(tr[0])
    lib = measure(rots, name)
    lib.notes += failed + check(lib)
    return lib


FAILED_PATH = ROOT / "data" / "forward" / "failed_sources.json"


def _failed_sources() -> dict:
    try:
        return json.loads(FAILED_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _record_failed(key: str, why: str) -> None:
    d = _failed_sources()
    d[key] = why
    FAILED_PATH.parent.mkdir(parents=True, exist_ok=True)
    FAILED_PATH.write_text(json.dumps(d, indent=1), encoding="utf-8")


def check(lib: Library) -> list[str]:
    """Compare measured multipliers with the Amber tables: a multiplier that matches no table value is listed."""
    from gtc.forward import data as D

    values = set()
    for kind in ("normal", "skill", "burst"):
        for vals in D.table(lib.name, kind).values():
            values |= {round(v, 4) for v in vals}
    out = []
    for e in lib.actions.values():
        for h in e.hits:
            if h.mult and round(h.mult, 4) not in values:
                out.append(f"{e.action}: {h.abil} multiplier {h.mult:.4f} is not a level-9 table value")
    return sorted(set(out))


def save(lib: Library, tag: str = "") -> None:
    LIB_DIR.mkdir(parents=True, exist_ok=True)
    p = LIB_DIR / f"{lib.name.replace(' ', '_')}{('.' + tag) if tag else ''}.json"
    p.write_text(json.dumps(asdict(lib), indent=1), encoding="utf-8")
