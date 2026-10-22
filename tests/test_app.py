"""UI phase: presentation layer (derived, never scored), application service, local HTTP API."""
import json
import threading
import urllib.request
from functools import lru_cache

import pytest

from gtc import SNAPSHOT_DIR


def _have_snapshot():
    return SNAPSHOT_DIR.exists() and any(SNAPSHOT_DIR.glob("*.json"))


pytestmark = pytest.mark.skipif(not _have_snapshot(), reason="needs an imported account snapshot")


@lru_cache(maxsize=1)
def _svc():
    from gtc.app.service import AppService

    s = AppService()
    s.load(background=False)  # no background thread outliving the test
    return s


def test_team_insights_are_structured_and_grounded():
    s = _svc()
    r = s.evaluate_team(["Hu Tao", "Xingqiu", "Yelan", "Zhongli"], substitutions=False)
    t = r["team"]
    assert {"strengths", "problems"} <= set(t)
    for x in t["strengths"]:
        assert {"type", "text", "evidence"} <= set(x)
    for x in t["problems"]:
        assert {"type", "severity", "text"} <= set(x) and x["severity"] in ("low", "medium", "high")
    assert any(p["type"] == "evidence" and "Poor community data" in p["text"] for p in t["problems"])


def test_substitutions_follow_compare():
    from gtc.app import present

    s = _svc()
    plan_team = sorted(s.plan.teams, key=lambda t: -t.potential)[0].team.members
    subs = present.substitutions(s.am, list(plan_team), s.roster, s.plan, s.advisor)
    assert set(subs) == {"direct", "rebuild", "experimental_hidden"}
    for x in subs["rebuild"]:
        assert x["kind"] == "rebuild" and x["recommendability"] in ("established", "credible")
    for x in subs["direct"]:
        assert x["kind"] in ("upgrade", "alternative", "frees a contested support")
        assert (x["kind"] == "upgrade") == (x["comparison"] == "better")
        assert (x["kind"] == "alternative") == (x["comparison"] == "roughly_equal")
        assert x["out"] in plan_team and x["in"] not in plan_team


def test_allocation_explanations_only_explain_a_better_plan():
    s = _svc()
    from gtc.app import present

    rows = present.allocation_explanations(s.am, s.plan, s.cands, s.roster)
    for r in rows:
        assert r["gain_on_a"] > 0  # the unit really is individually stronger on the other team
        assert r["net_account_effect"] >= 0  # and the chosen allocation is still better for the account
        assert r["unit"] in r["placed_on"] and r["unit"] not in r["alternative_team"]


def test_pull_pros_cons_never_change_the_gain():
    from gtc.app import present

    s = _svc()
    name = next(n for n in sorted(s.am.universe) if n not in s.owned and s.kb.characters.get(n) and not s.kb.characters[n].provisional)
    v = s.am.value_of(name, s.roster, s.plan, s.cands)
    before = (v.gain, v.estimate.value)
    pc = present.pull_pros_cons(v)
    assert set(pc) == {"pros", "cons"} and (v.gain, v.estimate.value) == before


def test_no_change_pulls_are_never_competitive():
    s = _svc()
    for name in [n for n in sorted(s.am.universe) if n not in s.owned][:25]:
        if name not in s.values:
            v = s.am.value_of(name, s.roster, s.plan, s.cands)
            if v is not None:
                s.values[name] = v
    groups = s.recommended_pulls()["groups"]
    for c in groups["Competitive / roughly equal"] + groups["Clear recommendation"]:
        assert c["kind"] != "no change"


def test_manual_team_and_illegal_team():
    s = _svc()
    r = s.evaluate_team(["Hu Tao", "Kamisato Ayaka", "Raiden Shogun", "Neuvillette"], substitutions=False)
    assert r["legal"] and r["team"]["status"] in ("unusual", "well_supported", "provisional")
    bad = s.evaluate_team(["Bennett", "Bennett", "Xingqiu", "Zhongli"])
    assert not bad["legal"] and bad["reasons"]


def test_http_api_round_trip():
    from http.server import ThreadingHTTPServer

    import gtc.app.service as svc_mod
    from gtc.app.server import Handler

    svc_mod._SERVICE = _svc()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{port}"
        status = json.load(urllib.request.urlopen(base + "/api/status"))
        assert status["loaded"]
        plan = json.load(urllib.request.urlopen(base + "/api/teams?overlap=0"))
        assert plan["overlap"] is False and len(plan["teams"]) >= 1
        names = [m for t in plan["teams"] for m in t["lineup"]]
        assert len(names) == len(set(names))  # no character twice without overlap
        req = urllib.request.Request(base + "/api/team", data=json.dumps({"lineup": plan["teams"][0]["lineup"], "substitutions": False}).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        team = json.load(urllib.request.urlopen(req))
        assert team["legal"] and team["team"]["ceiling"]["expected"] > 0
        page = urllib.request.urlopen(base + "/").read().decode()
        assert "Account Advisor" in page
        catalog = json.load(urllib.request.urlopen(base + "/api/characters"))
        assert any(not c["owned"] for c in catalog) and any(c["owned"] for c in catalog)
        assert all("uid" not in json.dumps(c).lower() for c in catalog[:3])
    finally:
        httpd.shutdown()
