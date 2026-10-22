"""Account review: what a theorycrafter would tell you after looking at your teams.

For every team reviewed, two kinds of evidence:
  measured   gcsim runs of YOUR builds on a community rotation for that exact lineup, plus one
             change at a time (talent, level, weapon from your own account, standard artifacts).
  checked    rules from Keqing Mains and Prydwen: talent priority, Energy Recharge requirement for
             this team, main stats, substat balance, sets, team-buff set holders, and teammates you
             own that the guides rank above your current pick.

Every suggestion uses only what you own. Each one says how much it is worth, whether that number
was measured or estimated, and what it costs: free (a swap), resin, or farming.
"""
from __future__ import annotations

from gtc import params

import re
from dataclasses import dataclass, field

import yaml

from gtc import KNOWLEDGE_DIR, gamedata
from gtc.evidence import Evidence
from gtc.knowledge import Knowledge
from gtc.report import Analysis, Assessment, analyze, assess
from gtc.sim import TeamSim, plan_variants
from gtc.snapshot import Character, Snapshot
from gtc.sources.names import norm
from gtc.stats import LABELS, element_dmg_key
from gtc.teams import fill_template

EFFORT_ORDER = {"free": 0, "resin": 1, "farming": 2, "pull": 3}
# Rough value of rule findings when no simulation measured them, as a share of team damage.
ESTIMATE = params.get("review.estimate")
SET_CRIT_BONUS = {"Blizzard Strayer": 40, "Night of the Sky's Unveiling": 30}


@dataclass
class Finding:
    team: str
    character: str | None
    category: str
    text: str
    gain: float | None = None  # share of team damage, e.g. 0.12 = +12%
    measured: bool = False
    effort: str = "free"
    source: str = ""
    # Simulation precision of a measured gain: gcsim's iteration noise only. It is NOT the uncertainty of the
    # recommendation, which also depends on the rotation and on the community-standard build compared against
    # (not measured until phase 10), so it is kept here and never printed as a ±.
    gain_sd: float = 0.0
    tier: str = ""  # evidence tier of an estimated gain (B, C, D), when it comes from the team evaluation

    @property
    def simulation_precision(self) -> float:
        return self.gain_sd

    @property
    def gain_label(self) -> str:
        if self.gain is None:
            return "unquantified"
        if self.measured:
            return f"{self.gain:+.0%} (A)"
        return f"{self.gain:+.0%} ({self.tier})" if self.tier else f"{self.gain:+.0%} (estimate)"


@dataclass
class TeamReview:
    assessment: Assessment
    sim: TeamSim | None
    findings: list[Finding] = field(default_factory=list)
    members: list[dict] = field(default_factory=list)


@dataclass
class Review:
    analysis: Analysis
    teams: list[TeamReview]

    def actions(self) -> list[Finding]:
        """Every finding across teams, best first: biggest gain, cheapest effort, measured before estimated."""
        all_f = [f for t in self.teams for f in t.findings]
        return sorted(all_f, key=lambda f: (-(f.gain or 0), EFFORT_ORDER.get(f.effort, 9), not f.measured))


class Guides:
    """Read access to Keqing Mains and Prydwen guide data for one character."""

    def __init__(self, ev: Evidence, names, elements: dict[str, str] | None = None):
        self.kqm, self.pry, self.names = ev.kqm, ev.prydwen.get("characters", {}), names
        self.elements = elements or {}

    def talent_order(self, name: str) -> list[str]:
        return (self.kqm.get(name) or {}).get("talent_priority", {}).get("order", [])

    def weapons(self, name: str) -> list[tuple[str, str, str]]:
        """Recommended weapons as (display name, note, source), Keqing Mains order first."""
        out, seen = [], set()
        for w in (self.kqm.get(name) or {}).get("weapons", []):
            d = self.names.weapon(w["name"])
            if d and d not in seen:
                seen.add(d)
                out.append((d, w.get("note") or "", "Keqing Mains"))
        for w in (self.pry.get(name) or {}).get("weapons", []):
            d = self.names.weapon(w["name"] or "")
            if d and d not in seen:
                seen.add(d)
                out.append((d, f"{w['team']:.0f}% team damage in Prydwen's comparison" if w.get("team") else "", "Prydwen"))
        return out

    def main_stats(self, name: str, slot: str, element: str) -> tuple[list[str], str]:
        tiers = (self.kqm.get(name) or {}).get("main_stats", {}).get(slot)
        source = "Keqing Mains"
        if not tiers:
            tiers = ((self.pry.get(name) or {}).get("main_stats", {}).get(slot) or {}).get("tiers")
            source = "Prydwen"
        if not tiers:
            usage = (self.pry.get(name) or {}).get("usage", {}).get(slot) or []
            tiers = [[u["stat"]] for u in usage if u["share"] >= 25]
            source = "player usage on Prydwen"
        flat = [k for tier in tiers or [] for k in tier]
        flat = [element_dmg_key(element) if k == "elemental_dmg_" else k for k in flat]
        return flat, source

    def substat_tiers(self, name: str) -> list[list[str]]:
        return (self.kqm.get(name) or {}).get("substat_priority", {}).get("tiers", [])

    def sets(self, name: str) -> list[tuple[list[dict], str, str]]:
        """Recommended set options as (pieces, note, source)."""
        out = []
        for o in (self.kqm.get(name) or {}).get("artifact_sets", []):
            pieces = [{"count": p["count"], "set": self.names.artifact_set(p["set"]) or p["set"]} for p in o["pieces"]]
            if pieces:
                out.append((pieces, o.get("note") or "", "Keqing Mains"))
        for o in (self.pry.get(name) or {}).get("artifact_sets", []):
            sname = self.names.artifact_set(o.get("set") or "")
            if sname:
                out.append(([{"count": 4, "set": sname}], o.get("note") or "", "Prydwen"))
        if not out:
            for u in ((self.pry.get(name) or {}).get("usage", {}).get("sets") or [])[:2]:
                if u["share"] >= 20 and u["sets"]:
                    counts: dict[str, int] = {}
                    for sname in u["sets"]:
                        counts[sname] = counts.get(sname, 0) + 2
                    out.append(([{"count": c, "set": s} for s, c in counts.items()], f"{u['share']:.0f}% of players", "player usage on Prydwen"))
        return out

    def er_target(self, name: str, lineup: list[str], cons: int) -> tuple[tuple[int, int], str] | None:
        """Energy Recharge range for this character in this lineup. Prydwen's per-team rows are used when
        they name this exact team; otherwise Keqing Mains' table row that mentions a teammate."""
        pg = self.pry.get(name) or {}
        cols = pg.get("energy_columns") or []
        col = max([i for i, c in enumerate(cols) if c.startswith("C") and c[1:2].isdigit() and int(c[1]) <= cons] or [0])
        for row in pg.get("energy", []):
            label = (row.get("team") or "").split("+")[0]
            team = {self.names.character(x.strip()) for x in label.split("/")}
            if set(lineup) <= team | {None} and len(team - {None}) >= 3 and set(lineup) == (team - {None}):
                vals = row.get("values") or []
                rng = _range(vals[col] if col < len(vals) else (vals[0] if vals else ""))
                if rng:
                    return rng, f"Prydwen, {row['team']}"
        for table in (self.kqm.get(name) or {}).get("er_requirements", []):
            columns = table.get("columns", [])
            ci = self._er_column(columns, lineup, cons)
            rows = table.get("rows", [])
            match = next((r for r in rows if set(r.get("names") or []) & set(lineup)), None)
            # Rows like "Double Cryo" or "With Raiden" describe the team instead of naming a teammate.
            match = match or next((r for r in rows if r["label"] and self._composition_match(r["label"], lineup)), None)
            match = match or next((r for r in rows if not r["label"]), None)
            match = match or next((r for r in rows if "other" in r["label"].lower()), None)
            match = match or (rows[0] if len(rows) == 1 else None)
            if match and ci < len(match["values"]) and match["values"][ci]:
                lo, hi = match["values"][ci]
                where = ", ".join(x for x in (match["label"], columns[ci] if ci < len(columns) else "") if x)
                return (lo, hi), f"Keqing Mains ({where})"
        return None

    def _composition_match(self, label: str, lineup: list[str]) -> bool:
        """'Double Pyro' matches a team with exactly two Pyro members; 'With Raiden' matches a team with Raiden."""
        counts: dict[str, int] = {}
        for m in lineup:
            counts[self.elements.get(m)] = counts.get(self.elements.get(m), 0) + 1
        em = re.match(r"(mono|single|double|triple|quad)\s+(\w+)", label.strip().lower())
        if em:
            return counts.get(em.group(2).capitalize(), 0) == {"mono": 1, "single": 1, "double": 2, "triple": 3, "quad": 4}[em.group(1)]
        wm = re.match(r"with\s+(.+)", label.strip(), flags=re.I)
        return bool(wm and self.names.character(wm.group(1).strip()) in lineup)

    def _er_column(self, columns: list[str], lineup: list[str], cons: int) -> int:
        con_cols = [i for i, c in enumerate(columns) if re.match(r"C(\d)", c) and int(re.match(r"C(\d)", c).group(1)) <= cons]
        if con_cols:
            return max(con_cols)
        comp = [i for i, c in enumerate(columns) if self._composition_match(c, lineup)]
        if comp:
            return comp[0]
        return next((i for i, c in enumerate(columns) if c.strip()), 0)

    def teammate_options(self, name: str) -> list[dict]:
        """Keqing Mains' ranked teammates per slot for this carry: [{slot, options: [{name, note}]}]."""
        return (self.kqm.get(name) or {}).get("teammates", [])

    def constellation_note(self, name: str, cons: int) -> str | None:
        rows = [r for r in (self.pry.get(name) or {}).get("constellations", []) if 0 < r["constellation"] <= cons and r.get("info")]
        return rows[-1]["info"] if rows else None


def _range(text: str) -> tuple[int, int] | None:
    m = re.search(r"(\d+)\s*(?:[–-]\s*(\d+))?\s*%", text or "")
    return (int(m.group(1)), int(m.group(2) or m.group(1))) if m else None


def load_team_sets() -> dict[str, dict]:
    path = KNOWLEDGE_DIR / "sets.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}


def _is_carry(name: str, a: Assessment) -> bool:
    return name == a.lead


def check_member(c: Character, a: Assessment, guides: Guides, owned_weapons, weapon_types, game, used_by_team: set[str]) -> list[Finding]:
    """Rule checks for one character in one team."""
    team = " / ".join(a.team.members)
    out: list[Finding] = []
    carry = _is_carry(c.key, a)
    lineup = a.team.members

    # Talents, by the guide's priority.
    order = [t for t in guides.talent_order(c.key) if t in ("normal", "skill", "burst")]
    eff = c.talents.effective
    base = {"normal": c.talents.normal, "skill": c.talents.skill, "burst": c.talents.burst}
    targets = [(order[0], 9 if carry else 8)] + ([(order[1], 8 if carry else 6)] if len(order) > 1 else []) if order else []
    for t, target in targets:
        if eff[t] < target:
            out.append(Finding(team, c.key, "talent", f"{c.key}'s {t} talent is {base[t]}" + (f" (plus {eff[t] - base[t]} from constellations)" if eff[t] > base[t] else "")
                               + f". The guide puts {t} {'first' if t == order[0] else 'second'}; aim for {target}.",
                               ESTIMATE["talent_carry" if carry else "talent_support"] * (target - eff[t]), False, "resin", "Keqing Mains talent priority"))
    if c.level < 80 or (carry and c.level < 90 and "level" in guides.talent_order(c.key)):
        out.append(Finding(team, c.key, "level", f"{c.key} is level {c.level}." + (" The guide lists Level 90 in the priority." if carry else ""),
                           ESTIMATE["level"] * (2 if c.level < 70 else 1), False, "resin", "Keqing Mains"))

    # Weapon: is it recommended, and do you own something better that nobody in this team uses?
    recs = guides.weapons(c.key)
    rec_names = [r[0] for r in recs]
    if recs and c.weapon.name not in rec_names:
        wtype = game.get(c.key, {}).get("weapon")
        mine = [w for w in owned_weapons if w.name in rec_names and w.name != c.weapon.name
                and weapon_types.get(w.name, {}).get("type") == wtype and (w.location is None or w.location not in used_by_team)]
        if mine:
            best = min(mine, key=lambda w: rec_names.index(w.name))
            note = next(n for nm, n, _ in recs if nm == best.name)
            where = f"held by {best.location}" if best.location else "in your inventory"
            out.append(Finding(team, c.key, "weapon", f"{c.key} uses {c.weapon.name}, which the guides do not list. You own {best.name} ({where}), which they do. {note}".strip(),
                               None, False, "free", "guides' weapon lists"))
    if c.weapon.level < 80 and c.level >= 70:
        out.append(Finding(team, c.key, "weapon", f"{c.key}'s {c.weapon.name} is only level {c.weapon.level}.", 0.04 if carry else 0.02, False, "resin", "investment"))

    # Artifacts.
    if len(c.artifacts) < 5:
        out.append(Finding(team, c.key, "artifacts", f"{c.key} has {len(c.artifacts)} of 5 artifact pieces equipped.", 0.15 * (5 - len(c.artifacts)) if carry else 0.03 * (5 - len(c.artifacts)),
                           False, "farming", "investment"))
    for art in c.artifacts:
        if art.slot not in (3, 4, 5):
            continue
        wanted, src = guides.main_stats(c.key, art.slot_name, c.element)
        if wanted and art.main_stat not in wanted:
            out.append(Finding(team, c.key, "main stat", f"{c.key}'s {art.slot_name} is {LABELS.get(art.main_stat, art.main_stat)}. {src} recommends "
                               + " or ".join(LABELS.get(k, k) for k in dict.fromkeys(wanted)) + ".",
                               ESTIMATE["main_stat_carry" if carry else "main_stat_support"], False, "farming", src))
        if art.level < 16 and art.rarity == 5:
            out.append(Finding(team, c.key, "artifacts", f"{c.key}'s {art.slot_name} is only +{art.level}.", 0.03 if carry else 0.01, False, "resin", "investment"))

    # Sets.
    active = c.active_sets()
    options = guides.sets(c.key)
    if options:
        def satisfied(pieces):
            return all(active.get(p["set"], 0) >= p["count"] for p in pieces)
        if not any(satisfied(p) for p, _, _ in options):
            best_pieces, note, src = options[0]
            want = " + ".join(f"{p['count']}pc {p['set']}" for p in best_pieces)
            have = ", ".join(f"{n}pc {s}" for s, n in active.items()) or "no set bonus"
            out.append(Finding(team, c.key, "set", f"{c.key} runs {have}. {src}'s first choice is {want}. {note}".strip(),
                               ESTIMATE["no_set" if not active else "unrecommended_set"] * (1 if carry else 0.5), False, "farming", src))

    # Energy Recharge requirement for this exact team.
    target = guides.er_target(c.key, lineup, c.constellation)
    er = c.stats.get("energy_recharge")
    if target and er:
        lo, hi = target[0]
        er_rolls = sum(s.get("rolls", 1) for a in c.artifacts for s in a.substats if s["key"] == "enerRech_")
        if er < lo - 2:
            out.append(Finding(team, c.key, "energy", f"{c.key} has {er:.0f}% Energy Recharge; {target[1]} asks for {lo}–{hi}% in this team.",
                               ESTIMATE["er_low"], False, "farming", target[1]))
        elif er > hi + 30 and er_rolls >= 4:
            out.append(Finding(team, c.key, "energy", f"{c.key} has {er:.0f}% Energy Recharge against {lo}–{hi}% needed here. About {er_rolls} substat rolls sit in Energy Recharge that could be CRIT or ATK.",
                               0.05 if carry else 0.01, False, "farming", target[1]))

    # Crit balance for characters whose guide values CRIT.
    tiers = guides.substat_tiers(c.key)
    wants_crit = any("critRate_" in t or "critDMG_" in t for t in tiers[:2])
    cr, cd = c.stats.get("crit_rate"), c.stats.get("crit_dmg")
    if (carry or wants_crit) and cr and cd:
        bonus = max((v for s, v in SET_CRIT_BONUS.items() if active.get(s, 0) >= 4), default=0)
        eff_cr = min(100.0, cr + bonus)
        ratio = cd / eff_cr
        if ratio > 3.3 and eff_cr < 70:
            out.append(Finding(team, c.key, "crit", f"{c.key} has {cr:.0f}% CRIT Rate" + (f" ({eff_cr:.0f}% with the {bonus}% set bonus)" if bonus else "")
                               + f" against {cd:.0f}% CRIT DMG. Guides aim for about 1 to 2, so favour CRIT Rate on the next upgrades.",
                               ESTIMATE["crit_ratio"] * (1 if carry else 0.3), False, "farming", "Keqing Mains stat guidance"))
        elif ratio < 1.4 and eff_cr > 60:
            out.append(Finding(team, c.key, "crit", f"{c.key} has {eff_cr:.0f}% effective CRIT Rate but only {cd:.0f}% CRIT DMG. Shift future rolls toward CRIT DMG.",
                               ESTIMATE["crit_ratio"] * (1 if carry else 0.3), False, "farming", "Keqing Mains stat guidance"))
    return out


def check_team_sets(a: Assessment, chars: dict[str, Character], guides: "Guides", team_sets: dict[str, dict]) -> list[Finding]:
    team = " / ".join(a.team.members)
    out = []
    members = [chars[m] for m in a.team.members]
    elements = {c.element for c in members}
    roles = {r for f in a.team.fills for r, q in f.member.roles.items() if q > 0}
    for set_name, rule in team_sets.items():
        holders = [c.key for c in members if c.active_sets().get(set_name, 0) >= 4]
        if rule.get("one_per_team") and len(holders) > 1:
            out.append(Finding(team, holders[1], "team set", f"{' and '.join(holders)} both use 4pc {set_name}. {rule.get('note', '')} One of them should run a different set.",
                               ESTIMATE["duplicate_team_set"], False, "free", "knowledge/sets.yaml"))
        wanted = rule.get("wanted_when") or {}
        need = bool(set(wanted.get("elements_any", [])) & elements) or bool(set(wanted.get("roles_any", [])) & roles)
        if need and not holders:
            eligible = [c.key for c in members if not rule.get("holder_elements") or c.element in rule["holder_elements"]]
            listed = {m for m in eligible if any(p["set"] == set_name for opts, _, _ in guides.sets(m) for p in opts)}
            eligible.sort(key=lambda m: (m == a.lead, m not in listed))
            who = f" {eligible[0]} is the natural holder." if eligible else ""
            out.append(Finding(team, eligible[0] if eligible else None, "team set", f"Nobody holds 4pc {set_name}.{who} {rule.get('note', '')}",
                               ESTIMATE["missing_team_set"], False, "farming", "knowledge/sets.yaml"))
    return out


SWAP_MIN_GAIN = params.get("review.swap_min_gain")
SWAP_MIN_CONFIDENCE = params.get("review.swap_min_confidence")
RELIABLE_ROUTES = ("exact_community", "pair_model")


def swap_verdict(a: Assessment, new: Assessment) -> dict | None:
    """Compare two lineups on the team evaluation's expected power (the same numbers team power uses), never on
    lineup fit: fit is relative to the lead's best simulated lineup, so when a swap changes the lead the two fits
    have different denominators (Raiden / Kazuha / Xingqiu / Yaoyao fit 60 against Raiden's best, with Keqing fit 85
    against Keqing's best, while its expected power falls from 47 to 39). None when either side has no reliable
    evidence route; such a swap gets no number."""
    from gtc import coverage
    from gtc.estimate import prob_greater

    ea, en = a.evaluation, new.evaluation
    if ea is None or en is None or "single_target" not in ea.power or "single_target" not in en.power:
        return None
    old_p, new_p = ea.power["single_target"], en.power["single_target"]
    if old_p.basis.route not in RELIABLE_ROUTES or new_p.basis.route not in RELIABLE_ROUTES or old_p.expected <= 0:
        return None
    status = coverage.worst([ea.coverage.get("status", coverage.UNKNOWN), en.coverage.get("status", coverage.UNKNOWN)])
    statistical = prob_greater(new_p.as_estimate(), old_p.as_estimate())
    return {"old": old_p, "new": new_p, "gain": new_p.expected / old_p.expected - 1, "statistical": statistical,
            "confidence": coverage.cap(statistical, status), "coverage": status,
            "missing": en.coverage.get("missing", [])}


def teammate_swaps(a: Assessment, an: Analysis, ev: Evidence, kb: Knowledge, guides: Guides, other_teams: dict[str, list[str]],
                   exclusive: bool = False) -> list[Finding]:
    """Owned characters that would make this lineup stronger, judged on expected team power with its evidence
    (swap_verdict). A swap is suggested only when both lineups have a reliable evidence route, the expected gain is
    at least SWAP_MIN_GAIN, and it is at least SWAP_MIN_CONFIDENCE likely to be better after the coverage cap.
    Anything weaker is not shown: no number beats a wrong one."""
    team = " / ".join(a.team.members)
    tpl, lead = a.team.template, a.lead
    out = []
    roster = {m.key: m for m in an.roster}
    kqm_rank = {o["name"]: (i, o["note"]) for s in guides.teammate_options(lead) for i, o in enumerate(s["options"])}
    for f in a.team.fills:
        old = f.member.key
        if old == lead:
            continue
        for cand in roster.values():
            if cand.key in a.team.members:
                continue
            lineup = [cand.key if m == old else m for m in a.team.members]
            filled = fill_template(tpl, [roster[k] for k in lineup], kb, limit=1, rank_by="potential")
            if not filled or set(filled[0].members) != set(lineup):
                continue
            v = swap_verdict(a, assess(filled[0], ev, an.model, kb))
            if v is None or v["gain"] < SWAP_MIN_GAIN or v["confidence"] < SWAP_MIN_CONFIDENCE:
                continue
            note = kqm_rank.get(cand.key, (None, ""))[1]
            elsewhere = [t for t, ms in other_teams.items() if cand.key in ms and t != team]
            if exclusive and elsewhere:
                continue
            build = f" {cand.key} is {an.investments[cand.key].total:.0%} built, so building them comes first." if an.investments[cand.key].total < 0.6 else ""
            conflict = f" Note that {cand.key} is already in your {elsewhere[0]} team." if elsewhere else ""
            o, n = v["old"], v["new"]
            src = {"exact_community": "community simulations", "pair_model": "pair model"}
            how = src[n.basis.route] if n.basis.route == o.basis.route else f"{src[o.basis.route]} against {src[n.basis.route]}"
            text = (f"Swap {old} for {cand.key}: expected team power {o.expected:.0f} to {n.expected:.0f} ({how}, "
                    f"{v['confidence']:.0%} likely better" + (f", mechanics coverage {v['coverage']}" if v["coverage"] != "complete" else "")
                    + ")." + (f" Keqing Mains: {note}" if note else "") + build + conflict)
            finding = Finding(team, old, "teammate", text, v["gain"], False, "free" if not build else "resin", how)
            finding.tier = n.basis.tier
            out.append(finding)
    best: dict[str, Finding] = {}
    for x in out:
        if x.character not in best or (x.gain or 0) > (best[x.character].gain or 0):
            best[x.character] = x
    return sorted(best.values(), key=lambda x: -(x.gain or 0))[:3]


def simulate(a: Assessment, snap: Snapshot, guides: Guides, names, weapon_types, game,
             plan_members: set[str] | None = None) -> tuple[TeamSim | None, list[Finding]]:
    team = " / ".join(a.team.members)
    chars = snap.by_key()
    ts = TeamSim(a.team.members, chars, names)
    if not ts.available:
        return None, []
    base = ts.baseline()
    if base.error:
        return ts, [Finding(team, None, "simulation", f"gcsim could not run this lineup: {base.error[:200]}", None, False, "free", "gcsim")]
    out = []
    for n, added in ts.er_deficit.items():
        out.append(Finding(team, n, "energy", f"On the community rotation {n} cannot afford their Burst; gcsim needed about +{added:.0f}% Energy Recharge to keep the rotation going. "
                           "Every other number for this team assumes that Energy Recharge is fixed.", None, True, "farming", "gcsim"))
    order = {n: guides.talent_order(n) for n in a.team.members}
    for v in plan_variants(ts, chars, snap.all_weapons(), weapon_types, game, order):
        if v.error or v.gain < 0.01:
            continue
        effort = {"talent": "resin", "level": "resin", "weapon": "free", "artifacts": "farming"}[v.kind]
        text = v.label
        if v.kind == "artifacts":
            text = f"{v.character}'s artifacts are holding the team back: with community-standard artifacts this team would deal {v.gain:+.0%}."
        if v.kind == "weapon":
            m = re.search(r"taken from (.+)\)$", v.label)
            donor = m.group(1) if m else None
            if donor and plan_members is not None and donor not in plan_members:
                text += f". {donor} is not in any of your planned teams."
            elif donor and donor in chars:
                donor_recs = [w for w, _, _ in guides.weapons(donor)]
                weapon = re.search(r"uses R\d (.+?) \(level", v.label).group(1)
                if weapon in donor_recs:
                    text += f". {donor} also wants this weapon, so this moves damage between teams rather than adding it."
                    effort = "free (trade-off)"
                else:
                    text += f". The guides do not list it for {donor}, so {donor} loses little."
        out.append(Finding(team, v.character, v.kind, text, v.gain, True, effort, "gcsim", v.gain_sd))
    return ts, out


def covered_by_theory(members: list[str]) -> bool:
    """The calculator only reasons about teams whose every member has kit numbers in knowledge/kits.yaml."""
    from gtc.tc.engine import load_kits

    kits = load_kits()
    return all(m in kits for m in members)


def theory_swaps(a: Assessment, ts: TeamSim, an: Analysis, kb: Knowledge, other_teams: dict[str, list[str]],
                 exclusive: bool = False) -> list[Finding]:
    """Teammate swaps judged by the theorycraft calculator on YOUR simulated team: formulas applied to the
    measured damage breakdown, with each candidate's own damage measured in another gcsim team."""
    from gtc.tc.cli import find_candidate
    from gtc.tc.engine import Theory, load_kits, swap
    from gtc.tc.profile import from_gcsim
    from gtc.teams import slot_candidates

    from gtc.tc import profile_for

    names = gamedata.names()
    kits = load_kits()
    if any(m not in kits for m in a.team.members):
        return []  # some member's buffs are unknown to the calculator; see covered_by_theory()
    got = profile_for(a.team.members, names, kits)
    if not got:
        return []
    # Community builds for everyone, so the comparison is about the lineup, not about investment.
    prof, base_text, base_keys = got
    from gtc.theory_guard import check_base, check_swap
    if not check_base(prof).supported:
        return []  # the calculator is not validated for this team (gtc/theory_guard.py): no number beats a wrong one
    theory = Theory(kits)
    team = " / ".join(a.team.members)
    out = []
    for f in a.team.fills:
        leaving = f.member.key
        if leaving == prof.lead:
            continue
        best = None
        for m, *_ in slot_candidates(f.slot, a.team.template, an.roster):
            if m.key in a.team.members or m.key not in kits:
                continue
            if exclusive and any(m.key in ms for t, ms in other_teams.items() if t != team):
                continue
            found = find_candidate(m.key, prof, base_text, base_keys, kits)
            if not found:
                continue
            cand, other = found
            remaining = {n: u for n, u in prof.units.items() if n != leaving}
            if not check_swap(prof, other, cand.unit.element, [u.element for u in remaining.values()],
                              theory.lunar_enabled({**remaining, m.key: cand.unit}), leaving=leaving).supported:
                continue
            res = swap(theory, prof, leaving, *found)
            if best is None or res.change > best[0].change:
                best = (res, m.key)
        if best and best[0].change > 0.02:
            res, who = best
            # Cross-check with the team evaluation: when it can judge the swapped lineup and expects it to be weaker,
            # the calculator's number is not shown.
            roster = {m.key: m for m in an.roster}
            lineup = [who if m == leaving else m for m in a.team.members]
            filled = fill_template(a.team.template, [roster[k] for k in lineup], kb, limit=1, rank_by="potential")
            verdict = swap_verdict(a, assess(filled[0], an.evidence, an.model, kb)) if filled and set(filled[0].members) == set(lineup) else None
            if verdict is not None and verdict["gain"] < 0:
                continue
            elsewhere = [t for t, ms in other_teams.items() if who in ms and t != team]
            build = an.investments[who].total
            text = (f"Swap {leaving} for {who}: with both built to the community standard, the theorycraft calculator puts this team at "
                    f"{res.change:+.0%} ({res.before / 1000:.1f}k to {res.after / 1000:.1f}k DPS)."
                    + (f" Your {who} is {build:.0%} built, so the gain only arrives after building them." if build < 0.75 else "")
                    + (f" {who} is already in your {elsewhere[0]} team." if elsewhere else "")
                    + (" " + " ".join(res.notes) if res.notes else "")
                    + (f" The team evaluation agrees: expected power {verdict['old'].expected:.0f} to {verdict['new'].expected:.0f}."
                       if verdict is not None else ""))
            out.append(Finding(team, leaving, "teammate", text, res.change, False, "free" if build >= 0.75 else "resin",
                               "theorycraft calculator"))
    return out


def build_review(snapshot: Snapshot, kb: Knowledge, extra_teams: int = 3, exclusive: bool = False,
                 an: Analysis | None = None) -> Review:
    """exclusive=True reviews a set of teams as one plan: no suggestion moves a character between them."""
    an = an or analyze(snapshot, kb)
    ev = an.evidence
    names = gamedata.names()
    weapon_types, game = gamedata.load_weapons(), gamedata.load_characters()
    chars = snapshot.by_key()
    guides = Guides(ev, names, {k: c.element for k, c in chars.items()})
    team_sets = load_team_sets()

    picked: list[Assessment] = [x for _, x in an.my_teams if x]
    for x in an.per_archetype:
        if len(picked) >= len(an.my_teams) + extra_teams:
            break
        if all(set(x.team.members) != set(p.team.members) for p in picked):
            picked.append(x)
    team_members = {" / ".join(p.team.members): p.team.members for p in picked}

    reviews = []
    for a in picked:
        plan_members = {m for p in picked for m in p.team.members} if exclusive else None
        ts, findings = simulate(a, snapshot, guides, names, weapon_types, game, plan_members)
        measured = {(f.character, f.category) for f in findings if f.measured}
        for m in a.team.members:
            for f in check_member(chars[m], a, guides, snapshot.all_weapons(), weapon_types, game, set(a.team.members)):
                if (f.character, f.category) in measured and f.category in ("talent", "level"):
                    continue  # the simulation measured this exact change
                if (f.character, "artifacts") in measured and f.category in ("set", "main stat", "artifacts", "crit"):
                    f.gain = None  # still explains why the artifacts fall short, but the measured number counts
                findings.append(f)
        findings += check_team_sets(a, chars, guides, team_sets)
        swaps = theory_swaps(a, ts, an, kb, team_members, exclusive) if ts and ts.base and not ts.base.error else None
        findings += swaps if swaps is not None and covered_by_theory(a.team.members) else teammate_swaps(a, an, ev, kb, guides, team_members, exclusive)
        members = []
        for m in a.team.members:
            c = chars[m]
            members.append({
                "name": m, "level": c.level, "cons": c.constellation,
                "talents": f"{c.talents.normal}/{c.talents.skill}/{c.talents.burst}",
                "weapon": f"{c.weapon.name} R{c.weapon.refinement} lv{c.weapon.level}",
                "sets": ", ".join(f"{n}pc {s}" for s, n in c.active_sets().items()) or "none",
                "er": c.stats.get("energy_recharge"), "cr": c.stats.get("crit_rate"), "cd": c.stats.get("crit_dmg"),
                "investment": an.investments[m].total, "con_note": guides.constellation_note(m, c.constellation),
            })
        reviews.append(TeamReview(a, ts, findings, members))
    return Review(an, reviews)


def synergy_lines(a: Assessment) -> list[str]:
    """Each teammate's measured share of team damage and what it is made of: from this exact lineup when it
    was simulated, otherwise their average alongside the same carry."""
    from gtc.synergy import table

    tbl = table()
    if tbl is None:
        return []
    lead = a.lead
    exact = tbl.by_lineup.get(frozenset(a.team.members))
    out = []
    for m in a.team.members:
        if m == lead:
            continue
        if exact:
            own = exact["own"].get(m, 0.0)
            kinds: dict[str, float] = {}
            for key, v in (exact["detail"].get(m) or {}).items():
                kind = key.split("|", 1)[1]
                kinds[kind] = kinds.get(kind, 0.0) + v
            # Buffs as a fair (Shapley) share, so teammates' shares add up; the buff types come from the per-buff
            # breakdown, scaled to that share. Enablement is reported apart: it is a share of teammates' damage
            # their auras or Dendro cores made possible, which overlaps with that damage rather than adding to it.
            marginal = exact["buffs_marginal"].get(m, 0.0)
            fair = exact.get("buffs_shapley", {}).get(m, marginal)
            scale = fair / marginal if marginal > 0 else 1.0
            kinds = {k: v * scale for k, v in kinds.items() if k != "enablement"}
            parts = ([f"own damage {own:.0%}"] if own >= 0.01 else []) + [f"{k} {v:.0%}" for k, v in sorted(kinds.items(), key=lambda x: -x[1]) if v >= 0.01]
            line = f"{m}: {own + fair:.0%} of this team's damage ({', '.join(parts) or 'little measurable effect'})"
            enable = (exact.get("enable_reaction") or {}).get(m, 0.0)
            amp = (exact.get("enable_amp") or {}).get(m, 0.0)
            if enable >= 0.01:
                line += f"; their auras or cores also make possible reactions worth {enable:.0%} of the team's damage"
            if amp >= 0.01:
                line += f"; their aura supplies the amplified part of Vaporize or Melt hits, {amp:.0%} of the team's damage"
            out.append(line + ".")
        elif lead is None:
            out.append(f"{m}: this lineup was not simulated and its damage is not built around one carry, so no measured synergy.")
        else:
            pair = tbl.pair(lead, m)
            if pair:
                out.append(f"{m}: about {pair.value:.0%} of team damage with {lead}, averaged over {pair.n} simulated team(s) ({pair.explain()}).")
            else:
                out.append(f"{m}: never simulated alongside {lead}, so no measured synergy.")
    return out


def render(r: Review) -> str:
    s = r.analysis.snapshot
    out = [f"# Account review for UID {s.uid}", "", f"Engine model {params.version()} ({params.fingerprint()}).", "",
           f"Snapshot taken {s.taken_at}. Data level: {s.data_level}. Inventory: " + ("included." if s.has_inventory else
           "not imported, so only equipped weapons and artifacts are considered for swaps, and no suggestion "
           "claims that a spare item does not exist."), "",
           "Every suggestion uses characters, weapons and artifacts you already own. Gains are a share of that team's damage. "
           "**Measured** gains come from gcsim runs of your actual builds; the rest are estimates from guide rules.", "", "(A) means gcsim ran your own builds on the community rotation. Those runs are precise as simulations, but the number leaves out uncertainty about the rotation and about the community-standard build it compares against, so no ± is shown; treat it as a measured direction and rough size.", "",
           "## Top changes across your account", "",
           "| # | Change | Team | Gain | Effort |", "|---|---|---|---|---|"]
    seen = set()
    rank = 0
    group = {"artifacts": "artifacts", "set": "artifacts", "main stat": "artifacts", "crit": "artifacts"}
    ordered = sorted(r.actions(), key=lambda f: (not f.measured, -(f.gain or 0)))
    keep = []
    for f in ordered:
        key = (f.character, group.get(f.category, f.category), f.text if f.category in ("weapon", "teammate", "talent", "level") else "")
        if f.gain is None or f.gain < 0.02 or key in seen:
            continue
        seen.add(key)
        keep.append(f)
    for f in sorted(keep, key=lambda f: (-(f.gain or 0), EFFORT_ORDER.get(f.effort, 9))):
        rank += 1
        out.append(f"| {rank} | {f.text} | {f.team} | {f.gain_label} | {f.effort} |")
        if rank >= 15:
            break
    out.append("")

    for t in r.teams:
        a = t.assessment
        out += [f"## {' / '.join(a.team.members)}", "", f"*{a.label}*. Team rating {a.today_power:.0f}, lineup fit {a.fit} ({a.fit.source}), build progress {a.build}%.", ""]
        if t.sim and t.sim.base and not t.sim.base.error:
            std = t.sim.config.db_dps
            raw = t.sim.raw.dps if t.sim.raw else t.sim.base.dps
            out += [f"**Simulated:** your builds deal {t.sim.base.dps / 1000:.1f}k DPS on the community rotation, against {std / 1000:.1f}k with the community's standard builds "
                    f"({t.sim.base.dps / std:.0%}). That is with Energy Recharge topped up where a Burst would otherwise stall.", ""]
            cost = t.sim.er_cost()
            if cost:
                skipped = "; ".join(f"{n} skips {lost:.0f} of {n_all:.0f} Bursts" for n, (lost, n_all) in sorted(cost["skipped"].items()))
                out += [f"**Energy Recharge, as built:** {cost['reality'] / 1000:.1f}k DPS, {cost['loss']:.0%} less than topped up"
                        + (f" ({skipped})" if skipped else "") + ". Added to stop stalls: "
                        + ", ".join(f"{n} +{er:.0f}%" for n, er in t.sim.er_deficit.items())
                        + f". A rotation that waits for every Burst instead deals {raw / 1000:.1f}k.", ""]
            share = t.sim.character_dps(t.sim.base)
            total = sum(share.values()) or 1
            out += ["Damage share: " + ", ".join(f"{k} {v / total:.0%}" for k, v in sorted(share.items(), key=lambda x: -x[1])) + ".", ""]
            if t.sim.problems:
                out += ["Simulation caveats: " + "; ".join(t.sim.problems) + ".", ""]
        else:
            out += ["**Not simulated:** nobody has submitted this exact lineup to the gcsim database, so the findings below are rule checks only.", ""]

        out += ["| Character | Level | Cons | Talents | Weapon | Sets | ER | CRIT | Built |", "|---|---|---|---|---|---|---|---|---|"]
        for m in t.members:
            crit = f"{m['cr']:.0f} / {m['cd']:.0f}" if m["cr"] else "n/a"
            out.append(f"| {m['name']} | {m['level']} | C{m['cons']} | {m['talents']} | {m['weapon']} | {m['sets']} | {m['er']:.0f}% | {crit} | {m['investment']:.0%} |")
        out.append("")

        groups = [("Changes", [f for f in t.findings if f.gain is not None and f.gain >= 0.01]),
                  ("Also worth knowing", [f for f in t.findings if f.gain is None or f.gain < 0.01])]
        for title, items in groups:
            if not items:
                continue
            out += [f"**{title}**", ""]
            for f in sorted(items, key=lambda f: (-(f.gain or 0), EFFORT_ORDER.get(f.effort, 9))):
                tag = f"{f.gain_label}, {f.effort}" if f.gain is not None else f.effort
                out.append(f"- **{f.category.capitalize()}** ({tag}): {f.text}")
            out.append("")
        syn = synergy_lines(a)
        if syn:
            out += ["**What each teammate brings** (measured from gcsim logs, hit by hit)", ""] + [f"- {x}" for x in syn] + [""]
        notes = [f"{m['name']} C{m['cons']}: {m['con_note']}" for m in t.members if m["con_note"] and m["cons"] > 0]
        if notes:
            out += ["**Your constellations, according to Prydwen**", ""] + [f"- {n}" for n in notes] + [""]
    return "\n".join(out)
