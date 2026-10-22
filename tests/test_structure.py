"""Phase 7: probabilistic damage structure."""
import pytest

from gtc import estimate, structure


def _est(damage, field, reaction=0.0, noise=None):
    ms = sorted(damage)
    return structure.estimate(ms, damage, field, reaction, noise or structure.prediction_noise(), "predicted")


def test_probabilities_are_a_distribution_and_deterministic():
    a = _est({"A": 0.6, "B": 0.2, "C": 0.1, "D": 0.1}, {"A": 0.7, "B": 0.1, "C": 0.1, "D": 0.1})
    b = _est({"A": 0.6, "B": 0.2, "C": 0.1, "D": 0.1}, {"A": 0.7, "B": 0.1, "C": 0.1, "D": 0.1})
    assert sum(a["probabilities"].values()) == pytest.approx(1.0)
    assert sum(a["primary"].values()) == pytest.approx(1.0)
    assert a == b


def test_near_a_threshold_both_types_keep_probability():
    # One member at 54%: just under the 55% hypercarry line, second at 25%: on the dual-carry line.
    st = _est({"A": 0.54, "B": 0.25, "C": 0.11, "D": 0.10}, {"A": 0.6, "B": 0.2, "C": 0.1, "D": 0.1})
    p = st["probabilities"]
    assert p["hypercarry"] > 0.2 and p["dual_carry"] > 0.2


def test_a_clear_hypercarry_is_confident_and_on_field():
    st = _est({"A": 0.85, "B": 0.05, "C": 0.05, "D": 0.05}, {"A": 0.8, "B": 0.07, "C": 0.07, "D": 0.06})
    assert st["type"] == "hypercarry" and st["probabilities"]["hypercarry"] > 0.9
    assert st["primary"]["A"] > 0.95 and st["patterns"]["on_field_carry"] > 0.9 and st["patterns"]["quickswap"] < 0.1


def test_measured_structures_keep_their_label_and_stay_sharp():
    prof = {"members": {"A": {"damage_share": 0.7, "field_share": 0.6}, "B": {"damage_share": 0.1, "field_share": 0.2},
                        "C": {"damage_share": 0.1, "field_share": 0.1}, "D": {"damage_share": 0.1, "field_share": 0.1}},
            "reaction_share": 0.0, "structure": {"type": "hypercarry", "owners": ["A"]}}
    st = structure.from_profile(["A", "B", "C", "D"], prof)
    assert st["type"] == "hypercarry" and st["source"] == "measured" and st["probabilities"]["hypercarry"] > 0.99


def test_held_out_probabilities_are_calibrated_and_beat_the_single_label():
    s = estimate.load().get("structure") or {}
    h, hard = s["held_out"], s["hard_labels_held_out"]
    assert h["n"] > 1000
    assert h["type_calibration_error"] < 0.05
    assert h["type_log_loss"] < hard["type_log_loss"] and h["type_brier"] < hard["type_brier"]
    assert h["type_accuracy"] >= hard["type_accuracy"]
