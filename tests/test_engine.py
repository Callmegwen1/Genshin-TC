"""Engine tests on small synthetic rosters, independent of your live account."""
from gtc import knowledge
from gtc.importers.hoyolab import _talents
from gtc.report import build_universe
from gtc.teams import Member, best_disjoint_pair, evaluate_lineup, fill_template, find_incomplete, ideal_team

KB = knowledge.load()


def roster(*specs, con=0):
    return [Member(key, element, inv, KB.characters[key].roles_at(con), con) for key, element, inv in specs]


FREEZE_CORE = roster(
    ("Kamisato Ayaka", "Cryo", 1.0), ("Xingqiu", "Hydro", 1.0), ("Shenhe", "Cryo", 1.0),
    ("Kaedehara Kazuha", "Anemo", 1.0), ("Zhongli", "Geo", 1.0),
)


def test_knowledge_base_is_valid():
    assert knowledge.validate(KB) == []


def test_freeze_prefers_anemo_buffer_in_flex():
    best = fill_template(KB.templates["freeze"], FREEZE_CORE, KB)[0]
    assert set(best.members) == {"Kamisato Ayaka", "Xingqiu", "Shenhe", "Kaedehara Kazuha"}


def test_investment_lowers_current_but_not_potential():
    built = fill_template(KB.templates["freeze"], FREEZE_CORE, KB)[0]
    unbuilt_roster = [Member(m.key, m.element, 0.0, m.roles) for m in FREEZE_CORE]
    unbuilt = fill_template(KB.templates["freeze"], unbuilt_roster, KB)[0]
    assert unbuilt.current < built.current
    assert unbuilt.potential == built.potential


def test_missing_core_slot_is_reported():
    no_hydro = [m for m in FREEZE_CORE if m.element != "Hydro"]
    inc = find_incomplete(KB.templates["freeze"], no_hydro, KB)
    assert inc is not None
    assert [s.name for s in inc.missing] == ["Hydro applicator"]


def test_lunar_requires_enabler_and_rewards_two_moonsign():
    r = roster(("Flins", "Electro", 1.0), ("Xingqiu", "Hydro", 1.0), ("Fischl", "Electro", 1.0),
               ("Sucrose", "Anemo", 1.0), ("Aino", "Hydro", 1.0))
    team = evaluate_lineup(["Flins", "Aino", "Fischl", "Sucrose"], r, KB)
    assert team is not None and team.template.id == "lunar_charged"
    assert any("Ascendant Gleam" in reason for reason in team.reasons)
    # Flins alone is a single Moonsign: no Ascendant Gleam bonus.
    solo = evaluate_lineup(["Flins", "Xingqiu", "Fischl", "Sucrose"], r, KB)
    assert not any("Ascendant Gleam" in reason for reason in solo.reasons)


def test_abyss_pair_shares_no_characters():
    r = FREEZE_CORE + roster(("Flins", "Electro", 1.0), ("Aino", "Hydro", 1.0), ("Fischl", "Electro", 1.0),
                             ("Sucrose", "Anemo", 1.0), ("Bennett", "Pyro", 1.0))
    teams = [t for tid in ("freeze", "lunar_charged") for t in fill_template(KB.templates[tid], r, KB)]
    a, b = best_disjoint_pair(teams)
    assert not set(a.members) & set(b.members)


def test_constellation_talent_bonus_is_subtracted():
    entry = {
        "skills": [
            {"skill_type": 1, "name": "Strike of Fortune", "level": 3},
            {"skill_type": 1, "name": "Passion Overload", "level": 9},
            {"skill_type": 1, "name": "Fantastic Voyage", "level": 11},
        ],
        "constellations": [
            {"is_actived": True, "effect": "Increases the Level of Passion Overload by 3.\\nMaximum upgrade level is 15."},
            {"is_actived": True, "effect": "Increases the Level of the Elemental Burst {LINK#S1}Fantastic Voyage{/LINK} by 3."},
        ],
    }
    t = _talents(entry)
    assert (t.normal, t.skill, t.burst) == (3, 6, 8)
    assert t.effective == {"normal": 3, "skill": 9, "burst": 11}


def test_mona_beats_xingqiu_in_freeze_because_of_her_buff():
    r = FREEZE_CORE + roster(("Mona", "Hydro", 1.0))
    mona = evaluate_lineup(["Kamisato Ayaka", "Mona", "Shenhe", "Kaedehara Kazuha"], r, KB)
    xq = evaluate_lineup(["Kamisato Ayaka", "Xingqiu", "Shenhe", "Kaedehara Kazuha"], r, KB)
    assert mona.potential > xq.potential


def test_ideal_ayaka_freeze_uses_furina():
    # The measured meta: characters known only from a provisional kit (phase 13) are left out here; with them,
    # Vodyanitsa can take the Hydro slot on kit-model evidence (tested in test_kit_schema.py).
    universe = [m for m in build_universe(KB) if not KB.characters[m.key].provisional]
    ideal = ideal_team(KB.templates["freeze"], universe, KB, lead="Kamisato Ayaka")
    assert "Furina" in ideal.members


def test_constellation_unlocks_roles():
    aino = KB.characters["Aino"]
    assert "buffer_lunar" not in aino.roles_at(0)
    assert aino.roles_at(6)["buffer_lunar"] == 3


def test_pruned_search_matches_full_enumeration():
    # Branch and bound must return exactly what scoring every lineup would.
    r = FREEZE_CORE + roster(("Mona", "Hydro", 0.3), ("Bennett", "Pyro", 0.8), ("Xiangling", "Pyro", 0.9),
                             ("Sucrose", "Anemo", 0.6), ("Furina", "Hydro", 0.5), ("Escoffier", "Cryo", 0.7))
    for t in KB.templates.values():
        for rank in ("potential", "current"):
            fast = fill_template(t, r, KB, limit=5, rank_by=rank)
            full = fill_template(t, r, KB, rank_by=rank)[:5]
            assert [round(getattr(x, rank), 6) for x in fast] == [round(getattr(x, rank), 6) for x in full], t.id
