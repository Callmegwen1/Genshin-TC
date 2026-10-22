"""Theorycrafting without the team's own simulations (rotation steps 1-2): action libraries measured from other
teams, the rotation generator, and the blind harness. gcsim runs are cached (data/sims)."""
import pytest

from gtc.sim import GCSIM

AYAKA_MONA = ["Kamisato Ayaka", "Shenhe", "Kaedehara Kazuha", "Mona"]
needs_gcsim = pytest.mark.skipif(not GCSIM.exists(), reason="local gcsim binary missing")


@needs_gcsim
def test_library_never_uses_the_blind_team():
    from gtc.forward.library import source_lineups

    for m in AYAKA_MONA:
        assert frozenset(AYAKA_MONA) not in {frozenset(x) for x in source_lineups(m, [AYAKA_MONA])}


@needs_gcsim
def test_library_measures_character_facts():
    from gtc.forward.library import build

    ayaka = build("Kamisato Ayaka", [AYAKA_MONA], role="carry", measured=True)   # the trace-measured path
    assert {"attack#0", "attack#1", "charge", "skill", "burst", "dash"} <= set(ayaka.actions)
    assert 18 <= len(ayaka.actions["burst"].hits) <= 22           # 19 cuts and the bloom
    kazuha = build("Kaedehara Kazuha", [AYAKA_MONA], role="support", measured=True)
    assert kazuha.follow.get("skill") == "high_plunge" and kazuha.actions["skill"].particles >= 3
    assert any(h.reaction == "swirl" for h in kazuha.actions["skill"].hits)


@needs_gcsim
def test_generator_respects_cooldowns_and_searches_orders():
    from gtc.forward.build import house_builds
    from gtc.forward.generator import _cd, candidates, generate
    from gtc.forward.library import build

    libs = {m: build(m, [AYAKA_MONA], role="carry" if m == "Kamisato Ayaka" else "support") for m in AYAKA_MONA}
    plans = candidates(AYAKA_MONA, libs)
    ayaka = [p for p in plans if p.carries == ("Kamisato Ayaka",)]
    assert len({p.supports for p in ayaka}) == 6                  # every support order, no ordering heuristic
    assert {p.carries for p in plans} >= {("Kamisato Ayaka",), ("Mona",)}   # any member may drive
    rot = generate(AYAKA_MONA, libs, house_builds(AYAKA_MONA, {m: 3.0 for m in AYAKA_MONA}), plans[0], 20)
    for m in AYAKA_MONA:
        for kind in ("skill", "burst"):
            ts = [a.t for a in rot.actions if a.char == m and a.action == kind]
            assert all(b - a >= _cd(m, kind) - 0.05 for a, b in zip(ts, ts[1:]))


@needs_gcsim
def test_blind_ayaka_freeze_lands_near_gcsim():
    from gtc.forward.blind import reveal, theorycraft

    r = theorycraft(AYAKA_MONA)
    ref = reveal(AYAKA_MONA)
    assert r["rotation"].source.startswith("generated")
    assert abs(r["evaluation"].dps / ref["gcsim_mean"] - 1) < 0.15
    assert r["evaluation"].damage_share["Kamisato Ayaka"] > 0.45


@needs_gcsim
def test_raiden_and_razor_conflict_emerges_from_their_windows():
    """No rule bans the pair: the generator tries Raiden carrying, Razor carrying, and both windows in turn, and the
    dual plans lose because the rotation stretches past the supports' buffs."""
    from gtc.forward.blind import theorycraft

    r = theorycraft(["Raiden Shogun", "Razor", "Bennett", "Xingqiu"])
    by = r["by_carries"]
    single = max(v["dps"] for k, v in by.items() if "+" not in k)
    dual = max(v["dps"] for k, v in by.items() if "+" in k)
    assert dual < single                       # both windows in turn lose to one carry (no rule says so)
    # the winner is never the two-carry plan; since the quickswap family exists it may be no long driver at all
    # (gcsim agrees here: quickswap 13.7k vs the best single-driver plan's 12.4k, same rotation, same builds)
    assert len(r["plan"].carries) == 1 or r["plan"].family == "quickswap"
