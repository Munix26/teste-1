"""Generate the creature reference data (creatures-data.js) from the wiki dump.

Pulls what the typed tables miss — elemental damage modifiers and max damage
live only in the wikitext — and prices each creature's loot table so the page
can show expected gold per kill.
"""
import json
import os
import re
import sys

import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://tibiawiki:tibiawiki@127.0.0.1:5432/tibiawiki")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "creatures-data.js")

ELEMENTS = ["physical", "earth", "fire", "death", "energy", "holy", "ice"]

# same rarity model as loot_value.py
RARITY = {"always": 1.0, "common": 0.20, "uncommon": 0.05,
          "semi-rare": 0.01, "rare": 0.0025, "very rare": 0.0005}
AMOUNT = {"Gold Coin": 100, "Platinum Coin": 25, "Small Diamond": 2, "Small Ruby": 2,
          "Small Emerald": 2, "Small Sapphire": 2, "Small Amethyst": 3, "Small Topaz": 2,
          "Small Enchanted Ruby": 2, "Small Enchanted Sapphire": 2, "Meat": 3, "Ham": 2}


def field(content, name):
    m = re.search(r"\|\s*" + name + r"\s*=\s*([^\n|]*)", content)
    return m.group(1).strip() if m else ""


def to_int(value):
    m = re.search(r"-?\d+", value or "")
    return int(m.group()) if m else None


def to_pct(value):
    """'125%' -> 125. Empty/unknown -> None (wiki uses '?' a lot)."""
    if not value or "?" in value:
        return None
    return to_int(value)


def loot_gold(content, prices):
    block = re.search(r"\|\s*loot\s*=\s*\{\{Loot Table(.*?)\n\s*\}\}", content, re.S)
    if not block:
        return None
    total = 0.0
    for m in re.finditer(r"\{\{Loot Item\|([^}|]+)(?:\|([^}|]+))?", block.group(1)):
        item = m.group(1).strip()
        if not item or item.isdigit():
            continue
        price = prices.get(item)
        if price is None:
            continue
        rarity = (m.group(2) or "common").strip().lower()
        total += RARITY.get(rarity, 0.05) * price * AMOUNT.get(item, 1)
    return round(total)


def main():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    out = []
    with conn.cursor() as cur:
        cur.execute("SELECT name, npc_value FROM items WHERE npc_value > 0")
        prices = {r["name"]: r["npc_value"] for r in cur.fetchall()}
        prices.setdefault("Gold Coin", 1)
        prices.setdefault("Platinum Coin", 100)

        cur.execute("SELECT title, content FROM raw_pages "
                    "WHERE NOT is_redirect AND content LIKE %s", ("%Infobox Creature%",))
        for row in cur.fetchall():
            c, title = row["content"], row["title"]
            hp, exp = to_int(field(c, "hp")), to_int(field(c, "exp"))
            if not hp or exp is None:
                continue  # summons, effects and other non-huntable entries

            mods = {e: to_pct(field(c, e + "DmgMod")) for e in ELEMENTS}
            maxdmg = re.search(r"\{\{Max Damage\|([^}]*)\}\}", c)
            dmg = {}
            if maxdmg:
                for part in maxdmg.group(1).split("|"):
                    if "=" in part:
                        k, _, v = part.partition("=")
                        n = to_int(v)
                        if n:
                            dmg[k.strip()] = n

            out.append({
                "name": title,
                "hp": hp,
                "exp": exp,
                "ratio": round(exp / hp, 3),
                "armor": to_int(field(c, "armor")),
                "speed": to_int(field(c, "speed")),
                "cls": field(c, "bestiaryclass") or field(c, "creatureclass"),
                "diff": field(c, "bestiarylevel"),
                "boss": field(c, "isboss").lower() == "yes",
                "mods": {k: v for k, v in mods.items() if v is not None},
                "dmg": dmg,
                "maxdmg": sum(dmg.values()) or None,
                "gold": loot_gold(c, prices),
            })
    conn.close()

    out.sort(key=lambda x: -x["exp"])
    with open(OUT, "w") as fh:
        fh.write("window.CREATURES = " + json.dumps(out, ensure_ascii=False) + ";\n")

    with_mods = sum(1 for c in out if c["mods"])
    with_gold = sum(1 for c in out if c["gold"])
    print(f"{len(out)} criaturas ({with_mods} com resistências, {with_gold} com loot precificado)")
    print("->", OUT)


if __name__ == "__main__":
    main()
