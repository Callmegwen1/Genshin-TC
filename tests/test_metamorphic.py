"""Metamorphic tests (development diagnostics): relationships that must hold whatever the reference DPS is.

Synthetic rotations from real kits and Amber data; each test perturbs one input and checks the direction of the
output. They catch broken formulas and accidental interactions that ordinary benchmarks can pass over.
"""
from dataclasses import replace

import pytest

from gtc.forward.trace import Action, Hit, Rotation

CHARS = [("Kamisato Ayaka", "Cryo", "normal"), ("Kamisato Ayaka", "Cryo", "burst"), ("Hu Tao", "Pyro", "charged"),
         ("Xiangling", "Pyro", "burst"), ("Neuvillette", "Hydro", "charged"), ("Raiden Shogun", "Electro", "burst"),
         ("Nahida", "Dendro", "skill"), ("Yelan", "Hydro", "burst"), ("Razor", "Physical", "normal"),
         ("Furina", "Hydro", "skill"), ("Fischl", "Electro", "skill"), ("Kaedehara Kazuha", "Anemo", "skill")]
PARTY = ["Bennett", "Shenhe", "Kaedehara Kazuha", "Furina", "Xingqiu", "Mona", "Sucrose", "Zhongli"]


def _lineup(char):
    others = [m for m in PARTY if m != char][:3]
    return [char] + others


def _rot(char, element, dtype, mult=1.5, n=16, duration=12.0, scale=1.0):
    from gtc.forward.build import scaling_stat

    lineup = _lineup(char)
    sc = scaling_stat(char) if element != "Physical" else "atk"
    actions = [Action(0.0, char, "skill", 0.5), Action(0.6 * scale, char, "burst", 1.6 * scale)]
    for m in lineup[1:]:
        actions.append(Action(0.0, m, "burst", 0.1))
    hits = [Hit(t=(1.0 + 0.6 * i) * scale, char=char, abil=f"{dtype} hit {i}", damage_type=dtype, element=element,
                mult=mult, scaling=sc, gauge=1.0 if i % 3 == 0 else 0.0) for i in range(n)]
    return Rotation(lineup, actions, hits, duration * scale, [], [(0.0, duration * scale, char)], "synthetic")


def _builds(rot, **extra):
    from gtc.forward.build import house_builds

    b = house_builds(rot.lineup)
    for m, add in extra.items():
        b[m] = replace(b[m], stats={**b[m].stats, **{k: b[m].stats.get(k, 0.0) + v for k, v in add.items()}})
    return b


def _dmg(rot, builds, **kw):
    from gtc.forward.model import evaluate

    ev = evaluate(rot, builds, **kw)
    return sum(e.damage for e in ev.events if e.char == rot.lineup[0])


@pytest.mark.parametrize("char,element,dtype", CHARS)
def test_higher_multiplier_never_lowers_damage(char, element, dtype):
    r1 = _rot(char, element, dtype, mult=1.5)
    r2 = _rot(char, element, dtype, mult=1.8)
    b = _builds(r1)
    assert _dmg(r2, b) >= _dmg(r1, b) - 1e-6


@pytest.mark.parametrize("char,element,dtype", CHARS)
def test_removing_a_positive_buff_never_raises_damage(char, element, dtype):
    from gtc.forward.effects import build_timeline

    rot = _rot(char, element, dtype)
    b = _builds(rot)
    base = _dmg(rot, b)
    for e in build_timeline(rot, b):
        if e.active and e.kind in ("atk", "atk_pct", "dmg_bonus", "elemental_dmg_bonus", "crit_rate", "crit_dmg",
                                   "res_shred", "em") and (e.amount or 0) > 0:
            assert _dmg(rot, b, exclude=frozenset({e.id})) <= base + 1e-6, e.id


@pytest.mark.parametrize("char,element,dtype", CHARS)
def test_more_res_shred_never_lowers_damage(char, element, dtype, monkeypatch):
    import gtc.forward.model as M

    rot = _rot(char, element, dtype)
    b = _builds(rot)
    base = _dmg(rot, b)
    monkeypatch.setattr(M, "ENEMY_RES", M.ENEMY_RES - 0.2)
    assert _dmg(rot, b) >= base - 1e-6


@pytest.mark.parametrize("char,element,dtype", CHARS)
@pytest.mark.parametrize("stat", ["cr", "cd"])
def test_crit_never_lowers_expected_damage(char, element, dtype, stat):
    rot = _rot(char, element, dtype)
    b0 = _builds(rot)
    if stat == "cr" and b0[char].stats.get("cr", 0) > 0.9:
        pytest.skip("CRIT Rate already near the cap")
    b1 = _builds(rot, **{char: {stat: 0.05}})
    assert _dmg(rot, b1) >= _dmg(rot, b0) - 1e-6


@pytest.mark.parametrize("char,element,dtype", CHARS)
def test_more_scaling_stat_never_lowers_damage(char, element, dtype):
    from gtc.forward.build import scaling_stat

    rot = _rot(char, element, dtype)
    key = {"atk": "atk_pct", "hp": "hp_pct", "def": "def_pct", "em": "em"}[scaling_stat(char) if element != "Physical" else "atk"]
    b0 = _builds(rot)
    b1 = _builds(rot, **{char: {key: 0.2 if key != "em" else 100}})
    assert _dmg(rot, b1) >= _dmg(rot, b0) - 1e-6


@pytest.mark.parametrize("char,element,dtype", [c for c in CHARS if c[0] not in ("Raiden Shogun",)])
def test_er_does_not_change_direct_damage_without_er_scaling(char, element, dtype):
    rot = _rot(char, element, dtype)
    b0 = _builds(rot)
    b1 = _builds(rot, **{char: {"er": 0.4}})
    assert _dmg(rot, b1) == pytest.approx(_dmg(rot, b0), rel=1e-9)


def test_er_scaling_kit_responds_to_er():
    """Positive control: Raiden's Burst damage grows with ER (her passive), so the relation above is not vacuous."""
    rot = _rot("Raiden Shogun", "Electro", "burst")
    b0 = _builds(rot)
    b1 = _builds(rot, **{"Raiden Shogun": {"er": 0.4}})
    assert _dmg(rot, b1) > _dmg(rot, b0)


@pytest.mark.parametrize("dur", [4.0, 8.0, 12.0])
def test_shorter_buff_never_covers_more(dur):
    from gtc.forward.effects import _instances

    rot = _rot("Bennett", "Pyro", "burst")
    long = _instances(rot, "Bennett", ["burst", "skill"], dur, 0.0)
    short = _instances(rot, "Bennett", ["burst", "skill"], dur * 0.5, 0.0)
    cover = lambda xs: sum(i.end - i.start for i in xs)
    assert cover(short) <= cover(long) + 1e-9


@pytest.mark.parametrize("cost", [40, 60, 80, 90])
def test_higher_burst_cost_never_improves_energy_feasibility(cost):
    from gtc.forward.energy import requirements

    rot = _rot("Xiangling", "Pyro", "burst", duration=40.0)
    rot.actions += [Action(20.0, "Xiangling", "burst", 21.0), Action(39.0, "Xiangling", "burst", 39.5)]
    rot.energy = [{"t": 5.0 + 3 * i, "char": "Xiangling", "kind": "particle", "amount": 6.0, "er": 1.0} for i in range(12)]
    lo = requirements(rot, {"Xiangling": cost})["Xiangling"]["required_er"]
    hi = requirements(rot, {"Xiangling": cost + 10})["Xiangling"]["required_er"]
    assert hi >= lo


def test_breaking_a_party_restriction_drops_the_effect():
    """Chevreuse's Vertical Force Coordination needs an all Pyro/Electro party."""
    from gtc.forward.effects import build_timeline

    ok = _rot("Raiden Shogun", "Electro", "burst")
    ok.lineup = ["Raiden Shogun", "Chevreuse", "Bennett", "Fischl"]
    bad = _rot("Raiden Shogun", "Electro", "burst")
    bad.lineup = ["Raiden Shogun", "Chevreuse", "Bennett", "Xingqiu"]
    from gtc.forward.build import house_builds

    state = lambda r: {e.source: e.state for e in build_timeline(r, house_builds(r.lineup)) if e.caster == "Chevreuse"}
    s_ok, s_bad = state(ok), state(bad)
    restricted = [k for k in s_ok if "Vertical Force" in k or "Coordinated Tactics" in k]
    assert restricted
    assert any(s_bad[k] == "unmet" for k in restricted if k in s_bad)


@pytest.mark.parametrize("value,expect", [(0.0, "unmet"), (1.0, "unmet"), (3.0, "met"), (5.0, "met")])
def test_resource_threshold_gates_an_effect(value, expect):
    from types import SimpleNamespace

    from gtc.forward.effects import TimedEffect, dynamic_ok

    rot = SimpleNamespace(timeline={"resources": {"X:stacks": [(0.0, value)]}, "states": []})
    e = TimedEffect("t", "X", "atk_pct", "self", {}, 0.1, "met", dynamic=[{"type": "resource_at_least", "resource": "stacks", "value": 3}])
    assert dynamic_ok(e, rot, 1.0) == expect


@pytest.mark.parametrize("char,element,dtype", CHARS[:8])
@pytest.mark.parametrize("scale", [1.1, 1.5])
def test_slower_identical_actions_never_raise_dps(char, element, dtype, scale):
    from gtc.forward.model import evaluate

    r1 = _rot(char, element, dtype)
    r2 = _rot(char, element, dtype, scale=scale)
    b = _builds(r1)
    assert evaluate(r2, b).dps <= evaluate(r1, b).dps * (1 + 1e-9)


@pytest.mark.parametrize("remove", ["Hydro", "Cryo", "Pyro", "Electro", "Dendro"])
def test_removing_an_aura_source_never_adds_reactions_that_need_it(remove):
    from gtc.forward.reactions import simulate

    team = ["Nahida", "Xingqiu", "Xiangling", "Fischl"]
    seq = ["Hydro", "Cryo", "Pyro", "Electro", "Dendro", "Hydro", "Electro", "Pyro", "Dendro", "Cryo"] * 3
    hits = [Hit(t=0.4 * i, char=team[i % 4], abil="x", damage_type="skill", element=el, mult=1.0, scaling="atk", gauge=1.0)
            for i, el in enumerate(seq)]
    _, c1 = simulate(hits, team)
    _, c2 = simulate([h for h in hits if h.element != remove], team)
    needs = {"Hydro": ("vaporize", "freeze", "bloom-core", "electrocharged"), "Cryo": ("melt", "freeze", "superconduct"),
             "Pyro": ("vaporize", "melt", "overloaded", "burgeon"), "Electro": ("overloaded", "superconduct", "electrocharged",
             "quicken", "aggravate", "hyperbloom"), "Dendro": ("quicken", "spread", "bloom-core", "hyperbloom", "burgeon")}[remove]
    for k in needs:
        assert c2.get(k, 0) <= c1.get(k, 0), k


@pytest.mark.parametrize("char,element,dtype", CHARS[:6])
def test_removing_an_artifact_set_never_raises_damage(char, element, dtype):
    from gtc.forward.standard import Choice, make_build

    rot = _rot(char, element, dtype)
    b = _builds(rot)
    with_set = dict(b)
    with_set[char] = make_build(char, Choice("Favonius Sword" if False else _weapon(char), 1,
                                             {"Gladiator's Finale": 2, "Shimenawa's Reminiscence": 2}, "atk_pct", "element", "cr", {}))
    without = dict(b)
    without[char] = make_build(char, Choice(_weapon(char), 1, {}, "atk_pct", "element", "cr", {}))
    assert _dmg(rot, without) <= _dmg(rot, with_set) + 1e-6


def _weapon(char):
    from gtc.forward.build import FAVONIUS, weapon_type

    return FAVONIUS[weapon_type(char)]


@pytest.mark.parametrize("cr", [0.2, 0.5, 0.8])
def test_higher_crit_rate_never_reduces_favonius_particles(cr):
    from gtc.forward.build import house_builds
    from gtc.forward.generator import _Sim

    team = ["Xiangling", "Bennett", "Xingqiu", "Sucrose"]
    libs = {}
    from gtc.forward.library import build

    for m in team:
        libs[m] = build(m, [team], role="support")

    def particles(c):
        b = house_builds(team)
        b["Bennett"] = replace(b["Bennett"], stats={**b["Bennett"].stats, "cr": c})
        s = _Sim(team, libs, b)
        s.on_field = "Bennett"
        s.segments = [(0.0, 99.0, "Bennett")]
        for i in range(30):
            s.emit(Hit(t=0.3 * i, char="Bennett", abil="x", damage_type="normal", element="Pyro", mult=1.0, scaling="atk"))
        s._flush_favonius(99.0)
        return sum(p[2] for p in s.pending if str(p[1]).startswith("favonius"))

    assert particles(min(1.0, cr + 0.2)) >= particles(cr) - 1e-9
