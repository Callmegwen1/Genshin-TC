"""Model 6.3 power reliability: typicality math, validity vs generation, capacity, ties, sd parts, literal gains."""
from functools import lru_cache

from gtc import typicality, validity
from gtc.bench import Engine
from gtc.pairmodel import load


@lru_cache(maxsize=1)
def _eng():
    return Engine()


def test_typicality_widens_never_narrows():
    f = [typicality.sd_factor(n) for n in range(4)]
    assert f[0] == 1.0 and all(b > a for a, b in zip(f, f[1:]))


def test_typicality_widens_an_extrapolated_lineup_and_leaves_a_measured_one():
    eng = _eng()
    atypical = ["Skirk", "Xiangling", "Bennett", "Xilonen"]  # pair model; Skirk without Cryo and Hydro teammates
    a = eng.am.assess_lineup(atypical, eng.roster(atypical))["assessment"]
    v = a.evaluation.validity
    assert any(x.startswith("carry_needs") for x in v["typicality"]) and v["sd_factor"] > 1.0
    assert "atypical" in a.evaluation.power["single_target"].basis.flags
    measured = ["Mavuika", "Citlali", "Xilonen", "Bennett"]  # its own community simulations
    m = eng.am.assess_lineup(measured, eng.roster(measured))["assessment"]
    assert m.evaluation.power["single_target"].basis.route == "exact_community" and m.evaluation.validity["sd_factor"] == 1.0


def test_mechanical_validity_is_separate_from_generation():
    known = {"Bennett": 1, "Xiangling": 1, "Xingqiu": 1, "Traveler (Anemo)": 1, "Traveler (Cryo)": 1, "Zhongli": 1}
    assert validity.mechanical(["Bennett", "Xiangling", "Xingqiu", "Zhongli"], known) == []
    assert validity.mechanical(["Bennett", "Bennett", "Xingqiu", "Zhongli"], known)
    assert validity.mechanical(["Traveler (Anemo)", "Traveler (Cryo)", "Xingqiu", "Zhongli"], known)
    assert validity.mechanical(["Bennett", "Xingqiu", "Zhongli"], known)


def test_a_legal_team_no_template_generates_is_still_evaluated():
    eng = _eng()
    team = ["Hu Tao", "Kamisato Ayaka", "Raiden Shogun", "Neuvillette"]
    r = eng.am.assess_lineup(team, eng.roster(team))
    assert r["status"] == "unusual" and r["assessment"] is not None
    assert r["assessment"].team.template.id == validity.MANUAL_ID
    assert eng.am.assess_lineup(["Bennett", "Bennett", "Xingqiu", "Zhongli"], eng.roster(["Bennett", "Xingqiu", "Zhongli"]))["status"] == "invalid"


def test_damage_capacity_lowers_lineups_nobody_carries():
    pm = load()
    assert pm.capacity_coef > 0
    team = frozenset(["Escoffier", "Citlali", "Furina", "Kaedehara Kazuha"])
    with_term = pm.predict(team)
    coef, pm.capacity_coef = pm.capacity_coef, 0.0
    try:
        without = pm.predict(team)
    finally:
        pm.capacity_coef = coef
    assert with_term < without


def test_near_ties_are_reported_not_decided():
    from gtc.account import near_alternatives
    from gtc.decision import compare

    eng = _eng()
    roster = ["Kamisato Ayaka", "Shenhe", "Kaedehara Kazuha", "Mona", "Bennett", "Xiangling"]
    _, plan, cands = eng.plan(roster)
    alts = near_alternatives(plan, cands)
    assert alts and all(compare(t.estimate, alt.estimate)["comparison"] == "roughly_equal" for t, alt, *_ in alts)


def test_pull_order_is_the_literal_gain_alone():
    from scenarios import account, ranked_values

    roster = account(["Arlecchino", "Bennett", "Xingqiu", "Kaedehara Kazuha", "Zhongli", "Xiangling", "Fischl", "Sucrose", "Chevreuse"])
    _, _, vals = ranked_values(roster, ["Mavuika", "Columbina", "Citlali", "Neuvillette"])
    assert [v.name for v in vals] == [v.name for v in sorted(vals, key=lambda v: (-v.gain, v.name))]


def test_account_power_reports_where_its_uncertainty_comes_from():
    import math

    from gtc.account_power import account_power
    from gtc.estimate import Estimate

    eng = _eng()
    team = ["Mavuika", "Citlali", "Xilonen", "Bennett"]
    a = eng.am.assess_lineup(team, eng.roster(team))["assessment"]
    ctx = {"ev": eng.am.ev, "investments": {}, "characters": {}, "newcomer_weapon": {m: 5 for m in team},
           "rarity": {m: 5 for m in team}}
    ap = account_power(a, ctx)
    parts = ap["sd_parts"]
    assert set(parts["current"]) == {"team", "build"} and set(parts["ceiling"]) == {"team", "constellations", "weapons"}
    ceil = ap["ceiling"]
    rel = math.sqrt(sum(v ** 2 for v in parts["ceiling"].values()))
    assert abs(ceil.sd / ceil.value - rel) < 1e-3 and isinstance(ceil, Estimate)
