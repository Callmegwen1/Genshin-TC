"""Phase 5: the TeamEvaluation pipeline and power decoupled from the generating template."""
import inspect
from functools import lru_cache

import pytest

from gtc import gamedata, knowledge
from gtc.evaluate import evaluate, lineup_power
from gtc.pairmodel import PairModel, load as load_pairs
from gtc.report import Model, build_universe, load_evidence
from gtc.teams import Member, fill_template


@lru_cache(maxsize=1)
def _ctx():
    kb = knowledge.load()
    ev = load_evidence(kb)
    return kb, ev, Model(kb, build_universe(kb, ev))


def _roster(kb, ev, names):
    game = gamedata.load_characters()
    out = []
    for n in names:
        c = 6 if game[n]["rarity"] == 4 else 0
        out.append(Member(n, game[n]["element"], 1.0, {**kb.characters[n].roles_at(c), **ev.faction_roles(n)}, c))
    return out


def _evaluations(names):
    kb, ev, model = _ctx()
    roster = _roster(kb, ev, names)
    out = []
    for t in kb.templates.values():
        for team in fill_template(t, roster, kb, limit=1):
            if set(team.members) == set(names):
                out.append(evaluate(team, ev, model, kb))
    return out


def test_power_does_not_depend_on_the_generating_template():
    # Several archetypes generate this lineup; before phase 5 one of them rated it 0 and another 54.
    evals = _evaluations(["Nahida", "Kuki Shinobu", "Xingqiu", "Yelan"])
    assert len({e.generated_by for e in evals}) >= 2
    values = {round(e.power["single_target"].expected, 6) for e in evals}
    assert len(values) == 1
    assert {e.power["single_target"].basis.route for e in evals} == {"exact_community"}


def test_a_simulated_lineup_is_valued_by_its_own_simulations():
    kb, ev, _ = _ctx()
    lineup = frozenset(["Nahida", "Kuki Shinobu", "Xingqiu", "Yelan"])
    p = lineup_power(lineup, ev)
    assert p.basis.route == "exact_community" and p.basis.tier == "B" and p.basis.member_distance == 0
    assert p.expected == pytest.approx(min(100.0, 100 * ev.lineup_median[lineup] / ev.normalizer))


def test_unsimulated_lineups_use_the_pair_model_with_their_distance():
    kb, ev, _ = _ctx()
    sim = next(k for k in sorted(ev.lineup_median, key=sorted) if len(k) == 4 and "Bennett" not in k
               and load_pairs().known(k))
    one_away = frozenset(sorted(sim)[:3] + ["Bennett"])
    if one_away in ev.lineup_median:
        pytest.skip("neighbour happens to be simulated")
    from gtc import distance

    f, near, away = distance.for_lineup(one_away, ev)
    assert away == 1 and len(near & one_away) == 3 and f["away"] == 1
    p = lineup_power(one_away, ev)
    assert p.basis.route == "pair_model" and p.basis.tier == "C"


def test_pair_model_has_no_archetype_term():
    assert "family" not in inspect.signature(PairModel.predict).parameters
    assert not hasattr(load_pairs(), "families")


def test_evaluation_record_carries_every_part():
    (e, *_) = _evaluations(["Nahida", "Kuki Shinobu", "Xingqiu", "Yelan"])
    assert e.lineup == frozenset(["Nahida", "Kuki Shinobu", "Xingqiu", "Yelan"])
    assert e.structure and e.structure["source"] == "measured"
    assert set(e.power) >= {"single_target", "aoe"}
    assert e.validity["ok"] and e.identity["archetype"] == e.generated_by
    assert "tier" in e.explanation and "fit" in e.explanation
