"""Generate imbuements-data.js from the TibiaWiki dump.

A tabela `imbuements` importou vazia (formato diferente — ver CLAUDE.md), então
tudo sai do wikitext em raw_pages: para cada imbuement, os slots de equipamento
que o aceitam, os parâmetros do efeito e os materiais (astral sources) por tier.

Também exporta a lista de crossbows (items.secondary_type = 'Crossbows'): os
slots do wiki distinguem "bows" de "crossbows", mas ambas as categorias viram
"Armas de Distância" no catálogo — o front usa essa lista para desambiguar.
"""
import json
import os
import re

import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://tibiawiki:tibiawiki@127.0.0.1:5432/tibiawiki")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "imbuements-data.js")

TIERS = ["Basic", "Intricate", "Powerful"]

FIELD = lambda name: re.compile(r"^ *\| *%s *= *(.*?) *$" % name, re.M)
F_TYPE = FIELD("type")
F_CAT = FIELD("category")
F_SLOTS = FIELD("slots")
F_SOURCES = FIELD("astralsources")
F_EFFECT = re.compile(r"\{\{Imbuement Effect/[^|}]+((?:\|[^|}]*)*)\}\}")


def parse_page(content):
    out = {}
    for rx, key in ((F_TYPE, "type"), (F_CAT, "cat"), (F_SLOTS, "slots"), (F_SOURCES, "src")):
        m = rx.search(content)
        if m:
            out[key] = m.group(1).strip()
    m = F_EFFECT.search(content)
    out["eff"] = [p.strip() for p in m.group(1).split("|")[1:]] if m else []
    return out


def main():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute(
        """SELECT title, content FROM raw_pages
           WHERE content LIKE '%%Infobox Imbuement%%' AND NOT is_redirect"""
    )
    types = {}
    for row in cur.fetchall():
        m = re.match(r"^(Basic|Intricate|Powerful) (.+)$", row["title"])
        if not m:  # páginas de visão geral ("Featherweight") não têm tier
            continue
        tier, name = m.groups()
        info = parse_page(row["content"])
        t = types.setdefault(name, {"n": name, "cat": "", "slots": [], "tiers": {}})
        if info.get("cat"):
            t["cat"] = info["cat"]
        if info.get("slots"):
            # "helmets (sorcerer)" etc. normaliza para a classe base
            slots = [re.sub(r"\s*\(.*\)", "", s).strip() for s in info["slots"].split(",")]
            t["slots"] = sorted(set(s for s in slots if s))
        t["tiers"][tier] = {"eff": info.get("eff", []), "src": info.get("src", "")}

    cur.execute(
        """SELECT name FROM items
           WHERE secondary_type = 'Crossbows' ORDER BY name"""
    )
    crossbows = [r["name"] for r in cur.fetchall()]

    data = {
        "types": [types[k] for k in sorted(types)],
        "crossbows": crossbows,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("window.IMBUEDATA = ")
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")
    print(f"{len(types)} imbuements, {len(crossbows)} crossbows -> {OUT}")


if __name__ == "__main__":
    main()
