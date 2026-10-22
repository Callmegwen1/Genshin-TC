"""Offline kit compiler (phases M6 to M8): official kit text → schema-3 kits, through an LLM at build time only.

Nothing here runs when the engine answers a question. The compiler is a batch tool:

    packets   `write_packets(names)` writes one work packet per character to data/compiler/packets/: the extraction
              instructions, the schema (gtc/kits.py), two reviewed example kits (never the target's), the character's
              official kit text (Project Amber cache: talents and passives, no constellations), and what the engine
              measured about them (capability profile). An LLM reads the packet and writes YAML to
              data/compiler/responses/<slug>.yaml. Any LLM can fill a packet: here fresh subagents that never saw
              the reviewed kits, or the Anthropic API through `fill_with_api` when ANTHROPIC_API_KEY is set.
    compile   `compile_response(name)` checks a response and, when it passes, writes knowledge/kits_compiled/<slug>.yaml:
                schema       gtc/kits.validate must pass
                grounding    every effect must name a talent from the packet's text, and a numeric amount must appear
                             in that text; ungrounded effects are dropped and listed (an LLM's invention never
                             becomes a fact)
                measurement  where the engine measured the character, behaviour that the advisor demotes on cannot
                             contradict it: on_field_damage, field time and damage ownership beyond one level, and
                             application, are replaced by the measured values and listed; function-critical roles
                             the engine measured (swirl support, grouping, healer, shielder, battery) are kept, and
                             owning a Swirl reaction implies swirl support
                provenance   every field is method llm_extracted, reviewed pending, confidence at most medium
    validate  `validate_reference()` compiles the reviewed reference characters blind and scores each field against
              the human-written kit (`score`). Population (M8) runs only after this passes.

Use of compiled kits: `gtc.kits.kit()` prefers a reviewed kit, then a compiled one, then a derived one. Compiled kits
feed the mechanical reasoner (functions, synergies, explanations). They never feed power: composition conditions for
the pair model come only from reviewed kits (gtc/kit_conditions.py) until a human reviews them.
"""
from __future__ import annotations

import glob
import json
import re
from pathlib import Path

import yaml

from gtc import KNOWLEDGE_DIR

ROOT = KNOWLEDGE_DIR.parent
WORK = ROOT / "data" / "compiler"
PACKETS, RESPONSES = WORK / "packets", WORK / "responses"
COMPILED_DIR = KNOWLEDGE_DIR / "kits_compiled"
AMBER_GLOB = str(ROOT / "data" / "sources" / "cache" / "amber" / "*.html")
EXAMPLES = ("Bennett", "Escoffier")          # few-shot examples; replaced when one of them is the target
EXAMPLE_SPARE = ("Xingqiu", "Kaedehara Kazuha")
ORDER = ("minimal", "low", "medium", "high")
CRITICAL_ROLES = {"swirl_support", "grouping", "healer", "shielder", "battery"}
COMPOSITION = ("party_element_count", "party_elements_only", "party_elements_forbidden", "hexerei_count",
               "party_element_types")
OWNERSHIP = ("none", "incidental", "sub_dps", "carry")


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


# ---------- the official text ----------

_AMBER: dict | None = None


def _clean(t: str) -> str:
    t = re.sub(r"<[^>]+>", "", t or "")
    t = re.sub(r"\{LINK#[^}]*\}|\{/LINK\}", "", t)
    t = re.sub(r"#?\{LAYOUT_MOBILE#[^}]*\}\{LAYOUT_PC#([^}]*)\}\{LAYOUT_PS#[^}]*\}", r"\1", t)  # platform wording: PC
    return t.replace("\\n", "\n").strip()


def amber() -> dict:
    global _AMBER
    if _AMBER is None:
        _AMBER = {}
        for f in glob.glob(AMBER_GLOB):
            try:
                d = json.load(open(f, encoding="utf-8"))["data"]
            except Exception:
                continue
            if d.get("name"):
                _AMBER[d["name"]] = d
    return _AMBER


PARAM = re.compile(r"\{param(\d+):([A-Z0-9]+)\}")
TABLE_LEVEL = "10"  # talent level whose scaling values go into the packet (a typical built level)


def _fmt(v: float, spec: str) -> str:
    if spec.endswith("P"):
        return f"{round(v * 100, 2):g}%"
    if spec == "I":
        return f"{int(round(v))}"
    return f"{round(v, 2):g}"


def _table(t: dict) -> str:
    """The talent's scaling table at TABLE_LEVEL with values filled in ("Energy Cost: 60; Duration: 12s; ...")."""
    pr = t.get("promote")
    lv = pr.get(TABLE_LEVEL) or pr.get("1") if isinstance(pr, dict) else None
    if not lv or not lv.get("params"):
        return ""
    params = lv["params"]

    def sub(m):
        i = int(m.group(1)) - 1
        return _fmt(params[i], m.group(2)) if 0 <= i < len(params) else m.group(0)

    rows = []
    for row in lv.get("description") or []:
        if "|" in row:
            label, val = _clean(row).split("|", 1)
            rows.append(f"{label}: {PARAM.sub(sub, val)}")
    return "; ".join(rows)


def talents(name: str) -> list[tuple[str, str]]:
    """[(talent name, description)] of talents and passives (no constellations); skill and Burst descriptions are
    followed by their scaling table at talent level TABLE_LEVEL."""
    d = amber().get(name)
    if not d:
        return []
    out = []
    for t in (d.get("talent") or {}).values():
        if not t.get("name"):
            continue
        desc = _clean(t.get("description"))
        if desc.startswith("Normal Attack"):
            # kept whole up to a generous cap: several kits put their core mechanic in the Normal Attack talent
            # (Arlecchino's Masque of the Red Death, Neuvillette's Charged Attack); a 600-character cut lost them
            desc = desc[:2500] + (" ..." if len(desc) > 2500 else "")
        elif str(t.get("type")) in ("0", "1"):
            tab = _table(t)
            if tab:
                desc += f"\n\nScaling at talent level {TABLE_LEVEL}: {tab}"
        out.append((t["name"], desc))
    return out


def kit_text(name: str) -> str:
    return "\n\n".join(f"### {n}\n{d}" for n, d in talents(name))


# ---------- packets ----------

INSTRUCTIONS = """You are extracting one Genshin Impact character's kit into a strict YAML schema. Work ONLY from this
packet: do not read any other file, do not use web search, and do not rely on outside knowledge of this character for
FACTS (effects, amounts, conditions). For BEHAVIOUR (field time, damage ownership, how strongly they apply their
element) use the kit text and the engine measurements below; general knowledge of how such kits are played is
allowed there, at confidence medium.

Rules:
- Facts must come from the kit text below. Every effect's `source` must start with the exact talent name it comes
  from (as written after ### below), optionally followed by a parenthesised detail.
- Amounts: a number only when the text states it (30% → 0.30; 50 Elemental Mastery → 50). Skill and Burst values
  come from the "Scaling at talent level 10" lines: use them, and say "at talent level 10" in the effect's stacking
  or source detail when you do. Values the text does not give: "unknown", or a short description such as
  "based on Bennett's Base ATK". The Burst's "Energy Cost" line gives behavior.energy.burst_cost.
- Use "unknown" whenever unsure. Never guess. Leave out constellation effects (C0 kit only).
- Only these effect kinds, targets, condition types, roles and reaction keys (vocabulary below). Effects that are
  pure self-damage scaling, utility or flavour can be omitted; buffs, debuffs, shields, heals, energy, infusions,
  reaction conversions and composition conditions must be included.
- Conditions on an effect (party elements, Hexerei count, a reaction that must happen, a state) go in that effect's
  `conditions`. Top-level `conditions` are ONLY party-composition rules the kit's main value depends on
  (party_element_count, party_elements_only, party_elements_forbidden, hexerei_count), never reactions or states.
  party_element_count needs an integer `full` (party members needed for the full effect) stated by the text; if the
  text gives no such number, do not add the condition.
- reactions.requires: reactions that teammates must trigger for the kit's main buff to work (as in the examples);
  reactions the character triggers themselves go in `owns` or `enables`.
- infusion means the character's own attacks are converted to an element. Applying an element to characters or
  enemies is not an infusion.
- provenance: exactly as in the examples, with method llm_extracted, reviewed pending, confidence high for facts read
  directly from the text and medium for behaviour.
- Output: ONLY the YAML document, top-level key = the character's name, written to the response path given at the
  end. No commentary in the file.
"""


def measured_summary(name: str) -> str:
    from gtc.capabilities import load as load_caps

    c = load_caps().get(name)
    if c is None:
        return "No simulation measurements for this character."
    app = ", ".join(f"{k}: {v:.1f}" for k, v in sorted((c.apply or {}).items()) if v >= 0.3) or "none measured"
    return (f"Measured across community simulations (team averages): field share {c.field_share:.0%} of the rotation; "
            f"share of team damage {c.damage_share:.0%}; off-field share of their own damage {c.offfield_share:.0%}; "
            f"element application per rotation (element.on / element.off field): {app}.")


def _vocab() -> str:
    from gtc import kits as K
    from gtc.reactions import BY_KEY

    return "\n".join([f"roles: {', '.join(K.ROLES)}", f"effect kinds: {', '.join(K.EFFECT_KINDS)}",
                      f"targets: {', '.join(K.TARGETS)}", f"condition types: {', '.join(K.CONDITION_TYPES)}",
                      f"damage types: {', '.join(K.DAMAGE_TYPES)}", f"stats: {', '.join(K.STATS)}",
                      f"reaction keys: {', '.join(sorted(BY_KEY))}"])


def examples_for(name: str) -> list[str]:
    ex = [e for e in EXAMPLES if e != name]
    ex += [e for e in EXAMPLE_SPARE if e != name and e not in ex]
    return ex[:2]


def packet(name: str) -> str:
    from gtc import kits as K

    g = _game().get(name) or {}
    ex = examples_for(name)
    ex_yaml = "\n".join(Path(K.KITS_DIR / f"{slug(e)}.yaml").read_text(encoding="utf-8") for e in ex)
    return "\n\n".join([
        f"# Kit extraction packet: {name}", INSTRUCTIONS,
        "## Schema (gtc/kits.py)\n```\n" + (K.__doc__ or "") + "\n```", "## Vocabulary\n" + _vocab(),
        f"## Two reviewed example kits ({', '.join(ex)})\n```yaml\n{ex_yaml}\n```",
        f"## {name}\nElement: {g.get('element')}. Weapon: {_weapon(g.get('weapon'))}.\n\n" + kit_text(name),
        "## Engine measurements\n" + measured_summary(name),
        f"## Response path\n{(RESPONSES / (slug(name) + '.yaml')).as_posix()}",
    ])


def _game() -> dict:
    from gtc import gamedata

    return gamedata.load_characters()


def _weapon(w):
    from gtc.kits import _WEAPON_ALIAS

    return _WEAPON_ALIAS.get(w, w)


def write_packets(names) -> list[Path]:
    PACKETS.mkdir(parents=True, exist_ok=True)
    RESPONSES.mkdir(parents=True, exist_ok=True)
    out = []
    for n in names:
        if not talents(n):
            continue
        p = PACKETS / f"{slug(n)}.md"
        p.write_text(packet(n), encoding="utf-8")
        out.append(p)
    return out


def fill_with_api(name: str, model: str = "claude-opus-5-5") -> Path:
    """Fill one packet through the Anthropic API (needs the anthropic package and ANTHROPIC_API_KEY)."""
    import anthropic

    text = (PACKETS / f"{slug(name)}.md").read_text(encoding="utf-8")
    msg = anthropic.Anthropic().messages.create(model=model, max_tokens=8000, messages=[{"role": "user", "content": text}])
    body = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    body = re.sub(r"^```(?:yaml)?\s*|\s*```\s*$", "", body.strip())
    path = RESPONSES / f"{slug(name)}.yaml"
    path.write_text(body, encoding="utf-8")
    return path


# ---------- compile: check a response ----------

def _grounded_source(source: str, names: list[str]) -> bool:
    s = (source or "").lower()
    return any(n and n.lower() in s for n in names)


def _number_in_text(x, text: str) -> bool:
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return True
    x = abs(x)  # "decreased by 100%" is written as -1.0
    cands = {f"{x:g}"}
    if x > 0 and (x <= 1 or x != int(x)):  # a fraction is written as a percentage in the text (1.008 = 100.8%)
        cands |= {f"{round(x * 100, 2):g}%", f"{x * 100:.1f}%", f"{round(x * 100, 2):g} %"}
    return any(c in text for c in cands)


def check(name: str, kit: dict) -> tuple[dict, list[str], list[str]]:
    """(normalised kit, errors, notes). Errors reject the kit; notes record what was dropped or replaced."""
    from gtc import kits as K

    notes = []
    kit = json.loads(json.dumps(kit))  # deep copy, plain types
    tal = talents(name)
    names = [n for n, _ in tal]
    text = kit_text(name)
    # grounding
    kept = []
    for ef in kit.get("effects") or []:
        if not _grounded_source(ef.get("source"), names):
            notes.append(f"dropped effect {ef.get('kind')} ({ef.get('source')!r}): source names no talent in the text")
        elif not _number_in_text(ef.get("amount"), text):
            notes.append(f"dropped effect {ef.get('kind')} ({ef.get('source')}): amount {ef.get('amount')} not in the text")
        else:
            kept.append(ef)
    kit["effects"] = kept
    # measurement guard
    meas = K.derived_kit(name)
    mb = (meas or {}).get("behavior") or {}
    b = kit.setdefault("behavior", {})
    if mb.get("on_field_damage") in (True, False):
        if b.get("on_field_damage") != mb["on_field_damage"]:
            notes.append(f"on_field_damage {b.get('on_field_damage')} replaced by measured {mb['on_field_damage']}")
            b["on_field_damage"] = mb["on_field_damage"]
        for f, order in (("field_time", ORDER), ("damage_ownership", OWNERSHIP)):
            v, m = b.get(f), mb.get(f)
            if m in order and (v not in order or abs(order.index(v) - order.index(m)) > 1):
                notes.append(f"{f} {v} replaced by measured {m}")
                b[f] = m
        if mb.get("application"):
            b["application"] = mb["application"]
    # function-critical roles: what the engine measured (placement roles) is kept, and owning Swirl is swirl support
    roles = list(kit.get("roles") or [])
    want = set((meas or {}).get("roles") or []) & CRITICAL_ROLES
    if any(str(r).startswith("swirl-") for r in (kit.get("reactions") or {}).get("owns") or []):
        want.add("swirl_support")
    for r in sorted(want - set(roles)):
        notes.append(f"role {r} added (measured placement role or owned Swirl)")
        roles.append(r)
    kit["roles"] = roles
    # provenance
    kit.setdefault("sources", {})
    kit["sources"].setdefault("amber", "Official kit text (Project Amber cache), extracted by an LLM (gtc/kitcompile.py)")
    prov = kit.get("provenance") or {}
    for f, p in list(prov.items()):
        if not isinstance(p, dict):
            prov[f] = p = {}
        p["method"], p["reviewed"] = "llm_extracted", "pending"
        if p.get("confidence") not in ("medium", "low"):
            p["confidence"] = "medium"
        if p.get("source") not in kit["sources"]:
            p["source"] = "amber"
        p.setdefault("span", "talents and passives")
    if "*" not in prov:
        prov["*"] = {"source": "amber", "span": "talents and passives", "confidence": "medium",
                     "method": "llm_extracted", "reviewed": "pending"}
    kit["provenance"] = prov
    kit["compiled"] = True
    _normalise(kit, notes)
    errors = K.validate(name, kit)
    return kit, errors, notes


def slug_names_with_responses() -> set[str]:
    """Characters (game names) that have a response file."""
    have = {p.stem for p in RESPONSES.glob("*.yaml")} if RESPONSES.exists() else set()
    return {n for n in _game() if slug(n) in have}


def _normalise(kit: dict, notes: list) -> None:
    """Generic repairs of encodings the schema already covers: a party_element_count over [all] elements is a count
    of distinct element types (party_element_types); free text in affects.elements is dropped."""
    from gtc.kits import ELEMENTS

    def fix(c):
        if c.get("type") == "party_element_count" and "all" in (c.get("elements") or []):
            c["type"] = "party_element_types"
            c.pop("elements", None)
            notes.append("party_element_count over all elements read as party_element_types")

    for c in kit.get("conditions") or []:
        fix(c)
    for ef in kit.get("effects") or []:
        for c in ef.get("conditions") or []:
            fix(c)
        aff = ef.get("affects") or {}
        els = aff.get("elements")
        if els:
            keep = [e for e in els if e in ELEMENTS + ("Physical", "all")]
            if keep != els:
                notes.append(f"{ef.get('source')}: dropped {[e for e in els if e not in keep]} from affects.elements")
                aff["elements"] = keep or ["all"]


def compile_response(name: str, write: bool = True) -> dict:
    """{"name", "ok", "errors", "notes", "path"} for one response file."""
    path = RESPONSES / f"{slug(name)}.yaml"
    if not path.exists():
        return {"name": name, "ok": False, "errors": ["no response"], "notes": []}
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        return {"name": name, "ok": False, "errors": [f"YAML: {e}"], "notes": []}
    raw = doc.get(name) if isinstance(doc, dict) else None
    if raw is None and isinstance(doc, dict) and len(doc) == 1:
        raw = next(iter(doc.values()))
    if not isinstance(raw, dict):
        return {"name": name, "ok": False, "errors": ["top-level key is not the character"], "notes": []}
    kit, errors, notes = check(name, raw)
    out = {"name": name, "ok": not errors, "errors": errors, "notes": notes, "kit": kit}
    if write and not errors:
        COMPILED_DIR.mkdir(parents=True, exist_ok=True)
        p = COMPILED_DIR / f"{slug(name)}.yaml"
        header = (f"# Compiled by gtc/kitcompile.py from the official kit text (LLM extraction, offline).\n"
                  f"# Not human-reviewed. Checks: {len(notes)} note(s).\n")
        for n in notes:
            header += f"#   {n}\n"
        p.write_text(header + yaml.safe_dump({name: kit}, sort_keys=False, allow_unicode=True, width=120), encoding="utf-8")
        out["path"] = str(p)
    return out


# ---------- validate against the reviewed reference kits ----------

def _eff_key(e: dict) -> tuple:
    t = e.get("target")
    t = "ally" if t in ("party", "party_others", "active", "matching_element_members") else t
    return (e.get("kind"), t)


def score(c: dict, r: dict) -> dict:
    """Field-by-field agreement of a compiled kit `c` with the reviewed kit `r`."""
    cb, rb = c.get("behavior") or {}, r.get("behavior") or {}
    out = {"element": c.get("element") == r.get("element"), "weapon": c.get("weapon") == r.get("weapon")}
    cr, rr = set(c.get("roles") or []), set(r.get("roles") or [])
    out["roles_jaccard"] = round(len(cr & rr) / len(cr | rr), 2) if cr | rr else 1.0
    out["on_field_damage"] = cb.get("on_field_damage") == rb.get("on_field_damage")

    def near(f, order):
        a, b = cb.get(f), rb.get(f)
        return a in order and b in order and abs(order.index(a) - order.index(b)) <= 1

    out["field_time_within_one"] = near("field_time", ORDER)
    out["ownership_within_one"] = near("damage_ownership", OWNERSHIP)
    out["off_field"] = cb.get("off_field") == rb.get("off_field")
    out["burst_cost"] = (cb.get("energy") or {}).get("burst_cost") == (rb.get("energy") or {}).get("burst_cost")
    cs, rs = cb.get("sustain") or {}, rb.get("sustain") or {}
    out["sustain"] = all((cs.get(k) not in (None, "none")) == (rs.get(k) not in (None, "none")) for k in ("heal", "shield"))
    # effects: greedy match by (kind, target class)
    ce, re_ = list(c.get("effects") or []), list(r.get("effects") or [])
    used, matched, amount_ok = set(), 0, 0
    for e in re_:
        for i, x in enumerate(ce):
            if i not in used and _eff_key(x) == _eff_key(e):
                used.add(i)
                matched += 1
                a, b = x.get("amount"), e.get("amount")
                if isinstance(b, (int, float)) and not isinstance(b, bool):
                    amount_ok += int(isinstance(a, (int, float)) and abs(a - b) < 1e-6)
                break
    numeric = sum(1 for e in re_ if isinstance(e.get("amount"), (int, float)) and not isinstance(e.get("amount"), bool))
    out["effect_recall"] = round(matched / len(re_), 2) if re_ else 1.0
    out["effect_precision"] = round(matched / len(ce), 2) if ce else (1.0 if not re_ else 0.0)
    # the same over the effect kinds the mechanical reasoner reads (buffs and debuffs): the reviewed kits leave out
    # heals, shields, cooldowns and utility on purpose, so raw precision partly measures that omission
    from gtc.team_mechanics import BUFF_KINDS

    cb_ = [x for x in ce if x.get("kind") in BUFF_KINDS]
    rb_ = [x for x in re_ if x.get("kind") in BUFF_KINDS]
    used2, m2 = set(), 0
    for e in rb_:
        for i, x in enumerate(cb_):
            if i not in used2 and _eff_key(x) == _eff_key(e):
                used2.add(i)
                m2 += 1
                break
    out["buff_precision"] = round(m2 / len(cb_), 2) if cb_ else (1.0 if not rb_ else 0.0)
    out["buff_recall"] = round(m2 / len(rb_), 2) if rb_ else 1.0
    out["numeric_amounts"] = f"{amount_ok}/{numeric}"

    def ctypes(k):  # party-composition conditions (what kit_conditions and the reasoner read)
        return sorted((x.get("type"), tuple(sorted(x.get("elements") or []))) for x in k.get("conditions") or []
                      if x.get("type") in COMPOSITION)

    out["kit_conditions"] = ctypes(c) == ctypes(r)
    out["reactions_requires"] = sorted((c.get("reactions") or {}).get("requires") or []) == \
        sorted((r.get("reactions") or {}).get("requires") or [])
    return out


def validate_reference(names=None) -> dict:
    """Score compiled reference responses against the reviewed kits (responses must exist; nothing is written to
    knowledge/kits_compiled for reviewed characters)."""
    from gtc import kits as K

    ref = K.reviewed_kits()
    rows = {}
    for n in names or sorted(ref):
        res = compile_response(n, write=False)
        rows[n] = {"ok": res["ok"], "errors": res["errors"], "notes": res["notes"],
                   "score": score(res["kit"], ref[n]) if res.get("kit") and res["ok"] else None}
    scored = [r["score"] for r in rows.values() if r["score"]]

    def rate(f):
        return round(sum(1 for s in scored if s[f] is True) / len(scored), 3) if scored else None

    def mean(f):
        return round(sum(s[f] for s in scored) / len(scored), 3) if scored else None

    summary = {"characters": len(rows), "valid": sum(r["ok"] for r in rows.values())}
    for f in ("element", "weapon", "on_field_damage", "field_time_within_one", "ownership_within_one", "off_field",
              "burst_cost", "sustain", "kit_conditions", "reactions_requires"):
        summary[f] = rate(f)
    for f in ("roles_jaccard", "effect_recall", "effect_precision", "buff_recall", "buff_precision"):
        summary[f] = mean(f)
    num = [tuple(map(int, s["numeric_amounts"].split("/"))) for s in scored]
    summary["numeric_amounts"] = round(sum(a for a, _ in num) / max(1, sum(b for _, b in num)), 3)
    return {"summary": summary, "rows": rows}


# acceptance for population (M8): judged on the reference set, fixed before the run
# Revised after the first (development) run: effect_precision was replaced by buff_precision, because the reviewed
# kits omit non-buff effects by design (40 of the 41 unmatched effects in that run were true kit statements), and
# burst_cost was added once packets carried the Energy Cost line.
ACCEPT = {"valid": 1.0, "on_field_damage": 1.0, "kit_conditions": 0.85, "effect_recall": 0.7, "buff_recall": 0.75,
          "buff_precision": 0.7, "numeric_amounts": 0.8, "burst_cost": 0.9}


def accepted(summary: dict) -> tuple[bool, list[str]]:
    fails = []
    for k, v in ACCEPT.items():
        got = summary["valid"] / summary["characters"] if k == "valid" else summary.get(k)
        if got is None or got < v:
            fails.append(f"{k} {got} < {v}")
    return not fails, fails
