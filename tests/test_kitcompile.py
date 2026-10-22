"""Offline kit compiler (phases M6 to M8): packets, response checks, reference scoring, and how compiled kits are used."""
import copy

from gtc import kitcompile as C
from gtc import kits as K


def _escoffier():
    return copy.deepcopy(K.reviewed_kits()["Escoffier"])


def test_packets_hold_the_text_but_never_the_target_kit():
    p = C.packet("Escoffier")
    assert "Inspiration-Immersed Seasoning" in p          # the official text
    assert "Escoffier:\n  schema: 3" not in p             # never the target's own reviewed kit
    assert C.examples_for("Escoffier") == ["Bennett", "Xingqiu"]
    assert "Response path" in p and "escoffier.yaml" in p


def test_ungrounded_effects_are_dropped():
    k = _escoffier()
    k["effects"].append({"kind": "crit_dmg", "target": "party", "affects": {"elements": ["all"]}, "amount": 0.4,
                         "duration": 10, "stacking": "none", "conditions": [], "source": "Imaginary Talent"})
    k["effects"].append({"kind": "atk_pct", "target": "party", "affects": {"elements": ["all"]}, "amount": 0.37,
                         "duration": 10, "stacking": "none", "conditions": [], "source": "Inspiration-Immersed Seasoning"})
    out, errors, notes = C.check("Escoffier", k)
    assert not errors
    assert len(out["effects"]) == len(_escoffier()["effects"])
    assert any("Imaginary Talent" in n for n in notes) and any("0.37 not in the text" in n for n in notes)


def test_measurements_override_contradicting_behaviour_and_provenance_is_pending():
    k = _escoffier()
    k["behavior"]["on_field_damage"] = True
    k["behavior"]["field_time"] = "high"
    out, errors, notes = C.check("Escoffier", k)
    assert not errors and out["behavior"]["on_field_damage"] is False
    assert any("on_field_damage" in n for n in notes) and any("field_time" in n for n in notes)
    assert all(p["method"] == "llm_extracted" and p["reviewed"] == "pending" and p["confidence"] != "high"
               for p in out["provenance"].values())


def test_reference_scoring_is_perfect_on_itself_and_sees_differences():
    r = K.reviewed_kits()["Shenhe"]
    s = C.score(r, r)
    assert s["effect_recall"] == s["effect_precision"] == 1.0 and s["kit_conditions"] and s["on_field_damage"]
    c = copy.deepcopy(r)
    c["effects"] = c["effects"][:2]
    assert C.score(c, r)["effect_recall"] < 1.0 and C.score(c, r)["effect_precision"] == 1.0


def test_acceptance_gate():
    good = {"characters": 17, "valid": 17, "on_field_damage": 1.0, "kit_conditions": 0.9, "effect_recall": 0.8,
            "buff_recall": 0.9, "buff_precision": 0.8, "numeric_amounts": 0.9, "burst_cost": 1.0}
    assert C.accepted(good)[0]
    assert not C.accepted({**good, "valid": 15})[0]
    assert not C.accepted({**good, "buff_precision": 0.5})[0]


def test_scaling_tables_ground_numbers():
    assert "Energy Cost: 60" in C.kit_text("Bennett")
    assert C._number_in_text(1.008, C.kit_text("Bennett"))      # ATK Bonus Ratio 100.8% at talent level 10
    assert not C._number_in_text(0.37, C.kit_text("Bennett"))


def test_kit_priority_and_compiled_kits_never_feed_power_conditions():
    from gtc.kit_conditions import conditions

    for n, k in K.compiled_kits().items():
        assert n not in K.reviewed_kits()                  # reviewed always wins; never compiled over it
        assert K.kit(n) is k and k["compiled"]
        assert all(p["reviewed"] == "pending" and p["method"] == "llm_extracted" for p in k["provenance"].values())
        assert K.validate(n, k) == []
    legacy_or_reviewed = set(K.reviewed_kits()) | {"Gorou", "Escoffier", "Chevreuse", "Nilou"}
    assert set(conditions()) <= legacy_or_reviewed


def test_kit_coverage_separates_reviewed_compiled_and_derived():
    from gtc.team_mechanics import analyse

    cov = analyse(["Chiori", "Escoffier", "Zhongli", "Albedo"]).kit_coverage
    assert cov["reviewed"] == ["Chiori", "Escoffier"]
    if K.compiled_kits().get("Zhongli"):
        assert "Zhongli" in cov["compiled"] and "Zhongli" not in cov["reviewed"]
