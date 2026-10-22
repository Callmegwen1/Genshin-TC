"""Model 5.3.1 correctness cleanup: build heterogeneity, swap advice, user-facing numbers, coverage guard."""
import math
from functools import lru_cache

import pytest

from gtc import coverage, estimate
from gtc.sources.gcsim_db import LineupValue, SimMember, SimTeam, aggregate


def _sim(dps, who, weapon):
    members = [SimMember("Hu Tao", 5, 0, weapon, 4, 1, {"shimenawasreminiscence": 4}),
               SimMember("Xingqiu", 4, 6, "favoniussword", 4, 3), SimMember("Yelan", 5, 0, "favoniuswarbow", 4, 3),
               SimMember("Zhongli", 5, 0, "favoniuslance", 4, 3)]
    return SimTeam("x", 0, "", 1, dps, [1], members, who)


def test_value_is_unchanged_by_build_tracking():
    sims = [_sim(69000, "a", "balladofthefjords"), _sim(41400, "b", "deathmatch"), _sim(40400, "", "deathmatch")]
    lv = aggregate(sims)
    assert lv.value == 41400 and lv.n_submitters == 3
    assert lv.mixed_builds and lv.n_builds == 2


def test_disagreeing_builds_are_not_repeated_measurements():
    mixed = aggregate([_sim(69000, "a", "balladofthefjords"), _sim(41400, "b", "deathmatch"), _sim(40400, "c", "deathmatch")])
    total, between = estimate.exact_rel_sd(mixed)
    assert between > 0.2 and total > 0.2  # far wider than three agreeing submitters would give
    assert total > 3 * estimate.community_rel_sd(3)


def test_agreeing_builds_add_nothing():
    lv = aggregate([_sim(50000, "a", "balladofthefjords"), _sim(50500, "b", "deathmatch")])
    total, between = estimate.exact_rel_sd(lv)
    assert between == 0.0 and total == pytest.approx(estimate.community_rel_sd(2))


def test_measured_gains_do_not_print_simulation_noise_as_uncertainty():
    from gtc.review import Finding

    f = Finding("t", "Flins", "artifacts", "x", 1.84, True, "farming", "gcsim", 0.011)
    assert f.gain_label == "+184% (A)" and "±" not in f.gain_label
    assert f.simulation_precision == 0.011


def test_coverage_caps_confidence_but_never_raises_it():
    assert coverage.cap(0.99, coverage.COMPLETE) == 0.99
    assert coverage.cap(0.99, coverage.PARTIAL) == coverage.CAPS["partial"]
    assert coverage.cap(0.5, coverage.UNKNOWN) == 0.5
    assert coverage.worst([coverage.COMPLETE, coverage.PARTIAL]) == coverage.PARTIAL


@lru_cache(maxsize=1)
def _am():
    from gtc.benchmark import engine

    return engine()


def _assess(names):
    from gtc.benchmark import roster
    from gtc.report import assess
    from gtc.teams import fill_template

    am = _am()
    r = roster(am, names)
    for t in am.kb.templates.values():
        for team in fill_template(t, r, am.kb, limit=1):
            if set(team.members) == set(names):
                return assess(team, am.ev, am.model, am.kb)
    return None


def test_exact_simulations_are_never_penalised_by_the_guard():
    a = _assess(["Nahida", "Kuki Shinobu", "Xingqiu", "Yelan"])
    assert a.evaluation.power["single_target"].basis.route == "exact_community"
    assert a.evaluation.coverage["status"] == coverage.COMPLETE


def test_a_pair_never_simulated_with_an_element_is_partial():
    # Chevreuse's buff needs an all Pyro and Electro party; her pair with Lyney was never simulated with Cryo.
    a = _assess(["Lyney", "Bennett", "Chevreuse", "Citlali"])
    assert a.evaluation.power["single_target"].basis.route == "pair_model"
    assert a.evaluation.coverage["status"] == coverage.PARTIAL
    assert any("Chevreuse" in m and "Cryo" in m for m in a.evaluation.coverage["missing"])


def test_swaps_compare_expected_power_not_fit():
    # Kazuha -> Keqing: lineup fit rose 60 -> 85 because the lead changed; expected power falls.
    from gtc.review import swap_verdict

    old = _assess(["Raiden Shogun", "Kaedehara Kazuha", "Xingqiu", "Yaoyao"])
    new = _assess(["Raiden Shogun", "Keqing", "Xingqiu", "Yaoyao"])
    v = swap_verdict(old, new)
    assert v is not None and v["gain"] < 0


def test_expected_power_and_decision_utility_are_separate():
    a = _assess(["Nahida", "Kuki Shinobu", "Xingqiu", "Yelan"])
    assert a.expected_power == pytest.approx(a.estimate.value)
    assert a.decision_utility == pytest.approx(a.potential)
    assert a.decision_utility < a.expected_power
