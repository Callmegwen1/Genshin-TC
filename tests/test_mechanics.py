"""Mechanical reasoning layer (phases M1 to M5): kit schema and validation, the reviewed reference kits, the central
mechanics, the TeamMechanics reasoner, and how the advisor uses it."""
import copy

import pytest

from gtc import kits as K
from gtc import mechanics as M
from gtc.team_mechanics import analyse, critical_functions

AYAKA_FREEZE = ["Kamisato Ayaka", "Shenhe", "Kaedehara Kazuha", "Mona"]
REFERENCE = {"Kamisato Ayaka", "Shenhe", "Mona", "Kaedehara Kazuha", "Sucrose", "Raiden Shogun", "Razor", "Escoffier",
             "Chiori", "Chevreuse", "Ineffa", "Citlali"}


# ---------- M1: schema and validation ----------

def test_every_reviewed_kit_validates_and_covers_the_reference_set():
    ks = K.reviewed_kits()
    assert REFERENCE <= set(ks)
    assert {n: K.validate(n, k) for n, k in ks.items() if K.validate(n, k)} == {}


def test_every_character_has_a_valid_kit_reviewed_or_derived():
    from gtc import gamedata

    bad = {n: K.validate(n, K.kit(n)) for n in gamedata.load_characters()}
    assert {n: e for n, e in bad.items() if e} == {}


def test_validation_rejects_bad_facts_and_accepts_unknown():
    k = copy.deepcopy(K.reviewed_kits()["Escoffier"])
    k["effects"][0]["amount"] = "unknown"
    assert K.validate("Escoffier", k) == []  # "unknown" is a valid value, never an error
    bad = copy.deepcopy(k)
    bad["effects"][0]["target"] = "everyone"
    bad["roles"].append("tank")
    bad["provenance"]["*"]["method"] = "guessed"
    errs = " ".join(K.validate("Escoffier", bad))
    assert "target" in errs and "role" in errs and "method" in errs
    nop = copy.deepcopy(k)
    nop.pop("provenance")
    assert K.validate("Escoffier", nop)


def test_derived_kits_are_marked_and_say_their_effects_are_unknown():
    d = K.derived_kit("Xiangling")
    assert d["derived"] and d["effects"] == []
    assert d["provenance"]["*"]["method"] == "derived" and d["provenance"]["*"]["confidence"] == "low"


# ---------- M3: reviewed kits against what was measured ----------

def test_reviewed_behaviour_agrees_with_the_measured_profile():
    order = ("minimal", "low", "medium", "high")
    own = ("none", "incidental", "sub_dps", "carry")
    for n, k in K.reviewed_kits().items():
        d = K.derived_kit(n)
        if d is None or not d["behavior"].get("application") and d["behavior"]["damage_ownership"] == "none":
            continue  # no measured profile
        b, db = k["behavior"], d["behavior"]
        assert b["on_field_damage"] == db["on_field_damage"], n
        assert abs(order.index(b["field_time"]) - order.index(db["field_time"])) <= 1, n
        assert abs(own.index(b["damage_ownership"]) - own.index(db["damage_ownership"])) <= 1, n


def test_reviewed_kit_conditions_replace_the_legacy_ones():
    from gtc.kit_conditions import conditions, status

    c = conditions()
    assert c["Chevreuse"]["each"] and c["Nilou"]["each"] and c["Escoffier"]["full"] == 4
    # all-Pyro Chevreuse: every member is Pyro or Electro, but the kit needs at least one of each
    s = status("Chevreuse", ["Chevreuse", "Bennett", "Xiangling", "Hu Tao"])
    assert not s["met"] and s["missing_each"] == ["Electro"]
    assert status("Chevreuse", ["Chevreuse", "Fischl", "Bennett", "Xiangling"])["met"]


# ---------- M2: central mechanics ----------

def test_central_mechanics_reuse_the_reaction_table():
    assert M.category("melt") == "amplifying" and M.category("aggravate") == "additive"
    assert M.category("lunarcharged") == "transformative" and M.category("freeze") == "control"
    assert M.reaction_of("electro_charged").key == "electrocharged"
    assert M.consumes_auras("Pyro", "freeze") == ["Cryo", "Hydro"]
    assert M.consumes_auras("Anemo", "freeze") == [] and M.consumes_auras("Cryo", "freeze") == []
    assert {"freeze", "superconduct", "electrocharged"} <= M.possible_reactions(["Cryo", "Hydro", "Electro"])
    assert M.conditioned_buffs() == {"Chevreuse": "overloaded", "Nilou": "bloom"}


def test_effect_applicability_filters_by_target_element_and_type():
    quill = K.reviewed_kits()["Shenhe"]["effects"][0]
    assert M.effect_applies(quill, {"element": "Cryo", "types": ["normal"]})
    assert not M.effect_applies(quill, {"element": "Geo", "types": ["skill"]})
    a1 = K.reviewed_kits()["Kamisato Ayaka"]["effects"][0]
    assert M.effect_applies(a1, {"element": "Cryo", "types": ["normal"]}, same=True)
    assert not M.effect_applies(a1, {"element": "Cryo", "types": ["normal"]}, same=False)  # self only


# ---------- M4: the reasoner ----------

def test_ayaka_freeze_is_coherent():
    tm = analyse(AYAKA_FREEZE)
    assert tm.central == ["freeze"] and not tm.conflicts and not tm.opportunity_losses
    assert {s["from"] for s in tm.synergies if s["kind"] == "buff" and s["to"] == "Kamisato Ayaka"} == \
        {"Shenhe", "Kaedehara Kazuha", "Mona"}
    assert critical_functions(tm, "Mona") == ["Hydro application"]
    assert critical_functions(tm, "Kaedehara Kazuha") == ["swirl support"]
    assert tm.missing_functions == ["sustain (soft)"]


def test_raiden_and_razor_compete_for_field_time():
    tm = analyse(["Raiden Shogun", "Razor", "Bennett", "Xingqiu"])
    ft = [c for c in tm.conflicts if c["kind"] == "field_time"]
    assert len(ft) == 1 and ft[0]["severity"] == "harm" and ft[0]["members"] == ["Raiden Shogun", "Razor"]


def test_escoffier_chiori_is_an_opportunity_loss_and_mona_is_not():
    chiori = analyse(["Chiori", "Escoffier", "Zhongli", "Albedo"])
    assert not chiori.harms()
    kinds = {o["kind"] for o in chiori.opportunity_losses if o["member"] == "Escoffier"}
    assert kinds == {"partial_condition", "self_only"}
    mona = analyse(["Escoffier", "Mona", "Kamisato Ayaka", "Shenhe"])
    assert not mona.opportunity_losses and not mona.conflicts
    assert any(s["from"] == "Escoffier" and s["to"] == "Kamisato Ayaka" for s in mona.synergies if s["kind"] == "buff")


def test_aura_removal_and_broken_conditions_are_harm():
    tm = analyse(["Kamisato Ayaka", "Shenhe", "Xiangling", "Mona"], central=["freeze"])
    assert any(c["kind"] == "aura" and c["severity"] == "harm" and c["members"] == ["Xiangling"] for c in tm.conflicts)
    tm = analyse(["Nilou", "Furina", "Kamisato Ayaka", "Xingqiu"])
    assert any(c["kind"] == "condition" and c["members"] == ["Nilou"] for c in tm.harms())
    assert {"member": "Nilou", "reaction": "bloom", "source": "kit", "met": False} in tm.reaction_dependencies


def test_reaction_dependencies_and_inactive_effects():
    tm = analyse(["Kamisato Ayaka", "Shenhe", "Kaedehara Kazuha", "Citlali"])
    dep = [d for d in tm.reaction_dependencies if d["member"] == "Citlali"]
    assert dep and not dep[0]["met"]  # mono Cryo: no Frozen or Melt for her shred
    assert any(c["kind"] == "buff_wasted" and c["severity"] == "caution" for c in tm.conflicts)


def test_unknown_behaviour_never_counts_as_on_field_damage(monkeypatch):
    # Iansan has no measured profile: her derived kit says "unknown", which must not read as true (it once made
    # Iansan + Raiden a field-time conflict). Compiled kits are switched off to test the derived fallback.
    monkeypatch.setattr(K, "_COMPILED", {})
    assert K.kit("Iansan")["behavior"]["on_field_damage"] == "unknown"
    tm = analyse(["Raiden Shogun", "Iansan", "Xiangling", "Xingqiu"])
    assert not any(c["kind"] == "field_time" for c in tm.conflicts)
    assert "Iansan" not in tm.supplied_functions.get("on-field damage", [])


def test_buff_wasted_respects_snapshotting_off_field_damage():
    tm = analyse(["Chevreuse", "Fischl", "Bennett", "Xiangling"])
    assert not any(c["kind"] == "buff_wasted" and c["members"] == ["Bennett"] for c in tm.conflicts)


def test_reasoner_produces_no_power():
    tm = analyse(AYAKA_FREEZE).as_dict()
    flat = repr(tm).lower()
    assert "power" not in flat and "score" not in flat


# ---------- M5: advisor ----------

def _assess(ident_central, members, route="pair_model"):
    from types import SimpleNamespace

    basis = SimpleNamespace(route=route, tier="B", evidence_state="", quality="", quality_reasons=[], flags=[],
                            sources=[], member_distance=1)
    p = SimpleNamespace(basis=basis)
    e = SimpleNamespace(power={"single_target": p}, validity={"typicality": []}, coverage={"status": "complete"},
                        identity={"central": ident_central, "primary_actor": members[0]})
    return SimpleNamespace(team=SimpleNamespace(members=members), evaluation=e)


class _Ev:
    prydwen = {"characters": {}}
    lineup_values = {}


def test_field_time_conflict_needs_an_exact_simulation():
    from gtc.advisor import recommendability

    team = ["Raiden Shogun", "Razor", "Bennett", "Xingqiu"]
    r = recommendability(_assess(["overloaded"], team), _Ev())
    assert r["level"] == "experimental" and any("field time" in x for x in r["reasons"])
    r = recommendability(_assess(["overloaded"], team, route="exact_community"), _Ev())
    assert r["level"] != "experimental" and any("field time" in x for x in r["reasons"])


def test_coherent_interpolated_team_stays_credible():
    from gtc.advisor import recommendability

    r = recommendability(_assess(["freeze"], AYAKA_FREEZE), _Ev())
    assert r["level"] == "credible" and not r["signals"]["mechanics"]["conflicts"]


def test_substitutions_preserve_critical_functions():
    from types import SimpleNamespace

    from gtc.advisor import substitution_kind

    class Adv:
        def level(self, a):
            return "credible"

    base = _assess(["freeze"], AYAKA_FREEZE)
    alt = SimpleNamespace()
    assert substitution_kind(base, alt, "Kaedehara Kazuha", "Sucrose", Adv()) == ("direct", [])
    kind, why = substitution_kind(base, alt, "Mona", "Citlali", Adv())
    assert kind == "rebuild" and any("Freeze needs Hydro" in w for w in why)
    kind, why = substitution_kind(base, alt, "Kaedehara Kazuha", "Ineffa", Adv())
    assert kind == "rebuild" and any("swirl support" in w for w in why)
    assert any("removes the Cryo and Hydro auras" in w for w in why)


def test_mechanically_harmful_teams_never_enter_the_advisor_pool():

    from gtc.advisor import Advisor
    from gtc.estimate import Estimate

    a = _assess(["overloaded"], ["Raiden Shogun", "Razor", "Bennett", "Xingqiu"])
    a.estimate, a.potential = Estimate(90, 2, "C"), 88  # far better than anything else by the model
    adv = Advisor(_Ev())
    assert adv.level(a) == "experimental" and adv.rec(a)["signals"]["mechanical_harm"]
    assert adv.admit([a]) == []  # no credible team of its core, still not admitted
    b = _assess(["freeze"], AYAKA_FREEZE)
    b.estimate, b.potential = Estimate(50, 2, "C"), 48
    assert adv.admit([b]) == [b]


def test_compiled_kits_keep_measured_critical_roles():
    k = K.kit("Lan Yan")
    assert k.get("compiled") and "swirl_support" in k["roles"]
