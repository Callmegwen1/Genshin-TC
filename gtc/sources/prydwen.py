"""Prydwen (prydwen.gg) Genshin tier list and character guides.

Parsed data per character:
  tiers           per role category: overall tier, Stygian Onslaught boss tiers, tags, assumed constellation
  teams           relative team damage, 100% being that character's best listed team
  constellations  damage gain per constellation, personal and team
  weapons         damage per weapon, team and solo
  energy          Energy Recharge targets per team, columns by constellation
  main_stats      recommended main stat per slot, with comments
  artifact_sets   ranked sets with notes
  synergies       key teammates with role, faction tag (Moonsign, Hexerei...) and why they work
  usage           what players actually run (sets and main stats), from Enka profiles, for every character

Prydwen's own caveat: tiers compare characters only within a role. An On-Field DPS rated T1
is not comparable with a Support rated T1.
"""
from __future__ import annotations

import html as htmllib
import json
import re

from gtc.sources import SOURCE_DIR
from gtc.sources.fetch import get
from gtc.sources.names import prydwen_slug

BASE = "https://www.prydwen.gg/genshin-impact"
OUT_PATH = SOURCE_DIR / "prydwen.json"
TIER_ORDER = ["T0", "T0.5", "T1", "T1.5", "T2", "T3", "T4", "T5"]


def rsc_arrays(page: str, key: str) -> list:
    """Every JSON array stored under `key` in a Next.js flight payload (escaped one level)."""
    marker = '\\"%s\\":[' % key
    out, start = [], 0
    while (i := page.find(marker, start)) >= 0:
        j = i + len(marker) - 1
        depth, k, in_str = 0, j, False
        while k < len(page):
            if page.startswith('\\"', k):
                in_str = not in_str
                k += 2
                continue
            ch = page[k]
            if not in_str:
                if ch == "[":
                    depth += 1
                elif ch == "]":
                    depth -= 1
                    if depth == 0:
                        break
            k += 1
        try:
            out.append(json.loads(json.loads('"' + page[j:k + 1] + '"')))
        except (ValueError, json.JSONDecodeError):
            pass
        start = k
    return out


def _text(fragment: str) -> str:
    return htmllib.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()


def _pct(s: str) -> float | None:
    m = re.search(r"([\d.]+)%", s or "")
    return float(m.group(1)) if m else None


def parse_tiers(page: str, names) -> dict[str, list[dict]]:
    """Character display name to its tier entries, one per role category."""
    out: dict[str, list[dict]] = {}
    seen = set()
    for arr in rsc_arrays(page, "_tierRatings") + rsc_arrays(page, "ratings"):
        for r in arr:
            if not isinstance(r, dict):
                continue
            key = (r.get("slug"), r.get("category"))
            if key in seen or not r.get("slug"):
                continue
            seen.add(key)
            name = names.character(r["slug"])
            if name is None:
                continue
            out.setdefault(name, []).append({
                "category": r.get("category"), "overall": r.get("ratingOverall"),
                "stygian": [r.get(f"ratingBoss{i}") for i in (1, 2, 3)],
                "tags": [t.strip() for t in (r.get("tags") or "").split(",") if t.strip()],
                "assumed_constellation": r.get("dupes"), "trend": r.get("marks") or None,
            })
    return out


def parse_character(page: str, names) -> dict:
    teams = []
    for row in re.findall(r'<div class="team-chart-row[^"]*" style="--team-percent:([\d.]+)%">(.*?)<div class="team-chart-value', page, flags=re.S):
        pct, body = row
        members = []
        for card in re.findall(r'<a class="team-member-card[^"]*" href="/genshin-impact/characters/([^"]+)">(.*?)</a>', body, flags=re.S):
            slug, inner = card
            con = re.search(r'member-constellation">C(\d)', inner)
            er = re.search(r"<span>(\d+) ER</span>", inner)
            members.append({"name": names.character(slug) or slug, "cons": int(con.group(1)) if con else None,
                            "er": int(er.group(1)) if er else None})
        meta = re.search(r'team-chart-meta"><span>(.*?)</span><strong>(.*?)</strong>(?:<em>(.*?)</em>)?', body, flags=re.S)
        teams.append({
            "percent": float(pct), "members": members,
            "label": _text(meta.group(1)) if meta else "", "name": _text(meta.group(2)) if meta else "",
            "description": _text(meta.group(3) or "") if meta else "",
        })

    constellations = []
    start = page.find("constellation-rank-table")
    if start >= 0:
        end = page.find("</section>", start)
        table = page[start:end if end >= 0 else len(page)]
        # Damage dealers get personal and team damage columns; supports often only get commentary.
        rows = re.split(r'<div class="build-rank-row"', table)[1:]
        for row in rows:
            con = re.search(r'constellation-rank-name">C(\d)<', row)
            if not con:
                continue
            nums = [_pct(x) for x in re.findall(r"<strong>([^<]*)</strong>", row)]
            info = re.search(r'constellation-info-body">(.*?)</div>', row, flags=re.S)
            constellations.append({
                "constellation": int(con.group(1)),
                "personal": nums[0] if len(nums) > 0 else None, "team": nums[1] if len(nums) > 1 else None,
                "info": _text(info.group(1)) if info else "",
            })

    weapons = []
    for arr in rsc_arrays(page, "weaponsData")[:1]:
        for w in arr:
            cell = (w.get("cells") or [{}])[0]
            weapons.append({"name": w.get("ref"), "refine": w.get("dupes"), "team": _pct(cell.get("team")),
                            "solo": _pct(cell.get("solo")), "notes": cell.get("notes")})

    energy = [{"team": e.get("label"), "values": e.get("values")} for arr in rsc_arrays(page, "energyData")[:1] for e in arr]
    columns = (rsc_arrays(page, "columns") or [[]])[0]

    from gtc.stats import PRYDWEN_KEYS, parse_priority

    main_stats = {}
    for arr in rsc_arrays(page, "artifactStats")[:1]:
        for r in arr:
            if isinstance(r, dict) and r.get("slot"):
                main_stats[r["slot"].lower()] = {"tiers": parse_priority(r.get("stat", "")), "comment": r.get("comment")}
    artifact_sets = []
    for arr in rsc_arrays(page, "artifactsData")[:1]:
        for r in arr:
            cell = (r.get("cells") or [{}])[0]
            artifact_sets.append({"set": r.get("ref"), "rank": cell.get("team"), "note": cell.get("notes")})
    synergies = [{"name": names.character(x.get("character") or x.get("name", "")) or x.get("name"), "role": x.get("role"),
                  "tag": x.get("tag"), "bullets": x.get("bullets") or [], "description": (x.get("description") or "").strip()}
                 for arr in rsc_arrays(page, "synergies")[:1] for x in arr if isinstance(x, dict)]
    usage = {
        "sets": [{"sets": [n for n in (x.get("nameA"), x.get("nameB")) if n], "share": x.get("percentage")}
                 for arr in rsc_arrays(page, "artifactSets")[:1] for x in arr],
    }
    for slot in ("sands", "goblet", "circlet"):
        usage[slot] = [{"stat": PRYDWEN_KEYS.get(x.get("statType"), x.get("statType")), "share": x.get("percentage")}
                       for arr in rsc_arrays(page, f"{slot}MainStats")[:1] for x in arr]
    return {"teams": teams, "constellations": constellations, "weapons": weapons, "energy": energy,
            "energy_columns": columns, "main_stats": main_stats, "artifact_sets": artifact_sets,
            "synergies": synergies, "usage": usage}


def update(characters: list[str], names) -> dict:
    """Fetch the tier list and each character's guide page. Pages are cached for a week."""
    tier_page = get(f"{BASE}/tier-list", "prydwen")
    updated = re.search(r"Last updated:(?:\s|<[^>]*>)*([0-9]{2}/[A-Za-z]+/[0-9]{4})", tier_page or "")
    version = re.search(r"Genshin Impact Tier List \(([\d.]+)\)", tier_page or "")
    data = {
        "tier_list_updated": updated.group(1) if updated else None,
        "version": version.group(1) if version else None,
        "tiers": parse_tiers(tier_page or "", names),
        "characters": {},
    }
    for name in characters:
        page = get(f"{BASE}/characters/{prydwen_slug(name)}", "prydwen")
        if page:
            data["characters"][name] = parse_character(page, names)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data


def load() -> dict:
    if not OUT_PATH.exists():
        return {"tiers": {}, "characters": {}}
    return json.loads(OUT_PATH.read_text(encoding="utf-8"))
