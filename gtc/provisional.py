"""Provisional power for characters with no community simulations (phase 6.5 Lite, completed in phase 13).

A provisional character has a hand-written kit in knowledge/kits_provisional/ (schema: gtc/kit_schema.py) and no
simulations. Their teams get route "provisional_kit" (evidence state "kit-model"), evidence tier E, a wide sd and
mechanics coverage "unknown" (so the confidence cap applies), and every report labels them. Once simulations
appear, the exact and pair-model routes take over by themselves: this route only runs for a lineup the pair model
cannot predict, and the audit flags the kit as stale.

A lineup with provisional members is valued by the first of these that applies:
  0. Restrictions: a lineup that breaks a kit restriction (e.g. Sandrone without an Electro or Anemo teammate) gets
     no number, with the kit's reason. Two provisional carries in one lineup get no number either.
  1. Same-page ratio: a simulated carry's Prydwen page lists the lineup and a fully simulated lineup of theirs.
     Prydwen's percentages on one carry's page share one scale, so power = measured power of the simulated lineup
     x (listed % of this lineup / listed % of the simulated one), the median over the page's simulated lineups.
  2. Provisional carry (one, with a Prydwen DPS tier):
       anchor: the character's best-team power from their Prydwen DPS tier, log(power) = a + b x tier value,
               fitted on every simulated carry with a tier (leave-one-out miss = the anchor's sd)
       fraction: a team Prydwen lists for them gets its listed %; a team at most two members from a listed one
               the listed % x the pair model's ratio of the two lineups with every provisional member replaced by
               their analogue (capped at 1); further from every listed team, no number; no listed team at all,
               the analogue's lineup over the analogue's best simulated lineup
       power = anchor x fraction, capped at 100
  3. Provisional supports only (the carry is simulated): every provisional member is replaced by their analogue and
     that lineup is valued by the measured routes (its own simulations, or the pair model).
The sd is never below the route's back-tested miss for that path (see `measure`), nor the pair model's far sd.
"""
from __future__ import annotations

import math
import statistics

from gtc import params

_FIT: dict | None = None
MIN_OWN_LINEUPS = params.get("provisional.min_own_lineups")  # simulated carries in the tier fit need this many own lineups
MIN_SHARED_WITH_LISTED = params.get("provisional.min_shared_with_listed")  # members a valued team shares with a listed team
# Back-tests: simulated characters valued as if unsimulated, each with the analogue a kit would name for them.
BACKTEST_CASES = {"Skirk": "Ganyu", "Neuvillette": "Mualani", "Mavuika": "Arlecchino", "Arlecchino": "Hu Tao"}
BACKTEST_SUPPORTS = {"Citlali": "Rosaria", "Xilonen": "Zhongli", "Escoffier": "Rosaria",
                     "Furina": "Sangonomiya Kokomi", "Chevreuse": "Bennett"}


_KITS: dict | None = None


def kits() -> dict:
    global _KITS
    if _KITS is None:
        from gtc.knowledge import provisional_kits

        _KITS = provisional_kits()
    return _KITS


def _element_of():
    from gtc import gamedata

    chars = gamedata.load_characters()
    ks = kits()
    return lambda m: (chars.get(m) or {}).get("element") or (ks.get(m) or {}).get("element")


def _carry_rows(ev, exclude: str | None = None) -> list[tuple[str, float, float]]:
    """(name, Prydwen tier value, best own-lineup power) for simulated carries with a Prydwen DPS tier."""
    from gtc.evidence import PRYDWEN_TIER_VALUE

    rows = []
    for c in sorted(ev._by_member):
        if c == exclude:
            continue
        pt = ev.prydwen_tier(c)
        if not pt or pt["category"] != "DPS" or pt.get("overall") not in PRYDWEN_TIER_VALUE:
            continue
        mine = {s.names for s in ev._by_member[c] if id(s) in ev._standard_ids and ev.attributed(s, c)}
        if len(mine) < MIN_OWN_LINEUPS or not ev.normalizer:
            continue
        rows.append((c, PRYDWEN_TIER_VALUE[pt["overall"]], max(100 * ev.lineup_median[n] / ev.normalizer for n in mine)))
    return rows


def _fit(rows) -> tuple[float, float]:
    xs, ys = [r[1] for r in rows], [math.log(r[2]) for r in rows]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    sxx = sum((x - mx) ** 2 for x in xs) or 1.0
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return my - b * mx, b


def tier_fit(ev) -> dict:
    """The tier mapping and its measured leave-one-out sd (relative, the 68.3rd percentile of |log miss|)."""
    global _FIT
    if _FIT is None or _FIT.get("ev") is not ev:
        rows = _carry_rows(ev)
        a, b = _fit(rows)
        misses = []
        for i, r in enumerate(rows):
            ai, bi = _fit(rows[:i] + rows[i + 1:])
            misses.append(abs(ai + bi * r[1] - math.log(r[2])))
        misses.sort()
        sd = misses[int(0.683 * len(misses))] if misses else 0.25
        _FIT = {"ev": ev, "a": a, "b": b, "sd": sd, "n": len(rows)}
    return _FIT


def anchor(ev, name: str, fit: dict | None = None) -> tuple[float, float] | None:
    """(expected best-team power, relative sd) from the character's Prydwen DPS tier."""
    from gtc.evidence import PRYDWEN_TIER_VALUE

    pt = ev.prydwen_tier(name)
    if not pt or pt["category"] != "DPS" or pt.get("overall") not in PRYDWEN_TIER_VALUE:
        return None
    f = fit or tier_fit(ev)
    return min(100.0, math.exp(f["a"] + f["b"] * PRYDWEN_TIER_VALUE[pt["overall"]])), f["sd"]


def listed_teams(ev, name: str) -> list[tuple[frozenset, float]]:
    return [(frozenset(m["name"] for m in t["members"]), float(t["percent"]))
            for t in ev.prydwen.get("characters", {}).get(name, {}).get("teams", []) if t.get("percent")]


def own_page(ev, owner: str) -> dict[frozenset, float]:
    """The owner's own teams on their Prydwen page (owner listed first), each lineup's median listed percentage
    (a lineup can appear several times: rotation and constellation variants)."""
    got: dict[frozenset, list[float]] = {}
    for t in ev.prydwen.get("characters", {}).get(owner, {}).get("teams", []):
        names = [m["name"] for m in t["members"]]
        if t.get("percent") and names and names[0] == owner:
            got.setdefault(frozenset(names), []).append(float(t["percent"]))
    return {k: statistics.median(v) for k, v in got.items()}


def _swap(lineup, mapping: dict[str, str]) -> frozenset:
    return frozenset(mapping.get(m, m) for m in lineup)


def analogues(lineup, hidden: dict[str, str] | None = None) -> dict[str, str]:
    """Provisional member -> analogue for this lineup (`hidden` adds back-test characters)."""
    out = {m: kits()[m].get("analogue") for m in lineup if m in kits() and kits()[m].get("analogue")}
    out.update({m: a for m, a in (hidden or {}).items() if m in lineup})
    return out


def page_ratio(ev, lineup, exclude: set[str] = frozenset()) -> tuple[float, list[str]] | None:
    """Path 1: (power, explanation) from a simulated carry's Prydwen page that lists this lineup and at least one
    fully simulated lineup of theirs. `exclude` hides characters (back-test)."""
    key = frozenset(lineup)
    norm = ev.normalizer
    if not norm:
        return None
    for owner in sorted(key):
        if owner in exclude or owner not in ev._by_member:
            continue
        page = own_page(ev, owner)
        if key not in page:
            continue
        refs = [(r, p) for r, p in page.items() if r != key and r in ev.lineup_median and not (r & exclude)]
        if not refs:
            continue
        est = [min(100.0, 100 * ev.lineup_median[r] / norm) * page[key] / p for r, p in refs]
        value = min(100.0, statistics.median(est))
        best = max(refs, key=lambda rp: (rp[1], sorted(rp[0])))
        return value, [f"Prydwen's {owner} page lists this team at {page[key]:.0f}%; scaled by {len(refs)} simulated "
                       f"team(s) on the same page (e.g. {' / '.join(sorted(best[0]))} at {best[1]:.0f}%)"]
    return None


def team_fraction(ev, name: str, lineup, analogue_map: dict[str, str] | str | None) -> tuple[float, float, str] | None:
    """(fraction of the character's best team, its relative sd, how it was found)."""
    from gtc import estimate
    from gtc.pairmodel import load

    if isinstance(analogue_map, str) or analogue_map is None:
        analogue_map = {name: analogue_map} if analogue_map else {}
    analogue = analogue_map.get(name)
    key = frozenset(lineup)
    listed = listed_teams(ev, name)
    prydwen_sd = estimate._u("prydwen", "sd", default=estimate._FALLBACK["prydwen"]) / 100
    for members, pct in listed:
        if members == key:
            return min(1.0, pct / 100), prydwen_sd, f"Prydwen lists this team at {pct:.0f}% of {name}'s best"
    pm = load()
    if pm is None or not analogue:
        return None
    target = _swap(key, analogue_map)
    if not pm.known(target):
        return None
    pred = pm.predict(target, analogue)
    near = estimate._u("pair", "near", "sd", default=estimate._FALLBACK["near"])
    # Extrapolate only near Prydwen's teams: at most two members away from a listed team (the character plus at
    # least one shared teammate). A character with listed teams gets no number for a team far from all of them.
    # The listed team compared with must be simulated apart from the character: an analogue standing in for another
    # provisional member there underrates it (the support back-test's bias is negative), and the capped ratio
    # would then rate any variant as good as Prydwen's best team.
    others_simulated = lambda m: all(x == name or x in pm.chars for x in m)
    usable = [(m, p) for m, p in listed if len(m & key) >= MIN_SHARED_WITH_LISTED and others_simulated(m)
              and pm.known(_swap(m, analogue_map))]
    if listed and not usable:
        return None
    if usable:
        members, pct = max(usable, key=lambda mp: (len(mp[0] & key), mp[1], sorted(mp[0])))
        ref = pm.predict(_swap(members, analogue_map), analogue)
        # Prydwen lists a character's strongest teams, so an unlisted team is never rated above the listed team
        # it is compared with: the teammate ratio is capped at 1.
        frac = min(1.0, pct / 100 * min(1.0, pred / ref))
        return frac, math.hypot(prydwen_sd, near), (f"{pct:.0f}% for Prydwen's {' / '.join(sorted(members))}, scaled by how the "
                                                    f"pair model rates the teammates with {analogue} in {name}'s place")
    own = [n for n in ev.lineup_median if analogue in n and len(n) == 4]
    if not own:
        return None
    best = max(ev.lineup_median[n] for n in own)
    far = estimate._u("pair", "far", "sd", default=estimate._FALLBACK["far"])
    return min(1.0, pred / best), far, f"no listed team to compare with: {analogue}'s version of this team against {analogue}'s best"


def _decline(ev, key, reason: str) -> None:
    ev.__dict__.setdefault("_provisional_declined", {})[key] = reason


def declined(ev, lineup) -> str | None:
    """Why the provisional route gave this lineup no number, if it did not."""
    return ev.__dict__.get("_provisional_declined", {}).get(frozenset(lineup))


def _measured_sd(path: str) -> float:
    from gtc import estimate

    u = estimate._u("provisional", default={}) or {}
    if path == "carry":
        return u.get("sd", 0.25)
    return (u.get(path) or {}).get("sd", u.get("sd", 0.25))


def provisional_power(lineup, ev):
    """A PowerEstimate on the provisional_kit route, or None (with the reason kept for `declined`) when the lineup
    has no provisional member, breaks a kit restriction, or no path applies."""
    from gtc import estimate, kit_schema
    from gtc.evaluate import Basis, PowerEstimate
    from gtc.pairmodel import load

    pm = load()
    ks = kits()
    key = frozenset(lineup)
    prov = sorted(m for m in key if m in ks and (pm is None or m not in pm.chars))
    if not prov:
        return None
    element_of = _element_of()
    broken = [r for m in prov for r in kit_schema.unmet_restrictions(m, ks[m], key, element_of)]
    if broken:
        _decline(ev, key, "; ".join(broken))
        return None
    carries = [m for m in prov if ks[m].get("role", "carry") == "carry"]
    if len(carries) > 1:
        _decline(ev, key, f"two provisional carries ({', '.join(carries)}) in one team")
        return None
    far = estimate._u("pair", "far", "sd", default=estimate._FALLBACK["far"])
    amap = analogues(key)
    label = ", ".join(prov)
    sources: tuple[str, ...]

    got = page_ratio(ev, key)
    if got is not None:
        value, how = got
        rel = max(far, _measured_sd("page_ratio"))
        sources = (f"provisional kit for {label} (no simulations yet)", *how)
    elif carries:
        name = carries[0]
        a = anchor(ev, name)
        if a is None:
            _decline(ev, key, f"{name} has no Prydwen DPS tier to anchor a provisional carry on")
            return None
        best, anchor_sd = a
        frac = team_fraction(ev, name, key, amap)
        if frac is None:
            _decline(ev, key, f"{name} has only a provisional kit, and this team is too far from the teams Prydwen lists for them")
            return None
        fraction, frac_sd, how = frac
        value = min(100.0, best * fraction)
        # Never tighter than the route's own measured miss on the back-test (heavy-tailed: see measure()).
        rel = max(far, _measured_sd("carry"), math.hypot(anchor_sd, frac_sd))
        pt = ev.prydwen_tier(name)
        sources = (f"provisional kit for {label} (no simulations yet)",
                   f"best team from Prydwen DPS tier {pt['overall']}: {best:.0f}", how)
    else:
        from gtc.evaluate import lineup_power

        stand_in = _swap(key, amap)
        if len(stand_in) < 4 or any(m in ks and m not in (pm.chars if pm else ()) for m in stand_in):
            _decline(ev, key, f"{label}: the analogue is already in this team")
            return None
        base = lineup_power(stand_in, ev)
        if base is None:
            _decline(ev, key, f"{label}: the team with analogues in their place ({' / '.join(sorted(stand_in))}) cannot be valued either")
            return None
        value = base.expected
        rel = max(far, _measured_sd("support"), base.basis.sd_relative)
        swaps = ", ".join(f"{a} for {m}" for m, a in sorted(amap.items()))
        sources = (f"provisional kit for {label} (no simulations yet)",
                   f"valued as {' / '.join(sorted(stand_in))} ({swaps}), {base.basis.route.replace('_', ' ')}")
    return PowerEstimate(value, value * rel, Basis("provisional_kit", "E", rel, None, 4, sources=sources,
                                                   flags=("provisional",)))


def backtest(cases: dict[str, str], ev) -> dict:
    """Hide simulated carries and value their measured lineups the provisional way. `cases` maps a carry to the
    analogue its kit would name. The anchor is refitted without the carry; listed teams use Prydwen's percentages;
    other measured lineups of theirs use the analogue ratio. Errors are log(predicted / measured)."""
    from gtc import estimate

    out = {}
    for name, analogue in cases.items():
        rows = _carry_rows(ev, exclude=name)
        a, b = _fit(rows)
        fit = {"a": a, "b": b, "sd": tier_fit(ev)["sd"]}
        got = anchor(ev, name, fit)
        if got is None:
            continue
        best, anchor_sd = got
        mine = sorted({s.names for s in ev._by_member.get(name, []) if id(s) in ev._standard_ids and ev.attributed(s, name)},
                      key=sorted)
        rows_out = []
        for lineup in mine:
            # The pair model knows `name`; value the lineup as if it did not, through the analogue only.
            frac = team_fraction(ev, name, lineup, analogue)
            if frac is None:
                continue
            fraction, frac_sd, how = frac
            pred = min(100.0, best * fraction)
            meas = 100 * ev.lineup_median[lineup] / ev.normalizer
            far = estimate._u("pair", "far", "sd", default=estimate._FALLBACK["far"])
            sd = max(far, math.hypot(anchor_sd, frac_sd))
            rows_out.append({"lineup": sorted(lineup), "predicted": round(pred, 1), "measured": round(meas, 1),
                             "log_error": round(math.log(pred / meas), 3), "sd": round(sd, 3),
                             "listed": how.startswith("Prydwen lists")})
        out[name] = {"analogue": analogue, "anchor": round(best, 1), "lineups": rows_out}
    return out


def backtest_supports(cases: dict[str, str], ev) -> dict:
    """Hide simulated supports. Path 1 (same-page ratio) on every measured lineup of theirs a simulated carry's page
    lists beside a measured lineup without them; path 3 (analogue stand-in) on every measured lineup of theirs.
    Errors are log(predicted / measured)."""
    from gtc.evaluate import lineup_power

    norm = ev.normalizer
    out = {"page_ratio": [], "support": []}
    for name, analogue in cases.items():
        mine = sorted({s.names for s in ev._by_member.get(name, []) if id(s) in ev._standard_ids}, key=sorted)
        for lineup in mine:
            meas = 100 * ev.lineup_median[lineup] / norm
            if meas <= 0:
                continue
            got = page_ratio(ev, lineup, exclude={name})
            if got is not None:
                out["page_ratio"].append({"hidden": name, "lineup": sorted(lineup), "predicted": round(got[0], 1),
                                          "measured": round(meas, 1), "log_error": round(math.log(got[0] / meas), 3)})
            stand_in = _swap(lineup, {name: analogue})
            if len(stand_in) < 4:
                continue
            base = lineup_power(stand_in, ev)
            if base is not None and base.expected > 0:
                out["support"].append({"hidden": name, "analogue": analogue, "lineup": sorted(lineup),
                                       "predicted": round(base.expected, 1), "measured": round(meas, 1),
                                       "log_error": round(math.log(base.expected / meas), 3)})
    return out


def _summary(errs: list[float]) -> dict:
    errs = sorted(abs(e) for e in errs)
    if not errs:
        return {}
    sd = errs[int(0.683 * len(errs))]
    return {"sd": sd, "n": len(errs), "within_1sd": sum(e <= sd for e in errs) / len(errs),
            "within_2sd": sum(e <= 2 * sd for e in errs) / len(errs)}


def measure() -> dict:
    """The provisional route's measured sd per path: the 68.3rd percentile of |log miss| over its back-test, with
    the share of misses within 1 and 2 sd. Written to uncertainty.json by `python -m gtc derive`."""
    from gtc import knowledge
    from gtc.report import load_evidence

    ev = load_evidence(knowledge.load())
    res = backtest(BACKTEST_CASES, ev)
    errs = [x["log_error"] for r in res.values() for x in r["lineups"]]
    if not errs:
        return {}
    out = _summary(errs)
    out["by_character"] = {k: {"analogue": v["analogue"], "lineups": len(v["lineups"]),
                               "median_log_error": sorted(x["log_error"] for x in v["lineups"])[len(v["lineups"]) // 2]}
                           for k, v in res.items() if v["lineups"]}
    sup = backtest_supports(BACKTEST_SUPPORTS, ev)
    for path in ("page_ratio", "support"):
        rows = sup[path]
        s = _summary([x["log_error"] for x in rows])
        if s:
            s["by_character"] = {}
            for name in sorted({x["hidden"] for x in rows}):
                e = sorted(x["log_error"] for x in rows if x["hidden"] == name)
                s["by_character"][name] = {"lineups": len(e), "median_log_error": e[len(e) // 2]}
            out[path] = s
    return out
