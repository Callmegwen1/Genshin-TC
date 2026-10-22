"""Prerelease-style theorycrafting (rotation step 6): a character built only from Amber data and a hand-written kit
file (knowledge/forward/prerelease/), never from community simulations."""
import pytest

from gtc.sim import GCSIM

needs_gcsim = pytest.mark.skipif(not GCSIM.exists(), reason="local gcsim binary missing")


def test_hand_kit_uses_amber_numbers_and_no_simulations():
    from gtc.forward import data as D
    from gtc.forward.library import load_hand

    lib = load_hand("Lohen")
    assert lib is not None and lib.hand and lib.sources == ["kit file"]
    assert lib.actions["etched"].hits[0].mult == pytest.approx(D.value("Lohen", "skill", "Etched Into Bone and Soul DMG"))
    assert len(lib.actions["burst"].hits) == 6
    assert set(lib.facts) == {"known", "assumed", "unknown"} and lib.facts["unknown"]


def test_states_specials_and_level_bonus():
    from gtc.forward.build import house_builds
    from gtc.forward.generator import _Sim
    from gtc.forward.library import load_hand

    team = ["Lohen", "Shenhe", "Mona", "Fischl"]
    libs = {"Lohen": load_hand("Lohen")}
    sim = _Sim(team, libs, house_builds(team, {m: 3.0 for m in team}))
    assert not sim.can("Lohen", "etched")                    # needs Masterstroke
    sim.act("Lohen", "skill")
    assert sim.state("Lohen", sim.t)["name"] == "masterstroke"
    assert [sim.act("Lohen", "etched") for _ in range(4)] == [True, True, True, False]   # at most 3 per Masterstroke
    lvl9 = libs["Lohen"].actions["etched"].hits[0].mult
    assert sim.hits[0].mult > lvl9                            # High Spirits: Skill level +1 for 9 s


def test_needs_are_read_from_the_kit():
    from gtc.forward.teamgen import needs, supplies

    n = needs("Lohen")
    assert n["element"] == "Cryo" and "freeze" in n["reactions"] and n["factions"].get("hexerei") == 2
    assert "buffs" in supplies("Shenhe", n) and "faction:hexerei" in supplies("Fischl", n)
