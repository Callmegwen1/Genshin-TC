"""The forward model's own reaction model (rotation step 4), on synthetic hits: gauge theory, Melt / Vaporize
direction, Freeze and Shatter, multi-aura Swirl, Lunar-Charged ticks, and the ICD rule (no gauge, no reaction)."""
from gtc.forward.reactions import Auras, lunar_team, simulate
from gtc.forward.trace import Hit


def h(t, char, el, gauge=1.0, dt="skill"):
    return Hit(t=t, char=char, abil=f"{char} {dt}", damage_type=dt, element=el, mult=1.0, scaling="atk", gauge=gauge)


def test_gauge_decays_over_its_duration():
    a = Auras()
    a.apply("Pyro", 1.0)                 # 0.8 units over 9.5 s
    a.advance(9.0)
    assert a.has("Pyro")
    a.advance(9.6)
    assert not a.has("Pyro")


def test_melt_and_vaporize_directions():
    hits, c = simulate([h(0, "Ganyu", "Cryo"), h(1, "Bennett", "Pyro")], ["Ganyu", "Bennett", "Mona", "Sucrose"])
    assert [x.amp for x in hits] == ["", "melt"] and c["melt"] == 1          # Pyro on Cryo: forward
    hits, _ = simulate([h(0, "Xingqiu", "Hydro"), h(1, "Hu Tao", "Pyro")], ["Xingqiu", "Hu Tao", "Bennett", "Zhongli"])
    assert hits[1].amp == "vaporize"                                          # Pyro on Hydro: reverse


def test_no_gauge_no_reaction():
    hits, c = simulate([h(0, "Xingqiu", "Hydro"), h(1, "Hu Tao", "Pyro", gauge=0)], ["Xingqiu", "Hu Tao", "Bennett", "Zhongli"])
    assert hits[1].amp == "" and "vaporize" not in c


def test_freeze_shatter_and_swirl_as_cryo():
    team = ["Kamisato Ayaka", "Mona", "Kaedehara Kazuha", "Shenhe"]
    hits, c = simulate([h(0, "Mona", "Hydro"), h(0.5, "Kamisato Ayaka", "Cryo"), h(1.0, "Kaedehara Kazuha", "Anemo", dt="plunge")], team)
    assert c["freeze"] == 1 and c["shatter"] == 1                             # the plunge is blunt
    hits, c = simulate([h(0, "Mona", "Hydro"), h(0.5, "Kamisato Ayaka", "Cryo"), h(1.0, "Kaedehara Kazuha", "Anemo")], team)
    assert c.get("swirl-cryo") == 1                                           # Frozen swirls as Cryo


def test_swirl_reacts_with_coexisting_auras_and_lunar_ticks():
    team = ["Flins", "Aino", "Ineffa", "Sucrose"]
    assert lunar_team(team)
    hits, c = simulate([h(0, "Ineffa", "Electro"), h(0.5, "Aino", "Hydro"), h(4.0, "Ineffa", "Electro", gauge=0),
                        h(4.5, "Sucrose", "Anemo")], team)
    assert c["lunarcharged"] >= 1
    assert c.get("swirl-hydro") == 1 and c.get("swirl-electro") == 1
