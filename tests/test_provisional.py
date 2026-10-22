"""Phase 6.5: provisional kits for characters with no simulations."""
from functools import lru_cache

import pytest

from gtc import coverage, estimate, knowledge, provisional
from gtc.evaluate import lineup_power
from gtc.report import load_evidence


@lru_cache(maxsize=1)
def _ev():
    return load_evidence(knowledge.load())


def test_kits_are_loaded_and_marked_provisional():
    kb = knowledge.load()
    for name in ("Lohen", "Nefer", "Sandrone", "Vesna", "Zibai"):
        info = kb.characters[name]
        assert info.provisional and any(r.startswith("carry_") and r != "carry_unsimulated" for r in info.roles)
        assert provisional.kits()[name]["analogue"]


def test_a_listed_team_uses_prydwens_percentage_on_the_provisional_route():
    p = lineup_power(("Nefer", "Nahida", "Columbina", "Sucrose"), _ev())
    best, _ = provisional.anchor(_ev(), "Nefer")
    assert p.basis.route == "provisional_kit" and p.basis.tier == "E" and "provisional" in p.basis.flags
    assert p.expected == pytest.approx(best * 0.56, rel=1e-6)  # Prydwen: 56% of Nefer's best
    assert p.basis.sd_relative >= estimate._u("provisional", "sd", default=0.25)


def test_teams_far_from_every_listed_team_get_no_number():
    # Sandrone's kit needs Superconduct or Cryo Swirl; this team shares only her with Prydwen's teams.
    assert lineup_power(("Sandrone", "Shenhe", "Chiori", "Zhongli"), _ev()) is None


def test_simulated_characters_never_take_the_provisional_route():
    assert provisional.provisional_power(("Flins", "Ineffa", "Columbina", "Sucrose"), _ev()) is None


def test_provisional_teams_have_unknown_mechanics_coverage():
    from gtc.evaluate import Basis

    status, missing = coverage.lineup_coverage(("Nefer", "Lauma", "Columbina", "Sucrose"),
                                               Basis("provisional_kit", "E", 0.2), None)
    assert status == coverage.UNKNOWN and coverage.cap(0.95, status) == coverage.CAPS["unknown"]


def test_backtest_sd_covers_the_misses():
    m = estimate.load().get("provisional") or {}
    assert m.get("n", 0) >= 100
    assert 0.6 <= m["within_1sd"] <= 0.8 and m["within_2sd"] >= 0.85


def test_ifa_is_valued_from_his_own_simulations():
    kb = knowledge.load()
    assert not kb.characters["Ifa"].provisional
    assert any(r.startswith("support_") for r in kb.characters["Ifa"].roles)
    p = lineup_power(("Ifa", "Durin", "Faruzan", "Nicole"), _ev())
    assert p.basis.route == "exact_community"
