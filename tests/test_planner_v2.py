"""Phase 12: content utilities, the useful-team gate, and pull value v2."""
from types import SimpleNamespace

from gtc import profiles
from gtc.estimate import Estimate


def _team(names, value):
    e = Estimate(value, 0.0, "B")
    return SimpleNamespace(team=SimpleNamespace(members=list(names)), power={"single_target": e, "aoe": e})


def test_abyss_prefers_a_balanced_pair():
    a = _team(["A", "B", "C", "D"], 100)
    b = _team(["E", "F", "G", "H"], 55)
    c = _team(["A", "B", "I", "J"], 92)
    d = _team(["C", "D", "E", "F"], 92)
    plan = profiles.plan_for("abyss", [a, b, c, d], {})
    assert {tuple(t.team.members) for t in plan.teams} == {("A", "B", "I", "J"), ("C", "D", "E", "F")}
    assert any(f[0] == 100 and f[1] == 55 for f in plan.frontier)  # the max-primary plan is shown, not chosen


def test_abyss_says_when_no_second_team_is_worth_building():
    a = _team(["A", "B", "C", "D"], 80)
    weak = _team(["E", "F", "G", "H"], 10)
    plan = profiles.plan_for("abyss", [a, weak], {})
    assert len(plan.teams) == 1 and plan.note == "No second team worth building yet."


def test_general_ignores_teams_below_the_useful_value():
    a = _team(["A", "B", "C", "D"], 80)
    weak = _team(["E", "F", "G", "H"], 10)
    plan = profiles.plan_for("general", [a, weak], {})
    assert len(plan.teams) == 1


def test_stygian_is_the_best_single_team():
    a, b = _team(["A", "B", "C", "D"], 80), _team(["E", "F", "G", "H"], 79)
    assert profiles.plan_for("stygian", [a, b], {}).teams == [a]


def test_pull_gain_is_the_literal_plan_change_and_is_decomposed():
    from scenarios import account, ranked_values
    roster = account(["Arlecchino", "Bennett", "Xingqiu", "Kaedehara Kazuha", "Zhongli", "Xiangling", "Fischl", "Sucrose", "Chevreuse"])
    base, _, vals = ranked_values(roster, ["Mavuika", "Columbina"])
    for v in vals:
        assert abs(v.gain - round(v.plan.value - base.value, 1)) < 0.11  # no label discounts the gain
        d = v.decomposition
        for k in ("plan_gain", "best_team_gain", "second_team_gain", "expected_gain", "new_mechanics", "new_viable_teams",
                  "improved", "displaced", "support_contention", "redundancy", "redundancy_score"):
            assert k in d
        assert set(d["redundancy"]) == {"role", "mechanic", "support_demand", "team", "content_coverage"}


def test_the_duplicate_element_factor_is_gone():
    import gtc.account as account
    from gtc import params
    assert not hasattr(account, "DUPLICATE_ELEMENT_FACTOR")
    assert "duplicate_element_factor" not in params.get("account")
