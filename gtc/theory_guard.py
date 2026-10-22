"""Where the theorycraft calculator (gtc/tc) may be trusted, and where it must refuse.

The calculator rescales measured damage sources with formulas for direct hits, Lunar damage and Swirl. It has no
model of amplifying reactions (Vaporize, Melt), transformative reactions other than Swirl (Overloaded,
Electro-Charged, Superconduct, Shatter, Burning, Bloom, Hyperbloom, Burgeon), catalyze (Aggravate, Spread) or
Lunar-Bloom and Lunar-Crystallize, and it cannot follow how a swap changes reaction frequency or auras.

Validation decides what is supported, not the formulas alone. On 200 sampled one-member swaps across all
families only 33% of predictions were within 10% of gcsim, and swaps whose damage was entirely direct, Lunar or
Swirl did no better (39%): the swapped team usually plays a different rotation, which the calculator cannot
follow. Lunar-Charged teams are the exception: with Lunar-Charged at least MIN_LUNAR_SHARE of the damage before
and after, and the team lead kept, 19 of 20 accepted swaps from 290 checked were within 10%; the refused ones
were within 10% only about a third of the time. So only those teams are
supported; every other team gets an explicit "unsupported" answer.

gcsim names every damage source in a run, and reaction damage is identifiable by name: amplified hits carry
"(vaporize)" or "(melt)", catalyzed hits "(aggravate)" or "(spread)", and transformative reactions are sources of
their own ("overload", "hyperbloom"...). So a team's damage can be split exactly into supported and unsupported
channels. A swap is only answered when both the base team and the swapped team (when it was simulated) keep the
unsupported share under MAX_UNSUPPORTED_SHARE. For a candidate with no simulated team, the swap is refused when
their element would add a reaction the calculator does not model.

Validated by gtc.tc.validate.run_broad on sampled one-member swaps (see docs/engine.md).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from gtc import params

MAX_UNSUPPORTED_SHARE = params.get("theory_guard.max_unsupported_share")
MIN_LUNAR_SHARE = params.get("theory_guard.min_lunar_share")

# Channels, source names and element pairs come from gtc/reactions.py. Lunar-Charged teams turn Hydro + Electro
# into Lunar-Charged, which the calculator models; Anemo (Swirl) and Geo (Crystallize, no damage) are fine.
from gtc.reactions import (AMPLIFYING_SUFFIXES, CATALYZE_SUFFIXES, REACTION_SOURCES, SUPPORTED_CHANNELS,  # noqa: E402
                           UNSUPPORTED_PAIRS)
HYDRO_ELECTRO = frozenset(("Hydro", "Electro"))


def channel(source: str) -> str:
    """The damage channel of one gcsim damage source name."""
    s = source.strip()
    m = re.search(r"\(([A-Za-z -]+)\)\s*$", s)
    if m:
        tag = m.group(1).strip().lower()
        if tag in AMPLIFYING_SUFFIXES:
            return AMPLIFYING_SUFFIXES[tag]
        if tag in CATALYZE_SUFFIXES:
            return CATALYZE_SUFFIXES[tag]
        if tag == "lunar-charged":
            return "lunar_charged"
        if tag == "lunar-bloom":
            return "lunar_bloom"
    low = s.lower()
    if low.startswith("swirl-"):
        return "swirl"
    if low in REACTION_SOURCES:
        return REACTION_SOURCES[low]
    return "direct"


@dataclass
class Coverage:
    shares: dict[str, float] = field(default_factory=dict)  # channel -> share of team DPS

    @property
    def unsupported_share(self) -> float:
        return sum(v for k, v in self.shares.items() if k not in SUPPORTED_CHANNELS)

    def unsupported(self) -> list[str]:
        return sorted((k for k, v in self.shares.items() if k not in SUPPORTED_CHANNELS and v > 0.005),
                      key=lambda k: -self.shares[k])


def coverage(profile) -> Coverage:
    """Channel shares of a calculator Profile (gtc.tc.profile), by gcsim source name."""
    total = sum(s.dps for s in profile.sources) or 1.0
    out: dict[str, float] = {}
    for s in profile.sources:
        # The calculator's own classification first: Lunar abilities named in a kit ("Northland Spearstorm")
        # carry no Lunar tag in their gcsim name.
        ch = "lunar_charged" if str(s.kind).startswith("lunar_charged") else channel(s.name)
        out[ch] = out.get(ch, 0.0) + s.dps / total
    return Coverage(out)


@dataclass
class Applicability:
    supported: bool
    reason: str = ""
    base_unsupported: float = 0.0
    target_unsupported: float | None = None


def _describe(cov: Coverage) -> str:
    return ", ".join(f"{k.replace('_', '-')} {cov.shares[k]:.0%}" for k in cov.unsupported()[:3])


def _team_ok(cov: Coverage, when: str) -> str:
    """Empty when supported, else the reason."""
    if cov.unsupported_share > MAX_UNSUPPORTED_SHARE:
        return (f"{when}{cov.unsupported_share:.0%} of the damage comes from reactions the calculator does not model "
                f"({_describe(cov)})")
    lunar = cov.shares.get("lunar_charged", 0.0)
    if lunar < MIN_LUNAR_SHARE:
        return (f"{when}Lunar-Charged is {lunar:.0%} of the damage; the calculator is only validated on Lunar-Charged "
                f"teams (at least {MIN_LUNAR_SHARE:.0%})")
    return ""


def check_base(profile) -> Applicability:
    cov = coverage(profile)
    reason = _team_ok(cov, "")
    return Applicability(not reason, reason, cov.unsupported_share)


def check_swap(base, target=None, candidate_element: str | None = None, remaining_elements: list[str] | None = None,
               lunar_after: bool = False, leaving: str | None = None) -> Applicability:
    """Whether a swap may be answered. `target` is the swapped team's simulated profile when one exists;
    otherwise the candidate's element is checked against the remaining members' elements. Replacing the team's
    lead is refused: the calculator keeps everyone else on the old rotation, which a new carry changes."""
    b = check_base(base)
    if not b.supported:
        return b
    if leaving is not None and leaving == base.lead:
        return Applicability(False, f"{leaving} is this team's main damage dealer; replacing them changes the whole "
                                    "rotation, which the calculator cannot follow", b.base_unsupported)
    if target is not None:
        cov = coverage(target)
        reason = _team_ok(cov, "after the swap ")
        return Applicability(not reason, reason, b.base_unsupported, cov.unsupported_share)
    if candidate_element:
        for el in remaining_elements or []:
            pair = frozenset((candidate_element, el))
            if pair in UNSUPPORTED_PAIRS or (pair == HYDRO_ELECTRO and not lunar_after):
                return Applicability(False, f"{candidate_element} next to {el} adds a reaction the calculator does not model, "
                                            "and no simulated team shows how much", b.base_unsupported)
    return Applicability(True, "", b.base_unsupported)


UNSUPPORTED_TEXT = "Unsupported for this team: {reason}."
