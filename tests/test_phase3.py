"""Phase 3: estimates with measured uncertainty, evidence tiers, the audit and hand-written kits."""
import pytest

from gtc.decision import compare_words
from gtc.estimate import Estimate, prob_greater, combine, worst_tier


def test_probability_and_wording():
    a, b = Estimate(80, 4, "B"), Estimate(70, 4, "B")
    assert prob_greater(a, b) > 0.9 and compare_words(a, b).startswith("likely better")
    c = Estimate(72, 8, "D")
    assert compare_words(c, b).startswith("roughly equivalent")


def test_combined_potential_takes_the_weaker_tier():
    e = combine(Estimate(80, 4, "B"), Estimate(90, 9, "D"))
    assert e.tier == "D" and abs(e.value - 72) < 1e-9 and e.sd > 72 * 0.1
    assert worst_tier(["B", "E", "C"]) == "E"


def test_custom_kit_places_an_unsimulated_character(tmp_path):
    from gtc import knowledge
    kb = knowledge.load()
    folder = tmp_path / "kits_custom"
    folder.mkdir()
    (folder / "nefer.yaml").write_text("Nefer:\n  element: Dendro\n  expected_archetypes:\n    auto_bloom_dendro_carry: {as: carry, quality: 4}\n",
                                       encoding="utf-8")
    knowledge._apply_custom_kits(tmp_path, kb.characters, kb.templates)
    info = kb.characters["Nefer"]
    assert info.custom_kit and "carry_unsimulated" not in info.roles
    assert info.roles[kb.templates["auto_bloom_dendro_carry"].slots[0].roles[0]] == 4


@pytest.mark.skipif(not __import__("gtc.estimate", fromlist=["x"]).UNCERTAINTY_PATH.exists(), reason="needs derive")
def test_measured_tiers_are_ordered_and_calibrated():
    from gtc import estimate
    u = estimate.load()
    single, near, far = u["B"]["sd_single"], u["pair"]["near"]["sd"], u["pair"]["far"]["sd"]
    # B (median of n >= 2 submissions) < C (pair model next to a simulation) < D (further away). The swap estimate
    # and its tier were deleted in phase 10.
    assert estimate.community_sd(single, 2) < near < far
    d = u["pair"]["near"]
    assert 0.6 <= d["within_1sd"] <= 0.76 and d["within_2sd"] >= 0.88


def test_audit_has_no_unexplained_findings():
    from gtc import audit
    flagged = [a for a in audit.run() if a.findings]
    assert not flagged, [(a.name, a.findings) for a in flagged]
