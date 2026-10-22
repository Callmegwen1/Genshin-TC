"""Phase 5: data levels, artifact quality, AoE, content modes, Energy Recharge reality, generated kits."""
import pytest

from gtc import SNAPSHOT_DIR


def test_basic_import_never_claims_a_spare_weapon_is_missing():
    from gtc.account import weapon_note

    class G:
        def weapons(self, name):
            return [("Mistsplitter Reforged", "", "")]

    note = weapon_note("Kamisato Ayaka", G(), [], {}, {"Kamisato Ayaka": {"weapon": "Sword"}}, data_level="basic")
    assert "none of the weapons" not in note.lower() and "not imported" in note
    full = weapon_note("Kamisato Ayaka", G(), [], {}, {"Kamisato Ayaka": {"weapon": "Sword"}}, data_level="full")
    assert "own none" in full


def test_artifact_weights_follow_priority_and_cap_energy_recharge():
    from types import SimpleNamespace
    from gtc.artifacts import rate
    from gtc.snapshot import Artifact
    kqm = {"substat_priority": {"tiers": [["enerRech_"], ["critRate_", "critDMG_"], ["atk_"]]},
           "er_requirements": [{"rows": [{"values": [[120, 130]]}]}]}
    arts = [Artifact(1, "x", 5, 20, "hp", 4780, [{"key": "critRate_", "value": 3.305 * 4}, {"key": "enerRech_", "value": 5.505 * 4}])]
    lots_of_er = SimpleNamespace(artifacts=arts, stats={"energy_recharge": 200.0})
    q = rate(lots_of_er, kqm)
    assert abs(q.useful_rolls - 3.4) < 0.05  # 4 crit rolls at 0.85; ER beyond the 120% requirement is wasted
    needs_er = SimpleNamespace(artifacts=arts, stats={"energy_recharge": 110.0})
    assert rate(needs_er, kqm).useful_rolls > q.useful_rolls


@pytest.mark.skipif(not __import__("gtc.aoe", fromlist=["x"]).AOE_PATH.exists(), reason="needs python -m gtc aoe")
def test_aoe_carries_rank_above_single_target_carries():
    from gtc.aoe import character_ratio
    aoe_carries = [character_ratio(n)[0] for n in ("Xiangling", "Nahida", "Raiden Shogun")]
    single = [character_ratio(n)[0] for n in ("Eula", "Kamisato Ayaka")]
    assert min(aoe_carries) > max(single)


def test_narrow_super_carry_account_wins_stygian_and_loses_theater():
    from gtc import benchmark, gamedata, profiles
    am = benchmark.engine()
    el = {n: g["element"] for n, g in gamedata.load_characters().items()}
    narrow = ["Neuvillette", "Furina", "Kaedehara Kazuha", "Zhongli", "Amber", "Kaeya", "Lisa", "Noelle"]
    broad = ["Xiangling", "Bennett", "Xingqiu", "Fischl", "Beidou", "Sucrose", "Chongyun", "Diona", "Barbara", "Noelle",
             "Ningguang", "Kaeya", "Lisa", "Razor", "Kujou Sara", "Yanfei", "Thoma", "Collei", "Dori", "Layla", "Kuki Shinobu", "Rosaria"]
    score = {}
    for label, names in (("narrow", narrow), ("broad", broad)):
        _, cands = am.plan(benchmark.roster(am, names))
        score[label] = {p: v.score for p, v in profiles.all_plans(cands, el).items()}
    assert score["narrow"]["stygian"] > score["broad"]["stygian"]
    assert score["broad"]["theater"] > score["narrow"]["theater"]


def test_burst_guard_rewrites_only_rotation_bursts():
    from gtc.sim import guard_bursts
    text = ('xq char lvl=90/90 cons=6;\nxq add weapon="sacrificialsword" refine=5;\nwhile 1 {\n'
            '  ayaka skill, burst, attack:2;\n  xq burst[hold=1]; # note\n  ayaka dash;\n}\n')
    out = guard_bursts(text, ["xq", "ayaka"])
    assert 'xq add weapon="sacrificialsword" refine=5;' in out and "xq char lvl=90/90 cons=6;" in out
    assert "if .ayaka.burst.ready { ayaka burst; }" in out and "ayaka skill;" in out and "ayaka attack:2;" in out
    assert "if .xq.burst.ready { xq burst[hold=1]; }" in out and "# note" in out
    assert "ayaka dash;" in out and out.count("burst.ready") == 4  # two waits and two guards


def test_generated_kits_are_overridden_by_hand_written_ones():
    from gtc.kitgen import KITS_AUTO_PATH
    from gtc.tc.engine import load_kits
    if not KITS_AUTO_PATH.exists():
        pytest.skip("needs python -m gtc kits")
    hand, merged = load_kits(generated=False), load_kits()
    assert merged["Furina"] == hand["Furina"]  # hand-written wins
    assert any(e["kind"] == "res_shred" and e["element"] == "Pyro" for e in merged["Chevreuse"]["effects"])
