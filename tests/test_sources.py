"""Source parsers and the evidence layer, tested on small synthetic inputs (no network)."""
import json

from gtc import knowledge
from gtc.evidence import Evidence, _matches, expert_level, fit_calibration
from gtc.sources import kqm, prydwen
from gtc.sources.gcsim_db import SimMember, SimTeam, is_standard
from gtc.sources.names import Names, kqm_slugs

KB = knowledge.load()
NAMES = Names(["Kamisato Ayaka", "Flins", "Ineffa", "Columbina", "Sucrose", "Aino", "Skirk", "Shenhe", "Furina",
               "Mona", "Kaedehara Kazuha", "Fischl"], {"Deathmatch": 4, "Bloodsoaked Ruins": 5, "Mistsplitter Reforged": 5})
GAME = {n: {"element": e, "rarity": r} for n, e, r in [
    ("Flins", "Electro", 5), ("Ineffa", "Electro", 5), ("Columbina", "Hydro", 5), ("Sucrose", "Anemo", 4),
    ("Aino", "Hydro", 4), ("Kamisato Ayaka", "Cryo", 5), ("Skirk", "Cryo", 5), ("Shenhe", "Cryo", 5),
    ("Furina", "Hydro", 5), ("Mona", "Hydro", 5), ("Kaedehara Kazuha", "Anemo", 5), ("Fischl", "Electro", 4)]}


def sim(dps, *members, tags=(1,), targets=1):
    ms = [SimMember(n, GAME[n]["rarity"], c, w, wr, r) for n, c, w, wr, r in members]
    return SimTeam(id=str(dps), date=0, description="", targets=targets, dps=dps, tags=list(tags), members=ms)


def std(name, cons=0):
    return (name, cons, "Deathmatch", 4, 1)


def test_names_match_across_sources():
    assert NAMES.character("kamisato-ayaka") == "Kamisato Ayaka"
    assert NAMES.character("kamisatoayaka") == "Kamisato Ayaka"
    assert NAMES.character("ayaka") == "Kamisato Ayaka"
    assert NAMES.character("luminecryo") == "Traveler (Cryo)"
    assert kqm_slugs("Kamisato Ayaka")[:2] == ["kamisato-ayaka", "ayaka"]


def test_standard_filter():
    assert is_standard(sim(1, std("Flins"), std("Ineffa"), std("Columbina"), std("Sucrose", 6)))
    assert not is_standard(sim(1, std("Flins", 1), std("Ineffa"), std("Columbina"), std("Sucrose")))
    assert not is_standard(sim(1, ("Flins", 0, "Bloodsoaked Ruins", 5, 2), std("Ineffa"), std("Columbina"), std("Sucrose")))
    assert not is_standard(sim(1, std("Flins"), std("Ineffa"), std("Columbina"), std("Sucrose"), targets=2))


def evidence(sims, tiers=None):
    return Evidence(KB, GAME, sims, {"tiers": tiers or {}, "characters": {}}, {})


def test_pure_carry_blocks_attribution():
    skirk_team = sim(115000, std("Skirk"), std("Kamisato Ayaka"), std("Furina"), std("Shenhe"))
    ev = evidence([skirk_team], tiers={"Skirk": [{"category": "DPS", "overall": "T0.5", "tags": [], "stygian": [], "assumed_constellation": "C0"}]})
    # Both are pure carries, so the sim is ambiguous and counts for neither.
    assert not ev.attributed(skirk_team, "Kamisato Ayaka")
    assert not ev.attributed(skirk_team, "Skirk")
    ayaka_team = sim(100000, std("Kamisato Ayaka"), std("Furina"), std("Shenhe"), std("Kaedehara Kazuha"))
    assert ev.attributed(ayaka_team, "Kamisato Ayaka")


def test_measured_fit_compares_standard_with_standard():
    best = sim(150000, std("Flins"), std("Ineffa"), std("Columbina"), std("Sucrose", 6))
    mine = sim(120000, std("Flins"), std("Ineffa"), std("Aino", 6), std("Sucrose", 6))
    ev = evidence([best, mine])
    fit = ev.measured_fit(KB.templates["lunar_charged"], ["Flins", "Aino", "Ineffa", "Sucrose"], "Flins")
    assert fit.source == "gcsim" and round(fit.value) == 80
    tier, _ = ev.archetype_tier(KB.templates["lunar_charged"], "Flins")
    assert tier.source == "gcsim" and tier.value == 100  # it is the only, so the strongest, lineup


def test_calibration_learns_the_curve():
    # Model says 90 where reality is 81 and 80 where reality is 64: measured = model ** 2 on the 0-1 scale.
    anchors = [(f"x{i}", "freeze", "Ayaka", m, 100 * (m / 100) ** 2) for i, m in enumerate([90, 80, 70, 95, 85])]
    cal = fit_calibration(anchors, set(), prior_weight=0)
    assert abs(cal.k - 2) < 0.01
    assert cal.error(True, set(), local=False) < cal.error(False, set())


def test_prydwen_parsers():
    payload = json.dumps(json.dumps({"_tierRatings": [{"slug": "flins", "category": "DPS", "ratingOverall": "T0.5",
                                                        "ratingBoss1": "T1", "ratingBoss2": None, "ratingBoss3": "T1",
                                                        "tags": "comfort", "dupes": "C0", "marks": ""}]}, separators=(",", ":")))[1:-1]
    tiers = prydwen.parse_tiers(f"<script>{payload}</script>", NAMES)
    assert tiers["Flins"][0]["overall"] == "T0.5" and tiers["Flins"][0]["tags"] == ["comfort"]

    page = (
        '<div class="team-chart-row source-team-row" style="--team-percent:61.7%">'
        '<a class="team-member-card lead-member" href="/genshin-impact/characters/flins"><strong>Flins</strong><em><span>100 ER</span></em></a>'
        '<a class="team-member-card" href="/genshin-impact/characters/aino"><span class="member-constellation">C6</span><strong>Aino</strong></a>'
        '<div class="team-chart-meta"><span>Budget</span><strong>Flins Budget</strong><em>Cheap.</em></div>'
        '<div class="team-chart-value">61.7%</div></div>'
        '<div class="build-rank-table constellation-rank-table"><div class="build-rank-row"><span class="constellation-rank-name">C1</span>'
        '<strong>126%</strong><strong>111%</strong></div></div>'
    )
    c = prydwen.parse_character(page, NAMES)
    assert c["teams"][0]["percent"] == 61.7
    assert [m["name"] for m in c["teams"][0]["members"]] == ["Flins", "Aino"]
    assert c["teams"][0]["members"][1]["cons"] == 6
    assert c["constellations"] == [{"constellation": 1, "personal": 126.0, "team": 111.0, "info": ""}]


def test_kqm_example_teams_and_matching():
    page = ("<h3>Example Teams</h3><figure><figcaption><strong>Flins — Ineffa — Columbina/Aino — Sucrose</strong></figcaption></figure>"
            "<p>The standard setup.</p>")
    g = kqm.parse_guide(page, NAMES)
    assert g["example_teams"][0]["slots"] == [["Flins"], ["Ineffa"], ["Columbina", "Aino"], ["Sucrose"]]
    assert g["example_teams"][0]["description"] == "The standard setup."
    assert _matches(g["example_teams"][0]["slots"], ["Flins", "Aino", "Ineffa", "Sucrose"])
    assert not _matches(g["example_teams"][0]["slots"], ["Flins", "Fischl", "Ineffa", "Sucrose"])


def test_expert_tag():
    assert expert_level(["expert (-2)", "flexible"]) == 2
    assert expert_level(["comfort"]) == 0
