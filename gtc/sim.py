"""Personal simulations: rerun a community gcsim config with YOUR characters' real builds.

How it works
  1. Find a gcsim database entry with exactly your four characters. Its rotation script is reused.
  2. Rewrite each character's build lines (level, constellation, talents, weapon, sets, stats)
     with the values from your snapshot.
  3. Run gcsim locally. Then run variants, one change at a time (a talent level, a weapon swap,
     standard artifacts), to measure what each change is worth for this team.

Limits
  Only lineups someone has simulated can be run, because a rotation is needed. Weapons or sets
  gcsim does not know are left as in the original config and reported.
"""
from __future__ import annotations

from gtc import params

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from gtc import KNOWLEDGE_DIR, ROOT
from gtc.snapshot import Character
from gtc.sources.gcsim_db import RAW_PATH
from gtc.sources.names import norm
from gtc.stats import to_gcsim

GCSIM = ROOT / "data" / "tools" / "gcsim.exe"
GCSIM_VERSION = "v2.48.8"
GCSIM_URL = f"https://github.com/genshinsim/gcsim/releases/download/{GCSIM_VERSION}/gcsim_windows_amd64.exe"
SIM_DIR = ROOT / "data" / "sims"
KEYS_PATH = KNOWLEDGE_DIR / "generated" / "gcsim_keys.json"
LEVEL_CAPS = [20, 40, 50, 60, 70, 80, 90]
ITERATIONS = params.get("sim.iterations")


def ensure_binary() -> Path:
    if not GCSIM.exists():
        import urllib.request

        GCSIM.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(GCSIM_URL, GCSIM)
    return GCSIM


class Keys:
    """gcsim's accepted names for characters, weapons and sets."""

    def __init__(self):
        data = json.loads(KEYS_PATH.read_text(encoding="utf-8"))
        self.weapons = {k for k, _ in data["weapon"]}
        self.sets = {k for k, _ in data["artifact"]}
        self.chars = {k for k, _ in data["character"]}
        self.char_canonical = {alias: canon for alias, canon in data["character"]}  # "chev" -> "Chevreuse"

    def weapon(self, name: str) -> str | None:
        k = norm(name)
        return k if k in self.weapons else None

    def artifact_set(self, name: str) -> str | None:
        k = norm(name)
        return k if k in self.sets else None


def _cap(level: int) -> int:
    """Assume the character or weapon is ascended at its level, the usual case."""
    if level >= 90:
        return level
    return next(c for c in LEVEL_CAPS if c > level or (c == level and c == 90))


@dataclass
class Build:
    """Everything gcsim needs about one character. Starts from the snapshot, variants edit it."""
    level: int
    cons: int
    talents: tuple[int, int, int]
    weapon: str  # display name
    refine: int
    weapon_level: int
    sets: dict[str, int]
    stats: dict[str, float]  # GOOD keys, artifact main stats plus substats
    standard_lines: list[str] | None = None  # use the config's original artifact lines instead
    weapon_ascension: int | None = None  # from the snapshot when known (HoYoLAB reports it); sets the level cap

    @classmethod
    def from_character(cls, c: Character) -> "Build":
        stats: dict[str, float] = {}
        for a in c.artifacts:
            stats[a.main_stat] = stats.get(a.main_stat, 0) + a.main_value
            for s in a.substats:
                stats[s["key"]] = stats.get(s["key"], 0) + s["value"]
        t = c.talents
        return cls(c.level, c.constellation, (t.normal, t.skill, t.burst), c.weapon.name, c.weapon.refinement,
                   c.weapon.level, c.active_sets(), stats, weapon_ascension=c.weapon.ascension)


@dataclass
class Config:
    text: str
    entry_id: str
    db_dps: float
    char_keys: dict[str, str]  # display name to the key used in this config


_RAW_CONFIGS: dict[str, dict] | None = None


def _raw_entries() -> dict[str, dict]:
    global _RAW_CONFIGS
    if _RAW_CONFIGS is None:
        _RAW_CONFIGS = {e["_id"]: e for e in json.loads(RAW_PATH.read_text(encoding="utf-8"))} if RAW_PATH.exists() else {}
    return _RAW_CONFIGS


def find_config(lineup: list[str], names) -> Config | None:
    """The community config for exactly these four characters: accepted, single target,
    standard gear when available, then the highest DPS."""
    from gtc.sources import gcsim_db

    want = frozenset(lineup)
    candidates = [t for t in gcsim_db.load() if t.names == want and t.targets == 1 and t.accepted]
    if not candidates:
        return None
    best = max(candidates, key=lambda t: (gcsim_db.is_standard(t), t.dps))
    e = _raw_entries().get(best.id)
    if not e:
        return None
    keys = {}
    canonical = Keys().char_canonical
    for line in e["config"].splitlines():
        m = re.match(r"\s*([a-z0-9]+)\s+char\s", line)
        if m:
            alias = m.group(1)
            display = names.character(alias) or names.character(canonical.get(alias, ""))
            if display:
                keys[display] = alias
    return Config(e["config"], e["_id"], best.dps, keys)


def _build_lines(key: str, b: Build, keys: Keys, original: list[str], problems: list[str]) -> list[str]:
    lines = [f"{key} char lvl={b.level}/{_cap(b.level)} cons={b.cons} talent={b.talents[0]},{b.talents[1]},{b.talents[2]};"]
    wkey = keys.weapon(b.weapon)
    orig_weapon = next((l for l in original if re.search(r"\badd\s+weapon=", l)), None)
    if wkey:
        extra = ""
        if orig_weapon and f'"{wkey}"' in orig_weapon:  # keep weapon-specific options such as stacks
            extra = " ".join(re.findall(r"\b(?!refine|lvl)\w+=[^\s;]+", orig_weapon.split('"', 2)[2]))
        # The weapon's real cap when its ascension is known; otherwise assume it is ascended at a breakpoint.
        wcap = LEVEL_CAPS[min(b.weapon_ascension, 6)] if b.weapon_ascension is not None else _cap(b.weapon_level)
        wcap = max(wcap, b.weapon_level)
        lines.append(f'{key} add weapon="{wkey}" refine={b.refine} lvl={b.weapon_level}/{wcap} {extra};'.replace(" ;", ";"))
    elif orig_weapon:
        problems.append(f"gcsim does not know {b.weapon}; kept the config's weapon for {key}")
        lines.append(orig_weapon.strip())
    if b.standard_lines is not None:
        return lines + b.standard_lines
    for set_name, count in b.sets.items():
        skey = keys.artifact_set(set_name)
        if skey:
            lines.append(f'{key} add set="{skey}" count={count};')
        else:
            problems.append(f"gcsim does not know the set {set_name}")
    parts = [f"{gk}={v:g}" for k, val in sorted(b.stats.items()) if (conv := to_gcsim(k, val)) for gk, v in [conv]]
    if parts:
        lines.append(f"{key} add stats {' '.join(parts)};")
    return lines


def render(config: Config, builds: dict[str, Build], keys: Keys, iterations: int = ITERATIONS) -> tuple[str, list[str]]:
    """Replace each character's build block in the config with lines from `builds`."""
    problems: list[str] = []
    out, done = [], set()
    by_key = {v: k for k, v in config.char_keys.items()}
    original: dict[str, list[str]] = {}
    for line in config.text.splitlines():
        m = re.match(r"\s*([a-z0-9]+)\s+(char|add\s+(?:weapon|set|stats))\b", line)
        if m and m.group(1) in by_key:
            original.setdefault(m.group(1), []).append(line)
    for line in config.text.splitlines():
        m = re.match(r"\s*([a-z0-9]+)\s+(char|add\s+(?:weapon|set|stats))\b", line)
        if m and m.group(1) in by_key:
            key = m.group(1)
            if key not in done:
                done.add(key)
                name = by_key[key]
                out += _build_lines(key, builds[name], keys, original[key], problems) if name in builds else original[key]
            continue
        out.append(line)
    text = "\n".join(out)
    text = re.sub(r"iteration=\d+", f"iteration={iterations}", text)
    return text, problems


@dataclass
class SimResult:
    dps: float
    character_dps: dict[str, float] = field(default_factory=dict)
    failed_actions: dict[str, dict] = field(default_factory=dict)
    warnings: dict = field(default_factory=dict)
    error: str | None = None
    raw_path: Path | None = None  # full gcsim JSON output, for the theorycraft profile
    dps_se: float = 0.0  # standard error of the mean DPS over gcsim's iterations (evidence tier A)
    bursts: dict[str, float] = field(default_factory=dict)  # mean bursts per run, by gcsim character key


def run(text: str) -> SimResult:
    """Run gcsim on a config, cached by content so repeated reviews are instant."""
    ensure_binary()
    SIM_DIR.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha1(text.encode()).hexdigest()[:16]
    cfg, out = SIM_DIR / f"{h}.txt", SIM_DIR / f"{h}.json"
    if not out.exists():
        cfg.write_text(text, encoding="utf-8")
        proc = subprocess.run([str(GCSIM), "-c", str(cfg), "-out", str(out)], capture_output=True, text=True, timeout=300)
        if proc.returncode != 0 or not out.exists():
            return SimResult(0.0, error=(proc.stdout + proc.stderr).strip()[-500:])
    d = json.loads(out.read_text(encoding="utf-8"))
    st = d["statistics"]
    chars = [c["name"] for c in d.get("character_details", [])]
    char_dps = {chars[i]: v["mean"] for i, v in enumerate(st.get("character_dps") or []) if i < len(chars)}
    failed = {chars[i]: v for i, v in enumerate(st.get("failed_actions") or []) if i < len(chars)}
    bursts = {}
    for i, v in enumerate(st.get("character_actions") or []):
        if i < len(chars):
            bursts[chars[i]] = ((v or {}).get("sources", {}).get("burst") or {}).get("mean", 0.0)
    iters = st.get("iterations") or ITERATIONS
    se = (st["dps"].get("sd") or 0.0) / max(iters, 1) ** 0.5
    return SimResult(st["dps"]["mean"], char_dps, failed, st.get("warnings") or {}, raw_path=out, dps_se=se, bursts=bursts)


def _split_top(text: str, sep: str) -> list[str]:
    """Split on `sep` outside brackets."""
    out, depth, cur = [], 0, []
    for ch in text:
        if ch in "[(":
            depth += 1
        elif ch in "])":
            depth -= 1
        if ch == sep and depth == 0:
            out.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    out.append("".join(cur))
    return out


WAIT_FRAMES = params.get("sim.burst_wait_frames")


def guard_bursts(text: str, char_keys) -> str:
    """Rewrite rotation statements so a Burst that is not ready is waited for briefly (WAIT_FRAMES, as a player
    would) and then skipped instead of stalling the rotation: `xq burst;` becomes a bounded wait followed by
    `if .xq.burst.ready { xq burst; }`, and `ayaka skill, burst, attack;` becomes
    `ayaka skill; if .ayaka.burst.ready { ayaka burst; } ayaka attack;`. Character, weapon and set lines,
    options and targets are left alone. Used for the reality mode: no Energy Recharge top-up, and the cost of
    the shortfall is the damage and the bursts lost."""
    keys = set(char_keys)
    counter = [0]
    out = []
    for line in text.splitlines():
        code, hash_, comment = line.partition("#")
        stmts = code.split(";")
        rebuilt = []
        changed = False
        for st in stmts[:-1]:  # the last piece follows the final ';' (usually empty)
            m = re.match(r"^(\s*)([a-z0-9_]+)\s+(.*\S)\s*$", st)
            if not m or m.group(2) not in keys or re.match(r"(char|add)\b", m.group(3)):
                rebuilt.append(st + ";")
                continue
            indent, c, rest = m.groups()
            actions = [a.strip() for a in _split_top(rest, ",")]
            if not any(re.match(r"burst\b", a) for a in actions):
                rebuilt.append(st + ";")
                continue
            changed = True
            pieces, buf = [], []
            for a in actions:
                if re.match(r"burst\b", a):
                    if buf:
                        pieces.append(f"{c} {', '.join(buf)};")
                        buf = []
                    counter[0] += 1
                    v = f"_bw{counter[0]}"
                    # Wait up to WAIT_FRAMES for the Burst, as gcsim would, then skip it rather than stall.
                    pieces.append(f"let {v} = 0; while !.{c}.burst.ready && {v} < {WAIT_FRAMES} {{ wait(6); {v} = {v} + 6; }} "
                                  f"if .{c}.burst.ready {{ {c} {a}; }}")
                else:
                    buf.append(a)
            if buf:
                pieces.append(f"{c} {', '.join(buf)};")
            rebuilt.append(indent + " ".join(pieces))
        if not changed:
            out.append(line)
            continue
        out.append("".join(rebuilt) + stmts[-1] + (hash_ + comment if hash_ else ""))
    return chr(10).join(out) + (chr(10) if text.endswith(chr(10)) else "")


@dataclass
class Variant:
    label: str
    kind: str  # talent, level, weapon, artifacts
    character: str
    dps: float = 0.0
    gain: float = 0.0  # fraction of team DPS
    error: str | None = None
    gain_sd: float = 0.0  # from both runs' standard errors; iteration noise only, not rotation differences


class TeamSim:
    """Your team as gcsim sees it, plus what-if variants."""

    def __init__(self, lineup: list[str], chars: dict[str, Character], names):
        self.lineup = lineup
        self.names = names
        self.config = find_config(lineup, names)
        self.keys = Keys() if self.config else None
        self.builds = {n: Build.from_character(chars[n]) for n in lineup if n in chars}
        import copy

        self.original_builds = copy.deepcopy(self.builds)  # before any Energy Recharge top-up
        self.real: SimResult | None = None
        self.problems: list[str] = []
        self.base: SimResult | None = None
        self.raw: SimResult | None = None  # first run, before any Energy Recharge top-up
        self.er_deficit: dict[str, float] = {}  # ER% added so the rotation stops stalling
        self.by_key = {v: k for k, v in self.config.char_keys.items()} if self.config else {}

    def _name(self, key: str) -> str | None:
        """gcsim results use full keys ('kamisatoayaka') even when the config used a shortcut ('ayaka')."""
        return self.by_key.get(key) or self.names.character(key)

    @property
    def available(self) -> bool:
        return self.config is not None

    def _run(self, builds: dict[str, Build]) -> SimResult:
        text, problems = render(self.config, builds, self.keys)
        self.problems = sorted(set(self.problems + problems))
        return run(text)

    def stall(self, r: SimResult) -> dict[str, float]:
        """Seconds each character spent waiting for energy, by display name."""
        out = {}
        for key, f in (r.failed_actions or {}).items():
            name = self._name(key)
            waited = (f.get("insufficient_energy") or {}).get("mean", 0) if isinstance(f, dict) else 0
            if name:
                out[name] = waited
        return out

    def baseline(self, max_steps: int = 12, step: float = 10.0, tolerance: float = 3.0) -> SimResult:
        """Your build as it is, except that characters who cannot afford their Burst on this rotation get
        Energy Recharge added in 10% steps until they can. gcsim waits for a Burst instead of skipping it,
        so without this one under-geared support stalls the whole team. The added ER is reported."""
        if self.base is None:
            self.raw = r = self._run(self.builds)
            for _ in range(max_steps):
                stalled = [n for n, sec in self.stall(r).items() if sec > tolerance]
                if not stalled:
                    break
                for n in stalled:
                    self.builds[n].stats["enerRech_"] = self.builds[n].stats.get("enerRech_", 0) + step
                    self.er_deficit[n] = self.er_deficit.get(n, 0) + step
                r = self._run(self.builds)
            self.base = r
        return self.base

    def reality(self) -> SimResult:
        """Your builds with no Energy Recharge top-up, on a rotation that skips a Burst that is not ready.
        Compared with the potential run (baseline), the gap is what the Energy Recharge shortfall costs."""
        if self.real is None:
            text, problems = render(self.config, self.original_builds, self.keys)
            self.real = run(guard_bursts(text, self.config.char_keys.values()))
        return self.real

    def er_cost(self) -> dict | None:
        """Damage and bursts lost to the Energy Recharge shortfall: potential (topped up) against reality."""
        base = self.baseline()
        if not self.er_deficit:
            return None
        real = self.reality()
        if real.error or not base.dps:
            return None
        skipped = {}
        for key, n in base.bursts.items():
            lost = n - real.bursts.get(key, 0.0)
            name = self._name(key)
            if name and lost >= 0.5:
                skipped[name] = (lost, n)
        return {"potential": base.dps, "reality": real.dps, "stalled": self.raw.dps if self.raw else None,
                "loss": 1 - real.dps / base.dps, "skipped": skipped}

    def character_dps(self, r: SimResult) -> dict[str, float]:
        return {self._name(k) or k: v for k, v in r.character_dps.items()}

    def standard_lines(self, name: str) -> list[str]:
        key = self.config.char_keys.get(name)
        if key is None:
            return []
        return [l.strip() for l in self.config.text.splitlines()
                if re.match(rf"\s*{key}\s+add\s+(set|stats)\b", l)]

    def variant(self, label: str, kind: str, name: str, change) -> Variant:
        import copy

        builds = copy.deepcopy(self.builds)
        change(builds[name])
        r = self._run(builds)
        base = self.baseline()
        v = Variant(label, kind, name, r.dps, error=r.error)
        if not r.error and base.dps:
            v.gain = r.dps / base.dps - 1
            v.gain_sd = (r.dps / base.dps) * ((r.dps_se / r.dps) ** 2 + (base.dps_se / base.dps) ** 2) ** 0.5 if r.dps else 0.0
        return v


def plan_variants(ts: TeamSim, chars: dict[str, Character], weapons, weapon_types: dict[str, dict],
                  game: dict[str, dict], talent_order: dict[str, list[str]]) -> list[Variant]:
    """Every single change worth measuring for this team, run on top of the baseline."""
    out: list[Variant] = []
    slot_index = {"normal": 0, "skill": 1, "burst": 2}
    team_holders = set(ts.lineup)
    for name in ts.lineup:
        c, b = chars[name], ts.builds[name]

        def set_talent(i, level):
            def f(x):
                t = list(x.talents)
                t[i] = level
                x.talents = tuple(t)
            return f

        order = [t for t in talent_order.get(name, []) if t in slot_index] or ["burst", "skill"]
        for t in order[:2]:
            i = slot_index[t]
            cur = b.talents[i]
            for target in sorted({min(cur + 1, 10), 9 if cur < 9 else min(cur + 1, 10)}):
                if target > cur:
                    out.append(ts.variant(f"{name} {t} talent {cur} to {target}", "talent", name, set_talent(i, target)))

        if c.level < 90:
            def lvl90(x):
                x.level = 90
            out.append(ts.variant(f"{name} level {c.level} to 90", "level", name, lvl90))

        std = ts.standard_lines(name)
        if std:
            def standard(x, lines=std):
                x.standard_lines = lines
            out.append(ts.variant(f"{name} with community-standard artifacts", "artifacts", name, standard))

        wtype = game.get(name, {}).get("weapon")
        for w in weapons:
            if w.name == c.weapon.name or weapon_types.get(w.name, {}).get("type") != wtype:
                continue
            if w.location in team_holders and w.location != name:
                continue  # already used by a teammate in this same team
            def swap(x, w=w):
                x.weapon, x.refine, x.weapon_level = w.name, w.refinement, w.level
            holder = f", taken from {w.location}" if w.location else ", from inventory"
            out.append(ts.variant(f"{name} uses R{w.refinement} {w.name} (level {w.level}{holder})", "weapon", name, swap))
    return out
