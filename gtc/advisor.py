"""Advisor layer (model 6.5): is a team something to recommend? Separate from validity (can it work) and power (what
the evidence estimates). Recommendability never changes power.

    established   a recognised composition with strong evidence: its own community simulations by independent
                  submitters who agree, or a team a guide lists exactly, with nothing unusual about it
    credible      evidence-backed and coherent, not necessarily canonical: its own simulations, or the pair model
                  next to a simulated lineup with no typicality finding, mechanics coverage not unknown, and no
                  mechanical harm (partial coverage and buffs that reach nobody are cautions, not demotions)
    experimental  evaluable, but niche or weakly supported: far interpolation, an unusual composition, a mechanic the
                  data never covered, poor community data, a provisional kit not listed, or a mechanical problem the
                  evidence does not answer (gtc/team_mechanics.py): a broken `only` kit condition always; two
                  on-field damage dealers competing for field time, an element removing the auras a central mechanic
                  needs, or a `count` condition below full (an opportunity loss), unless this exact team was
                  simulated (the simulation shows it works)
    unsupported   no simulation-based number at all (role rules or none)

Off-meta is not a signal; neither is popularity. Pair-level guide evidence ("Prydwen pairs Ayaka with Escoffier")
is never full-team proof: only an exactly listed lineup counts.

Advisor pool (`admit`): established and credible teams; an experimental team only when its core (primary actor, or
its central mechanics' owners) has no credible team on the account, or when compare() says it is better than the
best credible team of that core; never an unsupported team, and never a team with mechanical harm the evidence does
not answer (field-time competition, aura removal, a broken `only` condition: Raiden + Razor is not advice on
modelled power alone).

Team functions (`substitution_kind`): a one-character swap is a direct substitution only when it keeps what the
team depends on, read from the kits (gtc/team_mechanics.py): the carry, the elements its central mechanics need,
every critical function only the leaving member supplied (on-field damage, central-element application, swirl
support, sustain), no new mechanical harm (field-time competition, aura removal, a broken condition) and every kit
condition. Otherwise it is a rebuild (a different credible team) or experimental (not advice).
"""
from __future__ import annotations

from gtc.decision import compare

LEVELS = ("established", "credible", "experimental", "unsupported")


def listed_exactly(lineup, ev) -> bool:
    """A guide lists exactly this lineup (any character's Prydwen page)."""
    key = frozenset(lineup)
    cache = ev.__dict__.setdefault("_listed_lineups", None)
    if cache is None:
        cache = {frozenset(m["name"] for m in t["members"]) for c in ev.prydwen.get("characters", {}).values()
                 for t in c.get("teams", []) if t.get("members")}
        ev.__dict__["_listed_lineups"] = cache
    return key in cache


def recommendability(a, ev) -> dict:
    """{"level", "reasons", "signals"} for an Assessment. Reads evidence the engine already computed and the team's
    mechanics (gtc/team_mechanics.py)."""
    from gtc.team_mechanics import analyse

    e = a.evaluation if a is not None else None
    if e is None or "single_target" not in e.power:
        return {"level": "unsupported", "reasons": ["no evaluation"], "signals": {}}
    b = e.power["single_target"].basis
    lineup = list(a.team.members)
    lv = getattr(ev, "lineup_values", {}).get(frozenset(lineup))
    typ = list((e.validity or {}).get("typicality") or [])
    cov = (e.coverage or {}).get("status", "complete")
    listed = listed_exactly(lineup, ev)
    provisional = "provisional" in b.flags
    exact = b.route in ("exact_personal", "exact_community")
    ident = e.identity or {}
    tm = analyse(lineup, central=ident.get("central"))
    unmet = [f"{c['member']}: {c['text']}" for c in tm.conditions_failed if c["severity"] == "harm"]
    partial = [o["text"] for o in tm.opportunity_losses if o["kind"] == "partial_condition"]
    harm = [c for c in tm.harms() if c["kind"] in ("field_time", "aura")]
    signals = {"route": b.route, "tier": b.tier, "evidence_state": b.evidence_state, "quality": b.quality or None,
               "submitters": lv.n_submitters if lv else 0, "guide_listed": listed, "typicality": typ, "coverage": cov,
               "unmet_conditions": unmet, "partial_conditions": partial, "provisional": provisional,
               "mechanics": {"conflicts": [{"kind": c["kind"], "severity": c["severity"], "text": c["text"]} for c in tm.conflicts],
                             "opportunity_losses": [o["text"] for o in tm.opportunity_losses],
                             "missing": tm.missing_functions, "kits_reviewed": tm.kit_coverage["reviewed"]},
               "structure_confidence": round(float(ident.get("primary_probability") or ident.get("carry_probability") or 0), 2)}
    if b.route in ("none", "role_rules") or b.tier == "F":
        return {"level": "unsupported", "reasons": ["no simulation or interpolation behind the number"], "signals": signals}
    weak = []
    if provisional and not listed:
        weak.append("a member has only a provisional kit, and no guide lists this exact team")
    if b.tier == "D":
        weak.append("interpolated far from any simulated team")
    weak += [f.split(": ", 1)[-1] for f in typ]
    cautions = []
    if not exact and cov == "unknown":
        weak.append("relies on a mechanic the data never covered with this damage dealer (coverage unknown)")
    elif not exact and cov == "partial":
        # partial coverage caps confidence at 80% (gtc/coverage.py) and is common among ordinary interpolations: a
        # caution shown with the team, not a reason to stop recommending it on its own
        cautions.append("a pairing the data never saw alongside one of this team's elements (mechanics coverage partial)")
    weak += [f"kit condition unmet: {u}" for u in unmet]
    for c in harm:
        if exact:
            cautions.append(f"{c['text']}; this exact team's simulations show it can work")
        else:
            weak.append(f"{c['text']} (no simulation of this exact team shows the rotation works)")
    for p in partial:
        # an opportunity loss, not harm: the support still works, below full strength. The pair model discounts it
        # with one coefficient per support, so without this exact team's simulations it still keeps the team out of
        # the credible set
        if exact:
            cautions.append(f"kit condition partly met (opportunity loss): {p}")
        else:
            weak.append(f"kit condition unmet in full (opportunity loss): {p}")
    cautions += [c["text"] for c in tm.conflicts if c["severity"] == "caution"]
    if b.quality == "poor":
        weak.append("community simulations of poor quality: " + "; ".join(b.quality_reasons))
    signals["mechanical_harm"] = bool(unmet or (harm and not exact))
    if weak:
        return {"level": "experimental", "reasons": weak + cautions, "signals": signals}
    if exact and (b.quality == "good" or listed):
        why = "independent submitters agree" if b.quality == "good" else "a guide lists this exact team"
        return {"level": "established", "reasons": [f"simulated, and {why}"] + cautions, "signals": signals}
    if exact:
        return {"level": "credible", "reasons": [f"its own community simulations ({b.quality or 'unconfirmed'})"] + cautions, "signals": signals}
    if provisional:
        return {"level": "credible", "reasons": ["provisional kit, but a guide lists this exact team"] + cautions, "signals": signals}
    return {"level": "credible", "reasons": ["interpolated next to a simulated team"] + cautions, "signals": signals}


def core_key(a) -> str:
    """What a team is built around, for clustering near-duplicates: its primary actor, else the owners of its
    central mechanics, else its label."""
    ident = (a.evaluation.identity or {}) if a.evaluation else {}
    if ident.get("primary_actor"):
        return ident["primary_actor"]
    owners = sorted({o for k in ident.get("central") or [] for o in (ident.get("owners") or {}).get(k, [])})
    if not owners:
        owners = sorted(((a.evaluation.structure or {}).get("owners") or []) if a.evaluation else [])
    return " + ".join(owners) if owners else " / ".join(sorted(a.team.members))


class Advisor:
    """Caches recommendability per lineup and applies the advisor pool."""

    def __init__(self, ev):
        self.ev = ev
        self._rec: dict[frozenset, dict] = {}

    def rec(self, a) -> dict:
        k = frozenset(a.team.members)
        if k not in self._rec:
            self._rec[k] = recommendability(a, self.ev)
        return self._rec[k]

    def level(self, a) -> str:
        return self.rec(a)["level"]

    def harmful(self, a) -> bool:
        """Mechanical harm the evidence does not answer (never admitted on modelled power alone)."""
        return bool(self.rec(a)["signals"].get("mechanical_harm"))

    def admit(self, cands: list) -> list:
        """The advisor pool among these candidates (see the module docstring). Order is kept."""
        best_credible: dict[str, object] = {}
        for a in cands:
            if self.level(a) in ("established", "credible") and a.estimate is not None:
                k = core_key(a)
                if k not in best_credible or a.potential > best_credible[k].potential:
                    best_credible[k] = a
        out = []
        for a in cands:
            lvl = self.level(a)
            if lvl in ("established", "credible"):
                out.append(a)
            elif lvl == "experimental" and a.estimate is not None and not self.harmful(a):
                ref = best_credible.get(core_key(a))
                if ref is None or compare(a.estimate, ref.estimate)["comparison"] == "better":
                    out.append(a)
        return out

    def admitted_reason(self, a, cands: list) -> str | None:
        """Why an experimental team is in the advisor pool (None when it is not experimental)."""
        if self.level(a) != "experimental":
            return None
        ref = [c for c in cands if core_key(c) == core_key(a) and self.level(c) in ("established", "credible")]
        if not ref:
            return f"no credible {core_key(a)} team on this account"
        return "beats the best credible team of its core by more than the uncertainty"


def substitution_kind(base, alt, out_name: str, in_name: str, advisor: Advisor) -> tuple[str, list[str]]:
    """("direct" | "rebuild" | "experimental", reasons) for replacing out_name by in_name in `base` (Assessments)."""
    from gtc.kit_conditions import unmet
    from gtc.reactions import mechanic_elements, mechanic_name
    from gtc.team_mechanics import analyse, critical_functions

    def element(m):
        from gtc.kit_conditions import _element

        return _element(m)

    lost = []
    ident = (base.evaluation.identity or {}) if base.evaluation else {}
    if ident.get("primary_actor") == out_name:
        lost.append(f"{out_name} is the team's main damage dealer")
    new = [m for m in base.team.members if m != out_name] + [in_name]
    have = {element(m) for m in new}
    gone = set()
    for k in ident.get("central") or []:
        need = [x for x in mechanic_elements(k) if x not in have]
        gone |= set(need)
        if need:
            lost.append(f"{mechanic_name(k)} needs {' and '.join(need)}, which {in_name} does not bring")
    central = ident.get("central") or None
    before, after = analyse(base.team.members, central=central), analyse(new, central=central)
    for f in critical_functions(before, out_name):
        if f not in after.supplied_functions and f.split()[0] not in gone and not (
                f == "on-field damage" and ident.get("primary_actor") == out_name):
            lost.append(f"{out_name} is the team's only source of {f}, and {in_name} does not provide it")
    old = before.conflict_keys()
    for c in after.harms():
        if c["key"] not in old and c["kind"] != "condition":
            lost.append(c["text"])
    for n in set(unmet(new)) - set(unmet(base.team.members)):
        lost.append(f"{n}'s kit condition is no longer met")
    lvl = advisor.level(alt)
    if not lost and lvl in ("established", "credible"):
        return "direct", []
    if lvl in ("established", "credible"):
        return "rebuild", lost
    return "experimental", lost + [f"the resulting team is {lvl}"]
