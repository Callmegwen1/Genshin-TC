"""Presentation layer (UI-0): explanations derived from engine outputs, never a new score.

Everything here reads fields the engine already computed (identity, structure, measured profile, power by context,
sustain, mechanics coverage, typicality, evidence quality, account power, plan and pull decompositions) and turns
them into structured statements for the UI. Nothing here feeds back into power, plans or pull values. Thresholds
below only choose wording; where a comparison is implied, compare() decides.
"""
from __future__ import annotations

from gtc.decision import compare
from gtc.estimate import Estimate

# wording thresholds (presentation only)
CENTRAL_SHOWN = 0.5  # a mechanic this central is named as what the team runs on
AOE_STRONG, AOE_WEAK = 1.1, 0.9  # AoE ratio against the median team
BUILT_LOW, BUILT_MID = 0.5, 0.75  # current / ceiling
INVEST_LOW = 0.6  # a member's investment score below this is named as the build bottleneck


def _mech(key: str) -> str:
    from gtc.reactions import mechanic_name

    return mechanic_name(key)


def team_insights(a, investments: dict | None = None, snapshot_chars: dict | None = None) -> dict:
    """{"strengths": [...], "problems": [...]} for one assessment. Each item: type, text, and evidence (strengths) or
    severity (problems)."""
    strengths, problems = [], []
    if a is None or a.evaluation is None:
        return {"strengths": [], "problems": [{"type": "evidence", "severity": "high", "text": "This team cannot be evaluated."}]}
    e = a.evaluation
    ident = e.identity or {}
    st = e.structure or {}
    p = e.power.get("single_target")
    b = p.basis if p else None

    # what the team runs on (identity and structure: measured or predicted)
    systems = {k: float(v) for k, v in (ident.get("systems") or {}).items()}
    central = [k for k in ident.get("central") or [] if systems.get(k, 1.0) >= CENTRAL_SHOWN]
    src = "measured in its simulations" if ident.get("source") == "measured" else "predicted from its members"
    if central:
        strengths.append({"type": "synergy", "text": f"Runs on {', '.join(_mech(k) for k in central)}.",
                          "evidence": f"Mechanic centrality {', '.join(f'{_mech(k)} {systems.get(k, 1.0):.2f}' for k in central)} ({src})."})
    actor = ident.get("primary_actor")
    if actor and ident.get("structure") in ("hypercarry", "dual_carry", "on_field"):
        strengths.append({"type": "structure", "text": f"Built around {actor} ({ident['structure'].replace('_', ' ')}).",
                          "evidence": f"{actor} is the main damage owner with probability {ident.get('primary_probability', 0):.0%} ({src})."})
    # mechanics read from the kits (gtc/team_mechanics.py): representation, never power
    from gtc.team_mechanics import analyse

    tm = analyse(a.team.members, central=ident.get("central"))
    edges = [s for s in tm.synergies if s["kind"] == "buff" and s["state"] in ("always", "conditional")]
    if edges:
        by_to: dict = {}
        for s in edges:
            by_to.setdefault(s["to"], []).append(s["from"])
        to, givers = max(by_to.items(), key=lambda kv: len(set(kv[1])))
        strengths.append({"type": "mechanics", "text": f"{', '.join(sorted(set(givers)))} buff {to}'s damage.",
                          "evidence": "Kit effects whose target, element and damage type match: "
                                      + "; ".join(sorted({s['effect'] for s in edges if s['to'] == to}))[:240] + "."})
    for c in tm.conflicts:
        problems.append({"type": "mechanics", "severity": "high" if c["severity"] == "harm" else "low",
                         "text": c["text"][:1].upper() + c["text"][1:] + ".",
                         "evidence": f"Kit mechanics ({c['kind'].replace('_', ' ')}); resolved by {c['resolved_by']}."})
    for o in tm.opportunity_losses:
        if o["kind"] in ("partial_condition", "self_only"):
            problems.append({"type": "mechanics", "severity": "medium", "text": o["text"][:1].upper() + o["text"][1:] + ".",
                             "evidence": "An opportunity loss: the kit still works, below what it can do."})
    m = e.explanation.get("measurements") if e.explanation else None
    if m:
        mods = m.get("conditional_mods") or {}
        best = max(mods.items(), key=lambda kv: kv[1].get("damage", 0), default=None)
        if best and best[1].get("damage", 0) >= 0.1:
            strengths.append({"type": "synergy", "text": f"{best[1].get('owner')}'s buff lands on a large part of the damage.",
                              "evidence": f"Active on hits worth {best[1]['damage']:.0%} of team damage in the simulations."})

    # context
    st_e, aoe_e = a.power.get("single_target"), a.power.get("aoe")
    if st_e is not None and aoe_e is not None and st_e.value:
        ratio = aoe_e.value / st_e.value
        if ratio >= AOE_STRONG:
            strengths.append({"type": "aoe", "text": "Stronger than a typical team against groups.",
                              "evidence": f"AoE {ratio:.2f}x of its single-target power, relative to the median team."})
        elif ratio <= AOE_WEAK:
            problems.append({"type": "aoe", "severity": "low", "text": "Weaker than a typical team against groups.",
                             "evidence": f"AoE {ratio:.2f}x of its single-target power, relative to the median team."})

    # sustain (best healer or shield quality on the team, 0 to 100)
    sustain = a.power.get("sustain", 0) or 0
    if sustain >= 80:
        strengths.append({"type": "sustain", "text": "Has a dedicated healer or shielder.", "evidence": f"Sustain {sustain:.0f}/100."})
    elif sustain == 0:
        problems.append({"type": "sustain", "severity": "medium", "text": "No healer or shielder.",
                         "evidence": "Fine in short fights; harder in Abyss floors that punish mistakes."})

    # evidence
    if b is not None:
        if b.route in ("exact_personal", "exact_community") and b.quality in ("good", "unconfirmed", ""):
            strengths.append({"type": "evidence", "text": "Measured: this exact team has been simulated.",
                              "evidence": f"Evidence tier {b.tier}; community data {b.quality or 'n/a'}."})
        if b.quality in ("mixed", "poor"):
            problems.append({"type": "evidence", "severity": "high" if b.quality == "poor" else "low",
                             "text": f"{b.quality.capitalize()} community data.", "evidence": "; ".join(b.quality_reasons)})
        if "provisional" in b.flags:
            problems.append({"type": "evidence", "severity": "high",
                             "text": "Provisional: a member has no simulations yet; the number comes from a hand-written kit.",
                             "evidence": "; ".join(b.sources[1:]) or "provisional kit"})
        elif b.route == "pair_model" and b.tier == "D":
            problems.append({"type": "evidence", "severity": "medium", "text": "Interpolated far from any simulated team.",
                             "evidence": f"Members changed from the nearest simulated team: {b.member_distance}."})
        elif b.route in ("role_rules", "none"):
            problems.append({"type": "evidence", "severity": "high", "text": "No simulation-based estimate for this team.",
                             "evidence": "; ".join(b.sources) or b.route})
    cov = e.coverage or {}
    if cov.get("status") in ("partial", "unknown"):
        problems.append({"type": "coverage", "severity": "medium" if cov["status"] == "partial" else "high",
                         "text": "Relies on a mechanic the data never measured with this damage dealer.",
                         "evidence": "; ".join(cov.get("missing", [])[:3])})
    for f in (e.validity or {}).get("typicality") or []:
        kind, _, text = f.partition(": ")
        problems.append({"type": "unusual", "severity": "medium", "text": text[:1].upper() + text[1:] + ".",
                         "evidence": f"Typicality finding ({kind}); the uncertainty is widened."})
    for tag in a.execution or []:
        if tag in ("expert", "advanced", "difficult"):
            problems.append({"type": "execution", "severity": "low", "text": f"Demanding to play ({tag}).", "evidence": "Execution tag."})

    # build: current against ceiling, and the bottleneck member
    acc = a.account or {}
    cur, ceil = acc.get("current"), acc.get("ceiling")
    if cur is not None and ceil is not None and ceil.value:
        built = cur.value / ceil.value
        if built < BUILT_MID:
            weak = []
            for mem in a.team.members:
                inv = (investments or {}).get(mem)
                if inv is not None and inv.total < INVEST_LOW:
                    c = (snapshot_chars or {}).get(mem)
                    detail = (f"level {c.level}, talents {c.talents.normal}/{c.talents.skill}/{c.talents.burst}, "
                              f"{c.weapon.name} level {c.weapon.level}, {len(c.artifacts)} artifacts") if c else ""
                    weak.append((inv.total, mem, detail))
            weak.sort()
            problems.append({"type": "build", "severity": "high" if built < BUILT_LOW else "medium",
                             "text": f"Your builds reach about {built:.0%} of what this team can do on your account.",
                             "evidence": ("Weakest: " + "; ".join(f"{m} ({d})" for _, m, d in weak[:2])) if weak else
                             f"Current {cur.value:.0f} against ceiling {ceil.value:.0f}."})
    for n in acc.get("unknown_constellations") or []:
        problems.append({"type": "evidence", "severity": "low", "text": f"{n}'s constellation effect is not measured.",
                         "evidence": "Counted as neutral, with a wider uncertainty."})
    return {"strengths": strengths, "problems": problems}


def team_mechanics(a) -> dict:
    """The team's mechanics from its kits (gtc/team_mechanics.py) for the API: functions, conflicts, opportunity
    losses, buff edges, kit coverage. Representation only; nothing here enters power."""
    from gtc.team_mechanics import analyse

    ident = (a.evaluation.identity or {}) if a.evaluation else {}
    tm = analyse(a.team.members, central=ident.get("central"))
    return {"central": tm.central, "supplied_functions": tm.supplied_functions, "missing_functions": tm.missing_functions,
            "synergies": [s for s in tm.synergies if s["kind"] == "buff"],
            "conflicts": [{k: c[k] for k in ("kind", "severity", "members", "text", "resolved_by")} for c in tm.conflicts],
            "opportunity_losses": [{"member": o["member"], "kind": o["kind"], "text": o["text"]} for o in tm.opportunity_losses],
            "conditions_satisfied": [c["member"] for c in tm.conditions_satisfied],
            "reaction_dependencies": tm.reaction_dependencies, "kit_coverage": tm.kit_coverage}


def substitutions(am, team_names: list[str], roster, plan=None, advisor=None, per_slot: int = 6, limit: int = 8) -> dict:
    """One-character substitutions from the owned roster, in three kinds (gtc/advisor.substitution_kind):
      direct        keeps what the team depends on (carry, the elements its central mechanics need, any function only
                    the leaving member provided, kit conditions) and the new team is recommendable
      rebuild       changes how the team works but is itself a credible team ("alternative team style")
      experimental  the model can score it, but it breaks a dependency or is not recommendable: never shown as advice
    Direct swaps are then judged by compare(): upgrade, alternative (roughly equal), or frees a contested support. A
    cheap power pre-screen picks the most promising few per slot; those get the full evaluation."""
    from gtc.advisor import Advisor, substitution_kind
    from gtc.evaluate import lineup_power

    advisor = advisor or Advisor(am.ev)
    base = am.assess_lineup(list(team_names), roster)["assessment"]
    out = {"direct": [], "rebuild": [], "experimental_hidden": 0}
    if base is None or base.estimate is None or not base.estimate.value:
        return out
    owned = [m.key for m in roster]
    elsewhere = {}
    if plan is not None:
        for t in plan.teams:
            if set(t.team.members) != set(team_names):
                for x in t.team.members:
                    elsewhere[x] = " / ".join(t.team.members)
    for out_name in team_names:
        rest = [x for x in team_names if x != out_name]
        pre = []
        for in_name in owned:
            if in_name in team_names:
                continue
            p = lineup_power(frozenset(rest + [in_name]), am.ev)
            if p is not None and p.expected > 0:
                pre.append((p.expected - 0.674 * p.sd, in_name))
        pre.sort(reverse=True)
        for _, in_name in pre[:per_slot]:
            alt = am.assess_lineup(rest + [in_name], roster)["assessment"]
            if alt is None or alt.estimate is None or not alt.estimate.value:
                continue
            kind, why = substitution_kind(base, alt, out_name, in_name, advisor)
            if kind == "experimental":
                out["experimental_hidden"] += 1
                continue
            c = compare(alt.estimate, base.estimate)
            delta = alt.estimate.value - base.estimate.value
            ab = alt.evaluation.power["single_target"].basis if alt.evaluation else None
            row = {"out": out_name, "in": in_name, "lineup": rest + [in_name], "expected_change": round(delta, 1),
                   "probability_better": round(c["probability"], 2), "comparison": c["comparison"],
                   "power": round(alt.estimate.value, 1), "evidence_state": ab.evidence_state if ab else None,
                   "tier": ab.tier if ab else None, "provisional": bool(ab and "provisional" in ab.flags),
                   "recommendability": advisor.level(alt), "changes": why}
            if kind == "rebuild":
                row["kind"] = "rebuild"
                row["label"] = alt.label
                out["rebuild"].append(row)
                continue
            if c["comparison"] == "better":
                row["kind"] = "upgrade"
            elif c["comparison"] == "roughly_equal":
                row["kind"] = "alternative"
            elif out_name in elsewhere:
                row["kind"] = "frees a contested support"
                row["frees_for"] = elsewhere[out_name]
            else:
                continue
            out["direct"].append(row)
    order = {"upgrade": 0, "alternative": 1, "frees a contested support": 2}
    out["direct"].sort(key=lambda s: (order[s["kind"]], -s["expected_change"]))
    out["direct"] = out["direct"][:limit]
    out["rebuild"].sort(key=lambda s: -s["expected_change"])
    out["rebuild"] = out["rebuild"][:4]
    return out


def plan_changes(before, after) -> list[dict]:
    """Where an account gain comes from: each plan slot before and after (slots ranked by the plan before), matched
    by shared members. Values are the account-basis expected powers."""
    b = sorted(before.teams, key=lambda t: -t.potential)
    a = sorted(after.teams, key=lambda t: -t.potential)
    names = ["Best team", "Second team", "Team 3", "Team 4"]
    used, out = set(), []
    for i, t in enumerate(b):
        cand = [(len(set(t.team.members) & set(x.team.members)), -j, j) for j, x in enumerate(a) if j not in used]
        match = None
        if cand:
            _, _, j = max(cand)
            match = a[j]
            used.add(j)
        same = match is not None and set(match.team.members) == set(t.team.members)
        row = {"slot": names[i] if i < len(names) else f"Team {i + 1}", "before": t.team.members, "before_value": round(t.estimate.value),
               "after": match.team.members if match else None, "after_value": round(match.estimate.value) if match else 0,
               "changed": not same}
        row["text"] = (f"{row['slot']}: unchanged ({row['before_value']})" if same else
                       f"{row['slot']}: {row['before_value']} -> {row['after_value']} ({' / '.join(row['after'])})" if match else
                       f"{row['slot']}: dropped ({row['before_value']})")
        out.append(row)
    for j, x in enumerate(a):
        if j not in used:
            out.append({"slot": f"Team {len(out) + 1}", "before": None, "before_value": 0, "after": x.team.members,
                        "after_value": round(x.estimate.value), "changed": True,
                        "text": f"New team: {' / '.join(x.team.members)} ({round(x.estimate.value)})"})
    return out


def allocation_explanations(am, plan, cands, roster) -> list[dict]:
    """Why a unit sits on one plan team rather than another: for each member m of a plan team B and each member x
    of another plan team A, the counterfactual swap A' = A - x + m, B' = B - m + x. Reported when m would be
    individually stronger on A (A' above A) yet the swap lowers the account plan. Values are the account basis
    (ceiling) expected powers; the net effect and its confidence come from the existing plan value and
    gain_estimate."""
    from gtc.account import Plan, gain_estimate

    by_set = {frozenset(c.team.members): c for c in cands}

    def get(names):
        k = frozenset(names)
        if k not in by_set:
            r = am.assess_lineup(list(names), roster)["assessment"]
            if r is not None and r.estimate is not None and r.estimate.value:
                by_set[k] = r
        return by_set.get(k)

    teams = sorted(plan.teams, key=lambda t: -t.potential)
    out = {}
    for B in teams:
        for A in teams:
            if A is B:
                continue
            for m in B.team.members:
                for x in A.team.members:
                    a2 = get([y for y in A.team.members if y != x] + [m])
                    if a2 is None or a2.estimate.value <= A.estimate.value:
                        continue  # m is not individually stronger on A
                    b2 = get([y for y in B.team.members if y != m] + [x])
                    alt_teams = [t for t in plan.teams if t is not A and t is not B] + [a2] + ([b2] if b2 is not None else [])
                    alt = Plan(alt_teams)
                    change = gain_estimate(alt, plan)  # alternative minus the chosen plan
                    if alt.value >= plan.value:
                        continue  # the chosen plan is not better: nothing deliberate to explain
                    c = compare(Estimate(0.0, 0.0, "B"), change)
                    row = {
                        "unit": m, "placed_on": B.team.members, "alternative_team": A.team.members, "swapped_with": x,
                        "best_individual_placement": a2.team.members,
                        "team_a": {"lineup": A.team.members, "now": round(A.estimate.value, 1), "with_unit": round(a2.estimate.value, 1)},
                        "team_b": {"lineup": B.team.members, "now": round(B.estimate.value, 1),
                                   "without_unit": round(b2.estimate.value, 1) if b2 is not None else 0.0,
                                   "without_lineup": b2.team.members if b2 is not None else None},
                        "gain_on_a": round(a2.estimate.value - A.estimate.value, 1),
                        "loss_on_b": round(B.estimate.value - (b2.estimate.value if b2 is not None else 0.0), 1),
                        "net_account_effect": round(-change.value, 1), "net_sd": round(change.sd, 1),
                        "comparison": c["comparison"], "probability_chosen_is_better": round(c["probability"], 2),
                    }
                    row["text"] = (f"{m} would be stronger on {' / '.join(A.team.members)} ({row['team_a']['now']:.0f} to "
                                   f"{row['team_a']['with_unit']:.0f} swapping out {x}), but {' / '.join(B.team.members)} loses more "
                                   f"without {m} ({row['team_b']['now']:.0f} to {row['team_b']['without_unit']:.0f}). Keeping {m} "
                                   f"there is worth {row['net_account_effect']:+.1f} to the account plan"
                                   + (" (roughly equal: the evidence cannot separate the two allocations)." if c["comparison"] == "roughly_equal" else "."))
                    key = m
                    if key not in out or row["gain_on_a"] > out[key]["gain_on_a"]:
                        out[key] = row
    return sorted(out.values(), key=lambda r: -r["gain_on_a"])


def pull_pros_cons(v) -> dict:
    """Pros and cons of a pull, read off its decomposition and estimate (explanations of the literal account delta;
    they never change it)."""
    d = v.decomposition or {}
    pros, cons = [], []
    if d.get("best_team_gain", 0) > 0.5:
        pros.append(f"Improves your best team by {d['best_team_gain']:+.0f}.")
    if d.get("second_team_gain", 0) > 0.5:
        pros.append(f"Improves your second team by {d['second_team_gain']:+.0f}.")
    if d.get("new_mechanics"):
        pros.append("Adds " + ", ".join(_mech(k) for k in d["new_mechanics"]) + " to your account.")
    if d.get("new_viable_teams", 0) >= 3:
        # a count of lineups above the replacement level, not of distinct teams to build
        pros.append(f"Fits {d['new_viable_teams']} lineups on your account that clear the replacement level (flexible).")
    if d.get("improved"):
        pros.append("Makes " + ", ".join(d["improved"][:4]) + " more useful.")
    if not d.get("support_contention") and d.get("leads"):
        pros.append("Uses supports your plan is not already using.")
    if v.weapon_note and v.weapon_note.startswith("You own a recommended weapon"):
        pros.append(v.weapon_note)
    e = v.estimate
    if e is not None and e.tier in ("A", "B") and v.confidence >= 0.9:
        pros.append(f"Strong evidence ({e.tier}, {v.confidence:.0%} that the gain is real).")

    r = d.get("redundancy") or {}
    if r.get("content_coverage"):
        cons.append("Another on-field carry of an element your top teams already carry.")
    elif d.get("redundancy_score", 0) >= 0.5:
        cons.append("Overlaps heavily with roles and teams you already field.")
    if len(d.get("support_contention") or []) >= 2:
        cons.append("Competes for " + ", ".join(d["support_contention"]) + ", who your plan already uses.")
    if d.get("displaced"):
        cons.append("Takes over from " + ", ".join(d["displaced"][:4]) + " in your plan.")
    if d.get("best_team_gain", 0) <= 0.5 and d.get("second_team_gain", 0) <= 0.5 and v.gain > 0.5:
        cons.append("Only improves your lower plan teams.")
    if v.weapon_note and "None of your" in v.weapon_note:
        cons.append("You own none of the weapons the guides recommend for them.")
    flags = ()
    if v.team is not None and v.team.evaluation is not None:
        flags = v.team.evaluation.power["single_target"].basis.flags
    if "provisional" in flags:
        cons.append("Provisional: no simulations of this character yet.")
    if e is not None and (e.tier in ("D", "E") or v.coverage != "complete"):
        cons.append(f"Weak evidence (tier {e.tier}, mechanics coverage {v.coverage}).")
    if v.confidence < 0.8:
        cons.append(f"Uncertain gain: {v.confidence:.0%} that it is real.")
    return {"pros": pros, "cons": cons}
