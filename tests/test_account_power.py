"""Phase 11: MetaPower, CurrentPower and AccountCeiling."""
import json
from types import SimpleNamespace

import pytest

from gtc import account_power as ap


def _inv(level=1.0, talents=1.0, weapon=1.0, artifacts=1.0):
    return SimpleNamespace(level=level, talents=talents, weapon=weapon, artifacts=artifacts)


def test_a_fully_built_character_has_factor_one():
    f = {"gamma": {"level": 2.0, "talents": 0.5, "weapon": 1.5, "artifacts": 1.0}, "rho": 1.5}
    assert ap.character_factor(_inv(), f) == (1.0, 1.0)
    own, buff = ap.character_factor(_inv(artifacts=0.2), f)
    assert own < 1.0 and buff < own


def test_buffs_rescale_the_carrys_damage_instead_of_adding_a_share():
    """Double-counting guard: a support's buff factor only touches the part of the carry's damage it makes."""
    own = {"Carry": 0.9, "Support": 0.1}
    buffs = {"Support": {"Carry": 0.3}}  # 30% of the carry's damage comes from the support's buffs
    full = ap.team_factor(own, buffs, {"Carry": (1.0, 1.0), "Support": (1.0, 1.0)})
    assert full == pytest.approx(1.0)
    weak_support = ap.team_factor(own, buffs, {"Carry": (1.0, 1.0), "Support": (0.5, 0.5)})
    # carry loses 30% x half = 15% of its 90%; the support's own 10% halves: 0.9 x 0.85 + 0.1 x 0.5
    assert weak_support == pytest.approx(0.9 * 0.85 + 0.05)
    assert weak_support > 0  and weak_support < full


def test_unknown_constellations_are_flagged_not_assumed_neutral():
    f, sd, status = ap.constellation_factor("Nobody Simulated", 2, 5)
    assert f == 1.0 and sd > 0 and status == "constellation effect unknown"
    assert ap.constellation_factor("Anyone", 0, 5) == (1.0, 0.0, "standard")
    assert ap.constellation_factor("Anyone", 6, 4)[2] == "standard"


def test_measured_constellations_use_same_lineup_comparisons():
    # Bennett below C6: dozens of same-lineup comparisons against his standard C6, near 1.0.
    f, sd, status = ap.constellation_factor("Bennett", 5, 4)
    assert status.startswith("measured") and 0.9 <= f <= 1.1 and sd < ap.UNKNOWN_CONS_SD


@pytest.mark.skipif(not ap.CALIBRATION_PATH.exists(), reason="needs python -m gtc account --calibrate")
def test_the_build_model_is_calibrated_on_personal_simulations():
    f = json.loads(ap.CALIBRATION_PATH.read_text(encoding="utf-8"))
    assert f["teams"] >= 10
    assert f["loo_median_abs"] < f["no_model_median_abs"]  # far better than ignoring builds
    assert 0.55 <= f["within_1sd"] <= 0.85
