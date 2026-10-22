"""Weapon and artifact-set effects (phase H), in the same effect language as character passives.

A gear effect is a dict like an annotation entry:
    kind      atk_pct | atk | hp_pct | def_pct | em | crit_rate | crit_dmg | er | dmg_bonus | elemental_dmg_bonus |
              reaction_bonus | res_shred | flat_dmg | heal | energy | other
    target    self | party | party_others | enemy
    affects   {elements, damage_types, reactions}
    amount    number, or {of: <wearer stat>, rate, cap} (Emblem: 25% of ER), or a party spec (curated)
    trigger   always | skill | burst | swirl | hit:<types> | reaction_own:<kinds|any> | periodic
    duration  seconds (None for always)
    stack_max, stack_mode (independent | shared), icd
    state     met | unknown (a condition the engine does not model: no credit, listed)

Two sources, in order:
    knowledge/forward/gear.yaml   curated entries (provenance: Amber text, hand-structured), for effects whose value
                                  depends on the party, a resource or a mechanic the text compiler cannot read
    compile_text()                a sentence-level compiler over the Amber / set text: static stats, "after using an
                                  Elemental Skill ... for Ns", "upon triggering an Elemental Reaction", on-hit stacks,
                                  stat-scaled amounts, party targets, RES shred. A sentence with a condition the
                                  engine does not model (HP thresholds, shields, defeats, chance, Bond of Life, enemy
                                  aura checks, ...) becomes an unknown effect: no credit, listed.

`static_stats(gear)` folds unconditional self stats into the build (so caster-scaled buffs see them); `timeline(rot,
builds)` returns TimedEffects for the rest.
"""
from __future__ import annotations

import re
from functools import lru_cache

import yaml

from gtc import KNOWLEDGE_DIR

CURATED = KNOWLEDGE_DIR / "forward" / "gear.yaml"
ELEMENTS = ("Pyro", "Hydro", "Electro", "Cryo", "Anemo", "Geo", "Dendro")
REACTION_WORDS = {"overloaded": "overloaded", "electro-charged": "electrocharged", "superconduct": "superconduct",
                  "hyperbloom": "hyperbloom", "burgeon": "burgeon", "bloom": "bloom", "burning": "burning",
                  "swirl": "swirl", "vaporize": "vaporize", "melt": "melt", "aggravate": "aggravate", "spread": "spread",
                  "lunar-charged": "lunarcharged", "lunar-bloom": "lunarbloom", "lunar reaction": "lunar",
                  "shatter": "shatter", "crystallize": "crystallize"}
# conditions the engine does not model: a sentence containing one is not credited
BLOCKERS = ("hp is below", "hp is above", "hp falls", "current hp", "takes dmg", "taking dmg", "takes damage",
            "defeat", "bond of life", "nightsoul", "chance", "more than 50% hp", "weak point", "protected by a shield",
            "under a shield", "while shielded", "less than 30% hp",
            "distance", "moonsign", "energy capacity", "arkhe", "leaving combat", "melusine", "traveler",
            "playstation", "healed", "heals ", "healing effectiveness", "stamina", "sprint", "crit hit", "particle", "orb",
            "picked up", "0 elemental energy", "0 energy", "witch's homework", "hexerei", "liyue", "opponents nearby",
            "fewer than", "at least 2 opponents", "being affected", "elemental shard", "lunar-crystallize",
            "energy is less",
            "consumes", "radiance", "gleaming moon", "secret rite", "phlogiston", "harmonic", "every time",
            "in sequence", "when the value", "plays a", "elemental types involved", "types involved")
STAT_OF = {"atk": "atk", "def": "def", "max hp": "hp", "hp": "hp", "elemental mastery": "em", "energy recharge": "er"}
NUM = r"([\d.]+)"


@lru_cache(maxsize=1)
def curated() -> dict:
    return yaml.safe_load(CURATED.read_text(encoding="utf-8")) if CURATED.exists() else {}


def _clean(t: str) -> str:
    t = re.sub(r"<[^>]+>", "", t or "").replace("\\n", " ").replace("\n", " ")
    return re.sub(r"\s+", " ", t).strip()


@lru_cache(maxsize=512)
def weapon_text(name: str, refine: int = 1) -> str | None:
    from gtc.forward import data as D

    wid = D.weapon_id(name)
    if wid is None:
        return None
    d = D._json(f"en/weapon/{wid}") or {}
    aff = next(iter((d.get("affix") or {}).values()), None)
    if not aff:
        return ""
    up = aff.get("upgrade") or {}
    return _clean(up.get(str(max(0, min(4, refine - 1)))) or up.get("0", ""))


def set_text(name: str, pieces: int) -> list[str]:
    """The set's bonus texts that apply at this piece count (2-piece, and 4-piece at 4)."""
    from gtc import gamedata

    eff = (gamedata.load_sets().get(name) or {}).get("effects") or []
    if len(eff) == 1:
        return [_clean(eff[0])] if pieces >= 1 else []
    out = []
    if pieces >= 2 and eff:
        out.append(_clean(eff[0]))
    if pieces >= 4 and len(eff) > 1:
        out.append(_clean(eff[1]))
    return out


# ---------- the text compiler ----------

def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[a-z%)\"'])\.\s+(?=[A-Z\"])|(?<=[a-z%)])\.$", text) if s.strip()]


def _types(phrase: str) -> list[str]:
    p = phrase.lower()
    out = []
    if "normal" in p:
        out.append("normal")
    if "charged" in p:
        out.append("charged")
    if "plunging" in p:
        out.append("plunge")
    if "elemental skill" in p or re.search(r"\bskill\b", p):
        out.append("skill")
    if "elemental burst" in p or re.search(r"\bburst\b", p):
        out.append("burst")
    return out


def _stat_kind(phrase: str, pct: bool) -> tuple[str, dict] | None:
    """(kind, affects) for a stat phrase ("Elemental Burst CRIT Rate", "Pyro DMG Bonus", "Overloaded ... DMG")."""
    p = phrase.lower().strip()
    rx = [v for k, v in REACTION_WORDS.items() if re.search(rf"(?<![\w-]){re.escape(k)}(?![\w-])", p)]
    if rx and "dmg" in p:
        if "lunar" in rx:
            rx = [r for r in rx if r != "lunar"] + ["lunarcharged", "lunarbloom", "lunarcrystallize"]
        return "reaction_bonus", {"reactions": rx}
    types = _types(p)
    aff = {"damage_types": types} if types else {}
    if "crit rate" in p:
        return "crit_rate", aff
    if "crit dmg" in p:
        return "crit_dmg", aff
    if "elemental mastery" in p:
        return "em", {}
    if "energy recharge" in p:
        return "er", {}
    if "healing" in p:
        return "heal", {}
    if "shield strength" in p:
        return None
    for el in ELEMENTS:
        if f"{el.lower()} dmg" in p:
            return "elemental_dmg_bonus", {"elements": [el]}
    if "physical dmg" in p:
        return "elemental_dmg_bonus", {"elements": ["Physical"]}
    if "elemental dmg" in p:
        return "dmg_bonus", {"elements": list(ELEMENTS), **aff}
    if "dmg" in p:
        return "dmg_bonus", aff
    if re.search(r"\batk\b", p):
        return ("atk_pct" if pct else "atk"), {}
    if re.search(r"\bdef\b", p):
        return ("def_pct" if pct else "def"), {}
    if re.search(r"\b(max )?hp\b", p):
        return ("hp_pct" if pct else "hp"), {}
    return None


_CORE = (r"(?:CRIT Rate|CRIT DMG|DMG Bonus|DMG|ATK Bonus|ATK|DEF|Max HP|HP|Elemental Mastery|Energy Recharge|Healing Bonus"
         r"|Healing Effectiveness)")
_PREFIX = r"(?:(?:all |All )?(?:[A-Z][\w-]*(?:,? (?:and |or )?[A-Z][\w-]*)* )?(?:reaction )?(?:Attack )?)"
_STAT_WORDS = _PREFIX + _CORE
_OF = r"(?: of (?:the equipping character's |the wielder's |their |its )?(ATK|DEF|Max HP|HP|Elemental Mastery|Energy Recharge))?"
_WHO = (r"(?:the equipping character's |their |the character's |all party members' |all nearby party members' |"
        r"nearby party members' |the wielder's )")
PATTERNS = [
    re.compile(rf"(?P<stat>{_STAT_WORDS})(?: dealt)?(?: of [\w\s']+?)?(?: (?:is|are|will be|will))?(?: further| additionally)? "
               rf"(?:increased|increases|increase) by (?:an additional )?{NUM}(?P<pct>%)?{_OF}"),
    re.compile(rf"(?P<stat>{_STAT_WORDS}) \+{NUM}(?P<pct>%)?"),
    re.compile(rf"[Ii]ncreas(?:es?|ing) (?:the )?{_WHO}?(?P<stat>{_STAT_WORDS})(?: dealt)?(?: by (?:the )?[a-z][\w ]+?)? by {NUM}(?P<pct>%)?{_OF}"),
    re.compile(rf"(?:,|\band) (?:their |its )?(?P<stat>{_STAT_WORDS}) by {NUM}(?P<pct>%)?{_OF}"),
    re.compile(rf"[Gg]ain(?:s)? (?:a |an )?{NUM}(?P<pct>%) (?P<stat>(?:All )?(?:{'|'.join(ELEMENTS)}|Elemental|Physical) DMG Bonus)"),
    re.compile(rf"[Oo]btain {NUM}(?P<pct>%) (?P<stat>All Elemental DMG Bonus)"),
    re.compile(rf"grants? (?:a |an )?{NUM}(?P<pct>%) (?P<stat>(?:All )?(?:{'|'.join(ELEMENTS)}|Elemental|Physical) DMG Bonus)"),
    re.compile(rf"(?P<stat>deal|deals) {NUM}(?P<pct>%) (?:increased|more) DMG"),
    re.compile(rf"[Ii]ncreases? (?P<stat>DMG) against [\w\s]+? by {NUM}(?P<pct>%)"),
    re.compile(rf"(?P<stat>DMG(?: Bonus)? (?:dealt |caused |conferred )?by (?:the )?[A-Z][\w\s,-]+?) (?:(?:is |are )?(?:increased )?)?by {NUM}(?P<pct>%)"),
]
RES = re.compile(rf"(?:({'|'.join(ELEMENTS)})|Elemental) RES[\w\s']*?(?:will be )?decreased by {NUM}%|[Dd]ecreases opponent's Elemental RES[\w\s]*? by {NUM}%")


def _trigger(s: str) -> list[str] | None:
    l = s.lower()
    hits_any = ("scoring hits", "upon damaging an opponent", "after an attack hits", "hitting an opponent",
                "after the character hits", "hits opponents, ", "hit an opponent")
    if "switching characters" in l or "new character taking the field" in l:
        return ["swap_out"]
    if "takes the field" in l or "taking the field" in l:
        return ["swap_in"]
    hit_first = re.match(r"(?:normal|charged|plunging)(?: attacks?)?(?:,? (?:and |or )?(?:normal|charged|plunging)(?: attacks?)?)* hits?", l)
    if not hit_first and (re.search(r"(?:using|casting|cast|use|unleashing|after|when)[\w\s,]*? elemental skills? (?:and|or) (?:elemental )?bursts?", l)
                          or re.search(r"skills? or (?:elemental )?bursts? hits?", l)):
        return ["skill", "burst"]
    if re.search(r"(using|casting|cast|use|unleashing) (?:an |their |the )?elemental skill|elemental skill hits|elemental skills hit|after elemental skill", l):
        return ["skill"]
    if re.search(r"(using|casting|cast|use) (?:an |their |the )?elemental burst|elemental burst hits|after elemental burst", l):
        return ["burst"]
    if re.search(r"elemental reaction|triggering an? (?:elemental )?reaction|causing an elemental reaction|triggers? an? reaction", l):
        return ["reaction_own:any"]
    m = re.search(r"(?:after|when|on hit,|^)\s*(?:a |the character's )?((?:normal|charged|plunging)(?: attacks?)?(?:,? (?:and |or )?"
                  r"(?:normal|charged|plunging)(?: attacks?)?)*)(?: [\w ]*?)? hits?", l)
    if m or l.startswith("on hit, normal or charged"):
        types = _types(m.group(1) if m else "normal charged")
        return [f"hittype:{'|'.join(types)}"]
    if "dealing elemental dmg" in l or "deals elemental dmg" in l:
        return ["hittype:elemental"]
    if any(k in l for k in hits_any):
        return ["hittype:any"]
    if re.search(r"every \d+(?:\.\d+)?s", l) and "following effect" in l:
        return ["periodic"]
    return None


def _duration(s: str) -> float | None:
    m = re.search(r"(?:for|within|lasts?(?: for)?|lasting) (?:the next )?(\d+(?:\.\d+)?)\s?s(?:econds)?\b", s, re.I)
    return float(m.group(1)) if m else None


def _stacks(s: str) -> tuple[int | None, str]:
    m = re.search(r"[Mm]ax(?:imum of)? (\d+) stacks|stacks? up to (\d+) times|up to (\d+) stacks|(\d+) max stacks", s)
    n = next((int(g) for g in (m.groups() if m else []) if g), None)
    mode = "independent" if re.search(r"independent", s, re.I) else "shared"
    return n, mode


def _icd(s: str) -> float | None:
    m = re.search(r"once every (\d+(?:\.\d+)?)\s?s", s)
    return float(m.group(1)) if m else None


def _target(s: str) -> str:
    l = s.lower()
    if "other party members" in l or "other nearby party members" in l:
        return "party_others"
    if "all party members" in l or "all nearby party members" in l or "nearby party members" in l:
        return "party"
    return "self"


def compile_text(text: str, source: str) -> list[dict]:
    """Effects from one gear text. Each sentence is compiled alone; its trigger and duration may come from the
    previous sentence ("... gain X for 6s: ATK is increased by 25%")."""
    out: list[dict] = []
    prev_trig, prev_dur, prev_text = None, None, None
    for s in _sentences(text):
        # "increase ATK and DEF by 4%": both stats get the amount
        s = re.sub(r"\b(ATK|DEF|Max HP|HP|Elemental Mastery|CRIT Rate|CRIT DMG) and (ATK|DEF|Max HP|HP|Elemental Mastery|CRIT Rate|CRIT DMG) by ([\d.]+%?)",
                   r"\1 by \3 and \2 by \3", s)
        tiered = bool(re.search(r"\d%?/\d", s))
        s = re.sub(r"\s*/\s*", ", ", s) if not tiered else s
        l = s.lower()
        blocked = next((b for b in BLOCKERS if b in l), None)
        trig = _trigger(s)
        dur = _duration(s)
        stack_max, mode = _stacks(s)
        found = []
        for pat in PATTERNS:
            for m in pat.finditer(s):
                g = m.groupdict()
                stat = g.get("stat") or ""
                nums = [x for x in m.groups() if x and re.fullmatch(r"[\d.]+", x)]
                if not nums:
                    continue
                v = float(nums[0])
                pct = bool(g.get("pct"))
                if stat in ("deal", "deals"):
                    k = ("dmg_bonus", {})
                else:
                    k = _stat_kind(stat, pct)
                if k is None:
                    continue
                span = m.span()
                if any(a <= span[0] < b or span[0] <= a < span[1] for a, b, _ in found):
                    continue
                of = m.groups()[-1] if pat.pattern.endswith(_OF) else None
                amount: float | dict = v / 100 if pct else v
                kind, aff = k
                if of:
                    amount = {"of": STAT_OF[of.lower()], "rate": v / 100}
                    if kind == "dmg_bonus" and amount["of"] != "er":
                        kind = "flat_dmg"   # "DMG increased by 40% of DEF": flat damage from the wearer's stat
                found.append((span[0], span[1], {"kind": kind, "affects": aff, "amount": amount}))
        for m in RES.finditer(s):
            el = m.group(1)
            v = float(m.group(2) or m.group(3))
            swirl = "swirl" in l
            found.append((m.span()[0], m.span()[1], {"kind": "res_shred", "target": "enemy", "amount": v / 100,
                                                     "affects": {"elements": [el]} if el else {},
                                                     **({"element_from": "swirl"} if swirl else {})}))
        cap_only = re.search(rf"maximum of {NUM}%", s)
        if not found and out and cap_only and not trig:
            # "A maximum of 75% bonus DMG can be obtained in this way." caps the previous stat-scaled effect
            for e in out:
                if e.get("text") == prev_text and isinstance(e.get("amount"), dict):
                    e["amount"]["cap"] = float(cap_only.group(1)) / 100
            continue
        if not found and out and (stack_max or _icd(s)) and not trig:
            # "Max 2 stacks." / "Can occur once every 1s." in its own sentence: belongs to the previous effects
            for e in out:
                if e.get("text") and e["text"] == prev_text:
                    if stack_max:
                        e.update({"stack_max": stack_max, "stack_mode": mode})
                    if _icd(s):
                        e["icd"] = _icd(s)
            continue
        if not found and re.search(r"regenerates? \d+ (?:elemental )?energy|restore \d+ (?:elemental )?energy|\d+ energy", l):
            out.append({"kind": "energy", "target": "self", "affects": {}, "amount": None, "trigger": trig, "duration": dur,
                        "source": source, "provenance": "compiled from the Amber text", "text": s, "state": "unknown",
                        "why": "energy effect: not credited in the energy model"})
            continue
        if not found and re.search(r"deal(?:s|ing)? (?:an additional |aoe dmg equal to )?\d+% (?:of )?atk|\d+% atk (?:as )?dmg|dmg equal to \d+% of atk", l):
            out.append({"kind": "other", "target": "self", "affects": {}, "amount": None, "trigger": trig, "duration": dur,
                        "source": source, "provenance": "compiled from the Amber text", "text": s, "state": "unknown",
                        "why": "extra damage proc: not modelled"})
            continue
        if not found:
            if re.search(r"\d+(?:\.\d+)?%|by \d+", s) and re.search(r"increase|bonus|\+\d", l) and "shield strength" not in l:
                out.append({"kind": "other", "target": "self", "affects": {}, "amount": None, "trigger": trig,
                            "duration": dur, "source": source, "provenance": "compiled from the Amber text", "text": s,
                            "state": "unknown",
                            "why": f"condition not modelled ('{blocked}')" if blocked else "sentence not parsed"})
            if trig:
                prev_trig, prev_dur = trig, dur
            continue
        aura = re.search(r"(?:opponents?|enemies|targets?) (?:affected by|that are) ((?:Pyro|Hydro|Electro|Cryo|Dendro|Frozen)(?:,? (?:or |and )?(?:Pyro|Hydro|Electro|Cryo|Dendro))*)", s)
        conds = [{"type": "enemy_aura", "any": re.findall(r"Pyro|Hydro|Electro|Cryo|Dendro|Frozen", aura.group(1))}] if aura else []
        wt = re.search(r"uses? an? ((?:Sword|Claymore|Polearm|Catalyst|Bow)(?:,? (?:or |and )?(?:a )?(?:Sword|Claymore|Polearm|Catalyst|Bow))*)", s)
        if wt:
            conds.append({"type": "weapon_type", "any": [w.lower() for w in re.findall(r"Sword|Claymore|Polearm|Catalyst|Bow", wt.group(1))]})
        de = re.search(r"at least (\d) different Elemental Types", s)
        if de:
            conds.append({"type": "distinct_elements", "min": int(de.group(1))})
        if re.search(r"when (?:the equipping character is )?(?:not on the field|off-field)", l):
            conds.append({"type": "on_field", "value": False})
        cap = re.search(rf"maximum of {NUM}%", s)
        for _, _, e in found:
            e = dict(e)
            e.setdefault("target", "self" if e["kind"] != "res_shred" else "enemy")
            if e["kind"] != "res_shred":
                e["target"] = _target(s)
            if cap and isinstance(e["amount"], dict):
                e["amount"]["cap"] = float(cap.group(1)) / 100
            t = trig or ((prev_trig or None) if dur is None or prev_dur else None)
            if e.get("element_from") == "swirl":
                t = ["swirl"]
            d = dur if dur is not None else prev_dur
            if t is None and d is None:
                t = ["always"]
            e.update({"trigger": t, "duration": d, "source": source, "provenance": "compiled from the Amber text",
                      "text": s})
            if conds:
                e["conditions"] = conds
            if stack_max:
                e.update({"stack_max": stack_max, "stack_mode": mode})
            if _icd(s):
                e["icd"] = _icd(s)
            if blocked:
                e.update({"state": "unknown", "why": f"condition not modelled ('{blocked}')"})
            elif tiered or "respectively" in l:
                e.update({"state": "unknown", "why": "tiered or paired values not parsed"})
            elif re.search(r"\bagainst\b|\bunder\b|\bwhile\b|\bif\b|\bwhen\b(?! (?:using|casting|the character (?:uses|casts)))", l) \
                    and not conds and t == ["always"]:
                # an unconditional-looking stat with a condition word the compiler did not resolve: not credited
                e.update({"state": "unknown", "why": "condition in the text not resolved"})
            elif t is None:
                e.update({"state": "unknown", "why": "trigger not recognised"})
            elif "always" not in t and d is None and "periodic" not in t:
                e.update({"state": "unknown", "why": "duration not found"})
            else:
                e["state"] = "met"
            if e["kind"] in ("heal",):
                e["state"] = "met"
            out.append(e)
        prev_trig, prev_dur = trig or prev_trig, dur if dur is not None else prev_dur
        prev_text = s
    return out


def weapon_effects(name: str, refine: int = 1) -> list[dict]:
    cur = (curated().get("weapons") or {}).get(name)
    if cur is not None:
        return [_by_refine(dict(e, source=e.get("source", name), provenance="curated (Amber text, hand-structured)"), refine)
                for e in cur]
    text = weapon_text(name, refine)
    return compile_text(text or "", name) if text else []


def _by_refine(e: dict, refine: int) -> dict:
    i = max(0, min(5, refine) - 1)
    if e.get("stack_steps") and isinstance(e["stack_steps"][0], list):
        e["stack_steps"] = [lvl[min(i, len(lvl) - 1)] for lvl in e["stack_steps"]]
    a = e.get("amount")
    if isinstance(a, list):
        e["amount"] = a[max(0, min(len(a), refine) - 1)]
    elif isinstance(a, dict):
        e["amount"] = {k: (v[max(0, min(len(v), refine) - 1)] if isinstance(v, list) else v) for k, v in a.items()}
    return e


def set_effects(name: str, pieces: int) -> list[dict]:
    cur = (curated().get("sets") or {}).get(name)
    out = []
    for n, text in zip((2, 4), set_text(name, pieces)):
        key = f"{n}pc"
        if cur and key in cur:
            out += [dict(e, source=f"{name} {key}", provenance="curated (Amber text, hand-structured)") for e in cur[key]]
        else:
            out += compile_text(text, f"{name} {key}")
    return out


def gear_effects(gear: dict | None) -> list[dict]:
    if not gear:
        return []
    out = []
    if gear.get("weapon"):
        out += weapon_effects(gear["weapon"], gear.get("refine", 1))
    for s, n in (gear.get("sets") or {}).items():
        out += set_effects(s, n)
    return out


STATIC = {"atk_pct": "atk_pct", "atk": "atk", "hp_pct": "hp_pct", "hp": "hp", "def_pct": "def_pct", "def": "def",
          "em": "em", "er": "er", "crit_rate": "cr", "crit_dmg": "cd", "heal": "heal"}


def _is_static(e: dict) -> bool:
    """An unconditional self stat with no damage-type filter: part of the build itself."""
    return (e.get("state") == "met" and e.get("trigger") == ["always"] and e.get("target", "self") == "self"
            and e["kind"] in STATIC and not (e.get("affects") or {}).get("damage_types")
            and isinstance(e.get("amount"), (int, float)) and not e.get("stack_max") and not e.get("conditions")
            and not e.get("stack_sources"))


def static_stats(gear: dict | None) -> dict[str, float]:
    out: dict[str, float] = {}
    for e in gear_effects(gear):
        if _is_static(e):
            k = STATIC[e["kind"]]
            out[k] = out.get(k, 0.0) + float(e["amount"])
        elif e.get("state") == "met" and e.get("trigger") == ["always"] and e["kind"] == "elemental_dmg_bonus" \
                and e.get("target", "self") == "self" and isinstance(e.get("amount"), (int, float)) \
                and not e.get("conditions") and not e.get("stack_sources") and not e.get("stack_max"):
            for el in (e.get("affects") or {}).get("elements") or []:
                out[el] = out.get(el, 0.0) + float(e["amount"])
    return out


def conditional(gear: dict | None) -> list[dict]:
    """Gear effects that are not folded into the build's stats."""
    out = []
    for e in gear_effects(gear):
        if _is_static(e):
            continue
        if e.get("state") == "met" and e.get("trigger") == ["always"] and e["kind"] == "elemental_dmg_bonus" \
                and e.get("target", "self") == "self" and isinstance(e.get("amount"), (int, float)) \
                and not e.get("conditions") and not e.get("stack_sources") and not e.get("stack_max"):
            continue
        out.append(e)
    return out


# ---------- timeline ----------

def _party_amount(spec: dict, wearer: str, lineup: list[str], builds: dict) -> tuple[float | None, str]:
    from gtc.mechanics import element_of

    el = element_of(wearer)
    others = [m for m in lineup if m != wearer]
    if "per_same_element" in spec or "per_other_element" in spec:
        same = min(3, sum(element_of(m) == el for m in others))
        diff = min(3, sum(element_of(m) != el for m in others))
        if "per_same_element" in spec:
            return spec["per_same_element"] * same, f"{same} same-element member(s)"
        return spec["per_other_element"] * diff, f"{diff} other-element member(s)"
    if "party_energy_rate" in spec:
        from gtc.forward.trace import burst_cost

        tot = sum(burst_cost(m) or 0.0 for m in lineup)
        return min(spec["party_energy_rate"] * tot, spec.get("cap", 9e9)), f"party Energy capacity {tot:.0f}"
    if "of" in spec:
        v = (builds[wearer].total(spec["of"]) - spec.get("minus", 0.0)) * spec["rate"] - spec.get("above", 0.0)
        v = max(v, 0.0)
        return (min(v, spec["cap"]) if "cap" in spec else v), ""
    return None, "amount spec not understood"


def timeline(rot, builds: dict) -> list:
    """TimedEffects for every member's conditional gear effects on this rotation."""
    from gtc.forward.effects import Instance, TimedEffect, _instances

    out = []
    for m in rot.lineup:
        b = builds.get(m)
        gear = getattr(b, "gear", None) if b else None
        for i, e in enumerate(conditional(gear)):
            if e["kind"] in ("heal", "other", "energy", "er"):
                continue
            if e["kind"] == "own_element_dmg_bonus":     # Mistsplitter's Emblem: the wearer's element
                from gtc.mechanics import element_of

                e = {**e, "kind": "elemental_dmg_bonus", "affects": {"elements": [element_of(m)]}}
            te = TimedEffect(f"{m}:gear:{i}", m, e["kind"], e.get("target", "self"), e.get("affects") or {}, None,
                             e.get("state", "met"), source=f"{e['source']}", element_from=e.get("element_from", ""),
                             why=e.get("why", ""))
            te.gear = True
            for c in e.get("conditions") or []:
                if c.get("type") in ("enemy_aura", "on_field", "state_active", "resource_at_least"):
                    te.dynamic.append(c)
                elif c.get("type") == "weapon_type":
                    from gtc.forward.build import weapon_type

                    if weapon_type(m) not in c["any"]:
                        te.state, te.why = "unmet", f"needs a {'/'.join(c['any'])}"
                elif c.get("type") == "distinct_elements":
                    from gtc.mechanics import element_of

                    n = len({element_of(x) for x in rot.lineup} - {None})
                    if n < c["min"]:
                        te.state, te.why = "unmet", f"{n} elements in the party (needs {c['min']})"
                else:
                    from gtc.forward.effects import condition_state

                    st, note = condition_state(c, list(rot.lineup), rot)
                    if st != "met":
                        te.state = st if st in ("unmet", "unknown") else te.state
                        te.why = "; ".join(x for x in (te.why, note) if x)
            a = e.get("amount")
            if isinstance(a, (int, float)):
                te.amount = float(a)
            elif isinstance(a, dict):
                te.amount, note = _party_amount(a, m, rot.lineup, builds)
                if "of" in a and a.get("of") in ("atk", "hp", "def", "em") and not a.get("minus"):
                    te.scale_stat = a["of"]          # chained: the wearer's buffed stat when the effect starts
                if note:
                    te.why = "; ".join(x for x in (te.why, note) if x)
            if te.amount is None:
                te.state = "unknown"
            trig = e.get("trigger") or []
            if te.state == "met":
                if "always" in trig or "periodic" in trig:
                    te.instances = [Instance(0.0, rot.duration + 1)]
                    if "periodic" in trig:
                        te.why = "; ".join(x for x in (te.why, "periodic effect with full uptime (assumed)") if x)
                else:
                    te.instances = _instances(rot, m, trig, float(e.get("duration") or 0.0), 0.0, icd=e.get("icd"))
                te.stack_steps = e.get("stack_steps")
                te.stack_threshold = e.get("stack_threshold")
                for src in e.get("stack_sources") or []:
                    if src.get("always"):
                        te.stack_sources.append([Instance(0.0, rot.duration + 1)])
                    else:
                        te.stack_sources.append(_instances(rot, m, src["trigger"], float(src["duration"]), 0.0, icd=src.get("icd")))
                if te.stack_sources:
                    te.instances = [Instance(0.0, rot.duration + 1)]
                te.stack_max = e.get("stack_max")
                te.stack_mode = e.get("stack_mode", "shared")
                if te.stack_max:
                    te.trigger_times = _trigger_times(rot, m, trig, e.get("icd"))
                    te.stack_duration = float(e.get("duration") or 0.0)
            out.append(te)
    return out


def _trigger_times(rot, who: str, trig: list[str], icd: float | None) -> list[float]:
    from gtc.forward.effects import trigger_starts

    times = sorted(t for t, _ in trigger_starts(rot, who, trig, 0.0))
    if icd:
        kept, last = [], -1e9
        for t in times:
            if t - last >= icd - 1e-9:
                kept.append(t)
                last = t
        times = kept
    return times


def amount_at(te, t: float) -> float | None:
    """A stacking effect's amount at t (None: no stacks). Sources: each active source is a level; trigger stacks:
    x stacks, or the value at that level (stack_steps), or all-or-nothing at a threshold."""
    if te.stack_sources:
        n = sum(1 for src in te.stack_sources if any(i.start <= t < i.end for i in src))
    elif te.stack_max:
        n = stacks_at(te, t)
    else:
        return te.amount
    if te.stack_threshold:
        return te.amount if n >= te.stack_threshold else None
    if not n:
        return None
    if te.stack_steps:
        return float(te.stack_steps[min(n, len(te.stack_steps)) - 1])
    return te.amount * n


def stacks_at(te, t: float) -> int:
    """Stacks of a stacking effect at t: independent stacks count the triggers within their duration; shared stacks
    count the triggers of the current chain (each refreshes the whole stack)."""
    times = [x for x in (getattr(te, "trigger_times", None) or []) if x <= t]
    d = getattr(te, "stack_duration", 0.0) or 0.0
    if not times:
        return 0
    if te.stack_mode == "independent":
        n = sum(1 for x in times if t - x < d)
    else:
        n = 0
        for x in reversed(times):
            if n and (last - x) >= d:
                break
            if not n and t - x >= d:
                return 0
            n += 1
            last = x
    return min(n, te.stack_max)
