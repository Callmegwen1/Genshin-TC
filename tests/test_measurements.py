"""Phase 6 lineup measurements on hand-built gcsim logs: reaction shares, amplified hits, aura uptime, conditional
buffs, off-field damage, and the separate attribution views."""
import pytest

from gtc import capabilities
from gtc.sources.names import Names
from gtc.synergy import Attributor, _migrate

NAMES = Names(["Hu Tao", "Xingqiu", "Kamisato Ayaka"], {}, [])


def _app(frame, who, applied, existing, after):
    return {"event": "element", "msg": "application", "frame": frame, "char_index": who,
            "logs": {"applied_ele": applied, "existing": existing, "after": after, "target": 1}}


def _hit(frame, who, dmg, abil="Normal 0", **extra):
    return {"event": "damage", "frame": frame, "char_index": who, "logs": {"abil": abil, "damage": dmg, "target": 1, **extra}}


def _sample(logs):
    return {"character_details": [{"name": "hutao", "sets": {}, "cons": 0, "snapshot": []},
                                  {"name": "xingqiu", "sets": {}, "cons": 0, "snapshot": []}],
            "logs": logs}


def test_amplified_hits_and_aura_uptime():
    logs = [{"event": "action", "frame": 0, "char_index": 0, "logs": {}},
            _app(0, 1, "hydro", None, ["hydro: 20"]),           # Hydro on from frame 0
            _hit(30, 0, 1000.0, amp="vaporize", ele="pyro"),  # amplified
            _app(60, 1, "hydro", ["hydro: 10"], ["hydro: 25"]),  # still on at 60: on throughout 0-60
            _hit(90, 0, 1000.0, ele="pyro"),                   # not amplified
            _app(120, 0, "pyro", None, ["pyro: 10"]),          # Hydro gone before 120: assumed to expire at 90
            _hit(119, 1, 2000.0, ele="hydro"),                 # Xingqiu off field
            _hit(240, 0, 0.0)]
    p = Attributor(_sample(logs), NAMES, {}).attribute().profile
    assert p["amplified"] == {"vaporize": pytest.approx(0.25)}
    assert p["members"]["Hu Tao"]["amplified_share"] == pytest.approx(0.5)
    assert p["members"]["Xingqiu"]["offfield_share"] == pytest.approx(1.0)
    # Hydro: 0-60 on, 60-120 on until the midpoint 90, then gone: 90 of 240 frames.
    assert p["aura_uptime"]["hydro"] == pytest.approx(90 / 240, abs=1e-3)
    # Damage dealt while Hydro was on the target: the first two hits (2000 of 4000).
    assert p["aura_at_hit"]["hydro"] == pytest.approx(0.5)


def test_reaction_damage_by_type_and_conditional_buffs():
    logs = [{"event": "action", "frame": 0, "char_index": 0, "logs": {}},
            _hit(10, 1, 300.0, abil="electrocharged"),
            _hit(20, 0, 700.0, **{"hutao-a4": ["status: added", "cr: 0.12"]}),
            _hit(30, 0, 1000.0, **{"hutao-a4": ["status: rejected", "reason: conditions not met"]})]
    p = Attributor(_sample(logs), NAMES, {}).attribute().profile
    assert p["reaction_damage"] == {"electro_charged": pytest.approx(0.15)}
    assert p["reaction_share"] == pytest.approx(0.15)
    assert p["members"]["Xingqiu"]["reaction_damage"] == {"electro_charged": pytest.approx(0.15)}
    mod = p["conditional_mods"]["hutao-a4"]
    assert mod["owner"] == "Hu Tao" and mod["active"] == pytest.approx(0.5) and mod["damage"] == pytest.approx(0.35)


def test_old_database_entries_are_migrated_to_the_phase6_names():
    e = {"lineup": ["A", "B"], "own": {"A": 0.5}, "buffs": {"B": 0.2}, "shapley": {"B": 0.1}, "enable": {"B": 0.05}}
    _migrate(e)
    assert e["buffs_marginal"] == {"B": 0.2} and e["buffs_shapley"] == {"B": 0.1}
    assert e["enable_reaction"] == {"B": 0.05} and e["enable_amp"] == {} and "buffs" not in e


def test_capabilities_expose_the_attribution_views_separately():
    prof = {"members": {"A": {"damage_share": 0.8, "field_share": 0.7, "apply": {}, "triggers": {}, "amplified_share": 0.4},
                        "B": {"damage_share": 0.2, "field_share": 0.3, "apply": {"Hydro.off": 3.0}, "triggers": {},
                              "offfield_share": 0.9, "shields": True}},
            "reaction_share": 0.0, "conditional_mods": {"b-buff": {"owner": "B", "active": 0.5, "damage": 0.3}}}
    db = {"x": {"lineup": ["A", "B"], "profile": prof, "own": {"A": 0.8, "B": 0.2},
                "buffs_marginal": {"B": 0.3}, "buffs_shapley": {"B": 0.25}, "enable_reaction": {}, "enable_amp": {"B": 0.1},
                "detail": {"B": {"A|res shred": 0.2, "A|hydro%": 0.1}}}}
    c = capabilities.aggregate(db)["B"]
    assert (c.buffs_marginal, c.buffs_shapley, c.enable_amp) == (0.3, 0.25, 0.1)
    assert c.buff_effects == {"res shred": 0.2, "hydro%": 0.1} and c.buff_to_dealer == pytest.approx(1.0)
    assert c.offfield_share == 0.9 and c.shield_rate == 1.0
    assert c.conditional == {"b-buff": 0.5} and c.conditional_damage == pytest.approx(0.3)
    assert capabilities.aggregate(db)["A"].amplified_share == 0.4
