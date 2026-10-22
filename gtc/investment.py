"""Rate how built a character is, from 0 (untouched) to 1 (fully invested).

Artifacts combine how many pieces exist and how levelled they are with their substat quality in useful rolls
(gtc/artifacts.py), weighted by ROLL_QUALITY_SHARE.
"""
from __future__ import annotations

from gtc import params

from dataclasses import dataclass

from gtc.knowledge import CharacterInfo
from gtc.snapshot import Character

ARTIFACT_MAX_LEVEL = {5: 20, 4: 16, 3: 12, 2: 4, 1: 4}
ARTIFACT_RARITY_VALUE = params.get("investment.artifact_rarity_value")
ROLL_QUALITY_SHARE = params.get("investment.roll_quality_share")


def _curve(points: dict, x: float) -> float:
    xs = sorted(points)
    if x <= xs[0]:
        return points[xs[0]]
    for lo, hi in zip(xs, xs[1:]):
        if x <= hi:
            return points[lo] + (points[hi] - points[lo]) * (x - lo) / (hi - lo)
    return points[xs[-1]]


@dataclass
class Investment:
    level: float
    talents: float
    weapon: float
    artifacts: float
    total: float
    artifact_quality: object = None  # gtc.artifacts.ArtifactQuality: useful rolls, quality, saturation


def rate(char: Character, info: CharacterInfo | None, scoring: dict, kqm_entry: dict | None = None) -> Investment:
    from gtc.artifacts import rate as rate_artifacts

    level = _curve(scoring["level_curve"], char.level)

    target = scoring["talent_target"]
    eff = char.talents.effective
    keys = info.key_talents if info else ["skill", "burst"]
    talents = sum(min(1.0, (eff[k] - 1) / (target - 1)) for k in keys) / len(keys)

    weapon = _curve(scoring["level_curve"], char.weapon.level) * scoring["weapon_rarity"].get(char.weapon.rarity, 0.5)

    pieces = sum(
        ARTIFACT_RARITY_VALUE.get(a.rarity, 0) * min(1.0, a.level / ARTIFACT_MAX_LEVEL.get(a.rarity, 20))
        for a in char.artifacts
    ) / 5
    aq = rate_artifacts(char, kqm_entry)
    artifacts = (1 - ROLL_QUALITY_SHARE) * pieces + ROLL_QUALITY_SHARE * aq.quality

    w = scoring["investment_weights"]
    total = w["level"] * level + w["talents"] * talents + w["weapon"] * weapon + w["artifacts"] * artifacts
    return Investment(level=level, talents=talents, weapon=weapon, artifacts=artifacts, total=total, artifact_quality=aq)
