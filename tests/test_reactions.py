"""gtc/reactions.py: the derived views must equal the literal constants they replaced (phase 6)."""
from gtc import reactions as R


def test_transformative_and_catalyze_coefficients():
    assert R.TRANSFORMATIVE == {"hyperbloom": 3.0, "burgeon": 3.0, "bloom": 2.0, "overload": 2.75, "overloaded": 2.75,
                                "electrocharged": 2.0, "superconduct": 1.5, "shatter": 3.0, "burning": 0.25,
                                "swirl-pyro": 0.6, "swirl-hydro": 0.6, "swirl-electro": 0.6, "swirl-cryo": 0.6}
    assert R.CATALYZE == {"aggravate": 1.15, "spread": 1.25}
    assert R.LUNAR_MULT == {"lunar_charged": 3.0, "lunar_crystallize": 1.6}


def test_enablement_facts():
    assert R.AMP_AURA == {("vaporize", "pyro"): "hydro", ("vaporize", "hydro"): "pyro", ("melt", "pyro"): "cryo",
                          ("melt", "cryo"): "pyro"}
    assert R.REACTION_AURAS == {"overload": ("pyro", "electro"), "overloaded": ("pyro", "electro"),
                                "electrocharged": ("hydro", "electro"), "superconduct": ("cryo", "electro"),
                                "burning": ("pyro", "dendro", "burning"), "bloom": ("hydro", "dendro"),
                                "swirl-pyro": ("pyro",), "swirl-hydro": ("hydro",), "swirl-electro": ("electro",),
                                "swirl-cryo": ("cryo",), "shatter": ("frozen",)}
    assert R.CORE_REACTIONS == {"hyperbloom", "burgeon"}


def test_theory_guard_views():
    assert R.AMPLIFYING_SUFFIXES == {"vaporize": "vaporize", "melt": "melt"}
    assert R.CATALYZE_SUFFIXES == {"aggravate": "aggravate", "spread": "spread"}
    assert R.REACTION_SOURCES == {
        "overload": "overloaded", "overloaded": "overloaded", "electrocharged": "electro_charged", "superconduct": "superconduct",
        "shatter": "shatter", "burning": "burning", "bloom": "bloom", "hyperbloom": "hyperbloom", "burgeon": "burgeon",
        "lunarcharged": "lunar_charged", "lunarcrystallize": "lunar_crystallize", "lunarbloom": "lunar_bloom"}
    assert R.SUPPORTED_CHANNELS == {"direct", "lunar_charged", "swirl"}
    assert R.UNSUPPORTED_PAIRS == {frozenset(p) for p in [("Pyro", "Hydro"), ("Pyro", "Cryo"), ("Pyro", "Electro"), ("Pyro", "Dendro"),
                                                          ("Dendro", "Hydro"), ("Dendro", "Electro"), ("Cryo", "Electro"), ("Cryo", "Hydro")]}


def test_element_views():
    assert R.HELPERS == {"Anemo", "Geo"}
    assert R.REACTING == ("Pyro", "Hydro", "Electro", "Cryo", "Dendro")
    names = {("Pyro", "Hydro"): "Vaporize", ("Pyro", "Cryo"): "Melt", ("Pyro", "Electro"): "Overloaded", ("Pyro", "Dendro"): "Burning",
             ("Hydro", "Electro"): "Electro-Charged", ("Hydro", "Dendro"): "Bloom", ("Hydro", "Cryo"): "Freeze",
             ("Cryo", "Electro"): "Superconduct", ("Electro", "Dendro"): "Quicken"}
    for (a, b), name in names.items():
        assert R.reaction_between(a, b).family == name and R.reaction_between(b, a).family == name


def test_every_reaction_is_classified_and_owned():
    for r in R.REACTIONS:
        assert r.cls in {"amplifying", "catalyze", "transformative", "lunar", "control", "crystallize"}
        assert r.ownership in {"trigger", "core_creator", "contributors", "none"}
        assert all(e in R.ELEMENTS for e in r.elements)
        assert (r.ownership == "none") == (r.cls in ("control", "crystallize"))
