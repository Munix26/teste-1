"""Generate the hunting-place data (hunts-data.js) from the TibiaWiki dump.

Each spawn is joined to the creatures listed on its page, so the page can show
aggregate numbers the wiki never computes — average exp/HP and expected gold
per kill for the spawn as a whole.
"""
import json
import os
import re
import sys
from collections import defaultdict

import psycopg2
from psycopg2.extras import RealDictCursor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from loot import gold_range

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://tibiawiki:tibiawiki@127.0.0.1:5432/tibiawiki")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hunts-data.js")

# ordem fixa dos elementos — spawns.html lê como posição, não como chave,
# para não repetir sete nomes por criatura no arquivo de dados
ELEMENTS = ["physical", "fire", "earth", "energy", "ice", "holy", "death"]


def field(content, name):
    m = re.search(r"\|\s*" + name + r"\s*=[ \t]*([^\n|]*)", content)
    return m.group(1).strip() if m else ""


def big_field(content, name):
    m = re.search(r"\|\s*" + name + r"\s*=[ \t]*(.*?)(?=\n\s*\|\s+[a-zA-Z_]+\s*=|\n\s*\}\}\s*$)",
                  content, re.S)
    return m.group(1).strip() if m else ""


def clean(text):
    if not text:
        return ""
    text = re.sub(r"\{\{[Mm]apper Coords[^}]*\}\}", "", text)
    text = re.sub(r"\[\[([^|\]]*\|)?([^\]]+)\]\]", r"\2", text)
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    text = text.replace("'''", "").replace("''", "").replace("<br/>", " ").replace("<br>", " ")
    return re.sub(r"\s+", " ", text).strip(" .,|")


def to_int(value):
    m = re.search(r"-?\d+", (value or "").replace(",", ""))
    return int(m.group()) if m else None


def to_pct(value):
    """'110%' -> 110. Campos com '?' no wiki são palpite, não dado — viram None."""
    if not value or "?" in value:
        return None
    return to_int(value)


def elemental_mods(content):
    """[física, fogo, terra, energia, gelo, holy, death] — None onde o wiki não traz.

    Devolve None se a criatura não tem nenhuma resistência no infobox, para o
    arquivo de dados não carregar sete nulos por criatura sem informação.
    """
    mods = [to_pct(field(content, e + "DmgMod")) for e in ELEMENTS]
    return mods if any(v is not None for v in mods) else None


def creature_stats(rows):
    """name -> {hp, exp, gold, mods} for every creature we can price."""
    out = {}
    for title, content in rows:
        hp, exp = to_int(field(content, "hp")), to_int(field(content, "exp"))
        if not hp or exp is None:
            continue
        out[title] = {"hp": hp, "exp": exp, "content": content,
                      "mods": elemental_mods(content),
                      "boss": field(content, "isboss").lower() == "yes"}
    return out




def parse_creature_list(content):
    """Names inside {{CreatureList|...}} blocks on a hunting-place page."""
    names = []
    for block in re.finditer(r"\{\{CreatureList([^}]*)\}\}", content, re.S):
        for part in block.group(1).split("|"):
            part = part.strip()
            if not part or "=" in part or part.lower().startswith("type"):
                continue
            names.append(part)
    return names


def main():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    with conn.cursor() as cur:
        cur.execute("SELECT name, npc_value FROM items WHERE npc_value > 0")
        prices = {r["name"]: r["npc_value"] for r in cur.fetchall()}
        prices.setdefault("Gold Coin", 1)
        prices.setdefault("Platinum Coin", 100)

        cur.execute("SELECT title, content FROM raw_pages "
                    "WHERE NOT is_redirect AND content LIKE %s", ("%Infobox Creature%",))
        creatures = creature_stats([(r["title"], r["content"]) for r in cur.fetchall()])
        for name, c in creatures.items():
            c["gold"] = gold_range(c.pop("content"), prices)

        cur.execute("SELECT title, content FROM raw_pages "
                    "WHERE NOT is_redirect AND content LIKE %s", ("%Infobox Hunt%",))
        hunt_rows = cur.fetchall()
    conn.close()

    hunts = []
    for row in hunt_rows:
        c, title = row["content"], row["title"]
        levels = [to_int(field(c, f)) for f in ("lvlknights", "lvlpaladins", "lvlmages")]
        levels = [l for l in levels if l]

        names = parse_creature_list(c)
        known = [(n, creatures[n]) for n in names if n in creatures]
        # médias sobre os alvos de farm: sem bosses e sem objetos de 0 exp,
        # que distorceriam a leitura do spawn
        farm = [k for _, k in known if k["exp"] and not k["boss"]]
        exps = [k["exp"] for k in farm]
        hps = [k["hp"] for k in farm if k["hp"]]
        golds = [k["gold"] for k in farm if k["gold"]]  # cada um é [mín, máx]

        hunts.append({
            "n": title,
            "city": field(c, "city"),
            "lvl": min(levels) if levels else None,
            "lvlk": to_int(field(c, "lvlknights")),
            "lvlp": to_int(field(c, "lvlpaladins")),
            "lvlm": to_int(field(c, "lvlmages")),
            "voc": clean(field(c, "vocation")),
            "exps": to_int(field(c, "expstar")),
            "loots": to_int(field(c, "lootstar")),
            "expw": clean(field(c, "exp")),
            "lootw": clean(field(c, "loot")),
            "loc": clean(big_field(c, "location"))[:300],
            "best": [clean(field(c, f"bestloot{s}")) for s in ("", "2", "3", "4", "5")],
            "cr": [{"n": n, "hp": k["hp"], "exp": k["exp"], "gold": k["gold"],
                    **({"m": k["mods"]} if k["mods"] else {}),
                    **({"boss": 1} if k["boss"] else {})} for n, k in known],
            "miss": [n for n in names if n not in creatures],
            # médias do spawn — o wiki não calcula isso
            "avgexp": round(sum(exps) / len(exps)) if exps else None,
            "avghp": round(sum(hps) / len(hps)) if hps else None,
            "ratio": round(sum(exps) / sum(hps), 3) if exps and hps and sum(hps) else None,
            "avggold": [round(sum(g[0] for g in golds) / len(golds)),
                        round(sum(g[1] for g in golds) / len(golds))] if golds else None,
            "impl": field(c, "implemented"),
        })

    hunts.sort(key=lambda h: (-(h["lvl"] or 0), h["n"]))
    with open(OUT, "w") as fh:
        fh.write("window.HUNTS = " + json.dumps(hunts, ensure_ascii=False,
                                                separators=(",", ":")) + ";\n")

    crs = [c for h in hunts for c in h["cr"]]
    print(f"{len(hunts)} spawns — "
          f"{sum(1 for h in hunts if h['cr'])} com criaturas resolvidas, "
          f"{sum(1 for h in hunts if h['lvl'])} com level, "
          f"{sum(1 for h in hunts if h['exps'])} com rating de exp, "
          f"{sum(1 for h in hunts if h['ratio'])} com exp/HP calculado")
    print(f"{len(crs)} criaturas listadas — "
          f"{sum(1 for c in crs if c.get('m'))} com resistências elementais")
    print("->", OUT, f"({os.path.getsize(OUT)/1024:.0f} KB)")


if __name__ == "__main__":
    main()
