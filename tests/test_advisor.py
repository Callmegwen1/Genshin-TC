"""Model 6.5 advisor layer: recommendability is separate from power; substitutions preserve team functions; plans,
recommended teams and pulls use the advisor pool; kit conditions; where an account gain comes from."""
from functools import lru_cache
from types import SimpleNamespace

import pytest

from gtc import SNAPSHOT_DIR
from gtc.advisor import Advisor
from gtc.estimate import Estimate

needs_account = pytest.mark.skipif(not (SNAPSHOT_DIR.exists() and any(SNAPSHOT_DIR.glob("*.json"))),
                                   reason="needs an imported account snapshot")
FREEZE = ["Kamisato Ayaka", "Shenhe", "Mona", "Kaedehara Kazuha"]


@lru_cache(maxsize=1)
def _svc():
    from gtc.app.service import AppService

    s = AppService()
    s.load(background=False)  # no background thread outliving the test
    return s


def _subs(s, team):
    return s.evaluate_team(team)["substitutions"]


@needs_account
def test_freeze_direct_substitutions_keep_hydro_and_anemo():
    from gtc.kit_conditions import _element

    s = _svc()
    subs = _subs(s, FREEZE)
    for x in subs["direct"]:
        assert "Hydro" in {_element(m) for m in x["lineup"]}  # Freeze still has Hydro
        if x["out"] == "Kaedehara Kazuha":
            assert s.kb.characters[x["in"]].roles.get("buffer_anemo", 0) >= 2  # the Anemo support is replaced in kind
    assert any(x["out"] == "Kaedehara Kazuha" and x["in"] == "Sucrose" for x in subs["direct"])


@needs_account
def test_kazuha_to_ineffa_and_mona_to_citlali_are_not_direct():
    subs = _subs(_svc(), FREEZE)
    direct = {(x["out"], x["in"]) for x in subs["direct"]}
    assert ("Kaedehara Kazuha", "Ineffa") not in direct
    assert ("Mona", "Citlali") not in direct
    citlali = [x for x in subs["rebuild"] if (x["out"], x["in"]) == ("Mona", "Citlali")]
    for x in citlali:  # if offered at all, it is a different team style, and it says why
        assert any("Freeze needs Hydro" in c for c in x["changes"])


@needs_account
def test_experimental_team_is_still_evaluable():
    s = _svc()
    r = s.evaluate_team(["Kamisato Ayaka", "Shenhe", "Chiori", "Escoffier"], substitutions=False)
    t = r["team"]
    assert r["legal"] and t["ceiling"]["expected"] > 0
    assert t["recommendability"]["level"] == "experimental"
    assert any("kit condition unmet" in x for x in t["recommendability"]["reasons"])


def _a(names, value, sd, level, actor):
    a = SimpleNamespace(team=SimpleNamespace(members=names), estimate=Estimate(value, sd, "C"), potential=value - 0.674 * sd,
                        label="", evaluation=SimpleNamespace(identity={"primary_actor": actor}, structure={}))
    return a, level


def test_experimental_enters_the_pool_only_beyond_the_uncertainty():
    adv = Advisor(ev=None)
    cred, lc = _a(["A", "B", "C", "D"], 50, 5, "credible", "A")
    close, l1 = _a(["A", "B", "C", "E"], 53, 5, "experimental", "A")  # within the uncertainty
    far, l2 = _a(["A", "B", "C", "F"], 80, 5, "experimental", "A")  # far beyond it
    lone, l3 = _a(["G", "H", "I", "J"], 30, 5, "experimental", "G")  # no credible team of its core
    unsup, l4 = _a(["A", "K", "L", "M"], 90, 5, "unsupported", "A")
    levels = {id(x): l for x, l in [(cred, lc), (close, l1), (far, l2), (lone, l3), (unsup, l4)]}
    adv.level = lambda a: levels[id(a)]
    adv.harmful = lambda a: False
    pool = adv.admit([unsup, far, close, cred, lone])
    assert cred in pool and far in pool and lone in pool
    assert close not in pool and unsup not in pool


@needs_account
def test_recommended_teams_cluster_near_duplicates():
    s = _svc()
    d = s.recommended_teams()
    cores = [t["core"] for t in d["teams"]]
    assert len(cores) == len(set(cores))
    assert sum(1 for t in d["teams"] if "Flins" in t["lineup"] and "Ineffa" in t["lineup"]) <= 2
    assert all(t["recommendability"]["level"] in ("established", "credible") or t.get("admitted_because") for t in d["teams"])
    assert "not_recommended" in d  # raw-model teams stay visible


@needs_account
def test_pull_headline_uses_a_recommendable_team():
    s = _svc()
    for name in ["Escoffier", "Columbina", "Mavuika"]:
        w = s.what_if(name)
        if w.get("best_team"):
            lvl = w["best_team"]["recommendability"]["level"]
            assert lvl in ("established", "credible") or s.advisor.admitted_reason(
                next(a for a in s.adv_cands if list(a.team.members) == w["best_team"]["lineup"]), s.cands)
    w = s.what_if("Escoffier")
    assert set(w["best_team"]["lineup"]) != {"Kamisato Ayaka", "Shenhe", "Chiori", "Escoffier"}


@needs_account
def test_pair_level_guide_evidence_is_not_full_team_proof():
    from gtc.advisor import listed_exactly, recommendability

    s = _svc()
    team = ["Kamisato Ayaka", "Shenhe", "Chiori", "Escoffier"]
    assert not listed_exactly(team, s.an.evidence)
    a = s.am.assess_lineup(team, s.roster)["assessment"]
    assert recommendability(a, s.an.evidence)["level"] != "established"


@needs_account
def test_account_gain_explanation_names_the_changed_team():
    s = _svc()
    w = s.what_if("Escoffier")
    changed = [c for c in w["plan_changes"] if c["changed"]]
    assert changed and all(c["before_value"] != c["after_value"] or c["before"] != c["after"] for c in changed)
    for c in w["plan_changes"]:
        if not c["changed"]:
            assert "unchanged" in c["text"]


def test_kit_conditions_are_detected_and_fitted():
    from gtc.kit_conditions import status, unmet
    from gtc.pairmodel import load

    assert unmet(["Kamisato Ayaka", "Shenhe", "Chiori", "Escoffier"]) == ["Escoffier"]
    assert unmet(["Skirk", "Escoffier", "Furina", "Citlali"]) == []
    assert status("Chevreuse", ["Chevreuse", "Raiden Shogun", "Bennett", "Kaedehara Kazuha"])["met"] is False
    pm = load()
    assert pm.conditions.get("Escoffier", 0) < 0 and pm.conditions.get("Chevreuse", 0) < 0
