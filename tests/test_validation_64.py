"""Model 6.4: the out-of-sample guard for lineups nobody carries, community evidence quality, pull confidence
groups, and redundancy described next to the observed kind."""
from functools import lru_cache
from types import SimpleNamespace

from gtc.bench import Engine
from gtc.estimate import Estimate


@lru_cache(maxsize=1)
def _eng():
    return Engine()


def test_pure_buffer_lineups_keep_a_widened_number():
    """Model 6.4 rejected the no-number guard (a harness artifact); the low_capacity finding widens the sd."""
    eng = _eng()
    team = ["Bennett", "Kaedehara Kazuha", "Zhongli", "Sucrose"]
    r = eng.am.assess_lineup(team, eng.roster(team))
    a = r["assessment"]
    assert a.estimate.value > 0 and r["status"] == "unusual"
    assert any(x.startswith("low_capacity") for x in a.evaluation.validity["typicality"])
    assert a.evaluation.validity["sd_factor"] > 1.0


def test_hu_tao_vape_community_evidence_is_poor_not_automatically_clean():
    eng = _eng()
    team = ["Hu Tao", "Xingqiu", "Yelan", "Zhongli"]
    r = eng.am.assess_lineup(team, eng.roster(team))
    b = r["assessment"].evaluation.power["single_target"].basis
    assert b.route == "exact_community" and b.quality == "poor"
    assert any("Yelan owns the damage" in x for x in b.quality_reasons)
    assert r["status"] == "unusual"


def test_community_quality_labels():
    from gtc.estimate import community_quality
    from gtc.sources.gcsim_db import LineupValue

    one = LineupValue(100.0, 1, 1, {"a": 100.0}, 0.0, {("b",): (100.0, 1)})
    assert community_quality(one, ["A"])[0] == "unconfirmed"
    agree = LineupValue(100.0, 3, 3, {}, 0.1, {("b",): (100.0, 3)})
    assert community_quality(agree, ["A"])[0] == "good"
    split = LineupValue(100.0, 3, 3, {}, 0.7, {("b",): (100.0, 3)})
    assert community_quality(split, ["A"])[0] == "poor"


def _v(name, value, sd, coverage="complete"):
    return SimpleNamespace(name=name, estimate=Estimate(value, sd, "B"), coverage=coverage, gain=value)


def test_pull_groups_surface_a_clear_leader():
    from gtc.account import CLEAR, LOWER, pull_groups

    g = pull_groups([_v("A", 30, 2), _v("B", 10, 2), _v("C", 5, 2)])
    assert g == {"A": CLEAR, "B": LOWER, "C": LOWER}


def test_pull_groups_make_no_claim_inside_the_tie_zone():
    from gtc.account import COMPETITIVE, pull_groups

    g = pull_groups([_v("A", 20, 10), _v("B", 18, 10)])
    assert g == {"A": COMPETITIVE, "B": COMPETITIVE}


def test_pull_groups_do_not_assume_transitivity():
    from gtc.account import COMPETITIVE, LOWER, pull_groups
    from gtc.decision import compare

    a, b, c = _v("A", 30, 3), _v("B", 27, 3), _v("C", 24, 3)
    assert compare(b.estimate, c.estimate)["comparison"] == "roughly_equal"  # B ties C ...
    g = pull_groups([a, b, c])
    assert g["B"] == COMPETITIVE and g["C"] == LOWER  # ... but C is judged against the leader only


def test_unknown_mechanics_coverage_cannot_be_beaten_clearly():
    from gtc.account import COMPETITIVE, pull_groups

    g = pull_groups([_v("A", 30, 2), _v("B", 10, 2, coverage="unknown")])
    assert g["B"] == COMPETITIVE  # capped at 65%: the evidence cannot rule B out


def test_mavuika_keeps_her_observed_kind_with_redundancy_described():
    from scenarios import account, ranked_values

    roster = account(["Arlecchino", "Bennett", "Xingqiu", "Kaedehara Kazuha", "Zhongli", "Xiangling", "Fischl", "Sucrose", "Chevreuse"])
    base, _, vals = ranked_values(roster, ["Mavuika"])
    mav = vals[0]
    assert mav.kind == "new archetype"
    assert any(line.startswith("Functional redundancy") for line in mav.explanation)
    assert abs(mav.gain - round(mav.plan.value - base.value, 1)) < 0.11  # redundancy never touches the gain
