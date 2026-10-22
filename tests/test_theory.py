"""Theorycraft calculator: formulas, effect resolution and swap logic on synthetic teams (no gcsim)."""
import pytest

from gtc.tc import formulas as F
from gtc.tc import transplant
from gtc.tc.engine import Theory, kit_candidate, swap
from gtc.tc.profile import Profile, Source, Unit, classify


def test_formulas_match_gcsim_constants():
    assert F.reaction_base(90) == pytest.approx(1446.8535)
    assert F.res_mult(0.10) == pytest.approx(0.90)
    assert F.res_mult(-0.20) == pytest.approx(1.10)
    assert F.def_mult(90, 100) == pytest.approx(190 / 390)
    # Lunar-Charged reaction at level 90 with no EM or bonuses, no crit: 3 x 1446.85 x RES.
    assert F.lunar_reaction_hit(90, 0, 0, 0, 0, 0, 0.10) == pytest.approx(3 * 1446.8535 * 0.9)
    assert F.em_lunar(2000) == pytest.approx(3.0)


KITS = {
    "Carry": {"element": "Electro", "moonsign": 1, "enables": ["lunar_charged"], "applies": {"Electro": 1.0},
              "abilities": {"Big Hit": "lunar_charged_direct"}},
    "Buffer": {"element": "Electro", "moonsign": 1, "applies": {"Electro": 0.8},
               "effects": [{"kind": "react_bonus", "target": "party", "value": 0.5, "when": {"moonsign_at_least": 2},
                            "applies_to": ["lunar_charged_direct", "lunar_charged_reaction"]},
                           {"kind": "stat", "stat": "em", "target": "active", "value": {"of": "atk", "rate": 0.1}, "constellation": 1}]},
    "Hydro": {"element": "Hydro", "applies": {"Hydro": 1.0}},
    "Anemo": {"element": "Anemo", "effects": [{"kind": "res_shred", "element": "swirled", "value": 0.4}]},
    "Newbie": {"element": "Electro", "moonsign": 1, "applies": {"Electro": 0.8}, "stats": {"atk": 2000, "cr": 0.5, "cd": 1.0},
               "effects": [{"kind": "res_shred", "element": "Electro", "value": 0.2}],
               "hits": [{"name": "Zap", "kind": "lunar_charged_direct", "mult": 1.0, "per_rotation": 10}]},
}


def unit(name, element, atk=2000.0, cons=0):
    return Unit(name, element, 90, cons, {"atk": atk, "em": 100.0, "cr": 0.6, "cd": 1.2, "base_atk": 900.0}, {})


def profile():
    units = {"Carry": unit("Carry", "Electro"), "Buffer": unit("Buffer", "Electro", 1000, cons=1),
             "Hydro": unit("Hydro", "Hydro"), "Anemo": unit("Anemo", "Anemo")}
    sources = [Source("Carry", "Big Hit", "lunar_charged_direct", "Electro", 100000.0),
               Source("Buffer", "Poke", "direct", "Electro", 20000.0),
               Source("Carry", "lunarcharged", "lunar_charged_reaction", "Electro", 30000.0)]
    return Profile(list(units), "Carry", units, sources)


def test_effect_conditions():
    th = Theory(KITS)
    p = profile()
    fx = th.effects(p.units, p.lead)
    kinds = sorted((e.caster, e.kind, round(e.value, 3)) for e in fx)
    assert ("Buffer", "react_bonus", 0.5) in kinds  # Ascendant Gleam: two Moonsign characters
    assert ("Buffer", "stat", 100.0) in kinds        # C1 effect, 10% of the caster's 1000 ATK
    solo = {k: v for k, v in p.units.items() if k != "Carry"}
    assert all(e.kind != "react_bonus" for e in th.effects(solo, "Buffer"))  # only one Moonsign left


def test_losing_a_buffer_lowers_the_carry():
    th = Theory(KITS, beyond_gcsim=False)
    p = profile()
    cand = kit_candidate("Newbie", KITS, {k: v for k, v in p.units.items() if k != "Buffer"}, "Carry", th)
    res = swap(th, p, "Buffer", cand)
    carry_before, carry_after = next((b, a) for d, b, a in res.lines if d == "Carry own damage")
    # Newbie keeps Ascendant Gleam but not the 50% Lunar bonus or the EM; their Electro shred helps a little.
    assert carry_after < carry_before
    assert any(d == "Newbie own damage" and a > 0 for d, b, a in res.lines)


def test_losing_the_hydro_applier_kills_lunar_reactions():
    th = Theory(KITS, beyond_gcsim=False)
    p = profile()
    cand = kit_candidate("Newbie", KITS, {k: v for k, v in p.units.items() if k != "Hydro"}, "Carry", th)
    res = swap(th, p, "Hydro", cand)
    assert any("no off-field Hydro" in n for n in res.notes)
    assert next(a for d, b, a in res.lines if d == "Lunar-Charged reactions") == 0


def test_classify_sources():
    assert classify("swirl-electro", "Anemo", KITS) == ("swirl", "Electro")
    assert classify("lunarcharged", "Carry", KITS) == ("lunar_charged_reaction", "Electro")
    assert classify("Big Hit", "Carry", KITS)[0] == "lunar_charged_direct"
    assert classify("Gravity Interference (Lunar-Charged)", "Someone", KITS) == ("lunar_charged_direct", "Electro")


def test_transplant_copies_shared_builds():
    base = "flins char lvl=90/90 cons=0 talent=9,9,9;\nflins add weapon=\"deathmatch\" refine=1 lvl=90/90;\nflins skill;"
    target = "flins char lvl=90/90 cons=1 talent=9,9,9;\nflins add weapon=\"bloodsoakedruins\" refine=1 lvl=90/90;\naino skill;"
    out = transplant(target, base, {"Flins": ("flins", "flins")})
    assert "cons=0" in out and "deathmatch" in out and "bloodsoakedruins" not in out and "aino skill;" in out
