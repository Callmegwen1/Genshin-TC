"""Match character and weapon names across sources.

Every source spells names differently: "Kamisato Ayaka" (game), "kamisato-ayaka" (Prydwen),
"kamisatoayaka" (gcsim), "ayaka" (Keqing Mains). Lowercasing and dropping everything but
letters and digits makes most of them identical. ALIASES covers the rest.
"""
from __future__ import annotations

import re

ALIASES = {
    "childe": "Tartaglia", "raiden": "Raiden Shogun", "ayaka": "Kamisato Ayaka", "ayato": "Kamisato Ayato",
    "kazuha": "Kaedehara Kazuha", "kokomi": "Sangonomiya Kokomi", "itto": "Arataki Itto", "heizou": "Shikanoin Heizou",
    "sara": "Kujou Sara", "kuki": "Kuki Shinobu", "yae": "Yae Miko", "mizuki": "Yumemizuki Mizuki", "bina": "Columbina",
    "hutao": "Hu Tao", "arle": "Arlecchino", "neuv": "Neuvillette", "wrio": "Wriothesley",
}
TRAVELER = re.compile(r"^(aether|lumine|traveler)(anemo|geo|electro|dendro|hydro|pyro|cryo)$")


def norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


class Names:
    def __init__(self, display_names, weapon_rarity: dict[str, int] | None = None, set_names=()):
        self._chars = {norm(n): n for n in display_names}
        self._chars.update({norm(k): v for k, v in ALIASES.items()})
        self._weapons = {norm(k): v for k, v in (weapon_rarity or {}).items()}
        self._weapon_names = {norm(k): k for k in (weapon_rarity or {})}
        self._sets = {norm(n): n for n in set_names}

    def character(self, name: str) -> str | None:
        key = norm(name)
        if key in self._chars:
            return self._chars[key]
        m = TRAVELER.match(key)
        if m:
            return f"Traveler ({m.group(2).capitalize()})"
        return None

    def all_characters(self) -> set[str]:
        return set(self._chars.values())

    def weapon_rarity(self, name: str) -> int | None:
        return self._weapons.get(norm(name))

    def weapon(self, name: str) -> str | None:
        """Display name of a weapon from any spelling: 'FavoniusSword', 'favoniussword', 'Favonius Sword'."""
        return self._weapon_names.get(norm(name))

    def artifact_set(self, name: str) -> str | None:
        return self._sets.get(norm(name))


def kqm_slugs(display: str) -> list[str]:
    """Keqing Mains quickguide slugs to try, most specific first: kamisato-ayaka, then ayaka, then kamisato."""
    words = [w for w in re.split(r"[^a-z0-9]+", display.lower()) if w]
    out = ["-".join(words)]
    if len(words) > 1:
        out += [words[-1], words[0]]
    alias = {v: k for k, v in ALIASES.items()}.get(display)
    if alias:
        out.insert(1, alias)
    return list(dict.fromkeys(out))


def prydwen_slug(display: str) -> str:
    return "-".join(w for w in re.split(r"[^a-z0-9]+", display.lower()) if w)
