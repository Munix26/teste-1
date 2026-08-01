"""Shared parsing of creature loot tables.

Two things here are easy to get wrong, so they live in one place:

1. The {{Loot Item}} template has two shapes — with and without an amount:
       {{Loot Item|Platinum Coin|common}}
       {{Loot Item|1-8|Platinum Coin|common}}
   Half the creature pages use the second one. Reading the first parameter as
   the item name silently loses those drops.

2. The wiki documents rarity as *ranges*, not points (Rareness page, taken from
   the Bestiary classification). We keep the bounds and report gold per kill as
   a range, because picking a single number inside the range would be inventing
   precision the wiki does not have.
"""
import re

# Rareness page: label -> (chance mínima, chance máxima)
RARITY_BOUNDS = {
    "always": (1.0, 1.0),
    "common": (0.25, 1.0),
    "uncommon": (0.05, 0.25),
    "semi-rare": (0.01, 0.05),
    "rare": (0.005, 0.01),
    "very rare": (0.0, 0.005),
}

LOOT_ITEM = re.compile(r"\{\{Loot Item\|([^{}]*?)\}\}")


def parse_amount(token):
    """'1-8' -> (1, 8, 4.5); '3' -> (3, 3, 3.0); anything else -> None."""
    m = re.fullmatch(r"\s*(\d+)\s*(?:-\s*(\d+))?\s*", token)
    if not m:
        return None
    lo = int(m.group(1))
    hi = int(m.group(2)) if m.group(2) else lo
    return lo, hi, (lo + hi) / 2


def loot_items(content):
    """Yield {name, rarity, amount_avg, amount_lo, amount_hi} for one creature."""
    block = re.search(r"\|\s*loot\s*=\s*\{\{Loot Table(.*?)\n\s*\}\}", content, re.S)
    if not block:
        return
    for m in LOOT_ITEM.finditer(block.group(1)):
        parts = [p.strip() for p in m.group(1).split("|")]
        parts = [p for p in parts if p]
        if not parts:
            continue

        amount = parse_amount(parts[0])
        if amount and len(parts) > 1:
            lo, hi, avg = amount
            name = parts[1]
            rarity = parts[2].lower() if len(parts) > 2 else "common"
        else:
            lo = hi = 1
            avg = 1.0
            name = parts[0]
            rarity = parts[1].lower() if len(parts) > 1 else "common"

        if not name or parse_amount(name):
            continue
        if rarity not in RARITY_BOUNDS:
            rarity = "common"
        yield {"name": name, "rarity": rarity,
               "amount": avg, "amount_lo": lo, "amount_hi": hi}


def gold_range(content, prices):
    """(min, max) expected gold per kill, using the wiki's chance bounds.

    Items with no NPC price (Market-only) contribute nothing — the figure is a
    floor, not a full valuation.
    """
    lo_total = hi_total = 0.0
    priced = 0
    for it in loot_items(content):
        price = prices.get(it["name"])
        if price is None:
            continue
        priced += 1
        lo, hi = RARITY_BOUNDS[it["rarity"]]
        lo_total += lo * price * it["amount_lo"]
        hi_total += hi * price * it["amount_hi"]
    if not priced:
        return None
    return round(lo_total), round(hi_total)
