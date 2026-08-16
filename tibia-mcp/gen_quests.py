"""Generate quests-data.js from the TibiaWiki dump.

A tabela `quests` importou bem (371 linhas com level, recompensa, local e
perigos), mas `duration`/`team`/`difficulty`/`spoiler` vieram vazias — a página
de quests linka o spoiler do wiki em vez de reproduzi-lo.

Os itens de recompensa saem do wikitext ([[links]] do campo reward em
raw_pages), filtrados contra a tabela items — é o que permite mostrar cada
recompensa com sprite e link para a ficha do item.
"""
import json
import os
import re

import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://tibiawiki:tibiawiki@127.0.0.1:5432/tibiawiki")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "quests-data.js")

WIKILINK = re.compile(r"\[\[([^\]|]*)(?:\|([^\]]*))?\]\]")
FILE_TOKEN = re.compile(r"(?:File|Image):[^,\n]*?\.(?:gif|png|jpe?g)", re.I)
# campo multi-linha do infobox: termina no próximo " | chave =" (ver CLAUDE.md)
REWARD_FIELD = re.compile(r"^ *\| *reward[ \t]*=[ \t]*(.*?)(?=^ \| [a-z_]+[ \t]*=|\Z)", re.M | re.S)


def clean(text):
    if not text:
        return ""
    text = WIKILINK.sub(lambda m: m.group(2) or m.group(1), text)
    text = FILE_TOKEN.sub("", text)
    return re.sub(r"[ \t]+", " ", text).strip(" ,\n")


def main():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("SELECT lower(name) AS n FROM items")
    item_names = {r["n"] for r in cur.fetchall()}

    cur.execute(
        """SELECT q.name, q.reward, q.location, q.level, q.level_req, q.premium,
                  q.dangers, q.implemented, q.notes, r.content
           FROM quests q LEFT JOIN raw_pages r ON r.page_id = q.page_id
           ORDER BY q.name"""
    )
    quests = []
    for row in cur.fetchall():
        # itens de recompensa: [[links]] do wikitext que existem no catálogo
        ritems = []
        if row["content"]:
            m = REWARD_FIELD.search(row["content"])
            if m:
                seen = set()
                for link in WIKILINK.finditer(m.group(1)):
                    name = (link.group(1) or "").strip()
                    if name.lower() in item_names and name.lower() not in seen:
                        seen.add(name.lower())
                        ritems.append(name)
        q = {
            "n": row["name"],
            "lvl": row["level"],
            "req": row["level_req"],
            "prem": bool(row["premium"]),
            "loc": clean(row["location"]),
            "rw": clean(row["reward"]),
            "ri": ritems,
            "dg": clean(row["dangers"]),
            "impl": row["implemented"] or "",
            "no": clean(row["notes"]),
        }
        quests.append({k: v for k, v in q.items() if v not in (None, "", [], False)})

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("window.QUESTS = ")
        json.dump(quests, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")
    print(f"{len(quests)} quests, {sum(1 for q in quests if q.get('ri'))} com itens de recompensa -> {OUT}")


if __name__ == "__main__":
    main()
