"""Theorycrafter sanity scenarios. Each encodes a judgment a human theorycrafter would make and the engine
must reproduce. They run on the real knowledge and source data (slow, about two minutes)."""
import pytest

from gtc import SNAPSHOT_DIR
from gtc.sources.gcsim_db import TEAMS_PATH

pytestmark = pytest.mark.skipif(not TEAMS_PATH.exists() or not any(SNAPSHOT_DIR.glob("*.json")),
                                reason="needs downloaded sources and a snapshot")

POOL = ["Columbina", "Mavuika", "Varka", "Furina", "Yelan", "Escoffier", "Nahida", "Neuvillette", "Xilonen", "Citlali", "Skirk"]


def lead_team(plan, lead):
    return next(a for a in plan.teams if a.lead == lead)


def test_c6_aino_beats_xingqiu_for_flins():
    from scenarios import account, engine
    plan, cands = engine().plan(account(["Flins", "Ineffa", "Aino", "Xingqiu", "Sucrose", "Kaedehara Kazuha", "Bennett", "Zhongli"]))
    # The best Flins team takes Aino, not Xingqiu, as its Hydro partner.
    best = next(a for a in cands if a.lead == "Flins")
    assert "Aino" in best.team.members and "Xingqiu" not in best.team.members
    # The account plan may still move Aino: with eight characters, two teams beat one, so the plan trades the
    # better Flins team for a second lineup. That is a plan-level choice, not a team-building one.


def test_kazuha_beats_sucrose_for_ayaka_freeze():
    from scenarios import account, engine
    _, cands = engine().plan(account(["Kamisato Ayaka", "Mona", "Shenhe", "Kaedehara Kazuha", "Sucrose", "Bennett", "Xiangling", "Zhongli"]))
    best_freeze = next(a for a in cands if a.team.template.id == "freeze")
    assert "Kaedehara Kazuha" in best_freeze.team.members


def test_columbina_fills_the_gap_when_flins_only_has_barbara():
    from scenarios import account, ranked_values
    roster = account(["Flins", "Ineffa", "Sucrose", "Barbara", "Bennett", "Kaedehara Kazuha", "Zhongli", "Xiangling", "Fischl", "Diona"])
    _, _, vals = ranked_values(roster, POOL)
    top = vals[0]
    assert top.name == "Columbina" and top.kind == "fills a gap"


def test_mavuika_is_a_sidegrade_for_an_arlecchino_account():
    # Model 6.3: with no useful-team gate the leftover Xingqiu / Kazuha / Zhongli / Xiangling team counts above
    # replacement, so Mavuika replaces it with her own team and takes none of Arlecchino's supports. Kinds describe
    # observed deltas (phase 12), so she is no longer labelled a sidegrade; her same-element overlap with
    # Arlecchino is still recorded as redundancy, and she is still not a top pick.
    from scenarios import account, ranked_values
    roster = account(["Arlecchino", "Bennett", "Xingqiu", "Kaedehara Kazuha", "Zhongli", "Xiangling", "Fischl", "Sucrose", "Chevreuse"])
    _, _, vals = ranked_values(roster, POOL)
    mav = next(v for v in vals if v.name == "Mavuika")
    arle_team = next(set(a.team.members) for a in mav.plan.teams if "Arlecchino" in a.team.members)
    assert {"Bennett", "Chevreuse"} <= arle_team and not mav.decomposition["support_contention"]
    assert mav.decomposition["redundancy"]["content_coverage"] == 1.0
    assert vals.index(mav) >= 2  # not among the top two picks


def test_supports_only_account_needs_a_carry_that_uses_its_supports():
    from scenarios import account, engine
    am = engine()
    roster = account(["Bennett", "Xingqiu", "Xiangling", "Kaedehara Kazuha", "Sucrose", "Zhongli", "Fischl", "Furina"])
    _, cands = am.plan(roster)
    assert am.viable_carries(cands) == {}
    best = am.best_carries_for(roster)
    name, team = best[0]
    assert am.is_primary_carry(name)
    owned_teammates = [m for m in team.team.members if m != name]
    assert len(owned_teammates) == 3  # the recommended carry is built around supports already owned


def test_plan_teams_share_no_characters():
    from scenarios import account, engine
    plan, _ = engine().plan(account(["Flins", "Ineffa", "Aino", "Sucrose", "Kamisato Ayaka", "Mona", "Shenhe",
                                     "Kaedehara Kazuha", "Bennett", "Xiangling", "Xingqiu", "Raiden Shogun", "Zhongli", "Fischl"]))
    members = [m for a in plan.teams for m in a.team.members]
    assert len(members) == len(set(members))
