"""Phase 10: decision policy, calibrated comparisons, functional-distance uncertainty."""
from gtc import decision, distance, estimate
from gtc.estimate import Estimate


def test_utility_is_expected_minus_risk_times_sd():
    e = Estimate(60.0, 10.0, "C")
    assert decision.utility(e) == 60.0 - decision.RISK * 10.0


def test_compare_names_a_tie_inside_the_calibrated_zone():
    tie = decision.tie_probability()
    assert 0.5 < tie < 1.0
    assert decision.compare(Estimate(50, 5, "C"), Estimate(49, 5, "C"))["comparison"] == "roughly_equal"
    assert decision.compare(Estimate(80, 3, "B"), Estimate(40, 3, "B"))["comparison"] == "better"
    assert decision.compare(Estimate(40, 3, "B"), Estimate(80, 3, "B"))["comparison"] == "worse"


def test_tie_edge_and_reliability_are_measured():
    c = estimate.load()["compare"]
    assert c["pairs"] > 1000 and c["tie"] == decision.tie_probability()
    band = next(b for b in c["reliability"] if b["stated"] == "0.8-0.9")
    assert band["right"] >= decision.CLAIM_ACCURACY


def _feat(**kw):
    f = {k: 0.0 for k in distance.FEATURES}
    f.update({"away": 1.0, "scarcity": 1.0 / (1.0 + 6.0)})
    f.update(kw)
    return f


def test_distance_widens_with_members_changed_and_thin_data():
    base = distance.sd(_feat())
    assert distance.sd(_feat(away=2.0)) > base
    assert distance.sd(_feat(scarcity=1.0 / (1.0 + 0.69))) > base  # a member with a single simulated lineup
    m = estimate.load()["distance"]
    assert m["n_test"] > 1000 and 0.6 <= m["coverage_model"][0] <= 0.8


def test_the_swap_estimator_is_gone():
    import gtc.report as report
    import gtc.synergy as synergy
    assert not hasattr(report, "synergy_fit") and not hasattr(synergy.SynergyTable, "pair_value")
    assert "swap" not in estimate.load()
