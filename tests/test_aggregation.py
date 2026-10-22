"""Lineup values are robust to who submitted the simulations (gcsim_db.aggregate)."""
from gtc.sources.gcsim_db import SimTeam, aggregate


def _sims(rows):
    return [SimTeam(id=str(i), date=0, description="", targets=1, dps=d, tags=[1], members=[], submitter=who)
            for i, (who, d) in enumerate(rows)]


BASE = [("a", 100.0), ("b", 104.0), ("c", 96.0), ("d", 102.0), ("e", 98.0)]


def test_duplicating_one_submitters_runs_changes_nothing():
    base = aggregate(_sims(BASE)).value
    assert aggregate(_sims(BASE + [("a", 100.0)] * 50)).value == base  # the same run re-submitted 50 times


def test_one_submitter_flooding_high_runs_moves_at_most_to_the_next_submitter():
    flooded = aggregate(_sims(BASE + [("a", 140.0)] * 50)).value  # their vote becomes 140, still one vote
    assert flooded <= 102.0  # the next submitter's value; a plain median of all runs would be 140


def test_removing_the_most_prolific_submitter_moves_little():
    rows = BASE + [("a", 101.0)] * 20
    full = aggregate(_sims(rows)).value
    without = aggregate(_sims([r for r in rows if r[0] != "a"])).value
    assert abs(without / full - 1) < 0.03


def test_one_author_cannot_dominate():
    v = aggregate(_sims([("x", 200.0)] * 30 + [("b", 100.0), ("c", 102.0)]))
    assert v.n_submitters == 3 and v.value <= 102.0  # the prolific author is one vote of three


def test_outliers_have_bounded_influence():
    normal = aggregate(_sims(BASE)).value
    wild = aggregate(_sims(BASE[:-1] + [("e", 10_000.0)])).value
    assert abs(wild / normal - 1) < 0.03


def test_unknown_submitters_count_as_one_vote():
    v = aggregate(_sims([("migrated", 90.0), ("", 95.0), ("migrated", 300.0), ("b", 100.0)]))
    assert v.n_submitters == 2 and set(v.by_submitter) == {"unknown", "b"}


def test_uncertainty_follows_independent_submitters():
    from gtc.estimate import community_rel_sd
    one = aggregate(_sims([("a", 100.0)] * 10))
    many = aggregate(_sims(BASE))
    assert one.n_submitters == 1 and many.n_submitters == 5
    assert community_rel_sd(many.n_submitters) < community_rel_sd(one.n_submitters)
