"""Phase 13: provisional kit schema v2, evidence states, provisional supports, restrictions, supersession, audit."""
import copy
from functools import lru_cache

from gtc import estimate, kit_schema, knowledge, provisional
from gtc.evaluate import lineup_power
from gtc.pairmodel import load
from gtc.report import load_evidence


@lru_cache(maxsize=1)
def _ev():
    return load_evidence(knowledge.load())


def test_every_provisional_kit_is_valid_schema_2_with_provenance():
    pm = load()
    ks = provisional.kits()
    assert {"Alyosha", "Iansan", "Illuga", "Kachina", "Linnea", "Odette", "Vodyanitsa",
            "Lohen", "Nefer", "Sandrone", "Vesna", "Zibai"} <= set(ks)
    for name, kit in ks.items():
        assert kit_schema.validate(name, kit, pm.chars) == [], name


def test_validation_catches_missing_provenance_and_unknown_vocabulary():
    kit = copy.deepcopy(provisional.kits()["Iansan"])
    kit["provenance"] = {"buffs": kit["provenance"]["*"]}
    kit["buffs"][0]["kind"] = "vibes"
    kit["preferred_systems"] = ["stellar_conduct"]
    errs = " | ".join(kit_schema.validate("Iansan", kit, load().chars))
    assert "no provenance for `field`" in errs and "kind 'vibes'" in errs and "unknown reaction 'stellar_conduct'" in errs


def test_evidence_states_cover_the_four_kinds():
    ev = _ev()
    assert lineup_power(("Mavuika", "Citlali", "Xilonen", "Bennett"), ev).basis.evidence_state == "simulation"
    assert lineup_power(("Mavuika", "Citlali", "Iansan", "Bennett"), ev).basis.evidence_state == "kit-model"
    assert kit_schema.evidence_state("pair_model") == "interpolation"
    assert kit_schema.evidence_state("role_rules") == "rules-only"


def test_a_provisional_support_is_scaled_from_a_simulated_carrys_prydwen_page():
    p = lineup_power(("Mavuika", "Citlali", "Iansan", "Bennett"), _ev())
    assert p.basis.route == "provisional_kit" and p.basis.tier == "E" and "provisional" in p.basis.flags
    assert "Mavuika page" in p.basis.sources[1]
    assert p.basis.sd_relative >= estimate._u("pair", "far", "sd", default=estimate._FALLBACK["far"])


def test_a_provisional_support_off_every_page_stands_in_through_its_analogue():
    p = lineup_power(("Navia", "Kachina", "Bennett", "Xiangling"), _ev())
    assert p.basis.route == "provisional_kit" and "Albedo for Kachina" in p.basis.sources[1]
    assert p.basis.sd_relative >= estimate._u("provisional", "support", "sd", default=0.2)


def test_a_broken_restriction_gives_no_number_and_says_why():
    ev = _ev()
    team = ("Sandrone", "Shenhe", "Chiori", "Zhongli")
    assert lineup_power(team, ev) is None
    assert "needs an Electro or Anemo teammate" in provisional.declined(ev, team)


def test_simulations_supersede_the_kit(monkeypatch):
    """Once the pair model knows the character, the provisional route no longer runs for them."""
    import gtc.pairmodel as pairmodel

    pm = load()
    fake = copy.copy(pm)
    fake.chars = set(pm.chars) | {"Iansan"}
    monkeypatch.setattr(pairmodel, "load", lambda: fake)
    assert provisional.provisional_power(("Mavuika", "Citlali", "Iansan", "Bennett"), _ev()) is None


def test_the_audit_flags_a_kit_still_in_use_after_simulations_exist(monkeypatch):
    import gtc.pairmodel as pairmodel
    from gtc import audit

    pm = load()
    fake = copy.copy(pm)
    fake.chars = set(pm.chars) | {"Odette"}
    monkeypatch.setattr(pairmodel, "load", lambda: fake)
    monkeypatch.setattr(audit, "load_pairs", lambda: fake, raising=False)
    odette = next(a for a in audit.run() if a.name == "Odette")
    assert any("provisional kit is stale" in f for f in odette.findings)


def test_the_support_backtest_covers_its_misses():
    u = estimate._u("provisional", default={})
    for path in ("page_ratio", "support"):
        assert u[path]["n"] >= 10 and u[path]["within_2sd"] >= 0.9
