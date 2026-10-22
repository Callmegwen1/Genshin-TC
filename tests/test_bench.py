"""Benchmark v2: scoring rules, the locked set, and tuning's isolation from it."""
import inspect

from gtc import bench
from gtc.estimate import Estimate


def test_pairs_score_order_and_gap():
    big, small = Estimate(80, 2, "B"), Estimate(40, 2, "B")
    assert bench._pair_score(big, small, "large")[0] == 1.0
    assert bench._pair_score(big, small, "medium")[0] == 0.75   # right order, adjacent gap class
    assert bench._pair_score(small, big, "large")[0] == 0.0     # wrong order earns nothing


def test_close_calls_must_stay_close():
    a, b = Estimate(60, 8, "D"), Estimate(58, 8, "D")
    assert bench._pair_score(a, b, "small")[0] == 1.0
    assert bench._pair_score(Estimate(90, 1, "B"), Estimate(40, 1, "B"), "small")[0] == 0.0


def test_a_team_that_does_not_form_loses_the_comparison():
    assert bench._pair_score(Estimate(50, 5, "B"), None, "large")[0] == 1.0
    assert bench._pair_score(None, Estimate(50, 5, "B"), "large")[0] == 0.0


def test_kendall_with_ties():
    assert bench._kendall([["A", "B"], "C"], {"A": 3, "B": 5, "C": 1}) == 1.0
    assert bench._kendall(["A", "B", "C"], {"A": 1, "B": 2, "C": 3}) == 0.0


def test_locked_set_is_pinned():
    ok, msg = bench.check_lock()
    assert ok, msg


def test_tuning_reads_only_the_calibration_set():
    assert inspect.signature(bench._with).parameters["which"].default == ("calibration",)
    src = inspect.getsource(bench.tune)
    assert 'run(("locked",))' in src and "choose(" in src  # locked is scored for comparison, never chosen on


def test_every_case_evaluates_without_errors():
    results = bench.run()
    assert not [r.id for r in results if r.error]
    assert {r.question for r in results} >= {"pull_ranking", "team_ranking", "plan", "validity", "identity", "mode", "carries"}
