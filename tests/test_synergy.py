"""Synergy attribution on a hand-built gcsim log, checked against the formulas by hand."""
import pytest

from gtc.sources.names import Names
from gtc.synergy import Attributor, SynergyTable

NAMES = Names(["Kamisato Ayaka", "Kaedehara Kazuha", "Sucrose"], {}, ["Viridescent Venerer", "Blizzard Strayer"])


def sample(extra_mods):
    calc = {"abil": "Soumetsu", "use_hp": False, "use_def": False, "use_em": False, "total_scaling": 2000.0,
            "base_atk": 800.0, "em": 300.0, "react_bonus": 0.0, "cr": 0.5, "cd": 2.0, "bonus_dmg": 0.9,
            "res": -0.3, "ignore_def": 0, "melt_vape": False, "react_base_dmg_bonus": 0}
    damage = {"abil": "Soumetsu", "damage": 10000.0, "ele": "cryo", "attack-tag": 4,
              "resist_mods": ["vvcryo", ["status: added", "ele: cryo", "amount: -0.4"]], **extra_mods}
    return {
        "character_details": [{"name": "kamisatoayaka", "sets": {"blizzardstrayer": 4}, "cons": 0, "snapshot": []},
                              {"name": "kazuha", "sets": {"viridescentvenerer": 4}, "cons": 0, "snapshot": []}],
        "logs": [{"event": "calc", "frame": 10, "char_index": 0, "logs": calc},
                 {"event": "damage", "frame": 10, "char_index": 0, "logs": damage}],
    }


def test_damage_bonus_and_shred_are_credited_to_kazuha():
    s = sample({"kazuha-a4": ["status: added", "expiry_frame: 100", "cryo%: 0.40"],
                "sucrose-a4": ["status: rejected", "reason: conditions not met"]})
    syn = Attributor(s, NAMES, {}).attribute()
    b = syn.breakdown("Kaedehara Kazuha")
    # DMG% 0.4 out of a total bonus of 0.9: removing it leaves (1.5 / 1.9) of the damage.
    assert b[("Kamisato Ayaka", "cryo%")] == pytest.approx(1 - 1.5 / 1.9, rel=1e-6)
    # RES -0.3 with a -0.4 shred: without it RES is 0.1, multiplier 0.9 instead of 1.15.
    assert b[("Kamisato Ayaka", "res shred")] == pytest.approx(1 - 0.9 / 1.15, rel=1e-6)
    assert ("Kamisato Ayaka", "em") not in b  # rejected buffs count for nothing


def test_em_does_nothing_for_a_plain_cryo_hit():
    s = sample({"sucrose-a4": ["status: added", "em: 200"]})
    s["character_details"][1] = {"name": "sucrose", "sets": {}, "cons": 0, "snapshot": []}
    syn = Attributor(s, NAMES, {}).attribute()
    assert syn.breakdown("Sucrose") == {}  # Elemental Mastery cannot raise a non-reaction hit


def test_pair_table_averages_by_carry():
    db = {"a": {"lineup": ["Kamisato Ayaka", "Kaedehara Kazuha"], "own": {"Kaedehara Kazuha": 0.1}, "buffs_marginal": {"Kaedehara Kazuha": 0.2},
                "detail": {"Kaedehara Kazuha": {"Kamisato Ayaka|cryo%": 0.15, "Kamisato Ayaka|res shred": 0.05}}},
          "b": {"lineup": ["Kamisato Ayaka", "Kaedehara Kazuha", "Sucrose"], "own": {"Kaedehara Kazuha": 0.1}, "buffs_marginal": {"Kaedehara Kazuha": 0.4},
                "detail": {"Kaedehara Kazuha": {"Kamisato Ayaka|cryo%": 0.3}}}}
    cats = {"Kamisato Ayaka": {"DPS"}, "Kaedehara Kazuha": {"Support"}, "Sucrose": {"Support"}}
    pair = SynergyTable(db, cats).pair("Kamisato Ayaka", "Kaedehara Kazuha")
    assert pair.n == 2 and pair.value == pytest.approx(0.4) and pair.kinds["cryo%"] == pytest.approx(0.225)


def test_omen_ttds_and_quills_go_to_their_providers():
    s = sample({"ttds": ["status: added", "atk%: 0.48"],
                "pre_damage_mods": ["mona-omen", ["status: added", "dmg%: 0.50"]]})
    s["character_details"] = [
        {"name": "kamisatoayaka", "sets": {}, "cons": 0, "snapshot": [], "weapon": {"name": "mistsplitter"}},
        {"name": "mona", "sets": {}, "cons": 0, "snapshot": [], "weapon": {"name": "thrillingtalesofdragonslayers"}},
        {"name": "shenhe", "sets": {}, "cons": 0, "snapshot": [], "weapon": {"name": "favoniuslance"}},
    ]
    s["logs"][0]["logs"].update({"flat_dmg": 500.0, "base_dmg": 2500.0})
    names = Names(["Kamisato Ayaka", "Mona", "Shenhe"], {}, [])
    syn = Attributor(s, names, {}).attribute()
    mona = syn.breakdown("Mona")
    assert mona[("Kamisato Ayaka", "dmg%")] == pytest.approx(1 - 1.4 / 1.9, rel=1e-6)   # Omen, a pre-damage mod
    assert mona[("Kamisato Ayaka", "atk%")] == pytest.approx(800 * 0.48 / 2000, rel=1e-6)  # TTDS is Mona's weapon
    assert syn.breakdown("Shenhe")[("Kamisato Ayaka", "flat DMG")] == pytest.approx(500 / 2500, rel=1e-6)  # quills


def test_hyperbloom_em_share_and_reaction_bonus_from_teammates():
    from gtc.tc.formulas import em_transformative, reaction_base
    em, bonus = 800.0, 0.4
    flat = 3.0 * reaction_base(90) * (1 + em_transformative(em) + bonus)
    s = {
        "character_details": [{"name": "kukishinobu", "sets": {}, "cons": 0, "snapshot": [], "weapon": {"name": "x"}},
                              {"name": "nahida", "sets": {}, "cons": 0, "snapshot": [], "weapon": {"name": "y"}}],
        "logs": [
            {"event": "status", "msg": "react bonus mod added", "frame": 0, "char_index": 0, "logs": {"key": "nahida-test", "expiry": -1}},
            # Kuki's earlier hit shows the buffs she carries: 200 EM from Nahida.
            {"event": "damage", "frame": 5, "char_index": 0, "logs": {"abil": "Grass Ring", "damage": 100.0, "ele": "electro",
                                                                       "nahida-a1": ["status: added", "em: 200"]}},
            {"event": "calc", "frame": 10, "char_index": 0, "logs": {"abil": "hyperbloom", "em": em, "flat_dmg": flat, "char_lvl": 90}},
            {"event": "damage", "frame": 10, "char_index": 0, "logs": {"abil": "hyperbloom", "damage": 1000.0, "ele": "dendro"}},
        ],
    }
    names = Names(["Kuki Shinobu", "Nahida"], {}, [])
    b = Attributor(s, names, {}).attribute().breakdown("Nahida")
    full = 1 + em_transformative(em) + bonus
    assert b[("Kuki Shinobu", "em")] * 1100 == pytest.approx(1000 * (1 - (1 + em_transformative(em - 200) + bonus) / full), rel=1e-6)
    assert b[("Kuki Shinobu", "reaction bonus")] * 1100 == pytest.approx(1000 * (1 - (full - bonus) / full), rel=1e-6)


def test_aggravate_em_only_raises_the_added_damage():
    from gtc.tc.formulas import em_additive, reaction_base
    em = 300.0
    cat = reaction_base(90) * 1.15 * (1 + em_additive(em))
    calc = {"abil": "E", "use_hp": False, "use_def": False, "use_em": False, "total_scaling": 2000.0, "base_atk": 800.0,
            "em": em, "react_bonus": 0.0, "cr": 0.5, "cd": 1.0, "bonus_dmg": 0.5, "res": 0.1, "ignore_def": 0,
            "melt_vape": False, "catalyzed": True, "base_dmg": 4000.0 + cat, "flat_dmg": cat}
    s = {"character_details": [{"name": "keqing", "sets": {}, "cons": 0, "snapshot": [], "weapon": {"name": "x"}},
                               {"name": "nahida", "sets": {}, "cons": 0, "snapshot": [], "weapon": {"name": "y"}}],
         "logs": [{"event": "calc", "frame": 1, "char_index": 0, "logs": calc},
                  {"event": "damage", "frame": 1, "char_index": 0, "logs": {"abil": "E", "damage": 1000.0, "ele": "electro",
                                                                             "nahida-a1": ["status: added", "em: 200"]}}]}
    names = Names(["Keqing", "Nahida"], {}, [])
    b = Attributor(s, names, {}).attribute().breakdown("Nahida")
    new_cat = cat * (1 + em_additive(em - 200)) / (1 + em_additive(em))
    assert b[("Keqing", "em")] == pytest.approx(1 - (4000 + new_cat) / (4000 + cat), rel=1e-6)


def _shapley_of(effects, ctx, dmg=1000.0):
    from gtc.synergy import Attributor
    a = Attributor.__new__(Attributor)
    from collections import defaultdict
    a.shapley = defaultdict(float)
    a._shapley_hit("Carry", effects, ctx, dmg)
    return dict(a.shapley)


CTX = {"scaling": "atk", "S": 2000.0, "base": 1000.0, "em": 0.0, "react": 0.0, "cr": 0.5, "cd": 1.0, "bonus": 0.5,
       "res": 0.1, "lunar": False, "amp": False, "catalyze_flat": 0.0, "base_total": 0.0}


def test_shapley_shares_sum_to_the_buffed_minus_unbuffed_hit():
    from gtc.synergy import hit_factor
    effects = [("Bennett", "atk", 1000.0), ("Kazuha", "pyro%", 0.4), ("Zhongli", "res shred", -0.2), ("Bennett", "cd", 0.2)]
    phi = _shapley_of(effects, CTX)
    unbuffed = 1000.0 * hit_factor(CTX, [(st, v) for _, st, v in effects])
    assert abs(sum(phi.values()) - (1000.0 - unbuffed)) < 1e-6


def test_shapley_hand_check_two_multiplicative_buffs():
    # ATK x1.5 (2000 -> 1333.3 without the buff gives 2000/1333.3) and DMG bonus 1.5 -> 1.0: both multiply.
    # Hit 1000; without A: 1000/1.5; without B: 1000/1.5; without both: 1000/2.25.
    # Shapley: each gets half of the interaction: phi_A = 0.5[(1000 - 666.7) + (666.7 - 444.4)] = 277.8.
    ctx = dict(CTX, S=2000.0, base=2000.0, bonus=0.5)
    phi = _shapley_of([("A", "atk", 2000.0 / 3), ("B", "dmg%", 0.5)], ctx)
    assert abs(phi["A"] - 277.78) < 0.1 and abs(phi["B"] - 277.78) < 0.1


def test_self_buffs_are_not_shared():
    phi = _shapley_of([("Carry", "atk", 500.0), ("Bennett", "atk", 500.0)], CTX)
    assert set(phi) == {"Bennett"}


def test_gcsim_short_aliases_resolve_to_their_character():
    """'chev-a1-electro' is Chevreuse's RES shred; unresolved, it was credited to the attacker."""
    from gtc import gamedata
    from gtc.synergy import Attributor
    a = Attributor.__new__(Attributor)
    a.names = gamedata.names()
    a.members = ["Razor", "Chevreuse", "Fischl", "Bennett"]
    a.norm_members = {m.lower(): m for m in a.members}
    a.weapon_holder, a.sets = {}, {}
    assert a.owner_of("chev-a1-electro", "Razor") == "Chevreuse"
