"""Artifact quality by useful rolls.

    useful rolls = sum over substats of (value / one average roll) x weight

Weights come from the character's Keqing Mains substat priority, by tier (first tier 1.0, then decreasing,
see knowledge/model.yaml). Energy Recharge only counts up to the character's requirement: rolls beyond what
the lowest listed requirement needs are not useful. Without a guide, crit counts fully and the scaling stats
partly. Quality is useful rolls over a well-built benchmark (about 30 across five pieces), capped at 1.

Where a personal simulation exists, its "community-standard artifacts" variant measures the real gap; the
review uses that number and this rating is checked against it (`validate`).
"""
from __future__ import annotations

from dataclasses import dataclass

from gtc import params

# One average 5-star substat roll, in the units the snapshot uses (percent for % stats). Game fact.
AVG_ROLL = {"hp": 253.94, "atk": 16.54, "def": 19.68, "hp_": 4.955, "atk_": 4.955, "def_": 6.195,
            "eleMas": 19.815, "enerRech_": 5.505, "critRate_": 3.305, "critDMG_": 6.605}
TIER_WEIGHTS = params.get("artifacts.tier_weights")
FALLBACK_WEIGHTS = params.get("artifacts.fallback_weights")
BENCHMARK_ROLLS = params.get("artifacts.benchmark_rolls")
FLAT_FACTOR = params.get("artifacts.flat_factor")


@dataclass
class ArtifactQuality:
    useful_rolls: float
    quality: float  # useful rolls over the benchmark, capped at 1
    saturation: float  # share of the benchmark reached before the cap (can exceed 1)
    er_capped_rolls: float = 0.0  # Energy Recharge rolls beyond the requirement, not counted
    weights: dict[str, float] | None = None


def weights_for(tiers: list[list[str]]) -> dict[str, float]:
    """Substat weights from priority tiers (GOOD keys). Flat versions of a listed % stat count partly."""
    if not tiers:
        return dict(FALLBACK_WEIGHTS)
    w: dict[str, float] = {}
    for i, tier in enumerate(tiers):
        for key in tier:
            w.setdefault(key, TIER_WEIGHTS[min(i, len(TIER_WEIGHTS) - 1)])
    for pct, flat in (("atk_", "atk"), ("hp_", "hp"), ("def_", "def")):
        if pct in w and flat not in w:
            w[flat] = w[pct] * FLAT_FACTOR
    return w


def er_requirement(kqm_entry: dict | None) -> float | None:
    """The lowest Energy Recharge requirement Keqing Mains lists for the character (percent)."""
    lows = []
    for table in (kqm_entry or {}).get("er_requirements", []):
        for row in table.get("rows", []):
            for v in row.get("values", []):
                if v:
                    lows.append(v[0])
    return min(lows) if lows else None


def rate(char, kqm_entry: dict | None) -> ArtifactQuality:
    tiers = ((kqm_entry or {}).get("substat_priority") or {}).get("tiers") or []
    w = weights_for(tiers)
    rolls: dict[str, float] = {}
    for a in char.artifacts:
        for sub in a.substats:
            key = sub.get("key")
            if key in AVG_ROLL:
                rolls[key] = rolls.get(key, 0.0) + float(sub.get("value") or 0.0) / AVG_ROLL[key]
    capped = 0.0
    need = er_requirement(kqm_entry)
    total_er = (char.stats or {}).get("energy_recharge")
    if need is not None and total_er is not None and rolls.get("enerRech_"):
        excess_rolls = max(0.0, (total_er - need) / AVG_ROLL["enerRech_"])
        capped = min(rolls["enerRech_"], excess_rolls)
        rolls["enerRech_"] -= capped
    useful = sum(w.get(k, 0.0) * v for k, v in rolls.items())
    sat = useful / BENCHMARK_ROLLS if BENCHMARK_ROLLS else 0.0
    return ArtifactQuality(round(useful, 2), min(1.0, sat), round(sat, 3), round(capped, 2), w)


def validate(snapshot, kb=None) -> dict:
    """Rank correlation between useful rolls and the measured artifact gap from personal simulations (the
    "community-standard artifacts" variant: how much more the team deals with standard artifacts). More useful
    rolls should mean a smaller gap, so the target is a correlation of -0.7 or stronger."""
    from gtc import knowledge
    from gtc.review import build_review
    from gtc.sources import kqm

    kb = kb or knowledge.load()
    review = build_review(snapshot, kb)
    guides = kqm.load()
    gaps: dict[str, float] = {}
    for f in review.actions():
        if f.measured and f.category == "artifacts" and f.character:
            gaps[f.character] = max(gaps.get(f.character, 0.0), f.gain or 0.0)
    simulated = set(getattr(review, "simulated_characters", set())) or set(gaps)
    pairs = []
    for c in snapshot.characters:
        if c.key in simulated:
            pairs.append((rate(c, guides.get(c.key)).useful_rolls, gaps.get(c.key, 0.0), c.key))
    return {"n": len(pairs), "spearman": _spearman([p[0] for p in pairs], [p[1] for p in pairs]) if len(pairs) >= 3 else None,
            "pairs": sorted(pairs, key=lambda p: p[0])}


def _spearman(x: list[float], y: list[float]) -> float:
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2
            i = j + 1
        return r
    rx, ry = ranks(x), ranks(y)
    n = len(x)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    vx = sum((a - mx) ** 2 for a in rx) ** 0.5
    vy = sum((b - my) ** 2 for b in ry) ** 0.5
    return cov / (vx * vy) if vx and vy else 0.0
