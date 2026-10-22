"""Keqing Mains (keqingmains.com) character quickguides.

Keqing Mains publishes few damage numbers in its guides; its value is what a good build and
team look like, and why. Parsed per character:
  formulas         archetype shapes such as "Flins — Electro — Hydro — Anemo / Flex"
  example_teams    concrete lineups with alternatives, and the paragraph explaining each
  teammates        per slot ("Hydro", "Anemo", "Flex"...), ranked options with the reasoning
  talent_priority  e.g. ["burst", "level", "skill"], plus the original line
  er_requirements  Energy Recharge tables: rows by teammate setup, columns by constellation
  main_stats       acceptable main stats per slot, in priority tiers
  substat_priority tiers of substats
  artifact_sets    ranked sets with the pieces each option uses
  weapons          ranked weapons with rarity and notes
  pros, cons       the character overview lists
"""
from __future__ import annotations

import html as htmllib
import json
import re

from gtc.sources import SOURCE_DIR
from gtc.sources.fetch import get
from gtc.sources.names import kqm_slugs

BASE = "https://keqingmains.com/q"
OUT_PATH = SOURCE_DIR / "kqm.json"
DASH = re.compile(r"\s+[—–-]\s+")


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def _slots(line: str, names) -> list[list[str]]:
    """'Flins — Ineffa — Columbina/Aino — Sucrose' becomes [[Flins], [Ineffa], [Columbina, Aino], [Sucrose]].
    Words that are not characters, like 'Electro' or 'Flex', are kept as placeholders."""
    out = []
    for slot in DASH.split(line):
        options = [o.strip() for o in slot.split("/") if o.strip()]
        out.append([names.character(o) or o for o in options])
    return out


def _list_after(text_lines: list[str], header: str, stop: set[str]) -> list[str]:
    try:
        i = text_lines.index(header)
    except ValueError:
        return []
    out = []
    for line in text_lines[i + 1:]:
        if line in stop:
            break
        out.append(line)
    return out


TABLE_ROW = re.compile(r"<tr>(.*?)</tr>", re.S)
CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
RANGE = re.compile(r"(\d+)\s*(?:[–-]\s*(\d+))?\s*%")


def _section(page: str, anchor: str) -> str:
    """HTML from the heading with this id to the next heading of level 1 or 2. Guides with several
    playstyles prefix their ids ('Support_ER_Requirements'), so a suffix match is accepted too."""
    m = re.search(rf'id="((?:[A-Za-z0-9-]+_)?{re.escape(anchor)})"', page)
    if not m:
        return ""
    i = m.start()
    ends = [x for x in (page.find("<h2", i + 10), page.find("<h1", i + 10)) if x > 0]
    return page[i:min(ends) if ends else len(page)]


def _rows(fragment: str) -> list[list[str]]:
    return [[_text(c) for c in CELL.findall(r)] for r in TABLE_ROW.findall(fragment)]


def _ranked(fragment: str) -> list[tuple[str, str]]:
    """Two-column 'weapon-table' rows: bold name, explanation. Used for sets, weapons and teammates."""
    out = []
    for r in TABLE_ROW.findall(fragment):
        cells = CELL.findall(r)
        if len(cells) >= 2:
            title = re.search(r"<strong>(.*?)</strong>", cells[0], flags=re.S)
            out.append((_text(title.group(1) if title else cells[0]), _text(cells[1])))
    return out


TALENT_WORDS = {"burst": "burst", "elemental burst": "burst", "skill": "skill", "elemental skill": "skill",
                "normal attack": "normal", "normal attacks": "normal", "normal": "normal", "na": "normal", "attack": "normal"}


def parse_talent_priority(line: str) -> list[str]:
    out = []
    for tier in re.split(r"\s*(?:>|=|≥)\s*", line):
        t = tier.strip().lower()
        if t.startswith("level"):
            out.append("level")
        elif t in TALENT_WORDS:
            out.append(TALENT_WORDS[t])
    return out


def parse_set_option(title: str) -> dict:
    """'4pc Night of the Sky's Unveiling (NotSU)' or '2pc Gladiator's (Glad) + 2pc Shimenawa's'."""
    pieces = []
    for part in re.split(r"\s+\+\s+", title):
        m = re.match(r"(\d)\s*pc\s+(.*)", part.strip(), flags=re.I)
        if m:
            pieces.append({"count": int(m.group(1)), "set": re.sub(r"\s*\([^)]*\)\s*$", "", m.group(2)).strip()})
    return {"title": title, "pieces": pieces}


def parse_build(page: str, names) -> dict:
    from gtc.stats import parse_priority

    highlighted = lambda html: [_text(x) for x in re.findall(r'class="[^"]*substats[^"]*"[^>]*>(.*?)</p>', html, flags=re.S)]
    tp_lines = [l for l in highlighted(_section(page, "Talents")) if "priority" not in l.lower()]
    tp_text = tp_lines[0] if tp_lines else ""

    er_tables = []
    for table in re.findall(r"<table.*?</table>", _section(page, "ER_Requirements"), flags=re.S):
        rows = _rows(table)
        if len(rows) >= 2:
            body = []
            # Some tables have no label column: every header cell is a team setup and every body cell a range.
            no_label = all(len(r) == len(rows[0]) and RANGE.search(r[0] or "") for r in rows[1:])
            header = [""] + rows[0] if no_label else rows[0]
            for r in rows[1:]:
                vals = []
                if no_label:
                    r = [""] + r
                for cell in r[1:]:
                    m = RANGE.search(cell)
                    vals.append([int(m.group(1)), int(m.group(2) or m.group(1))] if m else None)
                body.append({"label": r[0], "names": [names.character(x.strip()) for x in r[0].split("/") if names.character(x.strip())], "values": vals})
            er_tables.append({"columns": header[1:], "rows": body})

    stats = _section(page, "Artifact_Stats")
    main_stats = {}
    rows = _rows(stats.split("</table>")[0]) if "<table" in stats else []
    if len(rows) >= 2:
        for slot, value in zip(rows[0], rows[1]):
            main_stats[slot.strip().lower()] = parse_priority(value)
    sp = [l for l in highlighted(stats) if "stat priority" in l.lower()]
    sub_text = re.sub(r"(?i)^.*?stat priority\s*:?\s*", "", sp[0]) if sp else ""

    sets = [{**parse_set_option(t), "note": n} for t, n in _ranked(_section(page, "Artifact_Sets"))]
    weapons = []
    for t, n in _ranked(_section(page, "Weapons")):
        m = re.match(r"(\d)\s*★\s*(.*)", t)
        for name in re.split(r"\s*,\s*|\s+/\s+", m.group(2) if m else t):
            name = re.sub(r"\s*\([^)]*\)$", "", name).strip()
            if name:
                weapons.append({"name": name, "rarity": int(m.group(1)) if m else None, "note": n})

    teammates = []
    tb = re.search(r'id="(?:[A-Za-z0-9-]+_)?Teambuilding"', page)
    team_start = tb.start() if tb else -1
    team_html = page[team_start:page.find("Example Teams", team_start)] if team_start >= 0 else ""
    for panel in re.findall(r'<div class="ub-content-filter-panel"[^>]*>(.*?)(?=<div class="ub-content-filter-panel"|</div>\s*</div>\s*<h)', team_html, flags=re.S):
        head = re.search(r"<h4[^>]*>(.*?)</h4>", panel, flags=re.S)
        intro = re.search(r"</h4>\s*<p>(.*?)</p>", panel, flags=re.S)
        options = [{"name": names.character(x) or x, "note": n} for t, n in _ranked(panel)
                   for x in re.split(r"\s*,\s*|\s+/\s+", t) if x]
        if head and options:
            teammates.append({"slot": _text(head.group(1)), "intro": _text(intro.group(1)) if intro else "", "options": options})

    return {
        "talent_priority": {"line": tp_text, "order": parse_talent_priority(tp_text)},
        "er_requirements": er_tables,
        "main_stats": main_stats,
        "substat_priority": {"line": sub_text, "tiers": parse_priority(sub_text)},
        "artifact_sets": sets,
        "weapons": weapons,
        "teammates": teammates,
    }


def parse_guide(page: str, names) -> dict:
    example_teams = []
    start = page.find("Example Teams")
    if start >= 0:
        section = page[start:]
        captions = list(re.finditer(r"<figcaption[^>]*>(.*?)</figcaption>", section, flags=re.S))
        for i, cap in enumerate(captions):
            line = _text(cap.group(1))
            if not DASH.search(line):
                continue
            end = captions[i + 1].start() if i + 1 < len(captions) else len(section)
            first_para = re.search(r"<p>(.*?)</p>", section[cap.end():end], flags=re.S)
            example_teams.append({"line": line, "slots": _slots(line, names), "description": _text(first_para.group(1)) if first_para else ""})

    plain = [l for l in re.split(r"\n+", htmllib.unescape(re.sub(r"<[^>]+>", "\n", re.sub(r"<script.*?</script>|<style.*?</style>", "", page, flags=re.S)))) if l.strip()]
    plain = [l.strip() for l in plain]
    team_lines = {t["line"] for t in example_teams}
    known = names.all_characters()
    formulas = sorted({
        l for l in plain
        if l.count("—") >= 3 and len(l) < 80 and l not in team_lines and not l.rstrip().endswith("/")
        and any(o not in known for slot in _slots(l, names) for o in slot)
    })
    return {
        "formulas": formulas,
        "example_teams": example_teams,
        "pros": _list_after(plain, "Pros", {"Cons"}),
        "cons": _list_after(plain, "Cons", {"Playstyles", "Character Overview"}),
        **parse_build(page, names),
    }


def update(characters: list[str], names) -> dict:
    data = {}
    for name in characters:
        for slug in kqm_slugs(name):
            url = f"{BASE}/{slug}-quickguide/"
            page = get(url, "kqm")
            if page:
                data[name] = {"url": url, **parse_guide(page, names)}
                break
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data


def load() -> dict:
    if not OUT_PATH.exists():
        return {}
    return json.loads(OUT_PATH.read_text(encoding="utf-8"))
