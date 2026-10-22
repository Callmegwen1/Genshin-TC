"""Party-composition conditions in kits (model 6.5; one source since phase M1).

Some supports give their full value only in a particular party: Escoffier's shred scales with the number of Hydro
and Cryo members, Chevreuse's buffs need an all Pyro and Electro party with at least one of each. The pair model
averaged such a support's effect over her simulated lineups (mostly full-condition ones), so a lineup that breaks
the condition was overpredicted: held out, +3.0% on 234 such lineups. One fitted effect per condition ("present,
condition unmet") removes that bias; see gtc/pairmodel.py.

Source of the conditions: the reviewed kit (knowledge/kits/, schema 3) when the character has one, else
knowledge/kit_conditions.yaml. Rules:
  count  the effect scales with the number of party members of these elements; full at `full`
  only   every party member must be one of these elements; with `each`, at least one of every listed element
"""
from __future__ import annotations

import yaml

from gtc import KNOWLEDGE_DIR

PATH = KNOWLEDGE_DIR / "kit_conditions.yaml"
_CONDITIONS: dict | None = None
_ELEMENTS: dict | None = None
_PARTY_TYPES = {"party_element_count": "count", "party_elements_only": "only"}


def _legacy() -> dict:
    return yaml.safe_load(PATH.read_text(encoding="utf-8")) if PATH.exists() else {}


def conditions() -> dict:
    """name -> {rule, elements, full, each, text}: the party condition per conditional support."""
    global _CONDITIONS
    if _CONDITIONS is None:
        from gtc.kits import reviewed_kits

        out = {n: {**c, "each": bool(c.get("each", False))} for n, c in _legacy().items()}
        for name, k in reviewed_kits().items():
            for c in k.get("conditions") or []:
                rule = _PARTY_TYPES.get(c.get("type"))
                if rule:
                    out[name] = {"rule": rule, "elements": list(c["elements"]), "full": c.get("full"),
                                 "each": bool(c.get("each_required", False)), "text": c.get("text", "")}
                    break
        _CONDITIONS = out
    return _CONDITIONS


def legacy_conditions(name: str) -> list[dict]:
    """The yaml condition of a character without a reviewed kit, in schema-3 form (for derived kits)."""
    c = _legacy().get(name)
    if not c:
        return []
    t = "party_element_count" if c["rule"] == "count" else "party_elements_only"
    out = {"type": t, "elements": c["elements"], "text": c["text"]}
    if c["rule"] == "count":
        out["full"] = c["full"]
    else:
        out["each_required"] = bool(c.get("each", False))
    return [out]


def _element(m: str) -> str | None:
    global _ELEMENTS
    if _ELEMENTS is None:
        from gtc import gamedata

        _ELEMENTS = {k: v.get("element") for k, v in gamedata.load_characters().items()}
    return m[10:-1] if m.startswith("Traveler (") else _ELEMENTS.get(m)


def status(name: str, lineup) -> dict | None:
    """For a conditional support in this lineup: {met, have, need, text}; None when `name` has no condition."""
    c = conditions().get(name)
    if c is None or name not in lineup:
        return None
    lineup = list(lineup)
    els = set(c["elements"])
    have = sum(1 for m in lineup if _element(m) in els)
    if c["rule"] == "count":
        need = c.get("full") or len(lineup)
        met = have >= need
    else:
        need = len(lineup)
        present = {_element(m) for m in lineup}
        met = have == need and (not c.get("each") or els <= present)
    out = {"met": met, "have": have, "need": need, "text": c["text"], "elements": sorted(els), "rule": c["rule"]}
    if c["rule"] == "only" and c.get("each") and have == need and not met:
        out["missing_each"] = sorted(els - {_element(m) for m in lineup})
    return out


def unmet(lineup) -> list[str]:
    """Names of the supports in this lineup whose party condition is not met."""
    return [n for n in conditions() if n in lineup and not status(n, lineup)["met"]]


def describe_unmet(lineup) -> list[str]:
    out = []
    for n in unmet(lineup):
        s = status(n, lineup)
        if s.get("missing_each"):
            out.append(f"{n}: {s['text']}; this team has no {' or '.join(s['missing_each'])} member")
        else:
            out.append(f"{n}: {s['text']}; this team has {s['have']} of {s['need']}")
    return out
