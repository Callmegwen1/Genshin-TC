"""Phase 8: identity from measurements, independent of the generating template."""
from functools import lru_cache

from gtc import identity, knowledge
from gtc.report import load_evidence


@lru_cache(maxsize=1)
def _ev():
    return load_evidence(knowledge.load())


def _id(*names):
    identity._CACHE.clear()
    return identity.identify(names, _ev())


def test_freeze_is_central_without_any_freeze_damage():
    i = _id("Kamisato Ayaka", "Shenhe", "Kaedehara Kazuha", "Mona")
    assert "freeze" in i["central"] and i["primary_actor"] == "Kamisato Ayaka"
    assert "reaction_damage" not in i["signals"]["freeze"] and i["signals"]["freeze"]["aura_at_hit"] > 0.3


def test_vaporize_is_central_through_the_carrys_amplified_hits():
    i = _id("Hu Tao", "Xingqiu", "Yelan", "Zhongli")
    assert "vaporize" in i["central"] and i["signals"]["vaporize"]["carry_amplified"] > 0.4
    assert i["owners"]["vaporize"] == ["Hu Tao"]


def test_a_conditioned_buffer_is_tracked_and_is_not_the_primary_actor():
    i = _id("Chevreuse", "Xiangling", "Raiden Shogun", "Yae Miko")
    assert "overloaded" in i["central"] and i["primary_actor"] != "Chevreuse"
    assert "conditioned_buffs" in i["signals"]["overloaded"]


def test_raiden_hyperbloom_is_a_raiden_team_with_incidental_hyperbloom():
    i = _id("Raiden Shogun", "Kaedehara Kazuha", "Xingqiu", "Yaoyao")
    assert i["primary_actor"] == "Raiden Shogun" and "hyperbloom" in i["incidental"]
    assert i["label"].startswith("Raiden Shogun") and "incidental Hyperbloom" in i["label"]


def test_lunar_charged_belongs_to_the_moonsign_members():
    i = _id("Clorinde", "Columbina", "Ineffa", "Kaedehara Kazuha")
    assert "lunar_charged" in i["central"] and "Clorinde" not in i["owners"]["lunar_charged"]
    assert "Lunar-Charged from Columbina and Ineffa" in i["label"]


def test_unsimulated_lineups_only_learn_from_neighbours_with_the_same_element_holders():
    # Raiden / Kazuha / Xingqiu / Nahida teams must not give a Yaoyao team their Quicken.
    i = _id("Raiden Shogun", "Kaedehara Kazuha", "Xingqiu", "Yaoyao")
    assert i["source"] == "predicted" and "quicken" not in i["central"] and "aggravate" not in i["central"]


def test_identity_is_the_same_whichever_template_generated_the_lineup():
    from test_evaluation import _evaluations

    evals = _evaluations(["Nahida", "Kuki Shinobu", "Xingqiu", "Yelan"])
    assert len({e.generated_by for e in evals}) >= 2
    assert len({e.identity["label"] for e in evals}) == 1
    assert len({e.identity["primary_actor"] for e in evals}) == 1
