"""Generate the full item catalogue (items-data.js) from the TibiaWiki dump.

Covers every item on the wiki, not just gear: quest and delivery-task items,
creature products, tools, valuables and so on. Each item carries a reverse
drop index (which creatures drop it, and where those creatures live) built by
inverting every creature loot table, plus the NPCs that trade it.
"""
import json
import os
import re
from collections import defaultdict

import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://tibiawiki:tibiawiki@127.0.0.1:5432/tibiawiki")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "items-data.js")

# primarytype -> friendly category. Anything unmatched falls back to objectclass.
CATEGORY = {
    "Distance Weapons": "Armas de Distância", "Ammunition": "Munição",
    "Quivers": "Aljavas", "Helmets": "Capacetes", "Armors": "Armaduras",
    "Legs": "Pernas", "Boots": "Botas", "Shields": "Escudos",
    "Amulets and Necklaces": "Amuletos", "Rings": "Anéis",
    "Extra Slot Items": "Slot Extra", "Extra Slot": "Slot Extra",
    "Sword Weapons": "Espadas", "Axe Weapons": "Machados",
    "Club Weapons": "Clavas", "Wands": "Wands", "Rods": "Rods",
    "Spellbooks": "Spellbooks", "Throwing Weapons": "Armas de Arremesso",
    "Runes": "Runas", "Potions": "Poções", "Creature Products": "Produtos de Criatura",
    "Quest Items": "Itens de Quest", "Valuables": "Valiosos", "Food": "Comida",
    "Containers": "Containers", "Tools (Objects)": "Ferramentas",
    "Light Sources": "Fontes de Luz", "Keys": "Chaves",
    "Imbuement Scrolls": "Pergaminhos de Imbuement", "Soul Cores": "Soul Cores",
    "Documents and Papers": "Documentos", "Musical Instruments": "Instrumentos",
    "Decorations": "Decoração", "Furniture": "Mobília",
}
FALLBACK = {
    "Household Items": "Casa e Decoração", "Plants, Animal Products, Food and Drink": "Plantas e Alimentos",
    "Body Equipment": "Equipamento", "Weapons": "Armas", "Constructions": "Construções",
    "Flora and Minerals": "Flora e Minerais", "Utilities": "Utilidades",
    "Living and Dead": "Vivos e Mortos", "Tools and other Equipment": "Ferramentas",
    "Flooring": "Pisos", "Wall Coverings": "Paredes", "Navigation": "Navegação",
    "Functional Objects": "Objetos Funcionais", "Magical Effects": "Efeitos Mágicos",
    "Signage": "Placas", "Rubbish": "Lixo", "Other Objects": "Outros",
    "Other Items": "Outros",
}

RARITY_ORDER = ["always", "common", "uncommon", "semi-rare", "rare", "very rare"]

# nomes de atributo normalizados para virar filtro (facet)
ATTR_ALIASES = [
    ("distance fighting", "Distance"), ("sword fighting", "Sword"),
    ("axe fighting", "Axe"), ("club fighting", "Club"), ("shielding", "Shielding"),
    ("fist fighting", "Fist"), ("holy magic level", "Magic Level (holy)"),
    ("death magic level", "Magic Level (death)"), ("fire magic level", "Magic Level (fire)"),
    ("ice magic level", "Magic Level (ice)"), ("earth magic level", "Magic Level (earth)"),
    ("energy magic level", "Magic Level (energy)"), ("magic level", "Magic Level"),
    ("speed", "Speed"), ("regeneration", "Regeneração"), ("mana", "Mana"),
    ("health", "Vida"), ("critical", "Crítico"), ("protection", "Proteção"),
]
ELEMENTS = ["physical", "fire", "earth", "energy", "ice", "holy", "death",
            "life drain", "mana drain", "drowning"]


def attr_facets(attrib):
    """'distance fighting +3, holy magic level +1' -> ['Distance', 'Magic Level (holy)']"""
    if not attrib:
        return []
    low = attrib.lower()
    found = []
    for needle, label in ATTR_ALIASES:
        if needle in low and label not in found:
            # 'magic level' genérico não deve capturar 'holy magic level'
            if needle == "magic level" and re.search(r"(holy|death|fire|ice|earth|energy) magic level", low):
                continue
            found.append(label)
    return found


def resist_facets(resist):
    """'fire +5%, earth -5%' -> [['fire', 5], ['earth', -5]]"""
    if not resist:
        return []
    out = []
    for m in re.finditer(r"([a-z ]+?)\s*([+-]?\d+)\s*%", resist.lower()):
        el = m.group(1).strip()
        if el in ELEMENTS:
            out.append([el, int(m.group(2))])
    return out


def parse_delivery_tasks(content):
    """Delivery Task page -> {item: [min, max, npc_buy_price]}"""
    out = {}
    for m in re.finditer(r"\|\s*\{\{ilink\|[^}]*\}\}\s*\|\|\s*\[\[([^\]|]+)(?:\|[^\]]*)?\]\]"
                         r"\s*\|\|\s*([\d,]+)\s*\|\|\s*([\d,]+)\s*\|\|\s*([\d,]+)", content):
        name = m.group(1).strip()
        out[name] = [int(m.group(2).replace(",", "")),
                     int(m.group(3).replace(",", "")),
                     int(m.group(4).replace(",", ""))]
    return out


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
    text = re.sub(r"\{\{[Ii]link\|[^}]*\}\}", "", text)
    text = re.sub(r"\[\[([^|\]]*\|)?([^\]]+)\]\]", r"\2", text)
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    text = text.replace("'''", "").replace("''", "").replace("<br/>", " ").replace("<br>", " ")
    return re.sub(r"\s+", " ", text).strip(" .|")


def to_int(value):
    m = re.search(r"-?\d+", (value or "").replace(",", ""))
    return int(m.group()) if m else None


def build_drop_index(rows):
    """creature loot tables -> {item name: [(creature, rarity)]}"""
    index = defaultdict(list)
    creatures = {}
    for title, content in rows:
        loc = clean(big_field(content, "location"))[:180]
        creatures[title] = loc
        block = re.search(r"\|\s*loot\s*=\s*\{\{Loot Table(.*?)\n\s*\}\}", content, re.S)
        if not block:
            continue
        for m in re.finditer(r"\{\{Loot Item\|([^}|]+)(?:\|([^}|]+))?", block.group(1)):
            item = m.group(1).strip()
            if not item or item.isdigit():
                continue
            index[item].append((title, (m.group(2) or "common").strip().lower()))
    return index, creatures


def main():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    with conn.cursor() as cur:
        cur.execute("SELECT title, content FROM raw_pages "
                    "WHERE NOT is_redirect AND content LIKE %s", ("%Infobox Creature%",))
        drops, creature_loc = build_drop_index([(r["title"], r["content"]) for r in cur.fetchall()])

        cur.execute("SELECT title, content FROM raw_pages "
                    "WHERE NOT is_redirect AND content LIKE %s", ("%Infobox Object%",))
        item_rows = cur.fetchall()

        cur.execute("SELECT content FROM raw_pages WHERE title = 'Delivery Task'")
        row = cur.fetchone()
        delivery = parse_delivery_tasks(row["content"]) if row else {}
    conn.close()

    # creatures referenced by any drop, stored once and referenced by index
    referenced = sorted({c for lst in drops.values() for c, _ in lst})
    cidx = {name: i for i, name in enumerate(referenced)}
    creature_table = [[n, creature_loc.get(n, "")] for n in referenced]

    items = []
    for row in item_rows:
        c, title = row["content"], row["title"]
        ptype = field(c, "primarytype")
        oclass = field(c, "objectclass")
        cat = CATEGORY.get(ptype) or FALLBACK.get(oclass) or (ptype or oclass or "Outros")

        by = sorted(drops.get(title, []), key=lambda x: RARITY_ORDER.index(x[1])
                    if x[1] in RARITY_ORDER else 9)
        attrib = clean(field(c, "attrib"))
        resist = clean(field(c, "resist"))
        items.append({
            "af": attr_facets(attrib),
            "rf": resist_facets(resist),
            "dt": delivery.get(title),
            "n": title,
            "c": cat,
            "t": ptype or oclass,
            "lvl": to_int(field(c, "levelrequired")),
            "voc": field(c, "vocrequired"),
            "arm": to_int(field(c, "armor")),
            "atk": clean(field(c, "atk_mod") or field(c, "attack")),
            "hit": clean(field(c, "hit_mod")),
            "def": clean(field(c, "defense")),
            "at": attrib,
            "rs": resist,
            "sl": to_int(field(c, "imbueslots")),
            "cl": to_int(field(c, "upgradeclass")),
            "w": clean(field(c, "weight")),
            "st": field(c, "stackable").lower() == "yes",
            "v": clean(field(c, "value")),
            "nv": to_int(field(c, "npcvalue")),
            "bf": clean(field(c, "buyfrom"))[:200],
            "sl_to": clean(field(c, "sellto"))[:200],
            "by": [[cidx[n], r] for n, r in by],
            "no": clean(big_field(c, "notes"))[:500],
        })

    # drop empty keys to keep the payload lean
    slim = []
    for it in items:
        slim.append({k: v for k, v in it.items()
                     if v not in (None, "", [], False)})

    cats = defaultdict(int)
    for it in items:
        cats[it["c"]] += 1
    order = [c for c, _ in sorted(cats.items(), key=lambda x: -x[1])]

    payload = {"cats": order, "creatures": creature_table, "items": slim}
    with open(OUT, "w") as fh:
        fh.write("window.ITEMDATA = " + json.dumps(payload, ensure_ascii=False,
                                                   separators=(",", ":")) + ";\n")

    with_drops = sum(1 for it in items if it["by"])
    print(f"{len(items)} itens em {len(order)} categorias — {with_drops} com fonte de drop, "
          f"{len(creature_table)} criaturas indexadas")
    print("->", OUT, f"({os.path.getsize(OUT)/1024:.0f} KB)")


if __name__ == "__main__":
    main()
