"""The kit language (phase A) and the reaction model families (phase B), on synthetic kits and hits."""
from types import SimpleNamespace

from gtc.forward.library import ActionEntry, Library
from gtc.forward.trace import Hit


def lib(name, **kw):
    L = Library(name=name, actions={}, filler=[], sources=["test"], hand=True)
    for k, v in kw.items():
        setattr(L, k, v)
    for act, a in (kw.get("raw_actions") or {}).items():
        L.actions[act] = ActionEntry(act, a.get("duration", 0.5), [L._template(h, act) for h in a.get("hits", [])], 0.0, 0)
        L.action_meta[act] = {k: a[k] for k in ("do", "requires_state", "requires_resource", "uses_per_state") if k in a}
    for p in (kw.get("procs") or {}).values():
        p["hits"] = [L._template(h) for h in p.get("hits", [])]
        if p.get("hits_cycle"):
            p["hits_cycle_t"] = [[L._template(h) for h in g] for g in p["hits_cycle"]]
    return L


def sim(libs):
    from gtc.forward.build import house_builds
    from gtc.forward.generator import _Sim

    team = list(libs)
    return _Sim(team, libs, house_builds(team, {m: 3.0 for m in team}))


HIT = {"offset": 0.1, "mult": 1.0, "element": "Cryo", "type": "normal", "gauge": 1.0}


def test_resources_thresholds_and_states():
    a = lib("Kamisato Ayaka", resources={"stacks": {"max": 3, "start": 0}},
            states={"empowered": {"duration": 5, "ends_on_swap": True}},
            rules=[{"on": {"event": "action", "action": "skill", "by": "self"}, "do": [{"gain": {"resource": "stacks", "amount": 1}}]},
                   {"when": {"resource": "stacks", "at_least": 3}, "do": [{"enter": "empowered"}, {"consume": {"resource": "stacks", "amount": 3}}]}],
            raw_actions={"skill": {"hits": [HIT]}, "attack#0": {"hits": [HIT]},
                         "attack#0@empowered": {"hits": [{**HIT, "mult": 5.0}]}})
    b = lib("Shenhe", raw_actions={"skill": {"hits": [HIT]}})
    s = sim({"Kamisato Ayaka": a, "Shenhe": b})
    for _ in range(3):
        s.act("Kamisato Ayaka", "skill")
        s.t += 0.1
        s.ready[("Kamisato Ayaka", "skill")] = 0
    assert s.state("Kamisato Ayaka", s.t)["name"] == "empowered" and s.res[("Kamisato Ayaka", "stacks")] == 0
    s.act("Kamisato Ayaka", "attack")
    assert s.hits[-1].mult == 5.0                    # state-dependent action
    s.act("Shenhe", "skill")                         # swapping out ends the state
    assert s.state("Kamisato Ayaka", s.t) is None


def test_unknown_amount_propagates():
    a = lib("Lohen", resources={"will": {"max": "unknown", "start": 0}},
            rules=[{"on": {"event": "hit", "by": "party"}, "do": [{"gain": {"resource": "will", "amount": "unknown"}}]}],
            raw_actions={"attack#0": {"hits": [HIT]}})
    s = sim({"Lohen": a})
    s.act("Lohen", "attack")
    assert s.res[("Lohen", "will")] is None


def test_procs_cycle_trigger_scaling_and_energy():
    x = lib("Xingqiu", summons={"swords": {"start_on": "burst", "duration": 15, "interval": 999, "hits": []}},
            procs={"rain": {"on": {"event": "hit", "by": "active", "types": ["normal"]}, "requires": {"summon": "swords"}, "icd": 1.0,
                            "hits_cycle": [[{**HIT, "element": "Hydro", "type": "burst"}] * 2, [{**HIT, "element": "Hydro", "type": "burst"}] * 3]}},
            raw_actions={"burst": {"hits": []}})
    r = lib("Razor", procs={"companion": {"on": {"event": "hit", "by": "self", "types": ["normal"]}, "icd": 0,
                                          "hits": [{**HIT, "mult": 0.5, "scale_trigger": True, "type": "burst"}]}},
            raw_actions={"attack#0": {"hits": [{**HIT, "mult": 2.0, "element": "Physical"}]}},
            rules=[{"on": {"event": "action", "action": "attack", "by": "self"}, "do": [{"energy": {"amount": 3, "to": "party_others"}}]}])
    s = sim({"Xingqiu": x, "Razor": r})
    s.act("Xingqiu", "burst")
    s.energy["Xingqiu"] = 0
    s.act("Razor", "attack")
    companion = [h for h in s.hits if h.char == "Razor" and h.damage_type == "burst"]
    assert companion and companion[0].mult == 1.0     # 0.5 x the triggering 2.0
    assert sum(1 for h in s.hits if h.char == "Xingqiu") == 2
    assert s.energy["Xingqiu"] == 3                    # flat energy ignores ER


def h(t, char, el, gauge=1.0):
    return Hit(t=t, char=char, abil=f"{char}", damage_type="skill", element=el, mult=1.0, scaling="atk", gauge=gauge)


def test_quicken_aggravate_spread_and_bloom_hyperbloom():
    from gtc.forward.reactions import simulate

    team = ["Nahida", "Fischl", "Xingqiu", "Kuki Shinobu"]
    hits, c = simulate([h(0, "Nahida", "Dendro"), h(0.5, "Fischl", "Electro"), h(1.0, "Fischl", "Electro"),
                        h(1.5, "Nahida", "Dendro")], team)
    # Aggravate does not consume Quicken and leaves an Electro aura beside it (gcsim logs: after = [electro, quicken]);
    # the later Dendro hit Spreads and reacts with that Electro, refreshing Quicken: two Quicken events
    assert c["quicken"] == 2 and c["aggravate"] == 1 and c["spread"] == 1
    hits, _ = simulate([h(0, "Nahida", "Dendro"), h(0.5, "Fischl", "Electro"), h(1.0, "Fischl", "Electro"),
                        h(1.2, "Fischl", "Electro", gauge=0.0)], team)
    assert {"Electro", "Quicken"} <= set(hits[-1].auras or ())
    hits, c = simulate([h(0, "Nahida", "Dendro"), h(0.3, "Xingqiu", "Hydro"), h(1.0, "Kuki Shinobu", "Electro")], team)
    assert c["bloom-core"] == 1 and c["hyperbloom"] == 1
    assert c["_detail"]["owners"]["hyperbloom"] == {"Kuki Shinobu": 1}


def test_reaction_damage_cooldown_and_plausibility():
    from gtc.forward.reactions import plausibility, simulate

    team = ["Kamisato Ayaka", "Fischl", "Shenhe", "Ineffa"]
    hits = []
    for i in range(10):          # alternating Cryo / Electro applications 0.05 s apart: many Superconducts in 0.5 s
        hits.append(h(i * 0.05, "Kamisato Ayaka" if i % 2 else "Fischl", "Cryo" if i % 2 else "Electro"))
    out, c = simulate(hits, team)
    assert c.get("superconduct", 0) <= 2 and c["_detail"]["suppressed_by_reaction_icd"].get("superconduct", 0) >= 1
    assert plausibility({"superconduct": 5.0})


def test_bloom_gauge_sides_and_dendro_on_electro_charged():
    from gtc.forward.reactions import simulate

    # Dendro on Hydro is the strong side: a 1U Dendro removes a 1U Hydro aura (2x)
    _, rx = simulate([h(0.0, "Xingqiu", "Hydro"), h(0.5, "Nahida", "Dendro"), h(1.0, "Kuki Shinobu", "Electro")],
                     ["Xingqiu", "Nahida", "Kuki Shinobu"])
    assert rx.get("bloom-core", 0) == 1 and rx.get("electrocharged", 0) == 0
    # Dendro on Electro + Hydro: Quicken first, then Bloom with the rest
    _, rx = simulate([h(0.0, "Xingqiu", "Hydro"), h(0.1, "Kuki Shinobu", "Electro"), h(0.2, "Nahida", "Dendro", 2.0)],
                     ["Xingqiu", "Nahida", "Kuki Shinobu"])
    assert rx.get("quicken", 0) == 1 and rx.get("bloom-core", 0) == 1


def test_swirl_uses_up_the_anemo_durability():
    from gtc.forward.reactions import simulate

    # a 1U Anemo hit on Hydro + Cryo-Frozen swirls one aura, not every aura it touches
    _, rx = simulate([h(0.0, "Xingqiu", "Hydro"), h(0.1, "Kamisato Ayaka", "Cryo"), h(0.2, "Xingqiu", "Hydro"),
                      h(0.3, "Kaedehara Kazuha", "Anemo")], ["Xingqiu", "Kamisato Ayaka", "Kaedehara Kazuha"])
    swirls = sum(v for k, v in rx.items() if k.startswith("swirl"))
    assert swirls == 1
