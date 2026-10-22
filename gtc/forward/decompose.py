"""Failure decomposition (brain v3, step 1): is a blind error the calculator, the selection, or the search?

For a team, with the builds the blind run settled on:
    1. every candidate plan is generated and scored by the ForwardModel (the normal search);
    2. the serious finalists (top by ForwardModel, the best per carry choice, per opener and per cycle length) are
       converted to gcsim scripts action for action and run under the same builds;
    3. the community rotation is run under its own builds (the reveal).
Metrics:
    calculator error   ForwardModel vs gcsim on the SAME generated rotation (the selected one)
    selection regret   gcsim of the best gcsim finalist vs gcsim of the ForwardModel-selected finalist
    search regret      reference gcsim vs the best gcsim among our finalists
A generated rotation run in gcsim keeps gcsim's own energy and cooldown handling: an action that is not ready waits,
so a rotation our energy model thought feasible may stretch. The stretch is reported (duration ratio).
Writes data/validation/decomposition_<profile>.json (personal use).
"""
from __future__ import annotations

import json
from collections import Counter
import re
import time

from gtc import ROOT

OUT = ROOT / "data" / "validation"
GCSIM_ACTION = {"attack": "attack", "charge": "charge", "skill": "skill", "burst": "burst", "dash": "dash",
                "jump": "jump", "high_plunge": "high_plunge", "low_plunge": "low_plunge", "aim": "aim"}
ITER = 100


def char_keys(lineup: list[str]) -> dict[str, str]:
    """gcsim character keys: the community config's when one exists, else gcsim's full-name alias."""
    from gtc import gamedata
    from gtc.sim import find_config

    cfg = find_config(lineup, gamedata.names())
    keys = dict(cfg.char_keys) if cfg else {}
    for m in lineup:
        keys.setdefault(m, re.sub(r"[^a-z0-9]", "", m.lower()))
    return keys


def _header(lineup: list[str]) -> list[str]:
    from gtc.forward.trace import house_config

    hc = house_config(lineup)
    lines = []
    if hc:
        for l in hc[0].splitlines():
            if re.match(r"\s*(options|target|energy)\b", l):
                lines.append(l.strip())
    if not any(l.startswith("options") for l in lines):
        lines.append("options swap_delay=12 iteration=100;")
    if not any(l.startswith("target") for l in lines):
        lines.append("target lvl=100 resist=0.1 hp=1000000000 pos=0,2.4 radius=2;")
    if not any(l.startswith("energy") for l in lines):
        lines.append("energy every interval=480,720 amount=1;")
    return [re.sub(r"iteration=\d+", f"iteration={ITER}", l) for l in lines]


def to_gcsim(rot, builds: dict, keys: dict[str, str] | None = None) -> str:
    """A gcsim config that plays this exact generated rotation, action for action, with these builds."""
    from gtc.forward import standard as S
    from gtc.forward.build import gcsim_lines

    keys = keys or char_keys(rot.lineup)
    lines = []
    for m in rot.lineup:
        b = builds[m]
        lines += S.gcsim_lines(keys[m], b) if getattr(b, "choice", None) is not None else gcsim_lines(keys[m], b)
    lines += _header(rot.lineup)
    lines.append(f"active {keys[rot.actions[0].char]};")
    from gtc.forward.generator import SWAP_DELAY

    prev_end, prev_char, prev_action, prev_t, prev_own = None, None, None, 0.0, False
    for a in rot.actions:
        act = GCSIM_ACTION.get(a.action)
        if not act:
            continue
        idle = 0.0
        if prev_end is not None:
            from gtc.forward import frames as FR

            # idle is time beyond the transition the generator used (the measured lock when known, else the kit
            # duration): a measured lock longer than the kit duration is not a wait (a plunge must follow its jump)
            # (the generator records the transition it used: state- and chain-position-aware measured gaps)
            if getattr(a, "earliest", None) is not None:
                idle = a.t - a.earliest
            else:
                lk = None if prev_own else FR.lock(prev_char, prev_action, act if a.char == prev_char else "swap")
                earliest = (prev_t + lk) if lk is not None else prev_end
                idle = a.t - earliest - (SWAP_DELAY if prev_char and a.char != prev_char else 0.0)
        if idle > 0.05:
            lines.append(f"wait({round(idle * 60)});")    # idle in the generated rotation (energy, cooldown); swaps excluded
        # the hold variant when the kit's cast carries a hold hit ("Hold DMG", "Press/Hold ... (Hold)")
        from gtc.forward import frames as FR

        hold = act == "skill" and any(h.char == a.char and abs((h.action_t or -1) - a.t) < 1e-6 and FR.is_hold(h.abil)
                                      for h in rot.hits)
        lines.append(f"{keys[a.char]} {act}{'[hold=1]' if hold else ''};")   # the variant the kit file measured
        prev_end = a.end or None
        prev_char, prev_action, prev_t = a.char, a.action, a.t
        prev_own = getattr(a, "own_duration", False)
    return "\n".join(lines) + "\n"


def run_generated(rot, builds: dict) -> dict:
    """gcsim on the exact generated rotation: mean DPS, its duration, and the sample trace."""
    from gtc.forward.trace import from_sample
    from gtc.sim import run
    from gtc.synergy import run_sample

    keys = char_keys(rot.lineup)
    text = to_gcsim(rot, builds, keys)
    r = run(text)
    out = {"gcsim_dps": r.dps, "error": r.error}
    try:
        inv = {v: k for k, v in keys.items()}
        tr = from_sample(run_sample(text, keep=True), inv, "generated rotation in gcsim")
        out["trace"] = tr
        out["gcsim_duration"] = tr.duration
        out["gcsim_same_trace"] = sum(h.gcsim_expected for h in tr.hits) / tr.duration if tr.duration else None
        # the same steady-state window: cycle starts mapped by action index onto gcsim's own timeline
        acts = [a for a in tr.actions if a.action]
        if len(rot.cycles) >= 3 and len(acts) > rot.cycles[-1][1]:
            # the same boundaries as the forward window: the boundary action's gcsim time minus the lead the forward
            # cycle had before that action (a cycle can start with a wait before its first action)
            def at(c):
                lead = rot.actions[c[1]].t - c[0] if c[1] < len(rot.actions) else 0.0
                return acts[c[1]].t - lead
            t0, t1 = at(rot.cycles[1]), at(rot.cycles[-1])
            out["gcsim_steady"] = sum(h.gcsim_expected for h in tr.hits if t0 <= h.t < t1) / max(t1 - t0, 1e-6)
            out["gcsim_window_s"] = round(t1 - t0, 1)
    except Exception as e:   # noqa: BLE001
        out["trace_error"] = f"{type(e).__name__}: {e}"
    return out


def all_candidates(lineup: list[str], libs: dict, builds: dict) -> list[tuple]:
    """Every plan (with the cycle-length alternatives of the best), scored by the ForwardModel: (dps, plan, rot, ev)."""
    from dataclasses import replace

    from gtc.forward import data as D
    from gtc.forward.deps import graph, respects
    from gtc.forward.generator import _alt_periods, _burst_search, _period, _policy_search, _run_plan, candidates
    from gtc.forward.rotation import window_fit

    base = window_fit(lineup)["period"]
    costs = {m: D.value(m, "burst", "Energy Cost") for m in lineup}
    out, graphs = [], {}
    for plan in candidates(lineup, libs):
        g = graphs.setdefault(plan.carries, graph(lineup, plan.carries, libs))
        if not respects(plan.supports, plan.carries, g):
            continue
        out.append(_run_plan(lineup, libs, builds, plan, _period(plan, libs, base), costs))
    best = []
    for r in sorted(out, key=lambda r: -r[0]):
        if r[1] not in best:
            best.append(r[1])
        if len(best) >= 6:
            break
    for plan in best:
        cur = _period(plan, libs, base)
        for p in _alt_periods(lineup, plan, libs):
            if abs(p - cur) >= 0.75:
                alt = replace(plan, period=round(p, 2))
                out.append(_run_plan(lineup, libs, builds, alt, alt.period, costs))
    # the same later stages as the blind search: Burst cadence, then the support policy (level 2: windows)
    _burst_search(lineup, libs, builds, out, base, costs)
    _policy_search(lineup, libs, builds, out, base, costs)
    out.sort(key=lambda r: -r[0])
    for r in out:
        r[2].builds = r[4]          # the builds this rotation was scored with (its own ER when builds is None)
    return [r[:4] for r in out]


def _realisation(rot, plan) -> dict:
    """State realisation of the selected rotation itself (as deps.realisation, over its own timeline)."""
    states = (getattr(rot, "timeline", None) or {}).get("states", [])
    out = {}
    for st in states:
        m, name, a, b = st[:4]
        nominal = st[4] if len(st) > 4 else b
        if nominal - a > 60:
            continue
        on = sum(max(0.0, min(b, y) - max(a, x)) for x, y, w in rot.segments if w == m)
        out.setdefault(f"{m}:{name}", []).append(on / max(nominal - a, 1e-6))
    return {k: round(sum(v) / len(v), 2) for k, v in out.items()}


def _family(plan, team: list[str]) -> str:
    from gtc.forward.generator import family_of
    from gtc.forward.rotation import window_fit

    return family_of(plan, window_fit(team)["period"])


def _label(plan) -> str:
    burst = {"skill_only": "carry Burst unused"}.get(plan.carry_first, f"carry {plan.carry_first} first")
    per = f", cycle {plan.period:.0f} s" if plan.period else ""
    return (f"driver {' then '.join(plan.carries)}; {burst}; supports {', '.join(plan.supports)}; "
            f"refresh {plan.refresh or 'none'}{per}"
            + (f"; supports {plan.support_policy}" if getattr(plan, "support_policy", "wait") != "wait" else "")
            + ("; driver state protected" if getattr(plan, "protect_state", False) else "")
            + (f"; {plan.family}" if getattr(plan, "family", "standard") != "standard" else ""))


def finalists(cands: list[tuple], top: int = 6) -> list[tuple]:
    """The serious finalists: the ForwardModel's top few, plus the best of every carry choice, opener and cycle."""
    keep, seen = [], set()

    def add(r):
        k = id(r)
        if k not in seen:
            seen.add(k)
            keep.append(r)

    for r in cands[:top]:
        add(r)
    groups: dict = {}
    for r in cands:
        p = r[1]
        for key in (("carries", p.carries), ("opener", p.carries, p.carry_first), ("period", p.carries, p.period)):
            groups.setdefault(key, r)       # cands are sorted: the first is the group's best
    for r in groups.values():
        add(r)
    return keep


def decompose(entry: dict, profile: str = "standard", top: int = 6) -> dict:
    from gtc.forward.blind import theorycraft
    from gtc.forward.generator import on_field_dealers, roles
    from gtc.forward.library import build
    from gtc.forward.trace import house_trace

    team = entry["team"]
    t0 = time.time()
    r = theorycraft(team, profile=profile)
    builds = r.get("builds") or r.get("used_builds")
    # neutral builds: every plan gets the Energy Recharge its own rotation needs, as in the blind search; realistic
    # (standard) builds are fixed gear chosen for the team
    search_builds = None if profile == "neutral" else builds
    carry, _ = roles(team)
    carries = set(on_field_dealers(team)) | {carry}
    libs = {m: build(m, [team], role="carry" if m in carries else "support") for m in team}
    cands = all_candidates(team, libs, search_builds)
    rb = lambda rot: getattr(rot, "builds", None) or builds      # noqa: E731
    fin = finalists(cands, top)
    rows = []
    chosen = cands[0][1]        # the ForwardModel's choice among these candidates, with these builds
    traces = {}
    for dps, plan, rot, ev in fin:
        g = run_generated(rot, rb(rot))
        traces[id(plan)] = g.get("trace")
        win = rot.steady_window()
        rows.append({"strategy": _label(plan), "forward_dps": round(dps),
                     "gcsim_dps": round(g.get("gcsim_steady") or g["gcsim_dps"] or 0), "gcsim_mean_whole": round(g["gcsim_dps"] or 0),
                     "window_forward": round(win[1] - win[0], 1) if win else None, "window_gcsim": g.get("gcsim_window_s"),
                     "gcsim_same_trace": round(g.get("gcsim_same_trace") or 0),
                     "duration_forward": round(rot.duration, 1), "duration_gcsim": round(g.get("gcsim_duration") or 0, 1),
                     "error": g.get("error") or g.get("trace_error"), "selected": plan == chosen,
                     "plan": plan})
    sel = next((x for x in rows if x["selected"]), rows[0])
    # execution parity of the selected rotation (gtc/forward/parity.py)
    from gtc.forward.parity import compare

    sel_rot = next(f[2] for f in fin if f[1] == chosen)
    par = compare(sel_rot, rb(sel_rot))
    burst_cadence = {m: {1: "every cycle", 2: "every second cycle", 0: "never"}[dict(chosen.bursts).get(m, 1)]
                     for m in team}
    if chosen.carry_first == "skill_only":
        burst_cadence[chosen.carries[0]] = "never"
    best = max(rows, key=lambda x: x["gcsim_dps"])
    tr = house_trace(team, r.get("builds"))
    ref = tr[1]["gcsim_dps"] if tr else None
    # structure: our selected / best strategies vs the reference, all as gcsim executed them (gtc/forward/structure.py)
    from gtc.forward import structure as ST

    structure = {}
    if tr:
        structure["reference"] = ST.profile(tr[0])
        for tag, x in (("selected", sel), ("best", best)):
            t_ = traces.get(id(x["plan"]))
            if t_ is not None:
                structure[tag] = ST.profile(t_)
                structure[f"delta_{tag}"] = ST.delta(structure[tag], structure["reference"])
    # expressiveness: the reference projected onto the strategy language and played in gcsim (gtc/forward/expressive.py)
    expressiveness = None
    if tr and ref:
        from gtc.forward.expressive import assess

        try:
            expressiveness = assess(team, tr[0], ref, builds, libs)
        except Exception as ex:   # noqa: BLE001
            expressiveness = {"verdict": "not assessed", "error": f"{type(ex).__name__}: {ex}"}
    # reaction / application events on the same rotation (gtc/forward/rxparity.py)
    from gtc.forward.rxparity import compare as rx_compare

    rxp = rx_compare(sel_rot, rb(sel_rot))
    ref_field = {}
    if tr:
        ft = tr[0].field_time()
        tot = sum(ft.values()) or 1.0
        ref_field = {m: round(v / tot, 3) for m, v in ft.items()}
    sel_field = {m: round(v / (sum(sel_rot.field_time().values()) or 1.0), 3) for m, v in sel_rot.field_time().items()}
    out = {"team": team, "family": entry["family"], "profile": profile, "candidates": len(cands), "finalists": len(rows),
           "selected": sel["strategy"], "forward_dps": sel["forward_dps"], "gcsim_same_rotation": sel["gcsim_dps"],
           "best_generated_gcsim": best["gcsim_dps"], "best_generated_strategy": best["strategy"],
           "reference_gcsim": round(ref) if ref else None,
           "calculator_error": round(sel["forward_dps"] / sel["gcsim_dps"] - 1, 3) if sel["gcsim_dps"] else None,
           "selection_regret": round(1 - sel["gcsim_dps"] / best["gcsim_dps"], 3) if best["gcsim_dps"] else None,
           "search_regret": round(1 - best["gcsim_dps"] / ref, 3) if ref and best["gcsim_dps"] else None,
           "duration_stretch": round(sel["duration_gcsim"] / sel["duration_forward"], 2) if sel["duration_forward"] else None,
           "selected_driver": " then ".join(chosen.carries), "burst_cadence": burst_cadence,
           "forward_duration": par["predicted_duration"], "gcsim_duration_same_rotation": par["gcsim_duration"],
           "duration_error": par["duration_error"],
           "timing_delta_by_class": {k: v for k, v in par["totals"]["delta"].items() if abs(v) >= 0.05 and k not in ("lock", "hitlag")},
           "unexplained_s": par["unexplained"], "explicit_waits_s": par["explicit_waits"],
           "first_divergence": {k: par["first_divergence"].get(k) for k in ("i", "char", "action", "t_forward", "t_gcsim", "dominant")}
           if par["first_divergence"] else None,
           "burst_availability_delta": {m: b["availability_delta"] for m, b in par["bursts"].items()},
           "energy_received": {m: (b["received_forward"], b["received_gcsim"]) for m, b in par["bursts"].items()},
           "finalist_rows": [{k: v for k, v in x.items() if k != "plan"} for x in rows],
           "residual": round(sel["forward_dps"] / ref - 1, 3) if ref else None,
           "structure": structure, "expressiveness": expressiveness,
           "cycle_family": {"selected": _family(chosen, team), "best": _family(best["plan"], team),
                      "candidates": dict(Counter(_family(c[1], team) for c in cands))},
           "reactions": rxp["reactions"], "reaction_owners": rxp["owners"], "applications": rxp["applications"],
           "cores_gcsim": rxp["cores_gcsim"], "rx_first_divergence": rxp["first_divergence"],
           "field_share_forward": sel_field, "field_share_reference": ref_field,
           "period": chosen.period, "carry_first": chosen.carry_first,
           "er_required_max": max([v.get("required_er") or 0 for v in (r["evaluation"].energy or {}).values()] or [0]) or None,
           "state_realisation": _realisation(sel_rot, chosen),
           "seconds": round(time.time() - t0, 1)}
    return out


def run_all(profile: str = "standard", teams: list | None = None) -> list[dict]:
    from gtc.forward.reference import REFERENCE

    rows = []
    for e in teams or REFERENCE:
        try:
            rows.append(decompose(e, profile))
        except Exception as ex:   # noqa: BLE001
            rows.append({"family": e["family"], "team": e["team"], "error": f"{type(ex).__name__}: {ex}"})
        (OUT / f"decomposition_{profile}.json").write_text(json.dumps(rows, indent=1, default=str), encoding="utf-8")
    return rows
