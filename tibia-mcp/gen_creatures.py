"""Generate the creature reference data (creatures-data.js) from the wiki dump.

Captures everything the detail view can show — most of it (elemental modifiers,
abilities, behaviour flags, loot) lives only in the wikitext, not in the typed
tables — and prices each loot table so the page can show expected gold per kill.
"""
import json
import os
import re

import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://tibiawiki:tibiawiki@127.0.0.1:5432/tibiawiki")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "creatures-data.js")

ELEMENTS = ["physical", "earth", "fire", "death", "energy", "holy", "ice",
            "drown", "hpDrain"]

# same rarity model as loot_value.py
RARITY = {"always": 1.0, "common": 0.20, "uncommon": 0.05,
          "semi-rare": 0.01, "rare": 0.0025, "very rare": 0.0005}
AMOUNT = {"Gold Coin": 100, "Platinum Coin": 25, "Small Diamond": 2, "Small Ruby": 2,
          "Small Emerald": 2, "Small Sapphire": 2, "Small Amethyst": 3, "Small Topaz": 2,
          "Small Enchanted Ruby": 2, "Small Enchanted Sapphire": 2, "Meat": 3, "Ham": 2}

# infobox flag -> label shown in the detail panel
FLAGS = [("pushable", "Empurrável"), ("pushobjects", "Empurra objetos"),
         ("illusionable", "Illusionable"), ("paraimmune", "Imune a paralyse"),
         ("senseinvis", "Enxerga invisível"), ("walksaround", "Desvia de"),
         ("walksthrough", "Atravessa"), ("usespells", "Usa spells")]


def field(content, name):
    m = re.search(r"\|\s*" + name + r"\s*=\s*([^\n|]*)", content)
    return m.group(1).strip() if m else ""


def big_field(content, name):
    """Fields whose value spans lines, up to the next top-level ' | key ='.

    Top-level fields are written ' | key = '; nested template params are
    written '|key=' with no space after the pipe, so requiring whitespace
    there keeps blocks like abilities= (which contain |scene=) intact.
    """
    # [ \t]* after '=' so an empty field does not swallow the next line
    m = re.search(r"\|\s*" + name + r"\s*=[ \t]*(.*?)(?=\n\s*\|\s+[a-zA-Z_]+\s*=|\n\s*\}\}\s*$)",
                  content, re.S)
    return m.group(1).strip() if m else ""


def clean(text):
    if not text:
        return ""
    text = re.sub(r"\{\{[Ii]link\|[^}]*\}\}", "", text)
    text = re.sub(r"\[\[([^|\]]*\|)?([^\]]+)\]\]", r"\2", text)
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    text = text.replace("'''", "").replace("''", "").replace("<br/>", " ").replace("<br>", " ")
    return re.sub(r"\s+", " ", text).strip(" .|")


def to_int(value):
    m = re.search(r"-?\d+", value or "")
    return int(m.group()) if m else None


def to_pct(value):
    if not value or "?" in value:
        return None
    return to_int(value)


def parse_abilities(content):
    """Return [{name, dmg, el}] from the {{Ability List}} block."""
    block = big_field(content, "abilities")
    if not block:
        return []
    out = []
    for m in re.finditer(r"\{\{(Melee|Ability|Haste|Healing|Summon)\s*([^{}]*)", block):
        kind, rest = m.group(1), m.group(2)
        # {{Ability List — the wrapper, not an ability itself
        if kind == "Ability" and rest.strip().startswith("List"):
            continue
        # a wikilink like [[Physical Damage|Green Sparkles]] carries a pipe that
        # is not a parameter separator — shield it before splitting
        rest = re.sub(r"\[\[[^\]]*\]\]", lambda m: m.group(0).replace("|", "\x00"), rest)
        named, positional = {}, []
        for p in (x.replace("\x00", "|").strip() for x in rest.split("|") if x.strip()):
            if "=" in p:
                k, _, v = p.partition("=")
                named[k.strip()] = v.strip()
            else:
                positional.append(p)
        if kind == "Melee":
            out.append({"name": "Melee", "dmg": clean(positional[0]) if positional else "",
                        "el": "physical"})
        elif kind == "Ability":
            out.append({"name": clean(positional[0]) if positional else "Ability",
                        "dmg": clean(positional[1]) if len(positional) > 1 else "",
                        "el": clean(named.get("element")
                                    or (positional[2] if len(positional) > 2 else ""))})
        else:
            out.append({"name": kind, "dmg": "", "el": ""})
    return out[:14]


def parse_loot(content, prices):
    """Return (items, expected_gold). Items carry rarity and NPC price."""
    block = re.search(r"\|\s*loot\s*=\s*\{\{Loot Table(.*?)\n\s*\}\}", content, re.S)
    if not block:
        return [], None
    items, total = [], 0.0
    for m in re.finditer(r"\{\{Loot Item\|([^}|]+)(?:\|([^}|]+))?", block.group(1)):
        name = m.group(1).strip()
        if not name or name.isdigit():
            continue
        rarity = (m.group(2) or "common").strip().lower()
        price = prices.get(name)
        items.append({"n": name, "r": rarity, "p": price})
        if price is not None:
            total += RARITY.get(rarity, 0.05) * price * AMOUNT.get(name, 1)
    return items, round(total)


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

            dmg = {}
            maxdmg = re.search(r"\{\{Max Damage\|([^}]*)\}\}", c)
            if maxdmg:
                for part in maxdmg.group(1).split("|"):
                    if "=" in part:
                        k, _, v = part.partition("=")
                        n = to_int(v)
                        if n:
                            dmg[k.strip()] = n

            mods = {}
            for e in ELEMENTS:
                v = to_pct(field(c, e + "DmgMod"))
                if v is not None:
                    mods[e] = v

            loot, gold = parse_loot(c, prices)
            flags = {k: field(c, k).lower() for k, _ in FLAGS}

            out.append({
                "name": title,
                "hp": hp,
                "exp": exp,
                "ratio": round(exp / hp, 3),
                "armor": to_int(field(c, "armor")),
                "mit": field(c, "mitigation") or None,
                "speed": to_int(field(c, "speed")),
                "cls": field(c, "bestiaryclass") or field(c, "creatureclass"),
                "diff": field(c, "bestiarylevel"),
                "occ": field(c, "occurrence"),
                "boss": field(c, "isboss").lower() == "yes",
                "type": field(c, "primarytype"),
                "atktype": field(c, "attacktype"),
                "spawn": field(c, "spawntype"),
                "summon": to_int(field(c, "summon")),
                "convince": to_int(field(c, "convince")),
                "mods": mods,
                "heal": to_pct(field(c, "healMod")),
                "dmg": dmg,
                "maxdmg": sum(dmg.values()) or None,
                "abil": parse_abilities(c),
                "flags": {k: v for k, v in flags.items() if v},
                "loot": loot,
                "gold": gold,
                "loc": clean(big_field(c, "location"))[:400],
                "behav": clean(big_field(c, "behaviour"))[:400],
                "strat": clean(big_field(c, "strategy"))[:500],
                "text": clean(big_field(c, "bestiarytext"))[:600],
                "sounds": [clean(s) for s in re.findall(r"\{\{Sound\|([^}]*)\}\}", c)][:6],
            })
    conn.close()

    out.sort(key=lambda x: -x["exp"])
    with open(OUT, "w") as fh:
        fh.write("window.CREATURES = " + json.dumps(out, ensure_ascii=False,
                                                    separators=(",", ":")) + ";\n")

    stats = {
        "resistências": sum(1 for c in out if c["mods"]),
        "loot": sum(1 for c in out if c["loot"]),
        "habilidades": sum(1 for c in out if c["abil"]),
        "localização": sum(1 for c in out if c["loc"]),
        "estratégia": sum(1 for c in out if c["strat"]),
    }
    print(f"{len(out)} criaturas — " + ", ".join(f"{v} com {k}" for k, v in stats.items()))
    print("->", OUT, f"({os.path.getsize(OUT)/1024:.0f} KB)")


if __name__ == "__main__":
    main()
