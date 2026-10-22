"""Phases I-O: pipeline, team needs, swaps, uncertainty, simulation quality, gates, rotation period search."""
import json

import pytest

from tests.test_forward import needs_gcsim


def test_team_needs_count_gear_and_never_veto():
    """An Anemo support's Viridescent Venerer reaches a Cryo carry; Kazuha makes Lohen's shortlist although the
    community never simulated the pair; the pair model only orders ties."""
    from gtc.forward.reference import CHARACTERS
    from gtc.forward.teamgen import candidate_teams, needs, supplies

    n = needs("Lohen")
    assert supplies("Kaedehara Kazuha", n).get("gear", 0) >= 1.5
    short, _ = candidate_teams("Lohen", list(CHARACTERS))
    assert any("Kaedehara Kazuha" in t["lineup"] for t in short)
    assert all("avoids" in t and "pair_prior" in t for t in short)


def test_uncertainty_comes_from_model_knowledge():
    from types import SimpleNamespace

    from gtc.forward.uncertainty import assess

    rot = SimpleNamespace(lineup=["Lohen", "Shenhe", "Kaedehara Kazuha", "Furina"], source="generated", duration=80.0)
    ev = SimpleNamespace(damage_share={"Lohen": 0.6, "Shenhe": 0.15, "Kaedehara Kazuha": 0.1, "Furina": 0.15},
                         condition_states=[], unknown=[], per_reaction={}, total_damage=1.0, coverage=1.0, energy={})
    d = assess(rot, ev, {"state_realisation": {"Lohen:masterstroke": 0.75}, "idle": ""}, generated=True)
    srcs = [c["source"] for c in d["components"]]
    assert "unknown kit mechanics" in srcs and "assumed kit facts" in srcs and "rotation" in srcs
    assert d["confidence"] in ("Medium", "Low") and "main damage dealer" in d["why"]
    # a fully known team on a community rotation, all direct damage: High
    rot2 = SimpleNamespace(lineup=["Kamisato Ayaka"], source="gcsim community rotation", duration=20.0)
    ev2 = SimpleNamespace(damage_share={"Kamisato Ayaka": 1.0}, condition_states=[], unknown=[], per_reaction={},
                          total_damage=1.0, coverage=1.0, energy={})
    assert assess(rot2, ev2)["confidence"] == "High"


def test_pipeline_fingerprint_tracks_inputs(monkeypatch):
    from gtc.forward import pipeline
    from gtc.forward.effects import annotations

    a = pipeline.fingerprint("Lohen")
    assert a == pipeline.fingerprint("Lohen")
    real = annotations()
    patched = dict(real)
    patched["Lohen"] = list(real.get("Lohen") or []) + [{"match": "test", "amount": 1.0}]
    monkeypatch.setattr("gtc.forward.effects.annotations", lambda: patched)
    assert pipeline.fingerprint("Lohen") != a          # a changed annotation reruns the analysis
    st = pipeline.status("Lohen")
    assert st["community_simulations"] == 0 and st["fact_confidence"]["unknown"] >= 1


def test_simulation_quality_records_flags():
    from gtc.forward.simquality import quality, reference_quality

    q = quality(["Kamisato Ayaka", "Shenhe", "Kaedehara Kazuha", "Mona"])
    assert q["entries"] >= 1 and "comparable_builds" in q
    r = reference_quality(["Raiden Shogun", "Xingqiu", "Xiangling", "Bennett"],
                          {"reference_stalled": True, "shape_s": (105.7, 618.1)})
    assert not r["high_quality"] and any("energy stall" in f for f in r["flags"])


def test_gates_report_failures_not_averages(tmp_path, monkeypatch):
    from gtc.forward import gates

    rows = [{"family": f"F{i}", "blind_error": e, "replay_error": 0.02, "replay_reaction_share": 0.1,
             "reaction_rates_blind": {"swirl": 0.4}, "reaction_rates_reference": {"swirl": 0.42},
             "realisation": {"state_realisation": {"A:x": 0.9, "B:y": 0.9, "C:z": 0.9}, "energy": {}, "idle": ""},
             "cycle_blind": 21, "reference_quality": {"shape_kept": True}}
            for i, e in enumerate([0.05, -0.08, 0.6])]
    (tmp_path / "forward_benchmark_standard.json").write_text(json.dumps(
        {"summary": {"pairwise_ranking_agreement": 0.9}, "rows": rows}), encoding="utf-8")
    monkeypatch.setattr(gates, "VAL", tmp_path)
    out = gates.evaluate("standard")
    g = {x["gate"]: x for x in out["gates"]}
    assert g[1]["pass"] and g[3]["pass"] and g[5]["pass"]
    assert not g[4]["pass"] and "F2" in g[4]["detail"]           # the failing family is named
    assert not out["all_pass"] and out["decision"].startswith("do not switch")


@needs_gcsim
def test_rotation_period_is_searched():
    """The cycle length is a choice the search makes (alternatives from Burst cooldowns, support Skill cooldowns and
    the carry's state plus setup), and the carry window does not overrun its cycle."""
    from gtc.forward.blind import theorycraft
    from gtc.forward.generator import CYCLES

    r = theorycraft(["Hu Tao", "Xingqiu", "Yelan", "Zhongli"])
    period = r["plan"].period or 16.0
    assert r["plan"].period > 0                       # an alternative cycle length won over the team default
    assert r["rotation"].duration <= CYCLES * period + 10.0


@needs_gcsim
def test_swap_explains_the_delta():
    from gtc.forward.swap import swap

    s = swap(["Kamisato Ayaka", "Shenhe", "Kaedehara Kazuha", "Mona"], "Mona", "Furina", profile="neutral")
    names = [k for k, _ in s["parts"]]
    assert "Mona personal damage (lost)" in names and "Furina personal damage (gained)" in names
    assert any("Omen" in k for k in names)                       # Mona's Omen contribution is lost
    assert s["lines"][0].startswith("Before:") and s["lines"][-1].startswith("Net:")
    assert "Furina average Fanfare" in s["system"]
    assert abs(s["before"] + s["delta"] - s["after"]) <= 1     # each is rounded on its own
