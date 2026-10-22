"""Game-wide knowledge: carry assignment, archetype naming, role extraction from talent text."""
from gtc.derive import family_of, sustain_and_shred
from gtc.evidence import assign_carry, role_categories

CATS = {"Flins": {"DPS"}, "Columbina": {"DPS", "Sub-DPS"}, "Ineffa": {"Sub-DPS"}, "Sucrose": {"Support"},
        "Kamisato Ayato": {"Driver"}, "Skirk": {"DPS"}, "Kamisato Ayaka": {"DPS", "Sub-DPS"}}


def test_carry_assignment():
    assert assign_carry(["Flins", "Columbina", "Ineffa", "Sucrose"], CATS) == "Flins"      # the one pure DPS
    assert assign_carry(["Columbina", "Ineffa", "Kamisato Ayato", "Sucrose"], CATS) == "Columbina"  # drivers do not carry
    assert assign_carry(["Skirk", "Flins", "Sucrose", "Ineffa"], CATS) is None             # two pure DPS: ambiguous
    assert assign_carry(["Kamisato Ayato", "Ineffa", "Sucrose"], CATS) == "Kamisato Ayato"  # a driver carries if nobody else can


def test_driver_tag_becomes_driver():
    pry = {"tiers": {"Kamisato Ayato": [{"category": "DPS", "tags": ["driver"]}], "Flins": [{"category": "DPS", "tags": ["comfort"]}]}}
    cats = role_categories(pry)
    assert cats == {"Kamisato Ayato": {"Driver"}, "Flins": {"DPS"}}


def test_families_follow_the_carry():
    assert family_of(["Pyro", "Hydro", "Anemo", "Pyro"], "Pyro", False)[:2] == ("Vaporize (Pyro carry)", "vaporize_pyro")
    assert family_of(["Hydro", "Pyro", "Anemo", "Geo"], "Hydro", False)[:2] == ("Vaporize (Hydro carry)", "international")
    assert family_of(["Electro", "Hydro", "Electro", "Anemo"], "Electro", True)[:2] == ("Lunar-Charged (Electro carry)", "lunar_charged")
    # Moonsign teammates do not make a Pyro carry's team Lunar-Charged.
    assert family_of(["Pyro", "Electro", "Hydro", "Anemo"], "Pyro", True)[0] == "Vaporize (Pyro carry)"
    assert family_of(["Anemo", "Anemo", "Hydro", "Pyro"], "Anemo", False)[0] == "Anemo carry"
    assert family_of(["Pyro", "Pyro", "Geo", "Pyro"], "Pyro", False)[0] == "Mono Pyro"


def test_talent_text_roles():
    assert sustain_and_shred("Restores HP to all party members and creates a shield.") == {"healer": 3, "shield": 3}
    assert "res_shred" in sustain_and_shred("Opponents' Cryo RES is decreased by 40%.")
    assert sustain_and_shred("Deals Pyro DMG.") == {}
