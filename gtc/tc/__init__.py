"""Theorycraft calculator: game formulas plus kits as numbers. See engine.py."""
from __future__ import annotations

import re

from gtc import gamedata
from gtc.sim import Keys, find_config, render, run
from gtc.tc.engine import Theory, load_kits
from gtc.tc.profile import Profile, from_gcsim


def transplant(target_text: str, base_text: str, shared_keys: dict[str, tuple[str, str]]) -> str:
    """Give characters shared with a base config the base config's exact build lines, so two teams are
    compared with identical builds for everyone they have in common. shared_keys maps a display name to
    (key in target, key in base)."""
    pattern = r"\s*{k}\s+(char|add\s+(?:weapon|set|stats))\b"
    out, done = [], set()
    for line in target_text.splitlines():
        hit = next((n for n, (tk, _) in shared_keys.items() if re.match(pattern.format(k=tk), line)), None)
        if hit is None:
            out.append(line)
            continue
        if hit in done:
            continue
        done.add(hit)
        tk, bk = shared_keys[hit]
        for bl in base_text.splitlines():
            if re.match(pattern.format(k=bk), bl):
                out.append(re.sub(rf"^\s*{bk}\b", tk, bl))
    return "\n".join(out)


def profile_for(lineup: list[str], names=None, kits: dict | None = None, base: Profile | None = None,
                base_text: str | None = None, base_keys: dict[str, str] | None = None) -> tuple[Profile, str, dict[str, str]] | None:
    """Damage profile of a lineup from its community gcsim config. With a base config, characters shared
    with the base use the base's builds, so profiles are directly comparable."""
    names = names or gamedata.names()
    kits = kits if kits is not None else load_kits()
    cfg = find_config(lineup, names)
    if cfg is None:
        return None
    text, _ = render(cfg, {}, Keys())
    if base_text and base_keys:
        shared = {n: (cfg.char_keys[n], base_keys[n]) for n in lineup if n in cfg.char_keys and n in base_keys}
        text = transplant(text, base_text, shared)
    r = run(text)
    if r.error:
        return None
    sets = gamedata.names().artifact_set
    lead = base.lead if base and base.lead in lineup else None
    return from_gcsim(r.raw_path, names, kits, gamedata.load_characters(), sets, lead, f"gcsim {cfg.entry_id}"), text, cfg.char_keys
