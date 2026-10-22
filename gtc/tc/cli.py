"""`python -m gtc theory`: would this character be a better pick for this slot, and why."""
from __future__ import annotations

from pathlib import Path

import yaml

from gtc import SNAPSHOT_DIR, gamedata
from gtc.sim import TeamSim
from gtc.snapshot import Snapshot, latest_snapshot
from gtc.sources import gcsim_db
from gtc.tc import profile_for
from gtc.tc.engine import Candidate, Theory, kit_candidate, load_kits, measured_candidate, swap, team_effects_table
from gtc.tc.profile import Profile, from_gcsim

VALIDATED_ERROR = ("validated on Lunar-Charged teams only: 19 of 20 accepted swaps within 10% of gcsim. "
                   "Other teams are refused (gtc/theory_guard.py)")


def base_profile(team: list[str], kits: dict, mine: bool) -> tuple[Profile, str, dict] | None:
    names = gamedata.names()
    if not mine:
        return profile_for(team, names, kits)
    snap = Snapshot.load(latest_snapshot(SNAPSHOT_DIR))
    ts = TeamSim(team, snap.by_key(), names)
    if not ts.available:
        return None
    r = ts.baseline()
    if r.error:
        return None
    prof = from_gcsim(r.raw_path, names, kits, gamedata.load_characters(), names.artifact_set, None, "your builds")
    return prof, "", {}


def find_candidate(name: str, base: Profile, base_text: str, base_keys: dict, kits: dict) -> tuple[Candidate, Profile | None] | None:
    """Prefer a measured team: the exact swapped lineup, else any simulated team with the same carry and
    this character. Fall back to the kit's listed hits."""
    names = gamedata.names()
    swapped_lineups = [[name if m == out else m for m in base.lineup] for out in base.lineup if out != base.lead]
    tried = []
    for lineup in swapped_lineups:
        tried.append(frozenset(lineup))
    sims = gcsim_db.load()
    others = sorted({t.names for t in sims if base.lead in t.names and name in t.names and t.targets == 1 and t.accepted} - set(tried),
                    key=lambda s: -len(s & set(base.lineup)))
    for lineup in [list(x) for x in tried] + [list(x) for x in others[:5]]:
        if not any(t.names == frozenset(lineup) for t in sims):
            continue
        got = profile_for(lineup, names, kits, base=base, base_text=base_text or None, base_keys=base_keys or None)
        if got and name in got[0].units:
            return measured_candidate(name, got[0]), got[0]
    if (kits.get(name) or {}).get("hits"):
        return kit_candidate(name, kits, {n: u for n, u in base.units.items()}, base.lead, Theory(kits)), None
    return None


def render_swap(res, theory: Theory, base: Profile, cand: Candidate, kits: dict) -> list[str]:
    out = [f"### {res.out} replaced by {res.candidate}", "",
           f"Team damage {res.before / 1000:.1f}k to {res.after / 1000:.1f}k DPS (**{res.change:+.1%}**). "
           f"{res.candidate}'s own damage is {'measured in gcsim (' + cand.origin + ')' if cand.origin.startswith('gcsim') else 'computed from their kit hits'}.", "",
           "| Part of the damage | Before | After |", "|---|---|---|"]
    out += [f"| {d} | {b / 1000:.1f}k | {a / 1000:.1f}k |" for d, b, a in res.lines]
    out.append("")
    units_after = {n: u for n, u in base.units.items() if n != res.out}
    units_after[res.candidate] = cand.unit
    lead = base.lead if base.lead != res.out else res.candidate
    before_fx = set(team_effects_table(theory, base.units, base.lead))
    after_fx = set(team_effects_table(theory, units_after, lead))
    lost, gained = sorted(before_fx - after_fx), sorted(after_fx - before_fx)
    if lost:
        out += ["Effects lost:", ""] + [f"- {x}" for x in lost] + [""]
    if gained:
        out += ["Effects gained:", ""] + [f"- {x}" for x in gained] + [""]
    if res.notes:
        out += ["Notes:", ""] + [f"- {n}" for n in res.notes] + [""]
    return out


def run(team: list[str], replace: str, with_name: str | None, rank: bool, mine: bool, kit_file: str | None,
        rotation: float, beyond_gcsim: bool) -> str:
    kits = load_kits()
    if kit_file:
        kits.update(yaml.safe_load(Path(kit_file).read_text(encoding="utf-8")) or {})
    theory = Theory(kits, beyond_gcsim=beyond_gcsim)
    got = base_profile(team, kits, mine)
    if not got:
        return f"No gcsim rotation exists for {' / '.join(team)}, so there is nothing to reason from. Pick a simulated lineup."
    base, base_text, base_keys = got
    from gtc.theory_guard import UNSUPPORTED_TEXT, check_base, check_swap
    title = f"# Theory: who fills {replace}'s slot in {' / '.join(team)}"
    applies = check_base(base)
    if not applies.supported:
        return title + "\n\n" + UNSUPPORTED_TEXT.format(reason=applies.reason)
    lines = [title, "",
             f"Starting point: {'your own builds' if mine else 'the community gcsim build'}, {base.dps / 1000:.1f}k DPS, carry {base.lead}. "
             f"The calculator is {VALIDATED_ERROR}. "
             + ("Includes Prydwen's Ascendant Gleam party buff, which gcsim does not model." if beyond_gcsim else "")
             + (" Your current members use your real builds, but candidates are assumed built to the community standard, so a swap"
                " can look better than it will be until the candidate is built." if mine else ""), ""]

    names = [with_name] if with_name else []
    if rank:
        snap_names = []
        try:
            snap_names = [c.key for c in Snapshot.load(latest_snapshot(SNAPSHOT_DIR)).characters]
        except FileNotFoundError:
            pass
        pool = set(snap_names) | {k for k, v in kits.items() if not k.startswith("_") and isinstance(v, dict)}
        names = sorted(pool - set(team))

    results, skipped, refused = [], [], []
    for name in names:
        found = find_candidate(name, base, base_text, base_keys, kits)
        if not found:
            skipped.append(name)
            continue
        cand, other = found
        remaining = {n: u for n, u in base.units.items() if n != replace}
        ok = check_swap(base, other, cand.unit.element, [u.element for u in remaining.values()],
                        theory.lunar_enabled({**remaining, name: cand.unit}), leaving=replace)
        if not ok.supported:
            refused.append((name, ok.reason))
            continue
        if other is None and cand.sources:
            cand = kit_candidate(name, kits, remaining, base.lead, theory, rotation)
        res = swap(theory, base, replace, cand, other)
        results.append((res, cand))

    if refused:
        lines += ["Unsupported, so no number is given: " + "; ".join(f"{n} ({why})" for n, why in refused) + ".", ""]
    if rank:
        lines += ["| Candidate | Team DPS | Change | Own damage from |", "|---|---|---|---|"]
        for res, cand in sorted(results, key=lambda x: -x[0].after):
            lines.append(f"| {res.candidate} | {res.after / 1000:.1f}k | {res.change:+.1%} | {'gcsim' if cand.origin.startswith('gcsim') else 'kit hits'} |")
        lines += ["", f"{replace} as it is: {base.dps / 1000:.1f}k.", ""]
        if skipped:
            lines += [f"Not evaluated, because no gcsim team pairs them with {base.lead} and their kit has no hits: "
                      + ", ".join(skipped) + ". Add hits in knowledge/kits_custom/ to include them.", ""]
        for res, cand in sorted(results, key=lambda x: -x[0].after)[:3]:
            lines += render_swap(res, theory, base, cand, kits)
    else:
        if not results:
            if refused:
                return "\n".join(lines)
            return "\n".join(lines + [f"Nothing is known about {with_name}'s own damage: no gcsim team with {base.lead} and no hits in their kit."])
        lines += render_swap(results[0][0], theory, base, results[0][1], kits)
    return "\n".join(lines)
