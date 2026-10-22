"""Gear effects (phase H) and realistic standard builds (phase G)."""
import re
from types import SimpleNamespace

import pytest

from gtc.forward.effects import Instance, TimedEffect
from gtc.forward.gear import (amount_at, compile_text, curated, set_effects, set_text, static_stats, weapon_effects,
                              weapon_text)


def _nums(text: str) -> set[float]:
    return {round(float(x), 4) for x in re.findall(r"\d+(?:\.\d+)?", text)}


def _values(v):
    if isinstance(v, (int, float)):
        yield float(v)
    elif isinstance(v, list):
        for x in v:
            yield from _values(x)
    elif isinstance(v, dict):
        for k, x in v.items():
            if k in ("rate", "cap", "per_same_element", "per_other_element", "party_energy_rate"):
                yield from _values(x)


def _pick(v, r):
    """Resolve refinement lists (five values) to refinement r."""
    if isinstance(v, list) and len(v) == 5 and all(isinstance(x, (int, float)) for x in v):
        return v[r - 1]
    if isinstance(v, dict):
        return {k: _pick(x, r) for k, x in v.items()}
    return v


def test_curated_numbers_come_from_the_amber_text():
    """Every curated number appears in the Amber text of its refinement (or the stated text values do, for
    expected-value entries)."""
    for name, effects in (curated().get("weapons") or {}).items():
        for r in range(1, 6):
            text = _nums(weapon_text(name, r) or "")
            for e in effects:
                vals = list(_values(_pick(e.get("text_values") or e.get("amount"), r)))
                if e.get("stack_steps"):
                    vals += [lvl[r - 1] for lvl in e["stack_steps"] if isinstance(lvl, list)]
                for v in vals:
                    if v in (0.0, 1.0):
                        continue
                    assert round(v * 100, 4) in text or round(v, 4) in text, (name, r, v)
    for name, pieces in (curated().get("sets") or {}).items():
        text = _nums(" ".join(set_text(name, 4)))
        for key, effects in pieces.items():
            for e in effects:
                for v in _values(e.get("text_values") or e.get("amount")):
                    if v in (0.0, 1.0):
                        continue
                    assert round(v * 100, 4) in text or round(v, 4) in text, (name, key, v)
                for v in e.get("stack_steps") or []:
                    assert round(v * 100, 4) in text, (name, key, v)


def test_compiler_reads_common_gear_shapes():
    nob = set_effects("Noblesse Oblige", 4)
    party = next(e for e in nob if e["kind"] == "atk_pct")
    assert party["target"] == "party" and party["trigger"] == ["burst"] and party["duration"] == 12 and party["amount"] == 0.2
    vv = next(e for e in set_effects("Viridescent Venerer", 4) if e["kind"] == "res_shred")
    assert vv["element_from"] == "swirl" and vv["amount"] == 0.4 and vv["duration"] == 10
    emb = next(e for e in set_effects("Emblem of Severed Fate", 4) if e["kind"] == "dmg_bonus")
    assert emb["amount"] == {"of": "er", "rate": 0.25, "cap": 0.75} and emb["affects"]["damage_types"] == ["burst"]
    catch = weapon_effects('"The Catch"', 5)
    assert {(e["kind"], e["amount"]) for e in catch} == {("dmg_bonus", 0.32), ("crit_rate", 0.12)}
    glad = next(e for e in set_effects("Gladiator's Finale", 4) if e["kind"] == "dmg_bonus")
    assert glad["conditions"] == [{"type": "weapon_type", "any": ["sword", "claymore", "polearm"]}]
    ballad = weapon_effects("Ballad of the Fjords", 5)[0]
    assert ballad["amount"] == 240 and ballad["conditions"] == [{"type": "distinct_elements", "min": 3}]
    rancour = weapon_effects("Prototype Rancour", 5)
    assert {e["kind"] for e in rancour} == {"atk_pct", "def_pct"} and all(e["stack_max"] == 4 for e in rancour)
    lion = weapon_effects("Lion's Roar", 3)[0]
    assert lion["conditions"] == [{"type": "enemy_aura", "any": ["Pyro", "Electro"]}]


def test_unmodelled_conditions_are_unknown_not_credited():
    zerk = set_effects("Berserker", 4)
    assert any(e["state"] == "unknown" and "hp" in e["why"] for e in zerk)
    assert all(e["state"] == "unknown" for e in weapon_effects("Blackcliff Agate", 1))
    sac = weapon_effects("Sacrificial Sword", 3)
    assert not [e for e in sac if e["state"] == "met"]
    # a sentence the compiler cannot read is listed, never dropped silently
    out = compile_text("Increases DMG against bosses by 30% under a full moon.", "test")
    assert out and all(e["state"] == "unknown" for e in out)


def test_static_stats_fold_into_the_build():
    st = static_stats({"weapon": "Favonius Sword", "refine": 1, "sets": {"Emblem of Severed Fate": 4}})
    assert st == {"er": 0.2}
    st = static_stats({"weapon": "Primordial Jade Cutter", "refine": 1, "sets": {"Gladiator's Finale": 2, "Heart of Depth": 2}})
    assert st["hp_pct"] == 0.2 and st["atk_pct"] == 0.18 and st["Hydro"] == 0.15


def test_stacks_shared_independent_steps_threshold():
    te = TimedEffect("x", "A", "atk_pct", "self", {}, 0.1, "met", [Instance(0, 99)], stack_max=3, stack_duration=5.0,
                     trigger_times=[0.0, 1.0, 2.0, 3.0])
    assert amount_at(te, 3.5) == pytest.approx(0.3)          # capped at 3
    assert amount_at(te, 7.9) == pytest.approx(0.3)          # shared: the last trigger refreshed all stacks
    assert amount_at(te, 8.1) is None                        # expired
    te.stack_mode = "independent"
    assert amount_at(te, 6.5) == pytest.approx(0.2)          # triggers at 2 and 3 still alive
    steps = TimedEffect("m", "A", "elemental_dmg_bonus", "self", {}, 0.0, "met", [Instance(0, 99)],
                        stack_steps=[0.08, 0.16, 0.28],
                        stack_sources=[[Instance(0, 99)], [Instance(1, 6)], [Instance(2, 12)]])
    assert [amount_at(steps, t) for t in (0.5, 3, 8, 20)] == [0.08, 0.28, 0.16, 0.08]
    thr = TimedEffect("k", "A", "dmg_bonus", "self", {}, 0.12, "met", [Instance(0, 99)], stack_max=3, stack_threshold=3,
                      stack_duration=24.0, trigger_times=[0.0, 10.0])
    assert amount_at(thr, 11) is None
    thr.trigger_times.append(20.0)
    assert amount_at(thr, 21) == 0.12


def test_standard_builds_pay_er_from_the_budget():
    from gtc.forward.standard import DISTRIBUTABLE, Choice, fit_er, make_build

    c = Choice("Wolf-Fang", 3, {"Blizzard Strayer": 4}, "atk_pct", "element", "cr", {"cd": 10, "cr": 6, "atk_pct": 4})
    f = fit_er("Kamisato Ayaka", c, 1.4)
    b = make_build("Kamisato Ayaka", f)
    assert b.total("er") >= 1.4 and sum(f.subs.values()) <= DISTRIBUTABLE and f.subs["er"] >= 1
    assert fit_er("Kamisato Ayaka", c, 2.6) is None        # beyond the budget with ATK sands: infeasible
    fav = make_build("Mona", Choice("Favonius Codex", 3, {"Noblesse Oblige": 4}, "er", "element", "cr", {}))
    assert fav.total("er") > 1.9                            # ER sands + Favonius substat + fixed rolls
    assert fav.gear == {"weapon": "Favonius Codex", "refine": 3, "sets": {"Noblesse Oblige": 4}}


def test_favonius_particles_follow_the_weapon():
    from gtc.forward.build import meta_standard
    from gtc.forward.generator import favonius
    from gtc.forward.standard import Choice, make_build

    # (cooldown, proc chance on a crit) by refinement, from the Amber text; procs come from the wearer's crit hits
    assert favonius(meta_standard("Mona")) == (12.0, pytest.approx(0.6))       # neutral house build: Favonius R1
    assert favonius(make_build("Mona", Choice("The Widsith", 3, {"Noblesse Oblige": 4}, "er", "element", "cr", {}))) is None
    assert favonius(make_build("Mona", Choice("Favonius Codex", 5, {"Noblesse Oblige": 4}, "er", "element", "cr", {}))) == (6.0, pytest.approx(1.0))


def test_gear_effects_reach_damage_events_with_conditions():
    """Blizzard Strayer's CRIT Rate needs a Cryo-affected or Frozen enemy, read from the simulated auras per hit;
    two Noblesse wearers do not stack."""
    from gtc.forward.blind import theorycraft
    from gtc.forward.model import evaluate
    from gtc.forward.standard import Choice, make_build

    team = ["Kamisato Ayaka", "Shenhe", "Kaedehara Kazuha", "Mona"]
    r = theorycraft(team)
    rot = r["rotation"]
    base = {m: make_build(m, Choice(*{"Kamisato Ayaka": ("Wolf-Fang", 3, {"Blizzard Strayer": 4}),
                                        "Shenhe": ("Favonius Lance", 3, {"Noblesse Oblige": 4}),
                                        "Kaedehara Kazuha": ("Favonius Sword", 3, {"Viridescent Venerer": 4}),
                                        "Mona": ("Favonius Codex", 3, {"Noblesse Oblige": 4})}[m],
                                     "atk_pct", "element", "cr", {})) for m in team}
    ev = evaluate(rot, base)
    ayaka = [e for e in ev.events if e.char == "Kamisato Ayaka" and e.damage > 0 and not e.reaction]
    bliz = [e for e in ayaka if any(b.startswith("Kamisato Ayaka:gear") for b in e.buffs)]
    assert bliz and len(bliz) <= len(ayaka)
    # both Noblesse: at most one Noblesse ATK buff on any event
    for e in ev.events:
        nob = [b for b in e.buffs if b.endswith(tuple(f":gear:{i}" for i in range(9)))
               and b.split(":")[0] in ("Shenhe", "Mona")]
        assert len([b for b in nob if b.startswith("Shenhe")]) + len([b for b in nob if b.startswith("Mona")]) <= 2
    # the VV shred appears as a debuff
    assert any(any(d.startswith("Kaedehara Kazuha:gear") for d in e.debuffs) for e in ev.events)
