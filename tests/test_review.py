"""Account review pieces: stat parsing, guide parsing, config rewriting, team checks. No network, no gcsim."""
import json

from gtc.importers import good
from gtc.importers.hoyolab import _artifact
from gtc.review import Guides, check_team_sets
from gtc.sim import Build, Config, Keys, render
from gtc.snapshot import Artifact, Character, Talents, Weapon
from gtc.sources import kqm
from gtc.sources.names import Names
from gtc.stats import crit_value, parse_priority

NAMES = Names(["Flins", "Ineffa", "Aino", "Sucrose", "Fischl", "Bennett", "Kaedehara Kazuha", "Xiangling", "Raiden Shogun", "Kamisato Ayaka"],
              {"Favonius Sword": 4, "Deathmatch": 4, "Bloodsoaked Ruins": 5},
              ["Viridescent Venerer", "Night of the Sky's Unveiling", "Noblesse Oblige"])


def test_stat_priority_phrases():
    assert parse_priority("ER (until requirement) > CRIT > ATK% > EM") == [["enerRech_"], ["critRate_", "critDMG_"], ["atk_"], ["eleMas"]]
    assert parse_priority("Electro DMG Bonus / ATK%") == [["electro_dmg_", "atk_"]]
    assert parse_priority("Elemental DMG Bonus") == [["elemental_dmg_"]]


def test_hoyolab_artifact_keeps_substats_and_rolls():
    raw = {"pos": 3, "set": {"name": "Blizzard Strayer"}, "rarity": 5, "level": 20,
           "main_property": {"property_type": 6, "value": "46.6%"},
           "sub_property_list": [{"property_type": 20, "value": "6.6%", "times": 1}, {"property_type": 22, "value": "13.2%", "times": 1}]}
    a = _artifact(raw, "Kamisato Ayaka")
    assert (a.slot_name, a.main_stat, a.main_value) == ("sands", "atk_", 46.6)
    assert a.substats[0] == {"key": "critRate_", "value": 6.6, "rolls": 2}
    assert crit_value(a.substats) == 26.4


GUIDE = """
<h2><span class="ez-toc-section" id="Talents"></span>Talents</h2>
<p class="has-text-align-center substats has-background"><strong>Burst &gt; Level 90 &gt; Skill</strong></p>
<h2><span class="ez-toc-section" id="ER_Requirements"></span>ER Requirements</h2>
<table><tbody><tr><td>Solo Pyro</td><td>Double Pyro</td><td>With Raiden</td></tr><tr><td>195–255%</td><td>175–220%</td><td>145–210%</td></tr></tbody></table>
<h2><span class="ez-toc-section" id="Artifact_Stats"></span>Artifact Stats</h2>
<table><tbody><tr><td><strong>Sands</strong></td><td><strong>Goblet</strong></td><td><strong>Circlet</strong></td></tr>
<tr><td>ATK% &gt; EM</td><td>ATK%</td><td>CRIT DMG / CRIT Rate</td></tr></tbody></table>
<p class="substats"><strong>Stat Priority:</strong> ER (until requirement) &gt; CRIT &gt; ATK%</p>
<h2><span class="ez-toc-section" id="Artifact_Sets"></span>Artifact Sets</h2>
<table class="weapon-table"><tbody><tr><td><strong>4pc Night of the Sky&#8217;s Unveiling (NotSU)</strong></td><td>Best set.</td></tr></tbody></table>
<h1><span class="ez-toc-section" id="Weapons"></span>Weapons</h1>
<table class="weapon-table"><tbody><tr><td><strong>5★ Bloodsoaked Ruins</strong></td><td>Signature.</td></tr>
<tr><td><strong>4★ Deathmatch (R5)</strong></td><td>Good.</td></tr></tbody></table>
<h2><span class="ez-toc-section" id="Teambuilding"></span>Teambuilding</h2>
<div class="ub-content-filter-panel" data-selectedFilters="[0]"><h4>Electro</h4><p>Pick one.</p>
<table class="weapon-table"><tbody><tr><td><strong>Ineffa</strong></td><td>Best.</td></tr><tr><td><strong>Fischl</strong></td><td>Good.</td></tr></tbody></table></div></div>
<h3>Example Teams</h3>
"""


def test_kqm_build_sections():
    b = kqm.parse_build(GUIDE, NAMES)
    assert b["talent_priority"]["order"] == ["burst", "level", "skill"]
    er = b["er_requirements"][0]
    assert er["columns"] == ["Solo Pyro", "Double Pyro", "With Raiden"] and er["rows"][0]["values"][1] == [175, 220]
    assert b["main_stats"]["sands"] == [["atk_"], ["eleMas"]]
    assert b["substat_priority"]["tiers"][1] == ["critRate_", "critDMG_"]
    assert b["artifact_sets"][0]["pieces"] == [{"count": 4, "set": "Night of the Sky’s Unveiling"}]
    assert [w["name"] for w in b["weapons"]] == ["Bloodsoaked Ruins", "Deathmatch"]
    assert [o["name"] for o in b["teammates"][0]["options"]] == ["Ineffa", "Fischl"]


class _Ev:
    def __init__(self, kqm_data):
        self.kqm, self.prydwen = kqm_data, {"characters": {}}


def test_er_target_reads_team_composition():
    data = {"Bennett": {"er_requirements": kqm.parse_build(GUIDE, NAMES)["er_requirements"]}}
    elements = {"Bennett": "Pyro", "Xiangling": "Pyro", "Raiden Shogun": "Electro", "Kaedehara Kazuha": "Anemo"}
    g = Guides(_Ev(data), NAMES, elements)
    (lo, hi), _ = g.er_target("Bennett", ["Bennett", "Xiangling", "Kaedehara Kazuha", "Fischl"], 5)
    assert (lo, hi) == (175, 220)  # Double Pyro


CONFIG = """options iteration=1000;
flins char lvl=90/90 cons=0 talent=9,9,9;
flins add weapon="deathmatch" refine=1 lvl=90/90;
flins add set="notsu" count=4;
flins add stats hp=4780 atk=311 atk%=0.466;
flins add stats cr=0.3 cd=0.6;
target lvl=100;
flins skill;
"""


def test_config_rewrite_uses_your_build():
    cfg = Config(CONFIG, "x", 100.0, {"Flins": "flins"})
    b = Build(level=80, cons=1, talents=(1, 2, 7), weapon="Bloodsoaked Ruins", refine=1, weapon_level=80,
              sets={"Night of the Sky's Unveiling": 2}, stats={"atk_": 46.6, "critRate_": 10.0, "eleMas": 40})
    text, problems = render(cfg, {"Flins": b}, Keys(), iterations=50)
    assert "flins char lvl=80/90 cons=1 talent=1,2,7;" in text
    assert 'flins add weapon="bloodsoakedruins" refine=1 lvl=80/90;' in text
    assert 'add set="nightoftheskysunveiling" count=2;' in text
    assert "flins add stats atk%=0.466 cr=0.1 em=40;" in text
    assert "add stats hp=4780" not in text and "iteration=50" in text and "flins skill;" in text
    assert problems == []


def _char(name, element, sets):
    arts = [Artifact(slot=i, set_name=s, rarity=5, level=20, main_stat="hp") for i, s in enumerate(sets, start=1)]
    return Character(1, name, element, 5, 90, 0, Talents(9, 9, 9), Weapon("Deathmatch", 4, 90, 1), arts, {})


class _A:
    def __init__(self, members, lead):
        class T:
            pass
        self.team = T()
        self.team.members, self.team.fills, self.lead = members, [], lead


def test_team_set_checks():
    rules = {"Viridescent Venerer": {"one_per_team": True, "holder_elements": ["Anemo"], "wanted_when": {"elements_any": ["Anemo"]}},
             "Noblesse Oblige": {"one_per_team": True}}
    chars = {"Flins": _char("Flins", "Electro", ["Noblesse Oblige"] * 4), "Bennett": _char("Bennett", "Pyro", ["Noblesse Oblige"] * 4),
             "Kaedehara Kazuha": _char("Kaedehara Kazuha", "Anemo", ["Gladiator's Finale"] * 4)}
    out = check_team_sets(_A(list(chars), "Flins"), chars, Guides(_Ev({}), NAMES), rules)
    texts = " ".join(f.text for f in out)
    assert "both use 4pc Noblesse Oblige" in texts
    assert "Nobody holds 4pc Viridescent Venerer. Kaedehara Kazuha is the natural holder." in texts


def test_good_inventory_import(tmp_path):
    f = tmp_path / "good.json"
    f.write_text(json.dumps({"format": "GOOD", "version": 2,
        "weapons": [{"key": "FavoniusSword", "level": 90, "ascension": 6, "refinement": 3, "location": ""},
                    {"key": "Deathmatch", "level": 90, "refinement": 1, "location": "Flins"}],
        "artifacts": [{"setKey": "ViridescentVenerer", "slotKey": "sands", "rarity": 5, "level": 20, "mainStatKey": "eleMas",
                       "substats": [{"key": "critRate_", "value": 6.6}], "location": ""}]}), encoding="utf-8")
    weapons, artifacts = good.parse(f, NAMES, {"Favonius Sword": {"rarity": 4, "type": "sword_one_hand"}})
    assert [(w.name, w.refinement, w.location) for w in weapons] == [("Favonius Sword", 3, None)]
    assert artifacts[0].set_name == "Viridescent Venerer" and artifacts[0].slot_name == "sands"
    assert artifacts[0].substats[0]["rolls"] == 2
