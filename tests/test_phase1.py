"""Phase 1 checks on real data: validity rules, measured structure, median aggregation."""
import pytest

from gtc import SNAPSHOT_DIR
from gtc.sources.gcsim_db import TEAMS_PATH
from gtc.synergy import DB_PATH

pytestmark = pytest.mark.skipif(not DB_PATH.exists() or not TEAMS_PATH.exists() or not any(SNAPSHOT_DIR.glob("*.json")),
                                reason="needs the synergy database, sources and a snapshot")


def test_every_archetype_keeps_its_own_simulated_teams():
    """Recall: the share of an archetype's own simulated teams its validity rules accept. Target 98%; the floor
    is 90% because the slot matcher places a few lineups in archetypes they do not play (Bennett / Kinich /
    Mavuika / Mona fills the Dendro bloom slots), and rejecting those is correct."""
    from gtc import validity
    rules = validity.load()
    recalls = {tid: r["recall"] for tid, r in rules.items() if r.get("recall") is not None}
    assert recalls, "derive has not learned validity rules"
    assert not {tid: r for tid, r in recalls.items() if r < 0.90}
    assert sum(r >= 0.98 for r in recalls.values()) / len(recalls) >= 0.7


def test_resemblance_no_longer_rejects_but_mechanics_still_do():
    """Phase 9: an Overloaded team with Kazuha is unusual, not broken, so the data-derived Overloaded archetype forms
    it. The Chevreuse archetype still refuses it: her buffs need an all Pyro and Electro party (a kit restriction,
    which is mechanical). A team without Electro cannot Overload at all."""
    from scenarios import account, engine
    from gtc.teams import fill_template
    am = engine()
    with_kazuha = account(["Razor", "Kaedehara Kazuha", "Chevreuse", "Bennett"])
    assert fill_template(am.kb.templates["auto_overloaded_electro_carry"], with_kazuha, am.kb, limit=1, rank_by="potential")
    assert not fill_template(am.kb.templates["overloaded"], with_kazuha, am.kb, limit=1, rank_by="potential")
    no_electro = account(["Chevreuse", "Bennett", "Xiangling", "Kaedehara Kazuha"])
    assert not fill_template(am.kb.templates["overloaded"], no_electro, am.kb, limit=1, rank_by="potential")


def test_known_nonsense_teams_are_rejected():
    from scenarios import account, engine
    am = engine()
    # Neuvillette as a support in Mono Pyro was produced by the old engine.
    roster = account(["Diluc", "Xiangling", "Yun Jin", "Neuvillette", "Bennett", "Zhongli", "Kaedehara Kazuha", "Thoma"])
    _, cands = am.plan(roster)
    for a in cands:
        if "Neuvillette" in a.team.members and a.primary_actor:
            # Identity (phase 8) names whose team it is: never Neuvillette as a Mono Pyro support.
            assert not a.label.startswith("Mono Pyro")


def test_hyperbloom_is_not_led_by_an_anemo_flex():
    from scenarios import account, engine
    from gtc.teams import fill_template
    am = engine()
    roster = account(["Nahida", "Xingqiu", "Fischl", "Yumemizuki Mizuki"])
    teams = fill_template(am.kb.templates["hyperbloom"], roster, am.kb, limit=1, rank_by="potential")
    if teams:
        assert am.ev.damage_lead(teams[0]) != "Yumemizuki Mizuki"


def test_structure_prediction_on_held_out_lineups():
    """Each lineup predicted from the OTHER simulated lineups. The top damage dealer decides whose team it is;
    the category has thresholds (55% for a hypercarry) that sit inside the 5% simulation noise, so it agrees less."""
    from gtc.capabilities import Neighbours, predict_structure
    from gtc.synergy import load_database
    db = load_database()
    nb = Neighbours(db)
    entries = [e for e in db.values() if e.get("profile") and len(e["lineup"]) == 4][::4]
    top = cat = n = 0
    for e in entries:
        lineup = frozenset(e["lineup"])
        got = nb.profile(e["lineup"], exclude=lineup)
        if not got:
            continue
        n += 1
        measured = e["profile"]["members"]
        top += max(got[0], key=lambda m: got[0][m]["damage_share"]) == max(measured, key=lambda m: measured[m]["damage_share"])
        cat += predict_structure(e["lineup"], nb=nb, exclude=lineup)["type"] == e["profile"]["structure"]["type"]
    assert top / n >= 0.84
    assert cat / n >= 0.72


def test_lineup_value_is_the_median_not_the_best_submission():
    from gtc import knowledge
    from gtc.report import load_evidence
    ev = load_evidence(knowledge.load())
    many = [names for names, v in ev.lineup_median.items() if sum(1 for s in ev.standard if s.names == names) >= 5]
    assert many
    for names in many[:20]:
        dps = sorted(s.dps for s in ev.standard if s.names == names)
        assert ev.lineup_median[names] < dps[-1]


def test_skirk_without_cryo_and_hydro_teammates_is_atypical_not_invalid():
    from gtc import typicality
    found = typicality.findings(["Skirk", "Chiori", "Lan Yan", "Zhongli"], "Skirk")
    assert any(f.startswith("carry_needs") for f in found)
    assert not typicality.findings(["Skirk", "Escoffier", "Furina", "Citlali"], "Skirk")
    assert typicality.sd_factor(len(found)) > 1


def test_team_whose_damage_is_raidens_is_not_an_anemo_carry_team():
    from scenarios import account, engine
    from gtc.teams import fill_template
    am = engine()
    roster = account(["Kaedehara Kazuha", "Raiden Shogun", "Shenhe", "Citlali"])
    # Phase 9: the Anemo template may generate it (provenance only), but its identity is Raiden's team.
    for team in fill_template(am.kb.templates["auto_anemo_carry"], roster, am.kb, limit=1, rank_by="potential"):
        a = am._assess(team)
        assert a.primary_actor != "Kaedehara Kazuha" and not a.label.startswith("Kaedehara Kazuha")


def test_only_moonsign_carries_lead_lunar_charged():
    """Clorinde out-damages Ineffa in some Lunar-supported teams, but her damage is her own Electro, not
    Lunar-Charged. Only a carry with a Moonsign kit can lead a Lunar family."""
    from gtc import knowledge
    kb = knowledge.load()
    leaders = {n for n, i in kb.characters.items() if i.roles.get("carry_lunar_charged")}
    assert "Clorinde" not in leaders and "Flins" in leaders
