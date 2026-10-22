"""gcsim as validation infrastructure (phase M): the quality of a community simulation is recorded, never assumed.

For a lineup's community entries (data/sources/gcsim_db_raw.json, personal use):
    entries / submitters    how many simulations and how many independent submitters
    comparable_build        constellations all 0 and weapon refinements low enough to compare with house builds
                            (the reveal re-renders the house builds anyway; this flags the community DPS itself)
    modern                  last updated within two years of the newest entry in the database
    valid                   gcsim's own database validity flag
    duration_s              the simulated duration (a plausible rotation runs long enough to loop)
For a reveal (the community rotation re-run with house builds):
    shape_kept              the realistic run keeps the ample-energy rotation's length (no energy stalls)
A reference counts as high quality when its shape is kept, the entry is valid and modern; the benchmark keeps the
others but reports them separately, so an exact community team is evidence, not truth.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache

from gtc import ROOT

RAW = ROOT / "data" / "sources" / "gcsim_db_raw.json"
TWO_YEARS = 2 * 365 * 86400


@lru_cache(maxsize=1)
def _raw() -> list[dict]:
    return json.loads(RAW.read_text(encoding="utf-8")) if RAW.exists() else []


@lru_cache(maxsize=1)
def _by_lineup() -> dict[frozenset, list[dict]]:
    from gtc.synergy import load_database

    db = load_database()
    out: dict[frozenset, list[dict]] = {}
    for e in _raw():
        d = db.get(e.get("_id"))
        if not d:
            continue
        lu = d.get("lineup")
        lu = lu if isinstance(lu, (list, tuple)) else []
        out.setdefault(frozenset(lu), []).append(e)
    return out


def _cons_refine(config: str) -> tuple[list[int], list[int]]:
    cons = [int(x) for x in re.findall(r"\bcons=(\d+)", config or "")]
    ref = [int(x) for x in re.findall(r"\brefine=(\d+)", config or "")]
    return cons, ref


def quality(lineup: list[str], entry_id: str | None = None) -> dict:
    entries = _by_lineup().get(frozenset(lineup), [])
    newest = max((int(float(e.get("last_update") or e.get("create_date") or 0)) for e in _raw()), default=0)
    rows = []
    for e in entries:
        cons, ref = _cons_refine(e.get("config", ""))
        ts = int(float(e.get("last_update") or e.get("create_date") or 0))
        dur = ((e.get("summary") or {}).get("sim_duration") or {}).get("mean") if isinstance(e.get("summary"), dict) else None
        rows.append({"id": e.get("_id"), "comparable_build": bool(cons) and max(cons) == 0 and (not ref or max(ref) <= 5),
                     "max_cons": max(cons) if cons else None, "modern": newest - ts <= TWO_YEARS,
                     "valid": str(e.get("is_db_valid")) == "True", "duration_s": dur, "submitter": e.get("submitter")})
    chosen = next((r for r in rows if r["id"] == entry_id), rows[0] if rows else None)
    return {"entries": len(rows), "submitters": len({r["submitter"] for r in rows}),
            "comparable_builds": sum(r["comparable_build"] for r in rows), "modern": sum(r["modern"] for r in rows),
            "reference_entry": chosen}


def reference_quality(lineup: list[str], info: dict) -> dict:
    """Quality of a reveal: the community entry it used and whether the realistic run kept the rotation's shape."""
    q = quality(lineup, info.get("config"))
    shape = info.get("shape_s")
    kept = not info.get("reference_stalled", False)
    entry = q.get("reference_entry") or {}
    high = kept and entry.get("valid", True) and entry.get("modern", True)
    flags = []
    if not kept:
        flags.append(f"energy stall: {shape[0]} s rotation took {shape[1]} s with realistic builds" if shape else "energy stall")
    if entry and not entry.get("modern"):
        flags.append("legacy entry (over two years older than the newest)")
    if entry and not entry.get("valid"):
        flags.append("not valid in the gcsim database")
    if q["submitters"] <= 1:
        flags.append("a single submitter")
    if entry and (entry.get("max_cons") or 0) > 0:
        flags.append(f"rotation written for constellations up to C{entry['max_cons']}, run at C0")
    return {"high_quality": bool(high), "shape_kept": kept, "shape_s": shape, "flags": flags, "community": q}
