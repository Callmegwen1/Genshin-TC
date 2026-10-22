"""Phase 9: typicality widens extrapolated uncertainty only; measured teams keep their measured sd."""
from gtc import estimate, typicality


def _evaluate(names):
    from gtc.benchmark import engine, roster
    from gtc.teams import fill_template

    am = engine()
    r = roster(am, names)
    for t in am.kb.templates.values():
        for team in fill_template(t, r, am.kb, limit=1):
            if set(team.members) == set(names):
                return am._assess(team).evaluation
    return None


def test_a_measured_atypical_team_keeps_its_measured_uncertainty():
    # Skirk with Chiori, Yelan and Zhongli: unusual for Skirk, but simulated (about 64k).
    e = _evaluate(["Skirk", "Chiori", "Yelan", "Zhongli"])
    assert e is not None and e.power["single_target"].basis.route == "exact_community"
    assert e.validity["typicality"] and e.validity["sd_factor"] == 1.0
    assert "atypical" not in e.power["single_target"].basis.flags


def test_an_extrapolated_atypical_team_gets_wider_uncertainty():
    e = _evaluate(["Skirk", "Chiori", "Lan Yan", "Zhongli"])
    assert e is not None and e.power["single_target"].basis.route in ("pair_model", "role_rules")
    assert len(e.validity["typicality"]) >= 1 and e.validity["sd_factor"] > 1.0
    assert "atypical" in e.power["single_target"].basis.flags


def test_the_widening_is_measured():
    m = estimate.load().get("typicality") or {}
    assert m["groups"]["0"]["n"] > 1000 and m["per_finding"] > 0
    assert typicality.sd_factor(0) == 1.0
