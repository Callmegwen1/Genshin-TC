"""Combine gcsim, Prydwen and Keqing Mains into the numbers the engine reports.

Every number comes back as a Measure that says where it came from. Order of preference:
  1. gcsim measurement under comparable assumptions (actual simulated damage)
  2. Prydwen's published figure (their own sims, fewer teams)
  3. our model, calibrated against the measurements in 1 and 2
Keqing Mains adds qualitative evidence: whether a lineup is a recommended team, and why.

Design notes and the gaps this fills are in docs/engine.md.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from gtc.knowledge import Knowledge, Template
from gtc.sources.gcsim_db import SimTeam, is_standard

PRYDWEN_TIER_VALUE = {"T0": 100, "T0.5": 92, "T1": 84, "T1.5": 76, "T2": 68, "T3": 56, "T4": 44, "T5": 32}
SUPPORT_ROLES = ("offfield_app", "offfield_dps", "buffer_general", "buffer_anemo", "buffer_atk", "buffer_cryo",
                 "buffer_lunar", "em_share", "healer", "shield", "battery")


@dataclass
class Measure:
    value: float | None
    source: str  # "gcsim", "prydwen", "synergy", "pairmodel", "model", or "none"
    detail: str = ""
    anchored: bool = True  # False for a model estimate with no simulated lineup of this carry nearby

    @property
    def measured(self) -> bool:
        return self.source in ("gcsim", "prydwen", "synergy")

    def __str__(self) -> str:
        return "n/a" if self.value is None else f"{self.value:.0f}"


@dataclass
class Calibration:
    """Turns the model's raw lineup fit into an estimate on the measured scale.

    1. A global curve: calibrated = 100 * (model/100) ** k, fitted on every measured lineup.
    2. A per-archetype baseline: the average measured fit of that archetype's lineups,
       pulled toward the global average when there are few of them.
    3. Trust: the estimate moves from the baseline toward the curve by `trust`. Archetypes whose
       slots have value formulas get full trust. Coarse ones barely separate lineups, so they get little.
    4. Local correction: if the same carry has measured lineups in this archetype, shift by the
       average miss on them, so estimates and measurements for one carry sit on the same scale.
    """
    k: float = 1.0
    anchors: list[tuple[str, str, str, float, float]] = field(default_factory=list)  # (lineup, template id, lead, model, measured)
    baseline: dict[str, float] = field(default_factory=dict)
    global_mean: float = 70.0
    coarse_trust: float = 0.25

    def curve(self, model_fit: float) -> float:
        return 100 * (max(model_fit, 0.1) / 100) ** self.k

    residual: dict[tuple[str, str], float] = field(default_factory=dict)
    k_by_template: dict[str, float] = field(default_factory=dict)

    def curve_for(self, model_fit: float, template_id: str | None) -> float:
        """Per-archetype curve: how strongly real damage separates lineups the model sees as close."""
        k = self.k_by_template.get(template_id, self.k)
        return 100 * (max(model_fit, 0.1) / 100) ** k

    def _global(self, model_fit: float, template_id: str, coarse: bool) -> float:
        base = self.baseline.get(template_id, self.global_mean)
        trust = self.coarse_trust if coarse else 1.0
        return base + trust * (self.curve_for(model_fit, template_id) - base)

    def apply(self, model_fit: float, template_id: str, coarse: bool, lead: str | None = None) -> float:
        est = self._global(model_fit, template_id, coarse) + self.residual.get((template_id, lead), 0.0)
        return max(1.0, min(100.0, est))

    def fit_residuals(self, coarse_ids: set[str], shrink: float = 2.0) -> None:
        groups: dict[tuple[str, str], list[float]] = {}
        for _, t, lead, m, y in self.anchors:
            groups.setdefault((t, lead), []).append(y - self._global(m, t, t in coarse_ids))
        self.residual = {k: sum(v) / (len(v) + shrink) for k, v in groups.items()}

    def error(self, calibrated: bool, coarse_ids: set[str], local: bool = True) -> float | None:
        """Average miss on the anchors. With local=True each anchor is scored leave-one-out, so the
        local correction cannot simply memorise the answer."""
        errs = self.errors(calibrated, coarse_ids, local)
        return sum(errs) / len(errs) if errs else None

    def sd(self, coarse_ids: set[str], local: bool) -> float | None:
        """One standard deviation of the calibrated estimate, from leave-one-out misses: the 68.3rd percentile
        of their absolute values. local=False is the estimate without a per-carry correction."""
        errs = sorted(self.errors(True, coarse_ids, local))
        return errs[min(len(errs) - 1, int(0.683 * len(errs)))] if errs else None

    def errors(self, calibrated: bool, coarse_ids: set[str], local: bool = True) -> list[float]:
        if not self.anchors:
            return []
        errs = []
        for i, (_, t, lead, m, y) in enumerate(self.anchors):
            if not calibrated:
                errs.append(abs(m - y))
                continue
            est = self._global(m, t, t in coarse_ids)
            if local:
                others = [yy - self._global(mm, tt, tt in coarse_ids)
                          for j, (_, tt, ll, mm, yy) in enumerate(self.anchors) if j != i and tt == t and ll == lead]
                est += sum(others) / (len(others) + 2.0)
            errs.append(abs(max(1.0, min(100.0, est)) - y))
        return errs


def fit_calibration(anchors: list[tuple[str, str, str, float, float]], coarse_ids: set[str], prior_weight: float = 5.0) -> Calibration:
    """Least squares on logs for the curve: ln(measured/100) = k * ln(model/100). Then per-archetype baselines."""
    pts = [(math.log(m / 100), math.log(y / 100)) for _, _, _, m, y in anchors if 0 < m < 100 and 0 < y <= 100]
    den = sum(x * x for x, _ in pts)
    k = sum(x * y for x, y in pts) / den if den > 1e-9 else 1.0
    measured = [y for *_, y in anchors]
    global_mean = sum(measured) / len(measured) if measured else 70.0
    by_t: dict[str, list[float]] = {}
    for _, t, _, _, y in anchors:
        by_t.setdefault(t, []).append(y)
    baseline = {t: (sum(ys) + prior_weight * global_mean) / (len(ys) + prior_weight) for t, ys in by_t.items()}
    cal = Calibration(k=max(0.5, min(k, 8.0)), anchors=anchors, baseline=baseline, global_mean=global_mean)
    # Per-archetype curve exponent, pulled toward the global one when an archetype has few measurements.
    by_tpl: dict[str, list[tuple[float, float]]] = {}
    for _, t, _, m, y in anchors:
        if 0 < m < 100 and 0 < y <= 100:
            by_tpl.setdefault(t, []).append((math.log(m / 100), math.log(y / 100)))
    for t, pts in by_tpl.items():
        den_t = sum(x * x for x, _ in pts)
        if den_t > 1e-9:
            k_t = sum(x * y for x, y in pts) / den_t
            n = len(pts)
            cal.k_by_template[t] = max(0.5, min(8.0, (n * k_t + 4 * cal.k) / (n + 4)))
    cal.fit_residuals(coarse_ids)
    return cal


def is_coarse(template: Template) -> bool:
    """True when no slot has a value formula, so the model only sees each character's main role."""
    return not any(s.value for s in template.slots)


def signature_ok(template: Template, elements: list[str]) -> bool:
    sig = template.signature or {}
    present = set(elements)
    if not set(sig.get("require", [])) <= present:
        return False
    if set(sig.get("forbid", [])) & present:
        return False
    only = sig.get("only")
    return not only or present <= set(only)


def role_categories(prydwen: dict) -> dict[str, set[str]]:
    """Prydwen role categories per character. An On-Field DPS entry tagged 'driver' (on-field, but the
    damage comes from teammates, like Ayato in Columbina teams) becomes 'Driver' rather than 'DPS'."""
    out: dict[str, set[str]] = {}
    for name, entries in prydwen.get("tiers", {}).items():
        for e in entries:
            driver = e["category"] == "DPS" and any(t.startswith("driver") for t in e.get("tags", []))
            out.setdefault(name, set()).add("Driver" if driver else e["category"])
    return out


def assign_carry(names, categories: dict[str, set[str]]) -> str | None:
    """Who carries a simulated team, using Prydwen's role categories: the one member rated purely as an
    On-Field DPS, or the only member rated as DPS at all. Anything else is ambiguous and returns None."""
    pure = [n for n in names if categories.get(n) == {"DPS"}]
    any_dps = [n for n in names if "DPS" in categories.get(n, set())]
    if len(pure) == 1:
        return pure[0]
    if not pure and len(any_dps) == 1:
        return any_dps[0]
    drivers = [n for n in names if "Driver" in categories.get(n, set())]
    if not any_dps and len(drivers) == 1:
        return drivers[0]
    return None


class Evidence:
    def __init__(self, kb: Knowledge, game: dict[str, dict], sims: list[SimTeam], prydwen: dict, kqm: dict):
        self.kb, self.game, self.prydwen, self.kqm = kb, game, prydwen, kqm
        self.sims = [s for s in sims if s.targets == 1 and s.accepted]
        self.standard = [s for s in self.sims if is_standard(s)]
        # A lineup's value is the median of per-submitter medians of its standard simulations
        # (gcsim_db.lineup_values): robust to the best submission's upward bias and to one prolific submitter.
        from gtc.sources.gcsim_db import aggregate

        groups: dict[frozenset, list] = {}
        for s in self.standard:
            groups.setdefault(s.names, []).append(s)
        values = {k: aggregate(v) for k, v in groups.items()}  # the shared rule, over this Evidence's own simulations
        self.lineup_values = values  # with per-build medians, for the exact route's uncertainty
        self.lineup_median: dict[frozenset, float] = {k: v.value for k, v in values.items()}
        self.lineup_n: dict[frozenset, int] = {k: v.n_submitters for k, v in values.items()}
        top = sorted(self.lineup_median.values(), reverse=True)[:3]
        # 100 on the archetype tier scale: the average of the three strongest distinct standard lineups.
        self.normalizer = sum(top) / len(top) if top else None
        self.calibration = Calibration()
        self.categories = role_categories(prydwen)
        # Indexes: simulations by member, and memoised lookups. The engine asks for a carry's simulations
        # thousands of times per report; scanning every simulation each time dominated the run time.
        self._by_member: dict[str, list[SimTeam]] = {}
        for sim in self.sims:
            for n in sim.names:
                self._by_member.setdefault(n, []).append(sim)
        self._standard_ids = {id(s) for s in self.standard}
        self._attributed: dict[tuple[int, str], bool] = {}
        self._sims_for: dict[tuple[str, str, bool], list[SimTeam]] = {}
        # Faction tags (Moonsign, Hexerei, Nightsoul...) from Prydwen's synergy entries.
        self.factions: dict[str, set[str]] = {}
        for guide in prydwen.get("characters", {}).values():
            for syn in guide.get("synergies", []):
                if syn.get("tag") and syn.get("name"):
                    tag = syn["tag"].strip().split(":")[0].strip().lower().replace(" ", "_")
                    self.factions.setdefault(syn["name"], set()).add(tag)

    def faction_roles(self, name: str) -> dict[str, int]:
        return {f"faction_{t}": 3 for t in self.factions.get(name, ())}

    # ---------- attribution ----------
    def element(self, name: str) -> str:
        if name.startswith("Traveler ("):
            return name[10:-1]
        return self.game.get(name, {}).get("element", "?")

    def carry_only(self, name: str) -> bool:
        """True if this character is played on-field as the main damage dealer and nothing else.
        Uses our role tags when we have them, otherwise Prydwen's role categories."""
        info = self.kb.characters.get(name)
        if info:
            carry = any(r.startswith("carry_") and q >= 3 for r, q in info.roles.items())
            support = any(info.roles.get(r, 0) >= 3 for r in SUPPORT_ROLES)
            return carry and not support
        cats = {t["category"] for t in self.prydwen.get("tiers", {}).get(name, [])}
        return cats == {"DPS"}

    def attributed(self, sim: SimTeam, lead: str) -> bool:
        key = (id(sim), lead)
        hit = self._attributed.get(key)
        if hit is None:
            hit = self._attributed[key] = self._attributed_uncached(sim, lead)
        return hit

    def measured_profile(self, names: frozenset) -> dict | None:
        """The simulated lineup's full measured profile (gtc.synergy.Attributor.measure_profile)."""
        from gtc.synergy import table

        tbl = table()
        e = tbl.by_lineup.get(names) if tbl else None
        return e.get("profile") if e else None

    def measured_structure(self, names: frozenset) -> dict | None:
        """The measured structure of a simulated lineup, with class probabilities from one sample's noise."""
        from gtc import structure
        from gtc.synergy import table

        tbl = table()
        e = tbl.by_lineup.get(names) if tbl else None
        prof = (e or {}).get("profile")
        return structure.from_profile(names, prof) if prof and prof.get("structure") else None

    def _attributed_uncached(self, sim: SimTeam, lead: str | None) -> bool:
        """Does this simulation belong to `lead`? From its MEASURED damage structure when available: the lineup's
        top damage owner. lead None asks for teams without a single carry (reaction cores, drivers, distributed)."""
        st = self.measured_structure(sim.names)
        if st is not None:
            carry = st["owners"][0] if st["type"] in ("hypercarry", "dual_carry") and st["owners"] else None
            return carry == lead
        if lead is None:
            return False
        return self._attributed_by_category(sim, lead)

    def _attributed_by_category(self, sim: SimTeam, lead: str) -> bool:
        """A simulation counts for `lead` only if `lead` is that team's carry. Prydwen's role categories
        decide when they cover the team (same rule as archetype discovery); otherwise our role tags do.
        This stops a Skirk or Columbina team that includes Ayaka or Ayato from counting as theirs."""
        if lead not in sim.names:
            return False
        if all(n in self.categories for n in sim.names):
            carry = assign_carry(sim.names, self.categories)
            if carry == lead:
                return True
            # Support-led teams (taser, hyperbloom, Chevreuse) have no carry at all; they count for their lead.
            lead_cats = self.categories.get(lead, set())
            return carry is None and not ({"DPS", "Driver"} & lead_cats) and not any(
                "DPS" in self.categories.get(n, set()) for n in sim.names)
        return not any(self.carry_only(n) for n in sim.names if n != lead)

    def calibration_sd(self, kb) -> tuple[float, float]:
        """(anchored, unanchored) sd of the calibrated role model in fit points, from leave-one-out misses."""
        if getattr(self, "_cal_sd", None) is None or self._cal_sd[0] is not self.calibration:
            coarse = {t.id for t in kb.templates.values() if is_coarse(t)}
            local = self.calibration.sd(coarse, True) or 15.0
            glob = self.calibration.sd(coarse, False) or 20.0
            self._cal_sd = (self.calibration, (local, max(local, glob)))
        return self._cal_sd[1]

    def family_lineups(self) -> dict[str, set[frozenset]]:
        """Generated archetypes count only the simulated lineups they were discovered from (gtc/derive.py)."""
        if getattr(self, "_family_lineups", None) is None:
            import json

            from gtc.derive import FAMILY_LINEUPS
            raw = json.loads(FAMILY_LINEUPS.read_text(encoding="utf-8")) if FAMILY_LINEUPS.exists() else {}
            self._family_lineups = {tid: {frozenset(x) for x in v} for tid, v in raw.items()}
        return self._family_lineups

    def sims_for(self, template: Template, lead: str | None, standard: bool = True) -> list[SimTeam]:
        key = (template.id, lead, standard)
        found = self._sims_for.get(key)
        if found is None:
            pool = self._by_member.get(lead, []) if lead else (self.standard if standard else self.sims)
            if standard:
                pool = [s for s in pool if id(s) in self._standard_ids]
            family = self.family_lineups().get(template.id)
            found = self._sims_for[key] = [s for s in pool if self.attributed(s, lead)
                                           and signature_ok(template, [self.element(n) for n in s.names])
                                           and (family is None or s.names in family)]
        return found

    # ---------- archetype tier ----------
    def prydwen_tier(self, name: str) -> dict | None:
        entries = self.prydwen.get("tiers", {}).get(name, [])
        dps = [e for e in entries if e["category"] == "DPS" and e.get("overall")]
        rated = dps or [e for e in entries if e.get("overall")]
        return min(rated, key=lambda e: list(PRYDWEN_TIER_VALUE).index(e["overall"])) if rated else None

    def archetype_tier(self, template: Template, lead: str | None) -> tuple[Measure, SimTeam | None]:
        sims = self.sims_for(template, lead)
        if sims and self.normalizer:
            best = max(sims, key=lambda s: self.lineup_median.get(s.names, s.dps))
            dps = self.lineup_median.get(best.names, best.dps)
            value = min(100.0, 100 * dps / self.normalizer)
            who = f"{lead} team" if lead else "team without a single carry"
            return Measure(value, "gcsim", f"best standard {who} simulates {dps / 1000:.0f}k DPS (median of its simulations; {len(sims)} sims)"), best
        if lead is None:
            return Measure(None, "none", "no simulated team of this archetype without a single carry"), None
        pt = self.prydwen_tier(lead)
        if pt and pt["category"] == "DPS":  # support tiers say nothing about an archetype's damage ceiling
            return Measure(PRYDWEN_TIER_VALUE[pt["overall"]], "prydwen", f"{lead} is {pt['overall']} in Prydwen's {pt['category']} list"), None
        return Measure(None, "none", "no simulation or rating found"), None

    # ---------- lineup fit ----------
    def _others_standard(self, sim: SimTeam, lead: str) -> bool:
        return all((m.rarity < 5 or m.cons == 0) and (m.weapon_rarity < 5 or m.refine == 1) for m in sim.members if m.name != lead)

    def measured_fit(self, template: Template, lineup: list[str], lead: str) -> Measure | None:
        """Two ways to measure, in order:
        1. Standard against standard: the lineup's best standard sim against the lead's best standard sim
           in this archetype. Same basis as the archetype tier.
        2. Like-for-like: if the lineup was only simulated with non-standard gear, compare it with the best
           sim that uses the exact same lead build (constellation, weapon, refinement), other 5-stars C0 R1.
           Only counts when at least one other lineup exists for that build."""
        team = frozenset(lineup)
        lead_pool = self.sims_for(template, lead, standard=True)
        mine_std = [s for s in lead_pool if s.names == team]
        if mine_std:
            mine_dps = self.lineup_median[team]
            top = max(lead_pool, key=lambda x: self.lineup_median.get(x.names, x.dps))
            top_dps = self.lineup_median.get(top.names, top.dps)
            who = lead or "this archetype"
            if top.names == team:
                return Measure(100.0, "gcsim", f"the best standard {who} lineup simulated ({mine_dps / 1000:.0f}k DPS, median)")
            return Measure(100 * mine_dps / top_dps, "gcsim",
                           f"{mine_dps / 1000:.0f}k vs {top_dps / 1000:.0f}k DPS for {' / '.join(sorted(top.names))}, standard gear, medians")

        pool = [s for s in self.sims_for(template, lead, standard=False) if self._others_standard(s, lead)]
        best = None
        for s in (p for p in pool if p.names == team):
            lb = s.member(lead)
            key = (lb.cons, lb.weapon, lb.refine)
            peers = [p for p in pool if p.names != team and (p.member(lead).cons, p.member(lead).weapon, p.member(lead).refine) == key]
            if not peers:
                continue
            top = max(peers + [s], key=lambda p: p.dps)
            ratio = 100 * s.dps / top.dps
            if best is None or ratio > best[0]:
                best = (ratio, s, top, lb)
        if best is None:
            return None
        ratio, s, top, lb = best
        if top is s:
            return Measure(100.0, "gcsim", f"the best lineup simulated with C{lb.cons} {lead} on R{lb.refine} {lb.weapon}")
        return Measure(ratio, "gcsim", f"{s.dps / 1000:.0f}k vs {top.dps / 1000:.0f}k DPS for {' / '.join(sorted(top.names))}, both with C{lb.cons} {lead}")

    def prydwen_fit(self, lineup: list[str], lead: str) -> Measure | None:
        for team in self.prydwen.get("characters", {}).get(lead, {}).get("teams", []):
            if {m["name"] for m in team["members"]} == set(lineup):
                return Measure(team["percent"], "prydwen", f"Prydwen lists it as '{team['name']}'")
        return None

    def lineup_fit(self, template: Template, lineup: list[str], lead: str, model_fit: float | None) -> Measure:
        m = self.measured_fit(template, lineup, lead) or self.prydwen_fit(lineup, lead)
        if m:
            return m
        if model_fit is None:
            return Measure(None, "none", "lineup includes characters the model has no tags for")
        coarse = is_coarse(template)
        how = "coarse archetype, so mostly its measured average" if coarse else f"raw model {model_fit:.0f}, calibrated"
        return Measure(self.calibration.apply(model_fit, template.id, coarse, lead), "model",
                       f"engine estimate with no simulated {lead or 'team'} lineup nearby ({how})", anchored=False)

    @staticmethod
    def _fits_core(team, name: str) -> bool:
        # The first slot is the archetype's carry slot; other core slots (a Hydro applicator) do not lead.
        core = [team.fills[0].slot] if team.fills and team.fills[0].slot.core else []
        if not core:
            return True
        member = next((f.member for f in team.fills if f.member.key == name), None)
        if member is None:
            return False
        return any((not slot.elements or member.element in slot.elements) and any(member.roles.get(r, 0) > 0 for r in slot.roles)
                   for slot in core)

    def damage_lead(self, team) -> str | None:
        """Whose damage the team is built around, from MEASURED behaviour: the lineup's own measured structure if
        it was simulated, otherwise one predicted from members' average damage shares. Teams without a single
        carry (reaction cores, drivers, distributed damage) return None and are judged as a whole."""
        from gtc.capabilities import load as load_caps, predict_structure

        st = self.measured_structure(frozenset(team.members))
        measured = st is not None
        if st is None:
            caps = load_caps()
            if caps and all(m in caps for m in team.members):
                st = predict_structure(team.members, caps)
        if st is not None:
            if st["type"] in ("hypercarry", "dual_carry", "driver") and st["owners"]:
                owner = st["owners"][0]
                # The damage owner leads only if the archetype would put them in its carry slot. Otherwise the
                # team is this archetype in name only (Ineffa topping damage next to Kazuha and Sucrose does not
                # make an Anemo carry team hers), and the archetype's own carry stays the lead.
                if self._fits_core(team, owner):
                    return owner
                return team.lead
            # Judged as a team without a single carry only when this exact lineup was simulated that way. A
            # PREDICTED carry-less structure is usually a team with no real damage dealer (Bennett / Aino /
            # Kazuha / Zhongli), which must not borrow the rating of the archetype's best reaction teams.
            return None if measured else team.lead
        best = None
        for f in team.fills:
            q = max((v for r, v in f.member.roles.items() if r.startswith("carry_")), default=0)
            if q >= 3 and (best is None or q > best[0]):
                best = (q, f.member.key)
        return best[1] if best else team.lead

    # ---------- Keqing Mains and Prydwen notes ----------
    def kqm_mentions(self, lineup: list[str]) -> list[str]:
        out, seen = [], set()
        for name in lineup:
            guide = self.kqm.get(name)
            if not guide:
                continue
            for t in guide["example_teams"]:
                slots = t["slots"]
                if len(slots) == len(lineup) and _matches(slots, lineup) and t["line"] not in seen:
                    seen.add(t["line"])
                    out.append(f"Keqing Mains lists {t['line']} as an example team in the {name} guide. {t['description']}")
        return out

    def execution_tags(self, name: str) -> list[str]:
        pt = self.prydwen_tier(name)
        return pt["tags"] if pt else []


def _matches(slots: list[list[str]], lineup: list[str]) -> bool:
    """Can each lineup member be assigned to a different slot whose options include them?"""
    def walk(i: int, used: set[int]) -> bool:
        if i == len(lineup):
            return True
        return any(j not in used and lineup[i] in slots[j] and walk(i + 1, used | {j}) for j in range(len(slots)))
    return walk(0, set())


def expert_level(tags: list[str]) -> int:
    """Prydwen's 'expert (-2)' tag: how many tiers the character drops without expert play."""
    for t in tags:
        if t.startswith("expert"):
            digits = "".join(ch for ch in t if ch.isdigit())
            return int(digits) if digits else 0
    return 0
