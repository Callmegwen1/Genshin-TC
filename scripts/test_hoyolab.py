"""Smoke test: confirm HoYoLAB cookies work and the roster is readable."""
import asyncio, os
from pathlib import Path
from dotenv import load_dotenv
import genshin

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

async def main():
    client = genshin.Client(
        {"ltuid_v2": os.environ["LTUID_V2"], "ltoken_v2": os.environ["LTOKEN_V2"], "ltmid_v2": os.environ["LTMID_V2"]},
        game=genshin.Game.GENSHIN,
    )
    uid = int(os.environ["UID"])
    chars = await client.get_genshin_characters(uid)
    print(f"Characters owned: {len(chars)}")
    for c in sorted(chars, key=lambda c: (-c.rarity, -c.level, c.name))[:15]:
        print(f"  {c.name:<22} {c.rarity}* Lv{c.level:<3} C{c.constellation}  {c.element}  weapon: {c.weapon.name} Lv{c.weapon.level} R{c.weapon.refinement}")
    notes = await client.get_genshin_notes(uid)
    print(f"Resin: {notes.current_resin}/{notes.max_resin}")

asyncio.run(main())
