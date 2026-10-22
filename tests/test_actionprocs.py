"""Procs triggered by an action being performed (Rain Swords, Exquisite Throw), the sustained window, and the
transition record the gcsim translation uses (Phase 7 parity)."""
from tests.test_kitlang import HIT, lib, sim

SWORD = {**HIT, "offset": 0.3, "element": "Hydro", "type": "burst", "mult": 0.5}


def _xq(sustained: bool = False, delay: float = 0.2):
    on = {"event": "action", "by": "active", "actions": ["attack"], "delay": delay}
    if sustained:
        on["sustained"] = True
    return lib("Xingqiu", summons={"swords": {"start_on": "burst", "duration": 15, "interval": 999, "hits": []}},
               procs={"rain": {"on": on, "requires": {"summon": "swords"}, "icd": 1.0, "hits": [SWORD]}},
               raw_actions={"burst": {"hits": []}})


def _carry(duration: float = 0.4, late: float = 0.1):
    return lib("Raiden Shogun", raw_actions={"attack#0": {"duration": duration, "hits": [{**HIT, "offset": late}]},
                                              "skill": {"duration": 0.5, "hits": [HIT]}})


def _swords(s):
    return sorted(round(h.t, 2) for h in s.hits if h.char == "Xingqiu")


def test_action_proc_fires_at_action_start_plus_delay():
    s = sim({"Xingqiu": _xq(), "Raiden Shogun": _carry(late=2.0)})   # the attack's hit lands 2 s later
    s.act("Xingqiu", "burst")
    s.act("Raiden Shogun", "attack")
    start = s.actions[-1].t
    assert _swords(s) == [round(start + 0.2 + 0.3, 2)]     # keyed on the action, not on the late hit


def test_action_proc_respects_action_list_and_icd():
    s = sim({"Xingqiu": _xq(), "Raiden Shogun": _carry()})
    s.act("Xingqiu", "burst")
    s.act("Raiden Shogun", "skill")
    assert _swords(s) == []                                 # a Skill is not a Normal Attack
    s.act("Raiden Shogun", "attack")
    s.act("Raiden Shogun", "attack")                        # within the 1 s ICD
    assert len(_swords(s)) == 1


def test_sustained_window_fires_when_icd_ends_mid_action_and_closes_at_next_action():
    s = sim({"Xingqiu": _xq(sustained=True, delay=0.0), "Raiden Shogun": _carry(duration=3.0)})
    s.act("Xingqiu", "burst")
    s.act("Raiden Shogun", "attack")
    t0 = s.actions[-1].t
    s._procs_sustained(t0 + 1.5)                            # the next action cuts the 3 s attack at 1.5 s
    got = [round(x - t0 - 0.3, 2) for x in _swords(s)]
    assert got == [0.0, 1.0]                                # at the start, then exactly one ICD later; not at 2.0


def test_sustained_window_runs_to_the_action_end_when_nothing_cuts_it():
    s = sim({"Xingqiu": _xq(sustained=True, delay=0.0), "Raiden Shogun": _carry(duration=2.5)})
    s.act("Xingqiu", "burst")
    s.act("Raiden Shogun", "attack")
    t0 = s.actions[-1].t
    s._procs_sustained(t0 + 10.0)
    assert [round(x - t0 - 0.3, 2) for x in _swords(s)] == [0.0, 1.0, 2.0]


def test_non_sustained_action_proc_does_not_fire_mid_action():
    s = sim({"Xingqiu": _xq(sustained=False, delay=0.0), "Raiden Shogun": _carry(duration=3.0)})
    s.act("Xingqiu", "burst")
    s.act("Raiden Shogun", "attack")
    s.t = s.actions[-1].t + 1.5
    s.act("Raiden Shogun", "skill")
    assert len(_swords(s)) == 1


def test_generator_records_the_transition_it_used():
    s = sim({"Xingqiu": _xq(), "Raiden Shogun": _carry()})
    s.act("Raiden Shogun", "attack")
    s.act("Raiden Shogun", "attack")
    a = s.actions[-1]
    assert a.earliest is not None and abs(a.t - a.earliest) < 1e-6    # no idle: the gcsim translation emits no wait
    s.t = a.t + 2.0                                                   # idle inserted on top of the transition
    s.act("Raiden Shogun", "attack")
    b = s.actions[-1]
    assert b.t - b.earliest > 1.0


def test_state_variant_use_cap_falls_back_to_the_base_action():
    a = lib("Flins", states={"window": {"duration": 6}},
            raw_actions={"skill": {"hits": [HIT]}, "burst": {"hits": [HIT]}, "burst@window": {"hits": [{**HIT, "mult": 9.0}]}})
    a.action_meta["skill"] = {"state": "window"}
    a.action_meta["burst@window"] = {"uses_per_state": 1, "energy_cost": 0}
    s = sim({"Flins": a})
    s.act("Flins", "skill")
    assert s._key("Flins", "burst") == "burst@window"
    s.energy["Flins"] = 999
    s.act("Flins", "burst")
    assert s.hits[-1].mult == 9.0
    assert s._key("Flins", "burst") == "burst"          # spent: the next Burst is the base one


def test_cooldown_context_press_vs_hold():
    from gtc.forward import frames as F

    F.table.cache_clear()
    t = F.table()["characters"]
    if "bennett" in t and (t["bennett"].get("cooldowns_ctx") or {}).get("skill"):
        assert F.cooldown("Bennett", "skill", False, True) < F.cooldown("Bennett", "skill", False, False)
    if "zhongli" in t and (t["zhongli"].get("cooldowns") or {}).get("skill"):
        assert F.cooldown("Zhongli", "skill", True, True) == max(t["zhongli"]["cooldowns"]["skill"])
