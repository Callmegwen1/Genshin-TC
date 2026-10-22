"""Application service (UI-1): the stable functions the website calls. The frontend never imports engine modules;
it talks to gtc/app/server.py, which calls only this module.

One AppService holds the account analysis and reuses it across screens:
  load()        snapshot, analysis, account-basis model, plan and candidates (synchronous, about 10 s)
  background    pull values for every unowned character, the whole-game meta plan, and support-allocation
                explanations (a thread; the engine lock is released between candidates so interactive calls
                interleave; `status()` reports progress)
Manual team evaluation reuses the loaded model and never reruns the account analysis.

Every number comes from the engine. Presentation choices (confidence badges, rounding) are documented where made.
"""
from __future__ import annotations

import threading
import time

from gtc.app import present

POWER_DECIMALS = 0  # powers are shown as whole numbers: sub-point differences are not meaningful
GAIN_DECIMALS = 1


def _r(x, d=1):
    return None if x is None else round(float(x), d)


def est(e, decimals: int = POWER_DECIMALS) -> dict | None:
    if e is None:
        return None
    return {"expected": _r(e.value, decimals), "sd": _r(e.sd, decimals), "tier": e.tier}


def confidence_badge(tier: str, status: str) -> str:
    """Presentation mapping (not a score): High for measured teams with clean evidence, Medium for well-supported
    interpolation, Low otherwise (far interpolation, unusual, provisional, rules-only or no number)."""
    if status == "well_supported" and tier in ("A", "B"):
        return "High"
    if status == "well_supported" and tier == "C":
        return "Medium"
    return "Low"


class AppService:
    def __init__(self):
        self.lock = threading.RLock()
        self.loaded = False
        self.progress = {"stage": "not loaded", "pulls_done": 0, "pulls_total": 0, "background_done": False}
        self.values: dict[str, object] = {}  # advisor pull values (plans over the advisor pool)
        self.raw_values: dict[str, object] = {}  # raw-model pull values (every candidate)
        self.blind: dict[str, str] = {}
        self.meta_plan = None
        self.allocation: list[dict] | None = None
        self.timings: dict[str, float] = {}

    # ---------- loading ----------
    def load(self, background: bool = True) -> None:
        from gtc import SNAPSHOT_DIR, gamedata, knowledge, profiles
        from gtc.account import AccountModel
        from gtc.report import analyze
        from gtc.review import Guides
        from gtc.snapshot import Snapshot, latest_snapshot

        with self.lock:
            t0 = time.perf_counter()
            self.progress["stage"] = "analysing account"
            self.snapshot = Snapshot.load(latest_snapshot(SNAPSHOT_DIR))
            self.kb = knowledge.load()
            self.an = analyze(self.snapshot, self.kb)
            self.am = AccountModel(self.an, self.kb, account_basis=True)
            self.roster = self.an.roster
            self.owned = {m.key for m in self.roster}
            self.chars = self.snapshot.by_key()
            self.game = gamedata.load_characters()
            self.progress["stage"] = "planning"
            self.raw_plan, self.cands = self.am.plan(self.roster)
            # Advisor layer (model 6.5, gtc/advisor.py): plans and recommendations use the advisor pool; the raw
            # model plan is kept for comparison. Team power is the same in both.
            from gtc.advisor import Advisor

            self.advisor = Advisor(self.an.evidence)
            ranked = sorted(self.cands, key=lambda a: (-a.potential, sorted(a.team.members)))
            self.adv_cands = self.advisor.admit(ranked)
            self.plan = self.am.best_plan(self.adv_cands)
            element_of = {k: v.get("element") for k, v in self.game.items()}
            self.modes = profiles.all_plans(self.adv_cands, element_of)
            self.guides = Guides(self.an.evidence, gamedata.names(), {c.key: c.element for c in self.snapshot.characters})
            self.weapons, self.weapon_types = self.snapshot.all_weapons(), gamedata.load_weapons()
            self.timings["load"] = round(time.perf_counter() - t0, 1)
            self.loaded = True
            self.progress["stage"] = "ready (pull values computing)"
        if background:
            threading.Thread(target=self._background, daemon=True).start()

    def _background(self) -> None:
        from gtc.account import AccountModel, partner_notes, weapon_note

        t0 = time.perf_counter()
        names = sorted(n for n in self.am.universe if n not in self.owned)
        self.progress["pulls_total"] = len(names)
        for name in names:
            with self.lock:
                info = self.kb.characters.get(name)
                if info and "carry_unsimulated" in info.roles and not any(
                        r.startswith(("carry_", "support_")) and r != "carry_unsimulated" for r in info.roles):
                    self.blind[name] = "no simulations and no kit yet"
                else:
                    v = self.am.value_of(name, self.roster, self.plan, self.adv_cands, admit=self.advisor.admit)
                    raw = self.am.value_of(name, self.roster, self.raw_plan, self.cands)
                    if raw is not None:
                        self.raw_values[name] = raw
                    if v is None and raw is not None:
                        self.blind[name] = "no recommendable team on this account (only experimental lineups score)"
                    elif v is None:
                        self.blind[name] = ("provisional kit, but no team on this account is close enough to its listed teams"
                                            if info and info.provisional else "no team on this account can be evaluated")
                    else:
                        v.weapon_note = weapon_note(name, self.guides, self.weapons, self.weapon_types, self.am.game,
                                                    self.snapshot.data_level)
                        v.explanation += partner_notes(name, self.owned, self.an.evidence.prydwen)
                        self.values[name] = v
            self.progress["pulls_done"] += 1
        self.timings["pulls"] = round(time.perf_counter() - t0, 1)
        t1 = time.perf_counter()
        with self.lock:
            self.progress["stage"] = "support allocation"
            self.allocation = present.allocation_explanations(self.am, self.plan, self.adv_cands, self.roster)
        self.timings["allocation"] = round(time.perf_counter() - t1, 1)
        t2 = time.perf_counter()
        with self.lock:
            self.progress["stage"] = "meta comparison"
            self.meta_plan, _ = AccountModel(self.an, self.kb).plan(list(self.am.universe.values()))
        self.timings["meta_plan"] = round(time.perf_counter() - t2, 1)
        self.progress["stage"] = "ready"
        self.progress["background_done"] = True

    def status(self) -> dict:
        return {"loaded": self.loaded, **self.progress, "timings": self.timings}

    # ---------- shared serialisation ----------
    def _team(self, a, full: bool = False) -> dict | None:
        if a is None:
            return None
        e = a.evaluation
        p = e.power.get("single_target") if e else None
        b = p.basis if p else None
        v = (e.validity or {}) if e else {}
        status = v.get("support", "unusual")
        if b is not None and "provisional" in b.flags:
            status = "provisional"
        acc = a.account or {}
        ceil = acc.get("ceiling") or a.estimate
        st_e, aoe_e = a.power.get("single_target"), a.power.get("aoe")
        ratio = (aoe_e.value / st_e.value) if st_e is not None and aoe_e is not None and st_e.value else None
        ident = (e.identity or {}) if e else {}
        stc = (e.structure or {}) if e else {}
        out = {
            "lineup": list(a.team.members),
            "status": status, "status_reasons": v.get("support_reasons", []),
            "meta": est(acc.get("meta") or a.estimate), "current": est(acc.get("current")), "ceiling": est(ceil),
            "sd_parts": acc.get("sd_parts"),
            "evidence": {"tier": b.tier if b else None, "state": b.evidence_state if b else None, "route": b.route if b else None,
                         "quality": (b.quality or None) if b else None, "quality_reasons": list(b.quality_reasons) if b else [],
                         "coverage": (e.coverage or {}).get("status") if e else None,
                         "badge": confidence_badge(b.tier if b else "F", status)},
            "identity": {"label": a.label, "primary_actor": ident.get("primary_actor"), "structure": ident.get("structure"),
                         "mechanics": {k: _r(x, 2) for k, x in (ident.get("systems") or {}).items()},
                         "central": ident.get("central") or [], "source": ident.get("source")},
            "structure": {k: _r(x, 2) for k, x in (stc.get("probabilities") or {}).items()},
            "damage_shares": {k: _r(x, 2) for k, x in (stc.get("damage_shares") or {}).items()},
            "sustain": a.power.get("sustain"),
            "context": {"single_target": est(ceil), "aoe": est(_scale(ceil, ratio)) if ratio else None, "aoe_ratio": _r(ratio, 2)},
            "unknown_constellations": acc.get("unknown_constellations") or [],
            "recommendability": {k: v for k, v in self.advisor.rec(a).items() if k != "signals"},
        }
        from gtc.advisor import core_key

        out["core"] = core_key(a)
        if full:
            out.update(present.team_insights(a, self.an.investments, self.chars))
            out["mechanics"] = present.team_mechanics(a)
        return out

    def _plan(self, plan) -> dict:
        teams = sorted(plan.teams, key=lambda t: (-t.potential, sorted(t.team.members)))
        return {"teams": [self._team(t) for t in teams], "value": _r(plan.value), "expected_power": _r(plan.power)}

    # ---------- account ----------
    def get_account(self) -> dict:
        s = self.snapshot
        return {"source": s.source, "taken_at": s.taken_at, "data_level": s.data_level,
                "owned": len(self.owned), "catalog": len(self.game),
                "plan": self._plan(self.plan)}

    def get_characters(self) -> list[dict]:
        out = []
        for name, g in sorted(self.game.items()):
            c = self.chars.get(name)
            inv = self.an.investments.get(name)
            info = self.kb.characters.get(name)
            out.append({"name": name, "element": g.get("element"), "rarity": g.get("rarity"), "weapon_type": g.get("weapon"),
                        "owned": c is not None, "constellation": c.constellation if c else None,
                        "level": c.level if c else None, "investment": _r(inv.total, 2) if inv else None,
                        "provisional": bool(info and info.provisional),
                        "in_plan": any(name in t.team.members for t in self.plan.teams)})
        return out

    def get_character(self, name: str) -> dict:
        from gtc import account_power

        g = self.game.get(name)
        if g is None:
            raise KeyError(name)
        c = self.chars.get(name)
        out = {"name": name, "element": g.get("element"), "rarity": g.get("rarity"), "weapon_type": g.get("weapon"),
               "owned": c is not None}
        teams = sorted((a for a in self.adv_cands if name in a.team.members), key=lambda a: -a.potential)[:5]
        out["best_teams"] = [self._team(a) for a in teams]
        if c is None:
            v = self.values.get(name)
            out["pull"] = self._pull_card(v) if v else ({"unavailable": self.blind.get(name)} if name in self.blind else None)
            return out
        inv = self.an.investments.get(name)
        f_own, f_buff = account_power.character_factor(inv, None, name) if inv else (None, None)
        problems = []
        if c.level < 90:
            problems.append(f"Level {c.level} of 90.")
        eff = c.talents.effective
        problems += [f"{k.capitalize()} talent {eff[k]}." for k in ("skill", "burst") if eff[k] < 8]
        if c.weapon.level < 90:
            problems.append(f"{c.weapon.name} is level {c.weapon.level}.")
        if len(c.artifacts) < 5:
            problems.append(f"{len(c.artifacts)} of 5 artifacts equipped.")
        out.update({
            "constellation": c.constellation, "level": c.level,
            "talents": {"normal": c.talents.normal, "skill": c.talents.skill, "burst": c.talents.burst, "effective": eff},
            "weapon": {"name": c.weapon.name, "rarity": c.weapon.rarity, "level": c.weapon.level, "refinement": c.weapon.refinement},
            "artifacts": [{"slot": a.slot_name, "set": a.set_name, "rarity": a.rarity, "level": a.level, "main": a.main_stat,
                           "main_value": _r(a.main_value, 3), "substats": [{"key": s.get("key"), "value": _r(s.get("value"), 3)} for s in a.substats]}
                          for a in c.artifacts],
            "stats": {k: _r(v, 3) for k, v in (c.stats or {}).items()},
            "investment": {k: _r(getattr(inv, k), 2) for k in ("level", "talents", "weapon", "artifacts", "total")} if inv else None,
            # the calibrated build factor (gtc/account_power.py): this character's own damage now, relative to the
            # community-standard build
            "build_factor": _r(f_own, 2),
            "build_problems": problems,
        })
        return out

    # ---------- team builder ----------
    def evaluate_team(self, lineup: list[str], substitutions: bool = True) -> dict:
        t0 = time.perf_counter()
        with self.lock:
            r = self.am.assess_lineup(list(lineup), self.roster)
            out = {"lineup": list(lineup), "legal": r["status"] != "invalid", "reasons": r["reasons"]}
            if r["assessment"] is None:
                return out
            out["team"] = self._team(r["assessment"], full=True)
            out["not_owned"] = [n for n in lineup if n not in self.owned]
            if substitutions and not out["not_owned"]:
                out["substitutions"] = present.substitutions(self.am, list(lineup), self.roster, self.plan, self.advisor)
        out["elapsed_s"] = round(time.perf_counter() - t0, 2)
        return out

    # ---------- recommended teams ----------
    def recommended_teams(self, n: int = 16, variants: int = 3, experimental: int = 6) -> dict:
        """Overlap allowed: the best recommendable team per core (primary actor or reaction core), strongest first,
        with a few variants of each; then the strongest lineups the advisor does not recommend, kept visible."""
        from gtc.advisor import core_key

        clusters: dict[str, list] = {}
        for a in self.adv_cands:
            clusters.setdefault(core_key(a), []).append(a)
        rows = sorted(clusters.items(), key=lambda kv: -kv[1][0].potential)[:n]
        teams = []
        for key, members in rows:
            card = self._team(members[0], full=True)
            card["variants"] = [self._team(v) for v in members[1:1 + variants]]
            why = self.advisor.admitted_reason(members[0], self.cands)
            if why:
                card["admitted_because"] = why
            teams.append(card)
        admitted = {frozenset(a.team.members) for a in self.adv_cands}
        others = [a for a in sorted(self.cands, key=lambda a: -a.potential) if frozenset(a.team.members) not in admitted][:experimental]
        return {"overlap": True, "teams": teams, "not_recommended": [self._team(a) for a in others]}

    def recommended_plan(self) -> dict:
        """Overlap off: the account plan (no character twice), why units sit where they do, close calls, modes."""
        from gtc.account import near_alternatives

        with self.lock:
            plan = self._plan(self.plan)
            for t, a in zip(plan["teams"], sorted(self.plan.teams, key=lambda t: (-t.potential, sorted(t.team.members)))):
                t.update(present.team_insights(a, self.an.investments, self.chars))
            ties = [{"team": t.team.members, "out": o, "in": i, "alternative": alt.team.members,
                     "probability_plan_better": _r(p, 2)} for t, alt, o, i, p in near_alternatives(self.plan, self.adv_cands)]
            modes = {k: {"teams": [list(a.team.members) for a in m.teams], "score": _r(m.score), "note": m.note,
                         "frontier": [{"values": [f[0], f[1]], "teams": f[2]} for f in (m.frontier or [])],
                         "core": m.core} for k, m in self.modes.items()}
        from gtc.account import gain_estimate

        raw = None
        if {frozenset(t.team.members) for t in self.raw_plan.teams} != {frozenset(t.team.members) for t in self.plan.teams}:
            g = gain_estimate(self.raw_plan, self.plan)
            raw = {"teams": self._plan(self.raw_plan)["teams"], "difference": est(g, GAIN_DECIMALS),
                   "note": "The raw model's best plan uses teams the advisor does not recommend."}
        plan.update({"overlap": False, "ties": ties, "modes": modes, "raw_model_plan": raw,
                     "allocation": self.allocation, "allocation_ready": self.allocation is not None})
        return plan

    # ---------- pulls ----------
    def _pull_card(self, v) -> dict:
        card = self._pull_card_core(v)
        card["gain_source"] = [c["text"] for c in present.plan_changes(self.plan, v.plan) if c["changed"]] or ["No plan team changes."]
        raw = self.raw_values.get(v.name)
        if raw is not None and raw.team is not None and v.team is not None and \
                frozenset(raw.team.team.members) != frozenset(v.team.team.members):
            if self.advisor.level(raw.team) not in ("established", "credible"):
                card["experimental_lineup"] = {"team": self._team(raw.team), "raw_gain": est(raw.estimate, GAIN_DECIMALS),
                                               "note": "Higher modeled experimental lineup: the raw model rates it higher, "
                                                       "but it is not a recommendable team."}
        return card

    def _pull_card_core(self, v) -> dict:
        e = v.estimate
        flags = v.team.evaluation.power["single_target"].basis.flags if v.team is not None and v.team.evaluation else ()
        return {"character": v.name, "gain": est(e, GAIN_DECIMALS), "plan_gain": _r(v.gain),
                "probability_positive": _r(v.confidence, 2), "statistical_probability": _r(v.statistical_confidence, 2),
                "kind": v.kind, "coverage": v.coverage, "provisional": "provisional" in flags,
                "best_team": self._team(v.team), "decomposition": v.decomposition,
                "explanation": v.explanation, "weapon_note": v.weapon_note, **present.pull_pros_cons(v)}

    def recommended_pulls(self) -> dict:
        from gtc.account import COMPETITIVE, LOWER, pull_groups

        values = sorted(self.values.values(), key=lambda v: (-v.gain, v.name))
        cards = {v.name: self._pull_card(v) for v in values}
        # A pull that does not change the plan has no value; it is never "competitive" just because an unknown
        # mechanics coverage keeps compare() from ruling it out.
        evidence = [v for v in values if not cards[v.name]["provisional"] and v.kind != "no change"]
        groups = pull_groups(evidence)
        out = {"Clear recommendation": [], "Competitive / roughly equal": [], "Lower-value": [],
               "Provisional / insufficient evidence": []}
        for v in values:
            if cards[v.name]["provisional"]:
                out["Provisional / insufficient evidence"].append(cards[v.name])
            else:
                g = groups.get(v.name, LOWER)
                if v.kind == "no change":
                    cards[v.name]["no_change"] = True
                out[g].append(cards[v.name])
        out["Provisional / insufficient evidence"] += [{"character": n, "unavailable": why} for n, why in sorted(self.blind.items())
                                                      if self.kb.characters.get(n) and self.kb.characters[n].provisional]
        return {"groups": out, "complete": self.progress["background_done"] or self.progress["pulls_done"] >= self.progress["pulls_total"],
                "progress": [self.progress["pulls_done"], self.progress["pulls_total"]],
                "competitive_note": "Candidates in the same group cannot be separated by the evidence; their order is not a ranking."
                if out[COMPETITIVE] else None}

    def what_if(self, name: str) -> dict:
        from gtc.account import pull_groups

        if name in self.owned:
            return {"character": name, "owned": True}
        t0 = time.perf_counter()
        with self.lock:
            v = self.values.get(name)
            if v is None and name not in self.blind:
                v = self.am.value_of(name, self.roster, self.plan, self.adv_cands, admit=self.advisor.admit)
                raw = self.am.value_of(name, self.roster, self.raw_plan, self.cands)
                if raw is not None:
                    self.raw_values[name] = raw
                if v is not None:
                    self.values[name] = v
        if v is None:
            return {"character": name, "unavailable": self.blind.get(name, "cannot be evaluated on this account")}
        before = {frozenset(t.team.members) for t in self.plan.teams}
        after = {frozenset(t.team.members) for t in v.plan.teams}
        group = None
        if self.progress["background_done"]:
            vals = sorted(self.values.values(), key=lambda x: (-x.gain, x.name))
            group = pull_groups(vals).get(name)
        card = self._pull_card(v)
        d = v.decomposition
        return {
            **card, "group": group, "plan_before": self._plan(self.plan), "plan_after": self._plan(v.plan),
            "teams_added": [sorted(t) for t in after - before], "teams_removed": [sorted(t) for t in before - after],
            "best_team_gain": d.get("best_team_gain"), "second_team_gain": d.get("second_team_gain"),
            "new_mechanics": d.get("new_mechanics"), "new_viable_teams": d.get("new_viable_teams"),
            "improved": d.get("improved"), "displaced": d.get("displaced"), "support_contention": d.get("support_contention"),
            "redundancy": d.get("redundancy"), "plan_changes": present.plan_changes(self.plan, v.plan),
            "elapsed_s": round(time.perf_counter() - t0, 2),
        }

    # ---------- dashboard ----------
    def dashboard(self) -> dict:
        from gtc.account import PLAN_WEIGHTS

        with self.lock:
            strongest = max(self.adv_cands, key=lambda a: (((a.account or {}).get("current") or a.estimate).value, -len(a.team.members)))
            abyss = self.modes.get("abyss")
            # highest-impact build improvement: the plan team with the largest weighted gap between ceiling and
            # current power, and its least-invested member
            best = None
            for w, t in zip(PLAN_WEIGHTS, sorted(self.plan.teams, key=lambda t: -t.potential)):
                acc = t.account or {}
                if acc.get("current") and acc.get("ceiling"):
                    gap = w * (acc["ceiling"].value - acc["current"].value)
                    weakest = min(t.team.members, key=lambda m: self.an.investments[m].total if m in self.an.investments else 1.0)
                    if best is None or gap > best["weighted_gap"]:
                        best = {"team": list(t.team.members), "current": _r(acc["current"].value, 0), "ceiling": _r(acc["ceiling"].value, 0),
                                "weighted_gap": _r(gap), "member": weakest,
                                "member_investment": _r(self.an.investments[weakest].total, 2) if weakest in self.an.investments else None}
            warnings = []
            for t in self.plan.teams:
                card = self._team(t)
                if card["status"] in ("provisional", "unusual") or card["evidence"]["quality"] in ("mixed", "poor"):
                    warnings.append({"team": card["lineup"], "status": card["status"], "badge": card["evidence"]["badge"],
                                     "reasons": card["status_reasons"] or card["evidence"]["quality_reasons"]})
        pulls = self.recommended_pulls() if self.values else None
        top = None
        if pulls:
            for g in ("Clear recommendation", "Competitive / roughly equal"):
                if pulls["groups"][g]:
                    top = {"group": g, "characters": [c["character"] for c in pulls["groups"][g]][:6]}
                    break
        meta = None
        if self.meta_plan is not None and self.meta_plan.power:
            meta = {"ratio": _r(self.plan.power / self.meta_plan.power, 2),
                    "meta_teams": [list(t.team.members) for t in sorted(self.meta_plan.teams, key=lambda t: -t.potential)[:2]]}
        return {
            "account": {"owned": len(self.owned), "data_level": self.snapshot.data_level, "taken_at": self.snapshot.taken_at},
            "strongest_current_team": self._team(strongest),
            "abyss": {"teams": [list(a.team.members) for a in abyss.teams], "note": abyss.note} if abyss else None,
            "plan": self._plan(self.plan), "against_meta": meta,
            "build_improvement": best, "pulls": top, "pulls_complete": bool(pulls and pulls["complete"]),
            "warnings": warnings,
        }


def _scale(e, ratio):
    if e is None or ratio is None:
        return None
    from gtc.estimate import Estimate

    return Estimate(e.value * ratio, e.sd * ratio, e.tier)


_SERVICE: AppService | None = None


def service() -> AppService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = AppService()
    return _SERVICE
