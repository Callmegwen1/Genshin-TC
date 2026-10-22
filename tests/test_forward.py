"""Forward model (FM-0 to FM-10): game data, builds, timeline effects and condition states, energy, field windows,
and the per-hit damage model against gcsim on the same rotation. gcsim runs are cached by content (data/sims), so
after the first run these tests are fast; they skip when the local gcsim binary is missing."""
import pytest

from gtc.forward import data as D
from gtc.forward.build import meta_standard
from gtc.sim import GCSIM

AYAKA_MONA = ["Kamisato Ayaka", "Shenhe", "Kaedehara Kazuha", "Mona"]
needs_gcsim = pytest.mark.skipif(not GCSIM.exists(), reason="local gcsim binary missing")


def test_base_stats_and_tables_come_from_amber():
    a = D.character_stats("Kamisato Ayaka", 90)
    assert abs(a["base_atk"] - 342.0) < 1.0 and abs(a["cd"] - 0.884) < 1e-3
    assert abs(D.weapon_stats("Favonius Sword", 90)["base_atk"] - 454.4) < 0.5
    assert D.table("Kamisato Ayaka", "normal")["4-Hit DMG"] == [0.416061] * 3     # "x3" expands
    assert D.value("Shenhe", "skill", "DMG Bonus") == pytest.approx(0.776152)
    assert D.talent_kind("Shenhe", "Spring Spirit Summoning (Icy Quill)") == "skill"


def test_house_build_is_built_for_the_right_stat():
    from gtc.forward.build import scaling_stat

    assert scaling_stat("Kaedehara Kazuha") == "em" and scaling_stat("Furina") == "hp" and scaling_stat("Shenhe") == "atk"
    k = meta_standard("Kaedehara Kazuha")
    assert k.total("em") > 700 and k.weapon == "Favonius Sword"


def test_factions_from_official_talent_names():
    from gtc.forward.effects import factions

    assert "moonsign" in factions("Flins") and "moonsign" in factions("Ineffa")
    assert "hexerei" in factions("Fischl") and not factions("Kamisato Ayaka")


def test_energy_requirement_formula():
    from types import SimpleNamespace

    from gtc.forward.energy import requirements, status

    rot = SimpleNamespace(lineup=["X"], actions=[SimpleNamespace(char="X", action="burst", t=t) for t in (1, 21, 41)],
                          energy=[{"char": "X", "kind": "particle", "amount": 20 * 1.5, "er": 1.5, "t": t} for t in (10, 30)])
    r = requirements(rot, {"X": 80})["X"]
    assert r["required_er"] == pytest.approx(160 / 40)       # two paid Bursts, 40 base energy
    assert status(1.5, 1.6) == "sustainable" and status(1.5, 1.4) == "marginal" and status(1.5, 1.0) == "unsustainable"


def test_field_windows_catch_raiden_and_razor():
    from gtc.forward.rotation import field_profile, window_fit

    assert field_profile("Raiden Shogun").kind == "burst_window" and field_profile("Raiden Shogun").minimum_seconds == 7
    assert field_profile("Razor").kind == "sustained"
    bad = window_fit(["Raiden Shogun", "Razor", "Bennett", "Xingqiu"])
    assert not bad["fits"] and min(bad["realisation"].values()) < 0.5
    assert window_fit(["Raiden Shogun", "Xingqiu", "Xiangling", "Bennett"])["fits"]      # Raiden alone on field
    assert window_fit(AYAKA_MONA)["fits"]


def _rot(lineup):
    from gtc.forward.trace import house_trace

    tr = house_trace(lineup)
    assert tr is not None
    return tr


@needs_gcsim
def test_unknown_conditions_earn_no_credit_and_partial_counts_follow_the_kit():
    from types import SimpleNamespace

    from gtc.forward.build import house_builds
    from gtc.forward.effects import build_timeline

    empty = SimpleNamespace(lineup=["Kamisato Ayaka", "Shenhe", "Escoffier", "Chiori"], actions=[], hits=[], duration=20.0,
                            segments=[], energy=[])
    tl = {e.source: e for e in build_timeline(empty, house_builds(empty.lineup))}
    esc = tl["Inspiration-Immersed Seasoning"]
    assert esc.state == "partial" and esc.amount == pytest.approx(0.15)          # 3 Hydro/Cryo members: 15%, not 55%
    fin = tl["The Finishing Touch"]                                               # needs a Geo construct: not tracked
    assert fin.state == "unknown" and not fin.active
    chev = SimpleNamespace(lineup=["Chevreuse", "Bennett", "Xiangling", "Hu Tao"], actions=[], hits=[], duration=20.0,
                           segments=[], energy=[])
    c = {e.source: e for e in build_timeline(chev, house_builds(chev.lineup))}
    assert c["Vanguard's Coordinated Tactics"].state == "unmet"                   # no Electro member


@needs_gcsim
def test_forward_matches_gcsim_on_the_same_rotation_ayaka_freeze():
    from gtc.forward.model import evaluate

    rot, info = _rot(AYAKA_MONA)
    ev = evaluate(rot, info=info)
    same = sum(h.gcsim_expected for h in rot.hits) / rot.duration
    assert abs(ev.dps / same - 1) < 0.05
    assert ev.coverage == 1.0
    assert ev.damage_share["Kamisato Ayaka"] > 0.45


@needs_gcsim
def test_icy_quill_amount_equals_gcsim_flat_damage():
    from gtc.forward.build import house_builds
    from gtc.forward.effects import build_timeline

    rot, info = _rot(AYAKA_MONA)
    quill = next(e for e in build_timeline(rot, house_builds(rot.lineup, info["er_added"])) if "Icy Quill" in e.source)
    gc = next(h.gcsim_calc["flat_dmg"] for h in rot.hits
              if h.char == "Kamisato Ayaka" and h.abil.startswith("Normal") and h.gcsim_calc.get("flat_dmg"))
    assert quill.amount == pytest.approx(gc, rel=1e-3) and quill.quota == 5


@needs_gcsim
def test_furina_fanfare_follows_party_hp_and_needs_a_healer():
    from gtc.forward.build import house_builds
    from gtc.forward.effects import build_timeline, fanfare_at, fanfare_curve

    rot, info = _rot(["Kamisato Ayaka", "Shenhe", "Kaedehara Kazuha", "Furina"])
    b = house_builds(rot.lineup, info["er_added"])
    cur = fanfare_curve(rot, b, build_timeline(rot, b))
    assert fanfare_at(cur, 18) > 100            # first Burst: the Salon drains a full party
    assert fanfare_at(cur, 40) < 10             # later Bursts: the party sits at 50% HP with no healer


@needs_gcsim
def test_flins_team_is_a_moonsign_lunar_team():
    from gtc.forward.model import evaluate

    rot, info = _rot(["Flins", "Aino", "Ineffa", "Sucrose"])
    ev = evaluate(rot, info=info)
    states = {c["source"]: c["state"] for c in ev.condition_states}
    assert states["Symphony of Winter"] == "met"                # 3 Moonsign members
    assert any(c["source"].startswith("Ascendant Gleam") for c in ev.condition_states)
    assert ev.per_reaction.get("lunarcharged", 0) > 0
    same = sum(h.gcsim_expected for h in rot.hits) / rot.duration
    assert abs(ev.dps / same - 1) < 0.08


def test_forward_model_is_separate_from_team_mechanics():
    import inspect

    import gtc.team_mechanics as TM

    src = inspect.getsource(TM)
    assert "gtc.forward" not in src     # the reasoner never reads numeric power
