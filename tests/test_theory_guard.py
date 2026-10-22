"""The theory calculator answers only where it is validated (gtc/theory_guard.py)."""
from gtc.tc.profile import Profile, Source, Unit
from gtc.theory_guard import channel, check_base, check_swap, coverage


def _profile(sources):
    units = {o: Unit(o, el) for o, el in {("Flins", "Electro"), ("Columbina", "Hydro"), ("Hu Tao", "Pyro"), ("Xingqiu", "Hydro")}}
    return Profile(sorted({s[0] for s in sources}), sources[0][0], units, [Source(o, n, "direct", "Electro", d) for o, n, d in sources])


def test_channels_from_gcsim_source_names():
    assert channel("Guhua Sword: Raincutter (vaporize)") == "vaporize"
    assert channel("Normal 0 (aggravate)") == "aggravate"
    assert channel("overload") == "overloaded" and channel("hyperbloom") == "hyperbloom"
    assert channel("lunarcharged") == "lunar_charged" and channel("Gravity Interference (Lunar-Charged)") == "lunar_charged"
    assert channel("swirl-hydro") == "swirl"
    assert channel("Musou Isshin 0") == "direct"


def test_vaporize_team_is_refused():
    vape = _profile([("Hu Tao", "Charged Attack (vaporize)", 60000), ("Hu Tao", "Charged Attack", 10000), ("Xingqiu", "Raincutter", 20000)])
    assert coverage(vape).unsupported_share > 0.6
    a = check_base(vape)
    assert not a.supported and "vaporize" in a.reason


def test_lunar_team_is_supported_and_a_pyro_newcomer_is_refused():
    lunar = _profile([("Flins", "lunarcharged", 70000), ("Flins", "Northland Spearstorm (Lunar-Charged)", 20000), ("Columbina", "Normal 0", 5000)])
    assert check_base(lunar).supported
    refused = check_swap(lunar, None, "Pyro", ["Electro", "Hydro"], lunar_after=True)
    assert not refused.supported and "Pyro" in refused.reason
    assert check_swap(lunar, None, "Anemo", ["Electro", "Hydro"], lunar_after=True).supported


def test_direct_only_team_is_unsupported_because_it_failed_validation():
    direct = _profile([("Flins", "Normal 0", 90000), ("Columbina", "Normal 0", 10000)])
    a = check_base(direct)
    assert not a.supported and "Lunar-Charged" in a.reason
