"""Realistic standard builds (phase G): equally reasonable investment, not equal stats.

META_STANDARD (this module) gives every character:
    level 90, C0, talents 9/9/9;
    an accessible weapon (4-star / craftable / battle pass / a standard 3-star, at stated refinements: craftable and
    event weapons R5, gacha 4-stars R3, battle-pass weapons R1), with its passive (gtc/forward/gear.py);
    a 4-piece artifact set or a 2+2 combination, with set effects;
    main stats chosen for the kit (sands: scaling stat / ER / EM; goblet: element / scaling stat / EM; circlet: CRIT
    Rate / CRIT DMG / scaling stat / EM / Healing);
    a standardised substat budget (KQM-style): 2 fixed rolls of every substat (20) plus 20 distributable rolls, at
    most 10 in one substat and 2 fewer for each main-stat piece of that stat, CRIT Rate capped at 100%.
Energy Recharge is paid for out of the same budget: distributable rolls go to ER first until the member meets the ER
its rotation needs (requirement x 1.1, the KQM convention), then the rest are spent where team DPS gains most.

Choices are made by the forward model itself: coordinate descent over weapon, set, main stats and the substat split,
maximising team DPS on the generated rotation, subject to every member's ER target. Nothing is hand-picked per
character; a support whose buff scales with EM ends up on EM because the team gains from it.

The old neutral profile (Favonius, no sets, fixed substats, ER added on top) stays as `build.meta_standard` for
regression and calculator (replay) checks.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

from gtc.forward import data as D
from gtc.forward.build import Build, _damage_element, _game, _merge, scaling_stat, weapon_type

# accessible pool per weapon type: (weapon, refinement)
POOL = {
    "sword": [("Favonius Sword", 3), ("Sacrificial Sword", 3), ("Prototype Rancour", 5), ("Amenoma Kageuchi", 5),
              ("Iron Sting", 5), ("Festering Desire", 5), ("Wolf-Fang", 3), ("Fleuve Cendre Ferryman", 5),
              ("Sapwood Blade", 5), ("Lion's Roar", 3), ("The Black Sword", 1), ("Harbinger of Dawn", 5)],
    "claymore": [("Favonius Greatsword", 3), ("Sacrificial Greatsword", 3), ("Prototype Archaic", 5),
                 ("Katsuragikiri Nagamasa", 5), ("Forest Regalia", 5), ("Mailed Flower", 5), ("Akuoumaru", 3),
                 ("Rainslasher", 3), ("Serpent Spine", 1), ("Whiteblind", 5), ("Makhaira Aquamarine", 3)],
    "polearm": [("Favonius Lance", 3), ('"The Catch"', 5), ("Kitain Cross Spear", 5), ("Missive Windspear", 5),
                ("Prototype Starglitter", 5), ("Deathmatch", 1), ("Dragon's Bane", 3), ("Wavebreaker's Fin", 3),
                ("Moonpiercer", 5), ("Ballad of the Fjords", 5)],
    "catalyst": [("Favonius Codex", 3), ("Sacrificial Fragments", 3), ("The Widsith", 3), ("Prototype Amber", 5),
                 ("Hakushin Ring", 5), ("Thrilling Tales of Dragon Slayers", 5), ("Mappa Mare", 3), ("Oathsworn Eye", 3),
                 ("Solar Pearl", 1), ("Wandering Evenstar", 3), ("Sacrificial Jade", 3), ("Flowing Purity", 5)],
    "bow": [("Favonius Warbow", 3), ("Sacrificial Bow", 3), ("The Stringless", 3), ("Prototype Crescent", 5),
            ("Hamayumi", 5), ("King's Squire", 5), ("Fading Twilight", 5), ("Mouun's Moon", 3), ("Rust", 3),
            ("The Viridescent Hunt", 1), ("Mitternachts Waltz", 3), ("Windblume Ode", 3)],
}
SETS_4PC = ["Noblesse Oblige", "Emblem of Severed Fate", "Viridescent Venerer", "Deepwood Memories", "Instructor",
            "Gilded Dreams", "Crimson Witch of Flames", "Thundering Fury", "Blizzard Strayer", "Heart of Depth",
            "Shimenawa's Reminiscence", "Gladiator's Finale", "Wanderer's Troupe", "Tenacity of the Millelith",
            "Golden Troupe", "Flower of Paradise Lost", "Nymph's Dream", "Marechaussee Hunter", "Silken Moon's Serenade",
            "Night of the Sky's Unveiling", "Aubade of Morningstar and Moon", "Vermillion Hereafter",
            "Echoes of an Offering", "Desert Pavilion Chronicle", "Pale Flame", "Ocean-Hued Clam",
            "Scroll of the Hero of Cinder City", "Vourukasha's Glow", "Finale of the Deep Galleries",
            "Song of Days Past", "Unfinished Reverie", "Fragment of Harmonic Whimsy"]
ELEMENT_SET = {"Pyro": "Crimson Witch of Flames", "Hydro": "Heart of Depth", "Electro": "Thundering Fury",
               "Cryo": "Blizzard Strayer", "Anemo": "Viridescent Venerer", "Geo": "Archaic Petra",
               "Dendro": "Deepwood Memories", "Physical": "Pale Flame"}
ATK_2PC = ("Gladiator's Finale", "Shimenawa's Reminiscence")

MAIN = {"atk_pct": 0.466, "hp_pct": 0.466, "def_pct": 0.583, "er": 0.518, "em": 187.0, "element": 0.466,
        "Physical": 0.583, "cr": 0.311, "cd": 0.622, "heal": 0.359}
ROLL = {"atk_pct": 0.0496, "hp_pct": 0.0496, "def_pct": 0.062, "em": 19.82, "er": 0.0551, "cr": 0.0331, "cd": 0.0662,
        "atk": 16.54, "hp": 253.94, "def": 19.68}
FIXED_ROLLS = 2
DISTRIBUTABLE = 20
MAX_PER_SUB = 10
ER_CAP = 2.6
SCALE_PCT = {"atk": "atk_pct", "hp": "hp_pct", "def": "def_pct", "em": "em"}
ASSUMPTIONS = ["META_STANDARD (realistic): level 90, C0, talents 9/9/9; accessible weapons (craftable/event R5, gacha "
               "4-stars R3, battle pass R1) with passives; artifact sets with set effects; main stats and a KQM-style "
               "substat budget (20 fixed + 20 distributable rolls) chosen by the forward model for team DPS",
               "Energy Recharge paid from the substat budget to reach 1.1 x the rotation's requirement",
               "enemy level 100, 10% RES, single target"]


@dataclass
class Choice:
    weapon: str
    refine: int
    sets: dict[str, int]
    sands: str
    goblet: str
    circlet: str
    subs: dict[str, int] = field(default_factory=dict)   # distributable rolls per substat

    def key(self) -> tuple:
        return (self.weapon, self.refine, tuple(sorted(self.sets.items())), self.sands, self.goblet, self.circlet,
                tuple(sorted(self.subs.items())))


def _element(name: str) -> str:
    el = _damage_element(name)
    return "Physical" if el == "Physical" else (_game(name).get("element") or "Physical")


def _scalings(name: str) -> list[str]:
    """Every stat the kit scales with (damage, buffs, conversions), as main/sub stat keys: the optimiser decides."""
    from gtc.kits import kit

    out = [SCALE_PCT[scaling_stat(name)]]
    for sc in (kit(name) or {}).get("scaling") or []:
        k = SCALE_PCT.get(sc.get("stat"))
        if k:
            out.append(k)
    return list(dict.fromkeys(out + ["atk_pct", "hp_pct"]))


def main_options(name: str) -> dict[str, list[str]]:
    sc = _scalings(name)
    sands = list(dict.fromkeys(sc + ["er", "em"]))
    goblet = list(dict.fromkeys(["element"] + sc + ["em"]))
    circlet = list(dict.fromkeys(["cr", "cd"] + sc + ["em", "heal"]))
    return {"sands": sands, "goblet": goblet, "circlet": circlet}


def set_options(name: str) -> list[dict[str, int]]:
    el = _element(name)
    out = [{s: 4} for s in SETS_4PC]
    es = ELEMENT_SET.get(el)
    out += [{ATK_2PC[0]: 2, ATK_2PC[1]: 2}, {"Gilded Dreams": 2, "Wanderer's Troupe": 2},
            {"Tenacity of the Millelith": 2, "Vourukasha's Glow": 2}, {"Emblem of Severed Fate": 2, "Noblesse Oblige": 2}]
    if es:
        out += [{es: 2, ATK_2PC[0]: 2}, {es: 2, "Emblem of Severed Fate": 2}, {es: 2, "Gilded Dreams": 2}]
    return out


def default_choice(name: str) -> Choice:
    w, r = POOL[weapon_type(name)][0]
    sc = SCALE_PCT[scaling_stat(name)]
    if sc == "em":
        return Choice(w, r, {"Gilded Dreams": 2, "Wanderer's Troupe": 2}, "em", "em", "em", {})
    return Choice(w, r, {ATK_2PC[0]: 2, ATK_2PC[1]: 2}, sc, "element", "cr", {})


def _cap(choice: Choice, sub: str) -> int:
    mains = [choice.sands, choice.goblet, choice.circlet]
    return max(0, MAX_PER_SUB - 2 * sum(1 for m in mains if m == sub))


def artifacts(name: str, choice: Choice) -> dict[str, float]:
    """Artifact stats (mains + fixed and distributable substats): what gcsim gets as `add stats`."""
    el = _element(name)
    arts: dict[str, float] = {"hp": 4780.0, "atk": 311.0}
    for slot in (choice.sands, choice.goblet, choice.circlet):
        if slot == "element":
            arts[el] = arts.get(el, 0.0) + (MAIN["Physical"] if el == "Physical" else MAIN["element"])
        else:
            arts[slot] = arts.get(slot, 0.0) + MAIN[slot]
    for sub, v in ROLL.items():
        arts[sub] = arts.get(sub, 0.0) + FIXED_ROLLS * v
    for sub, n in choice.subs.items():
        arts[sub] = arts.get(sub, 0.0) + n * ROLL[sub]
    return arts


def make_build(name: str, choice: Choice) -> Build:
    from gtc.forward.gear import static_stats

    gear = {"weapon": choice.weapon, "refine": choice.refine, "sets": dict(choice.sets)}
    arts = artifacts(name, choice)
    stats = _merge(D.character_stats(name, 90), D.weapon_stats(choice.weapon, 90), arts, static_stats(gear))
    unmodelled = [f"{choice.weapon} R{choice.refine} and {', '.join(f'{s} {n}pc' for s, n in choice.sets.items())}: "
                  "effects the compiler could not read are listed with the evaluation's unknowns"]
    b = Build(name, "META_STANDARD", 90, 0, {"normal": 9, "skill": 9, "burst": 9}, choice.weapon, stats, unmodelled,
              arts, gear)
    b.choice = choice
    return b


def fit_er(name: str, choice: Choice, target: float | None) -> Choice | None:
    """The choice with distributable rolls spent on ER first until the build reaches `target` (None: no
    requirement). Returns None when the target cannot be met with this weapon, set and main stats."""
    c = replace(choice, subs={k: v for k, v in choice.subs.items() if k != "er"})
    if not target:
        return c
    target = min(target, ER_CAP)
    have = make_build(name, c).total("er")
    if have >= target:
        return c
    need = -(-(target - have) // ROLL["er"])
    need = int(need)
    if need > min(_cap(c, "er"), DISTRIBUTABLE):
        return None
    # take the rolls from the other substats (largest first)
    spare = DISTRIBUTABLE - need
    subs = dict(c.subs)
    while sum(subs.values()) > spare:
        k = max(subs, key=lambda x: subs[x])
        subs[k] -= 1
        if subs[k] <= 0:
            subs.pop(k)
    subs["er"] = need
    return replace(c, subs=subs)


def _fav_factor(build) -> float:
    """Favonius particles of this wearer relative to the R1 baseline the reference rotation was generated with."""
    from gtc.forward.generator import FAV_CHANCE, FAV_ICD, favonius

    f = favonius(build)
    if f is None:
        return 0.0
    return (f[1] / FAV_CHANCE[0]) * (FAV_ICD[0] / f[0])


WINDOW_BUFFER = 1.05


def er_targets(rot, builds: dict, costs: dict, buffer: float = WINDOW_BUFFER) -> dict[str, float | None]:
    """Each member's ER target for these builds on a rotation generated or traced with every member on Favonius R1
    (a member not wearing Favonius loses their procs' particles for the whole party; a higher refinement adds
    proportionally more). The target is exact for the schedule, not an average: the member's energy is replayed with
    the cap at the Burst cost, every scheduled Burst must find it full, and the lowest ER that keeps the schedule is
    found by bisection (x buffer for particle timing)."""
    import re
    from collections import defaultdict

    keyof = {re.sub(r"[^a-z0-9]", "", m.lower()): m for m in rot.lineup}
    factor = {m: _fav_factor(builds[m]) for m in rot.lineup}
    bursts = defaultdict(list)
    for a in rot.actions:
        if a.action == "burst":
            bursts[a.char].append(a.t)
    out = {}
    for who in rot.lineup:
        times, cost = bursts.get(who, []), costs.get(who)
        if not times or not cost:
            out[who] = None
            continue
        last = times[-1]
        p = f = 0.0
        for e in rot.energy:
            if e["char"] != who or e["t"] > last:
                continue
            src = str(e.get("source") or "")
            w = 1.0
            if src.startswith("favonius-"):
                owner = src[9:]
                owner = owner if owner in rot.lineup else keyof.get(re.sub(r"[^a-z0-9]", "", owner.lower()))
                w = factor.get(owner, 1.0)
            if e["kind"] == "particle":
                p += w * e["amount"] / max(e.get("er") or 1.0, 1e-6)
            elif e["kind"] == "flat":
                f += e["amount"]
        evs = []
        for e in rot.energy:
            if e["char"] != who or e["t"] > last:
                continue
            src = str(e.get("source") or "")
            w = 1.0
            if src.startswith("favonius-"):
                owner = src[9:]
                owner = owner if owner in rot.lineup else keyof.get(re.sub(r"[^a-z0-9]", "", owner.lower()))
                w = factor.get(owner, 1.0)
            if e["kind"] == "particle":
                evs.append((e["t"], "p", w * e["amount"] / max(e.get("er") or 1.0, 1e-6)))
            elif e["kind"] == "flat":
                evs.append((e["t"], "f", e["amount"]))
        evs.sort()

        def keeps(er: float) -> bool:
            energy, i = cost, 0                     # starts full
            for bt in times:
                while i < len(evs) and evs[i][0] <= bt:
                    energy = min(cost, energy + (evs[i][2] * er if evs[i][1] == "p" else evs[i][2]))
                    i += 1
                if energy < cost - 0.5:
                    return False
                energy = 0.0
            return True

        if not p and len(times) > 1 and not f:
            out[who] = None
            continue
        lo, hi = 1.0, 4.0
        if keeps(lo):
            out[who] = buffer * lo if len(times) > 1 else None
            continue
        if not keeps(hi):
            out[who] = hi            # the schedule cannot be kept at any realistic ER
            continue
        for _ in range(24):
            mid = (lo + hi) / 2
            lo, hi = (lo, mid) if keeps(mid) else (mid, hi)
        out[who] = hi * buffer
    return out


def max_er(name: str, choice: Choice) -> Choice:
    """The most Energy Recharge this investment allows: ER sands, a Favonius weapon of the type (R3), every allowed
    roll on ER. Used when no build meets the target: the member still gets as close as the budget allows."""
    fav = next(((w, r) for w, r in POOL[weapon_type(name)] if w.startswith("Favonius")), (choice.weapon, choice.refine))
    c = replace(choice, sands="er", weapon=fav[0], refine=fav[1], subs={})
    return replace(c, subs={"er": min(_cap(c, "er"), DISTRIBUTABLE)})


def feasible(name: str, choice: Choice, target: float | None) -> Choice:
    """fit_er, then with ER sands, then the maximum-ER fallback."""
    return fit_er(name, choice, target) or fit_er(name, replace(choice, sands="er"), target) or max_er(name, choice)


def _fill_subs(name: str, choice: Choice, score, step: int = 2) -> Choice:
    """Spend the distributable rolls left after ER greedily, `step` rolls at a time, where `score` gains most."""
    cands = list(dict.fromkeys(["cr", "cd"] + _scalings(name) + ["em"]))
    c = choice
    while sum(c.subs.values()) < DISTRIBUTABLE:
        left = DISTRIBUTABLE - sum(c.subs.values())
        n = min(step, left)
        best, best_v = None, None
        for sub in cands:
            if c.subs.get(sub, 0) + n > _cap(c, sub):
                continue
            trial = replace(c, subs={**c.subs, sub: c.subs.get(sub, 0) + n})
            if sub == "cr" and make_build(name, trial).total("cr") > 1.0 + 1e-9:
                continue
            v = score(trial)
            if best_v is None or v > best_v:
                best, best_v = trial, v
        if best is None:
            break
        c = best
    return c


def optimise(lineup: list[str], rot, targets: dict[str, float | None] | None, choices: dict | None = None,
             passes: int = 2, pool: dict | None = None, costs: dict | None = None) -> tuple[dict[str, Build], dict]:
    """Coordinate descent over each member's weapon, set, main stats and substats, maximising team DPS on `rot`,
    every member meeting their ER target. With `costs` (and `rot` generated or traced with everyone on Favonius R1),
    targets are recomputed for every candidate (who wears Favonius changes the whole party's particles); otherwise the
    fixed `targets` apply. Returns (builds, report)."""
    from gtc.forward.model import evaluate

    choices = {m: (choices or {}).get(m) or default_choice(m) for m in lineup}
    dynamic = costs is not None
    er_targets_now = dict(targets or {})
    if dynamic:
        er_targets_now = er_targets(rot, {m: make_build(m, choices[m]) for m in lineup}, costs)
    for m in lineup:
        choices[m] = feasible(m, choices[m], er_targets_now.get(m))
    builds = {m: make_build(m, choices[m]) for m in lineup}
    evals = 0

    def team_dps(m, c) -> float:
        nonlocal evals
        evals += 1
        b = dict(builds)
        b[m] = make_build(m, c)
        if dynamic and _fav_factor(b[m]) != _fav_factor(builds[m]):
            # Favonius on or off changes everyone's particles: re-fit the others' ER to the new targets
            tg = er_targets(rot, b, costs)
            for o in lineup:
                if o == m:
                    if tg.get(m) and b[m].total("er") < min(tg[m], ER_CAP) - 1e-9:
                        return -1.0
                    continue
                f = fit_er(o, choices[o], tg.get(o))
                if f is None:
                    if b[o].total("er") + 1e-9 < min(tg.get(o) or 0, ER_CAP) and builds[o].total("er") + 1e-9 >= min(er_targets_now.get(o) or 0, ER_CAP):
                        return -1.0          # this candidate breaks a teammate that was fine
                    continue
                b[o] = make_build(o, f)
        return evaluate(rot, b).dps

    def finish(m, c):
        c = fit_er(m, c, er_targets_now.get(m))
        if c is None:
            return None
        return _fill_subs(m, c, lambda x: team_dps(m, x))

    for _ in range(passes):
        for m in lineup:
            cur = choices[m]
            best_c, best_v = cur, team_dps(m, cur)
            opts = main_options(m)
            # weapon, then set, then each main slot: a cheap screen with the current substats, then refill subs
            for w, r in (pool or POOL)[weapon_type(m)]:
                try:
                    D.weapon_stats(w, 90)
                except KeyError:
                    continue
                c = fit_er(m, replace(best_c, weapon=w, refine=r), er_targets_now.get(m))
                if c is None and dynamic:
                    c = replace(best_c, weapon=w, refine=r)      # Favonius may lower its own target: team_dps checks
                if c is None:
                    continue
                v = team_dps(m, c)
                if v > best_v + 1e-6:
                    best_c, best_v = c, v
            for sets in set_options(m):
                c = fit_er(m, replace(best_c, sets=sets), er_targets_now.get(m))
                if c is None:
                    continue
                v = team_dps(m, c)
                if v > best_v + 1e-6:
                    best_c, best_v = c, v
            for slot in ("sands", "goblet", "circlet"):
                for opt in opts[slot]:
                    # screened with the current substats (ER re-fitted); the greedy substat fill runs once, below
                    c = fit_er(m, replace(best_c, **{slot: opt}), er_targets_now.get(m))
                    if c is None:
                        continue
                    v = team_dps(m, c)
                    if v > best_v + 1e-6:
                        best_c, best_v = c, v
            if dynamic:
                er_targets_now.update(er_targets(rot, {**builds, m: make_build(m, best_c)}, costs))
            c = finish(m, best_c)
            if c is not None and team_dps(m, c) >= best_v - 1e-6:
                best_c = c
            choices[m] = best_c
            builds[m] = make_build(m, best_c)
            if dynamic:
                er_targets_now.update(er_targets(rot, builds, costs))
                for o in lineup:
                    f = fit_er(o, choices[o], er_targets_now.get(o)) or fit_er(o, replace(choices[o], sands="er"), er_targets_now.get(o))
                    if f is not None and f.key() != choices[o].key():
                        if sum(f.subs.values()) < DISTRIBUTABLE:
                            f = _fill_subs(o, f, lambda x: team_dps(o, x))
                        choices[o] = f
                        builds[o] = make_build(o, f)
    report = {m: describe(builds[m]) for m in lineup}
    for m in lineup:
        tg = er_targets_now.get(m)
        report[m]["er_target"] = None if tg is None else round(tg, 3)
        if tg and builds[m].total("er") + 1e-6 < min(tg, ER_CAP):
            report[m]["er_unreachable"] = True     # the rotation asks for more ER than this investment allows
    report["_evaluations"] = evals
    return builds, report


# warm starts (staged optimisation): the last optimised choice per (character, role); a team whose members are all
# cached is re-optimised in one pass from there instead of from scratch
_CACHE: dict[tuple, Choice] = {}
CACHE_FILE = None


def _cache_path():
    from gtc import ROOT

    return ROOT / "data" / "forward" / "build_cache.json"


def cached_choice(name: str, role: str) -> Choice | None:
    global _CACHE
    if not _CACHE:
        import json

        p = _cache_path()
        if p.exists():
            try:
                for k, v in json.loads(p.read_text(encoding="utf-8")).items():
                    n, r = k.split("|", 1)
                    _CACHE[(n, r)] = Choice(v["weapon"], v["refine"], v["sets"], v["sands"], v["goblet"], v["circlet"], v["subs"])
            except (ValueError, KeyError):
                _CACHE = {}
    return _CACHE.get((name, role))


def remember(builds: dict, roles: dict[str, str]) -> None:
    import json

    for m, b in builds.items():
        if getattr(b, "choice", None) is not None:
            _CACHE[(m, roles.get(m, "support"))] = b.choice
    p = _cache_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({f"{n}|{r}": vars(c) for (n, r), c in _CACHE.items()}, indent=0), encoding="utf-8")


def describe(b: Build) -> dict:
    c = b.choice
    return {"weapon": f"{c.weapon} R{c.refine}", "sets": c.sets, "mains": [c.sands, c.goblet, c.circlet],
            "subs": dict(sorted(c.subs.items(), key=lambda kv: -kv[1])), "er": round(b.total("er"), 3),
            "cr": round(b.stats.get("cr", 0), 3), "cd": round(b.stats.get("cd", 0), 3), "em": round(b.stats.get("em", 0)),
            "atk": round(b.total("atk")), "hp": round(b.total("hp"))}


def relax_er(name: str, b: Build) -> Build | None:
    """The build with no ER requirement: damage sands instead of ER sands, ER rolls moved to the substat the build
    already valued most. None when the build spends nothing on ER."""
    c = b.choice
    er_rolls = c.subs.get("er", 0)
    if c.sands != "er" and not er_rolls:
        return None
    subs = {k: v for k, v in c.subs.items() if k != "er"}
    sands = c.sands if c.sands != "er" else main_options(name)["sands"][0]
    f = replace(c, sands=sands, subs=subs)
    top = max(subs, key=subs.get) if subs else "cd"
    left = DISTRIBUTABLE - sum(subs.values())
    cands = [top, "cr", "cd"] + _scalings(name)
    for k in cands:
        if left <= 0:
            break
        room = _cap(f, k) - f.subs.get(k, 0)
        add = min(left, max(0, room))
        if add:
            f = replace(f, subs={**f.subs, k: f.subs.get(k, 0) + add})
            left -= add
    return make_build(name, f)


def refit(builds: dict[str, Build], er_targets: dict[str, float | None]) -> dict[str, Build]:
    """The same weapons, sets and main stats with the ER rolls re-split for another rotation's requirement (the
    reveal runs the community rotation with the blind builds' investment policy). A target the build cannot meet is
    met as far as the budget allows."""
    out = {}
    for m, b in builds.items():
        c = b.choice
        f = fit_er(m, c, er_targets.get(m)) or fit_er(m, replace(c, sands="er"), er_targets.get(m))
        if f is None:
            f = max_er(m, c)
        if sum(f.subs.values()) < DISTRIBUTABLE:   # rolls freed from ER go back to the stat the blind build valued most
            top = max(((k, v) for k, v in c.subs.items() if k != "er"), key=lambda kv: kv[1], default=("cd", 0))[0]
            left = DISTRIBUTABLE - sum(f.subs.values())
            f = replace(f, subs={**f.subs, top: min(f.subs.get(top, 0) + left, _cap(f, top))})
        out[m] = make_build(m, f)
    return out


GCSIM_STAT = {"hp": "hp", "atk": "atk", "def": "def", "hp_pct": "hp%", "atk_pct": "atk%", "def_pct": "def%", "em": "em",
              "cr": "cr", "cd": "cd", "er": "er", "heal": "heal", "Physical": "phys%"} | {
    e: f"{e.lower()}%" for e in ("Pyro", "Hydro", "Electro", "Cryo", "Anemo", "Geo", "Dendro")}


def gcsim_key(name: str) -> str:
    import re

    return re.sub(r"[^a-z0-9]", "", name.lower())


def gcsim_lines(key: str, b: Build) -> list[str]:
    """gcsim build lines for a standard build: weapon with refinement, sets, artifact stats."""
    c = b.choice
    t = b.talents
    stats = " ".join(f"{GCSIM_STAT[k]}={round(v, 4)}" for k, v in b.artifacts.items() if k in GCSIM_STAT)
    lines = [f"{key} char lvl=90/90 cons=0 talent={t['normal']},{t['skill']},{t['burst']};",
             f'{key} add weapon="{gcsim_key(c.weapon)}" refine={c.refine} lvl=90/90;']
    for s, n in c.sets.items():
        lines.append(f'{key} add set="{gcsim_key(s)}" count={n};')
    lines.append(f"{key} add stats {stats};")
    return lines
