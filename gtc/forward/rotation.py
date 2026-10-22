"""Field time as windows (FM-5) and rotation feasibility.

A character's field-time profile:
    sustained     their damage needs them on field for most of a rotation (Razor in his Burst, Neuvillette, Ayaka)
    burst_window  a timed on-field state from their Burst (Raiden's Musou Isshin, 7 s)
    short_window  a timed on-field state from their Skill (Ayato, Yoimiya, Hu Tao)
    driver        on field to trigger others' off-field damage, with little damage of their own
    setup_only    cast and leave (supports, off-field damage dealers)
with minimum_seconds (what the kit needs per rotation) and preferred_seconds (what reference rotations give them,
when a trace was measured).

window_fit(lineup): the rotation period is the longest Burst cooldown among the on-field damage dealers (at least
15 s: buffs are refreshed on that cycle); the team needs the sum of every setup and every window. Two windows that
do not fit in one period cannot both be realised: the result says how much of the second window is left. A dual-
carry team is not banned: windows that fit are fine, and a traced rotation that shows both windows working (an exact
simulation) overrides this estimate.
"""
from __future__ import annotations

from dataclasses import dataclass

from gtc.forward import data as D

SETUP_PER_ACTION = 1.2   # seconds a support spends per Skill or Burst cast, swap included (typical, judgment)
MIN_PERIOD = 15.0
WINDOW_ROWS = {  # the on-field state of a kit, read from its talent tables (annotation; extend per kit)
    "Raiden Shogun": ("burst", "Musou Isshin Duration"),
    "Razor": ("burst", "Duration"),
    "Kamisato Ayato": ("skill", "Takimeguri Kanka Duration"),
    "Yoimiya": ("skill", "Duration"),
    "Hu Tao": ("skill", "Duration"),
}
SUSTAINED_SECONDS = {"high": 10.0, "medium": 6.0}


@dataclass
class FieldProfile:
    name: str
    kind: str
    minimum_seconds: float
    preferred_seconds: float | None = None
    source: str = ""


def field_profile(name: str, measured: float | None = None) -> FieldProfile:
    from gtc.kits import kit

    b = (kit(name) or {}).get("behavior") or {}
    if b.get("on_field_damage") is not True:
        if b.get("driver") is True:
            return FieldProfile(name, "driver", 6.0, measured, "kit: driver")
        return FieldProfile(name, "setup_only", 2 * SETUP_PER_ACTION, measured, "kit: no on-field damage")
    row = WINDOW_ROWS.get(name)
    if row:
        v = D.value(name, row[0], row[1])
        if v:
            kind = "burst_window" if row[0] == "burst" else "short_window"
            if row[0] == "burst" and v >= 12:
                kind = "sustained"
            return FieldProfile(name, kind, float(v), measured, f"talent table: {row[1]}")
    secs = SUSTAINED_SECONDS.get(b.get("field_time"), 4.0)
    return FieldProfile(name, "sustained" if b.get("field_time") == "high" else "flexible", secs, measured,
                        f"kit field time {b.get('field_time')}")


def burst_cd(name: str) -> float | None:
    v = D.value(name, "burst", "CD")
    return float(v) if v else None


def window_fit(lineup: list[str], measured: dict[str, float] | None = None) -> dict:
    profs = [field_profile(m, (measured or {}).get(m)) for m in lineup]
    carries = [p for p in profs if p.kind in ("sustained", "burst_window", "short_window")]
    period = max([MIN_PERIOD] + [burst_cd(p.name) or 0 for p in carries])
    setup = sum(p.minimum_seconds for p in profs if p.kind in ("setup_only",))
    driver = sum(p.minimum_seconds for p in profs if p.kind in ("driver", "flexible"))
    need = setup + driver + sum(p.minimum_seconds for p in carries)
    out = {"profiles": [p.__dict__ for p in profs], "period": period, "needed": round(need, 1),
           "fits": need <= period * 1.05, "realisation": {}}
    if len(carries) >= 2 and not out["fits"]:
        # the largest window is served first; what is left of the period goes to the next
        left = period - setup - driver
        for p in sorted(carries, key=lambda p: -p.minimum_seconds):
            got = max(0.0, min(p.minimum_seconds, left))
            out["realisation"][p.name] = round(got / p.minimum_seconds, 2)
            left -= got
        out["text"] = (f"{' and '.join(p.name for p in carries)} need {sum(p.minimum_seconds for p in carries):.0f} s "
                       f"of field windows plus {setup + driver:.1f} s of setup in a {period:.0f} s rotation")
    elif len(carries) >= 2:
        out["text"] = f"{' and '.join(p.name for p in carries)}: windows fit in a {period:.0f} s rotation ({need:.1f} s needed)"
    return out
