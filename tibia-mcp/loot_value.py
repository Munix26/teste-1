"""Estimate gold per kill for a set of creatures, from wiki loot tables + NPC prices.

Usage:  python3 tibia-mcp/loot_value.py Werelion Werelioness "White Lion"
"""
import os
import re
import sys

import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://tibiawiki:tibiawiki@127.0.0.1:5432/tibiawiki")

# TibiaWiki rarity buckets -> drop chance commonly used by the community
RARITY = {
    "always": 1.0,
    "common": 0.20,
    "uncommon": 0.05,
    "semi-rare": 0.01,
    "rare": 0.0025,
    "very rare": 0.0005,
}
# stackable loot: average amount per drop
AMOUNT = {"Gold Coin": 100, "Platinum Coin": 25, "Small Diamond": 2, "Small Ruby": 2,
          "Small Emerald": 2, "Small Sapphire": 2, "Small Amethyst": 3, "Small Topaz": 2,
          "Small Enchanted Ruby": 2, "Small Enchanted Sapphire": 2, "Meat": 3, "Ham": 2}


def loot_rows(content):
    """Yield (item, rarity) from the {{Loot Table ...}} block of a creature page."""
    block = re.search(r"\|\s*loot\s*=\s*\{\{Loot Table(.*?)\n\s*\}\}", content, re.S)
    if not block:
        return
    for m in re.finditer(r"\{\{Loot Item\|([^}|]+)(?:\|([^}|]+))?", block.group(1)):
        name = m.group(1).strip()
        if not name or name.isdigit():
            continue
        yield name, (m.group(2) or "common").strip().lower()


def main(creatures):
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    with conn.cursor() as cur:
        cur.execute("SELECT name, npc_value FROM items WHERE npc_value > 0")
        prices = {r["name"]: r["npc_value"] for r in cur.fetchall()}
        prices.setdefault("Gold Coin", 1)
        prices.setdefault("Platinum Coin", 100)

        for cname in creatures:
            cur.execute("SELECT content FROM raw_pages WHERE title = %s", (cname,))
            row = cur.fetchone()
            if not row:
                print(f"\n### {cname}: página não encontrada")
                continue

            total, unpriced, lines = 0.0, [], []
            for item, rarity in loot_rows(row["content"]):
                price = prices.get(item)
                if price is None:
                    unpriced.append(item)
                    continue
                amount = AMOUNT.get(item, 1)
                ev = RARITY.get(rarity, 0.05) * price * amount
                total += ev
                if ev >= 5:
                    lines.append((ev, item, rarity, price, amount))

            print(f"\n### {cname}: {total:,.0f} gp/kill (valor esperado, preço de NPC)")
            for ev, item, rarity, price, amount in sorted(lines, reverse=True)[:8]:
                print(f"   {ev:>8,.0f}  {item} ({rarity}, {price:,}gp x{amount})")
            if unpriced:
                print(f"   sem preço de NPC ({len(unpriced)}): {', '.join(unpriced[:6])}")
    conn.close()


if __name__ == "__main__":
    args = sys.argv[1:] or ["Werelion", "Werelioness", "White Lion"]
    main(args)
