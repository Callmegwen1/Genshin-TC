"""The pair model recovers known effects from synthetic lineups."""
import math
import random
from itertools import combinations


def _synthetic(n=600, seed=3):
    rng = random.Random(seed)
    chars = [f"C{i}" for i in range(14)]
    strength = {c: rng.uniform(-0.2, 0.2) for c in chars}
    core = {"C1", "C2"}  # planted pair: +30% together
    data, seen = [], set()
    while len(data) < n:
        lineup = frozenset(rng.sample(chars, 4))
        if lineup in seen:
            continue
        seen.add(lineup)
        v = 11 + sum(strength[c] for c in lineup) + (math.log(1.3) if core <= lineup else 0) + rng.gauss(0, 0.02)
        data.append((lineup, math.exp(v), 1, "other", None))
    return data


def test_recovers_a_planted_pair_effect():
    from gtc import pairmodel
    model = pairmodel.fit(_synthetic())
    effect, se = model.pair_effect("C1", "C2")
    assert abs(effect - 0.30) < 0.05 and effect / se > 5
    others = [abs(model.pair_effect(a, b)[0]) for a, b in combinations(sorted(model.chars), 2)
              if {a, b} != {"C1", "C2"} and model.pair_effect(a, b)]
    assert max(others) < 0.08


def test_predicts_held_out_lineups():
    from gtc import pairmodel
    data = _synthetic()
    cv = pairmodel.cross_validate(data, folds=5)
    assert cv["all"]["median_error"] < 0.03
