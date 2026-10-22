"""The theorycraft calculator: what happens to a team's damage when one member is replaced.

How a theorycrafter reasons, and how this code does it:
  1. Start from a measured team (a gcsim damage profile).
  2. Collect every buff and shred in the team from the kits: who gives what, to whom, under which
     conditions (Ascendant Gleam, Hexerei, constellations, set holders).
  3. For each damage source, compute its multiplier with the old team's effects and with the new
     team's effects, using the game formulas. The source scales by the ratio.
  4. Remove the leaving member's own damage. Add the newcomer's: measured in another gcsim team
     with the same carry when it exists, otherwise computed from their kit's hits.
  5. Check the team still works: a Lunar enabler, Hydro and Electro application.

What it does not model: rotation changes, energy, and how each buff's uptime shifts with a new
rotation. Those are why gcsim exists; this gives a fast, explainable first answer.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from gtc import KNOWLEDGE_DIR
from gtc.tc import formulas as F
from gtc.tc.profile import Profile, Source, Unit

LUNAR_KINDS = ("lunar_charged_direct", "lunar_charged_reaction")
SWIRLABLE = ("Pyro", "Hydro", "Electro", "Cryo")


def load_kits(generated: bool = True) -> dict:
    """Hand-written kits (kits.yaml, kits_custom/) over generated ones (generated/kits_auto.yaml, from gcsim
    logs): a hand-written character replaces their generated entry as a whole."""
    kits = yaml.safe_load((KNOWLEDGE_DIR / "kits.yaml").read_text(encoding="utf-8")) or {}
    auto = KNOWLEDGE_DIR / "generated" / "kits_auto.yaml"
    if generated and auto.exists():
        for name, kit in (yaml.safe_load(auto.read_text(encoding="utf-8")) or {}).items():
            kits.setdefault(name, kit)
    custom = KNOWLEDGE_DIR / "kits_custom"
    if custom.exists():
        for path in sorted(custom.glob("*.yaml")):
            if not path.name.startswith("_"):  # _TEMPLATE.yaml and other drafts are skipped
                kits.update(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
    return kits


@dataclass
class Effect:
    caster: str
    kind: str
    target: str
    value: float
    stat: str | None = None
    element: str | None = None
    applies_to: tuple[str, ...] | None = None
    note: str = ""
    key: str = ""  # identical keys do not stack (two holders of the same set)


def _value(spec, caster: Unit) -> float:
    if isinstance(spec, (int, float)):
        return float(spec)
    stat = caster.stats.get(spec["of"], 0.0)
    v = stat / spec.get("per", 1) * spec["rate"]
    return min(v, spec["cap"]) if "cap" in spec else v


class Theory:
    def __init__(self, kits: dict, beyond_gcsim: bool = True):
        self.kits = kits
        self.beyond_gcsim = beyond_gcsim

    # ---------- team state ----------
    def counts(self, units: dict[str, Unit]) -> dict[str, int]:
        return {
            "moonsign": sum((self.kits.get(n) or {}).get("moonsign", 0) for n in units),
            "hexerei": sum(1 for n in units if (self.kits.get(n) or {}).get("hexerei")),
        }

    def effects(self, units: dict[str, Unit], lead: str) -> list[Effect]:
        counts = self.counts(units)
        out: list[Effect] = []

        def allowed(spec, caster: Unit) -> bool:
            when = spec.get("when") or {}
            if counts["moonsign"] < when.get("moonsign_at_least", 0) or counts["hexerei"] < when.get("hexerei_at_least", 0):
                return False
            return caster.cons >= spec.get("constellation", 0)

        def add(spec, caster: Unit, key: str):
            if not allowed(spec, caster):
                return
            v = _value(spec["value"], caster) * spec.get("uptime", 1.0)
            out.append(Effect(caster.name, spec["kind"], spec.get("target", "party"), v, spec.get("stat"), spec.get("element"),
                              tuple(spec["applies_to"]) if spec.get("applies_to") else None, spec.get("note", ""), key))

        for name, u in units.items():
            for i, spec in enumerate((self.kits.get(name) or {}).get("effects", [])):
                add(spec, u, f"{name}:{i}")
            for set_name, pieces in u.sets.items():
                if pieces >= 4:
                    for i, spec in enumerate((self.kits.get("_sets") or {}).get(set_name, [])):
                        add(spec, u, f"set:{set_name}:{i}")

        rule = ((self.kits.get("_rules") or {}).get("ascendant_gleam_non_moonsign") or {})
        if rule and counts["moonsign"] >= 2 and (self.beyond_gcsim or rule.get("in_gcsim")):
            best, who = 0.0, None
            for name, u in units.items():
                if (self.kits.get(name) or {}).get("moonsign"):
                    continue
                spec = (rule.get("per_element") or {}).get(u.element)
                if spec:
                    v = min(_value(spec, u), rule.get("cap", 1.0))
                    if v > best:
                        best, who = v, name
            if who:
                out.append(Effect(who, "react_bonus", "party", best, applies_to=LUNAR_KINDS,
                                  note="Ascendant Gleam buff from a non-Moonsign member (Prydwen; not in gcsim)", key="rule:ag"))

        # Identical effects (same set held twice) do not stack.
        seen, unique = set(), []
        for e in out:
            k = e.key if e.key.startswith("set:") else f"{e.key}"
            k = k.split(":", 1)[1] if k.startswith("set:") else k
            if k in seen:
                continue
            seen.add(k)
            unique.append(e)
        return unique

    @staticmethod
    def _targets(e: Effect, owner: str, lead: str) -> bool:
        return (e.target == "party" or (e.target == "self" and owner == e.caster)
                or (e.target == "active" and owner == lead) or (e.target == "others" and owner != e.caster))

    def multiplier(self, src_kind: str, element: str, owner: Unit, lead: str, effects: list[Effect],
                   team_elements: set[str], scaling: str = "atk") -> float:
        s = dict(owner.stats)
        react, base, extra = 0.0, 0.0, 0.0
        res = {el: F.ENEMY_RES for el in F_ELEMENTS}
        for e in effects:
            if e.kind == "res_shred":
                els = [el for el in SWIRLABLE if el in team_elements] if e.element == "swirled" else (F_ELEMENTS if e.element == "all" else [e.element])
                for el in els:
                    res[el] -= e.value
                continue
            if e.kind == "extra_hit":
                extra += e.value
                continue
            if not self._targets(e, owner.name, lead):
                continue
            if e.applies_to and src_kind not in e.applies_to:
                continue
            if e.kind == "stat":
                if e.stat in ("atk_pct", "hp_pct", "def_pct"):
                    stat = e.stat[:-4]
                    s[stat] = s.get(stat, 0) + owner.stats.get(f"base_{stat}", 0) * e.value
                else:
                    s[e.stat] = s.get(e.stat, 0) + e.value
            elif e.kind == "react_bonus":
                react += e.value
            elif e.kind == "base_bonus":
                base += e.value
        r = res.get(element, F.ENEMY_RES)
        stat = s.get(scaling, 0.0)
        if src_kind == "lunar_charged_direct":
            return stat * (1 + base) * (1 + F.em_lunar(s.get("em", 0)) + react) * F.res_mult(r) * F.crit_avg(s.get("cr", 0), s.get("cd", 0))
        if src_kind == "lunar_charged_reaction":
            return (1 + base) * (1 + F.em_lunar(s.get("em", 0)) + react) * F.res_mult(r) * F.crit_avg(s.get("cr", 0), s.get("cd", 0)) * (1 + extra)
        if src_kind == "swirl":
            return (1 + F.em_transformative(s.get("em", 0)) + react) * F.res_mult(r)
        dmg = s.get("dmg_pct", 0) + s.get(element, 0)
        return stat * (1 + dmg) * F.res_mult(r) * F.crit_avg(s.get("cr", 0), s.get("cd", 0))

    # ---------- swap ----------
    def application(self, units: dict[str, Unit], element: str) -> float:
        return sum(((self.kits.get(n) or {}).get("applies") or {}).get(element, 0.0) for n in units)

    def lunar_enabled(self, units: dict[str, Unit]) -> bool:
        return any("lunar_charged" in ((self.kits.get(n) or {}).get("enables") or []) for n in units)

    def evaluate(self, profile: Profile, units: dict[str, Unit], extra_sources: list[Source], lead: str) -> tuple[float, list[tuple[Source, float]]]:
        """Team DPS when the profile's damage sources are re-scored with `units` as the team."""
        old_fx = self.effects(profile.units, profile.lead)
        new_fx = self.effects(units, lead)
        old_els = {u.element for u in profile.units.values()}
        new_els = {u.element for u in units.values()}
        lunar_ok = self.lunar_enabled(units)
        app_old = min(self.application(profile.units, "Hydro"), self.application(profile.units, "Electro")) or 1.0
        app_new = min(self.application(units, "Hydro"), self.application(units, "Electro"))
        out = []
        for src in list(profile.sources) + extra_sources:
            if src.owner not in units and src.kind != "lunar_charged_reaction":
                continue
            if src.kind in LUNAR_KINDS and not lunar_ok:
                out.append((src, 0.0))
                continue
            owner_name = lead if src.kind == "lunar_charged_reaction" else src.owner
            old_owner = profile.units.get(profile.lead if src.kind == "lunar_charged_reaction" else src.owner)
            new_owner = units[owner_name]
            if old_owner is None:  # a newcomer's own source, already scored for this team
                out.append((src, src.dps))
                continue
            scaling = "hp" if src.owner in units and ((self.kits.get(src.owner) or {}).get("scaling") == "hp") else "atk"
            before = self.multiplier(src.kind, src.element, old_owner, profile.lead, old_fx, old_els, scaling)
            after = self.multiplier(src.kind, src.element, new_owner, lead, new_fx, new_els, scaling)
            ratio = after / before if before else 1.0
            if src.kind == "lunar_charged_reaction":
                ratio *= max(0.5, min(1.5, app_new / app_old)) if app_new else 0.0
            out.append((src, src.dps * ratio))
        return sum(v for _, v in out), out


F_ELEMENTS = ["Pyro", "Hydro", "Electro", "Cryo", "Anemo", "Geo", "Dendro", "Physical"]


@dataclass
class Candidate:
    """Someone who might join the team. Own damage comes from a measured team or from kit hits."""
    unit: Unit
    sources: list[Source] = field(default_factory=list)  # their own damage, already in this team's terms
    origin: str = ""


def kit_candidate(name: str, kits: dict, team_units: dict[str, Unit], lead: str, theory: "Theory",
                  rotation_seconds: float = 20.0) -> Candidate:
    """A character known only from their kit (for example, unreleased): own damage from listed hits."""
    kit = kits[name]
    st = {"atk": 2000.0, "hp": 20000.0, "def": 900.0, "em": 100.0, "cr": 0.6, "cd": 1.2, "dmg_pct": 0.0}
    st.update(kit.get("stats") or {})
    unit = Unit(name, kit["element"], 90, kit.get("cons", 0), st, {s: 4 for s in kit.get("sets", [])})
    units = {**team_units, name: unit}
    fx = theory.effects(units, lead)
    els = {u.element for u in units.values()}
    sources = []
    for h in kit.get("hits", []):
        kind = h.get("kind", "direct")
        m = theory.multiplier(kind, h.get("element", unit.element), unit, lead, fx, els, h.get("scaling", "atk"))
        mv = h["mult"] * (F.LUNAR_MULT["lunar_charged"] if kind == "lunar_charged_direct" else 1.0)
        if kind == "direct":
            m *= F.def_mult()
        dmg = mv * m * h.get("per_rotation", 1)
        sources.append(Source(name, h["name"], kind, h.get("element", unit.element), dmg / rotation_seconds))
    return Candidate(unit, sources, "kit hits")


def measured_candidate(name: str, other: Profile) -> Candidate:
    """A character whose own damage was measured in another gcsim team (ideally with the same carry)."""
    own = [Source(s.owner, s.name, s.kind, s.element, s.dps) for s in other.sources
           if s.owner == name and s.kind != "lunar_charged_reaction"]
    return Candidate(copy.deepcopy(other.units[name]), own, other.origin)


@dataclass
class SwapResult:
    out: str
    candidate: str
    before: float
    after: float
    lines: list[tuple[str, float, float]]  # (description, before dps, after dps)
    notes: list[str]

    @property
    def change(self) -> float:
        return self.after / self.before - 1 if self.before else 0.0


def swap(theory: Theory, profile: Profile, out_name: str, cand: Candidate, cand_other: Profile | None = None) -> SwapResult:
    units = {n: u for n, u in profile.units.items() if n != out_name}
    units[cand.unit.name] = cand.unit
    lead = profile.lead if profile.lead != out_name else cand.unit.name
    # Newcomer's measured damage was earned in another team: re-score it for this one.
    extra = []
    if cand_other is not None:
        for s in cand.sources:
            before = theory.multiplier(s.kind, s.element, cand_other.units[cand.unit.name], cand_other.lead,
                                       theory.effects(cand_other.units, cand_other.lead), {u.element for u in cand_other.units.values()})
            after = theory.multiplier(s.kind, s.element, cand.unit, lead, theory.effects(units, lead), {u.element for u in units.values()})
            extra.append(Source(s.owner, s.name, s.kind, s.element, s.dps * (after / before if before else 1)))
    else:
        extra = cand.sources
    before_total = profile.dps
    after_total, scored = theory.evaluate(profile, units, extra, lead)

    lines = []
    for name in list(profile.units) + [cand.unit.name]:
        b = sum(s.dps for s in profile.sources if s.owner == name and s.kind != "lunar_charged_reaction")
        a = sum(v for s, v in scored if s.owner == name and s.kind != "lunar_charged_reaction")
        if b or a:
            lines.append((f"{name} own damage", b, a))
    b = sum(s.dps for s in profile.sources if s.kind == "lunar_charged_reaction")
    a = sum(v for s, v in scored if s.kind == "lunar_charged_reaction")
    if b or a:
        lines.append(("Lunar-Charged reactions", b, a))

    notes = []
    old_c, new_c = theory.counts(profile.units), theory.counts(units)
    if old_c["moonsign"] >= 2 > new_c["moonsign"]:
        notes.append("The team loses Ascendant Gleam (fewer than 2 Moonsign characters).")
    if new_c["moonsign"] >= 2 > old_c["moonsign"]:
        notes.append("The team gains Ascendant Gleam.")
    if not theory.lunar_enabled(units) and theory.lunar_enabled(profile.units):
        notes.append("Nobody left can enable Lunar-Charged, so all Lunar damage is lost.")
    if theory.lunar_enabled(profile.units) and (theory.application(units, "Hydro") == 0 or theory.application(units, "Electro") == 0):
        notes.append("The team has no off-field Hydro or Electro application left; reactions depend on the carry alone.")
    if not cand.sources:
        notes.append(f"No own damage known for {cand.unit.name}: add hits to their kit or simulate a team with them.")
    unknown = [n for n in units if n not in theory.kits]
    if unknown:
        notes.append(f"No kit numbers for {', '.join(unknown)}: their buffs and shreds count as zero. Add them to knowledge/kits.yaml.")
    return SwapResult(out_name, cand.unit.name, before_total, after_total, lines, notes)


def team_effects_table(theory: Theory, units: dict[str, Unit], lead: str) -> list[str]:
    return [f"{e.caster}: {e.kind.replace('_', ' ')}" + (f" {e.stat}" if e.stat else "") + (f" {e.element}" if e.element else "")
            + f" {e.value:.3g} to {e.target}" + (f" ({e.note})" if e.note else "") for e in theory.effects(units, lead)]
