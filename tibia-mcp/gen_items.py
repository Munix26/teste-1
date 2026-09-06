"""Generate the full item catalogue (items-data.js) from the TibiaWiki dump.

Covers every item on the wiki, not just gear: quest and delivery-task items,
creature products, tools, valuables and so on. Each item carries a reverse
drop index (which creatures drop it, and where those creatures live) built by
inverting every creature loot table, plus the NPCs that trade it.
"""
import json
import os
import re
import sys
from collections import defaultdict

import psycopg2
from psycopg2.extras import RealDictCursor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from loot import loot_items
import categorize
import proficiency

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
ATTACK_ELEMENTS = ["fire", "earth", "ice", "energy", "death", "holy"]


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


def dropped_by(content):
    """`{{Dropped By|Grand Master Oberon|…}}` da página do item -> nomes."""
    m = re.search(r"\{\{Dropped By\|([^}]*)\}\}", content)
    return [x.strip() for x in m.group(1).split("|") if x.strip()] if m else []


def merge_dropped_by(item_rows, drops, creature_info):
    """O índice reverso vem das loot tables das criaturas; a página do item
    também lista quem dropa, e às vezes sabe mais (Amazon Armor ← Orc Warlord).
    Entra com raridade "unknown" — a página do item não diz a chance."""
    added = 0
    for row in item_rows:
        have = {c for c, _ in drops.get(row["title"], [])}
        for name in dropped_by(row["content"]):
            if name in creature_info and name not in have:
                drops[row["title"]].append((name, "unknown"))
                have.add(name)
                added += 1
    return added


def store_offers(content):
    """`{{Store Trades|{{Store Product|11|amount=100}}…}}` -> [[coins, qtd]]."""
    raw = big_field(content, "storevalue")
    return [[int(c), int(a or 1)]
            for c, a in re.findall(r"\{\{Store Product\|(\d+)(?:\|amount=(\d+))?", raw)]


def attack_elements(content):
    """fire_attack=46, earth_attack=… -> [["fire", 46], …] (dano elemental da arma)."""
    out = []
    for el in ATTACK_ELEMENTS:
        v = to_int(field(content, el + "_attack"))
        if v:
            out.append([el, v])
    return out


def split_list(text):
    """Campo com várias linhas/entradas (augments) -> lista limpa."""
    return [clean(x) for x in re.split(r"<br\s*/?>|\n|,(?![^(]*\))", text) if clean(x)]


def build_drop_index(rows):
    """creature loot tables -> {item name: [(creature, rarity)]}, plus creature info."""
    index = defaultdict(list)
    info = {}
    for title, content in rows:
        info[title] = {
            "loc": clean(big_field(content, "location"))[:180],
            "hp": to_int(field(content, "hp")),
            "diff": field(content, "bestiarylevel"),
            "boss": field(content, "isboss").lower() == "yes",
        }
        for it in loot_items(content):
            index[it["name"]].append((title, it["rarity"]))
    return index, info


def spawn_levels(rows):
    """creature -> [levels of the hunting places it appears in].

    Old creatures show up in many mixed spawns, so the spread is real
    information — a range is more honest than a single number.
    """
    levels = defaultdict(list)
    for title, content in rows:
        lv = [to_int(field(content, f)) for f in ("lvlknights", "lvlpaladins", "lvlmages")]
        lv = [x for x in lv if x]
        if not lv:
            continue
        low = min(lv)
        for block in re.finditer(r"\{\{CreatureList([^}]*)\}\}", content, re.S):
            for part in block.group(1).split("|"):
                part = part.strip()
                if part and "=" not in part and not part.lower().startswith("type"):
                    levels[part].append(low)
    return levels


def main():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    with conn.cursor() as cur:
        cur.execute("SELECT title, content FROM raw_pages "
                    "WHERE NOT is_redirect AND content LIKE %s", ("%Infobox Creature%",))
        drops, creature_info = build_drop_index([(r["title"], r["content"]) for r in cur.fetchall()])

        cur.execute("SELECT title, content FROM raw_pages "
                    "WHERE NOT is_redirect AND content LIKE %s", ("%Infobox Hunt%",))
        levels = spawn_levels([(r["title"], r["content"]) for r in cur.fetchall()])

        cur.execute("SELECT title, content FROM raw_pages "
                    "WHERE NOT is_redirect AND content LIKE %s", ("%Infobox Object%",))
        item_rows = cur.fetchall()

        cur.execute("SELECT content FROM raw_pages WHERE title = 'Delivery Task'")
        row = cur.fetchone()
        delivery = parse_delivery_tasks(row["content"]) if row else {}

        cur.execute("SELECT content FROM raw_pages WHERE title = 'Weapon Proficiency Tables'")
        row = cur.fetchone()
        prof_tables = proficiency.parse_tables(row["content"]) if row else {}
    conn.close()
    resolver = proficiency.Resolver(prof_tables)

    # a página do item complementa as loot tables (antes de indexar as criaturas)
    extra_drops = merge_dropped_by(item_rows, drops, creature_info)

    # creatures referenced by any drop, stored once and referenced by index
    referenced = sorted({c for lst in drops.values() for c, _ in lst})
    cidx = {name: i for i, name in enumerate(referenced)}
    # [nome, local, hp, dificuldade, level mínimo, level máximo] — os levels vêm
    # dos spawns onde a criatura aparece; None quando ela não está em nenhum
    creature_table = []
    for n in referenced:
        info = creature_info.get(n, {})
        lv = levels.get(n) or []
        creature_table.append([n, info.get("loc", ""), info.get("hp"),
                               info.get("diff", ""),
                               min(lv) if lv else None, max(lv) if lv else None])

    # tabelas de proficiência guardadas uma vez e referenciadas por índice: um
    # mesmo conjunto de perks serve todas as armas do mesmo set, tipo e mãos
    prof_table, pidx = [], {}

    items = []
    for row in item_rows:
        c, title = row["content"], row["title"]
        ptype = field(c, "primarytype")
        oclass = field(c, "objectclass")
        # grupo → categoria → subcategoria (ver categorize.py). Páginas de
        # lista só citam o Infobox dentro de uma DPL: não abrem com ele.
        group, cat, sub = categorize.classify(title, {
            "pt": ptype, "st": field(c, "secondarytype"), "oc": oclass,
            "hands": field(c, "hands"), "voc": field(c, "vocrequired"),
            "dmg": field(c, "damagetype"), "imb": bool(field(c, "imbuements")),
            "infobox": bool(re.search(r"\{\{Infobox Object", c)),
        })

        prof, generic = None, False
        if oclass == "Weapons":
            perks, generic = resolver.find(title, ptype, field(c, "secondarytype"),
                                           field(c, "hands"), field(c, "vocrequired"),
                                           field(c, "upgradeclass"))
            if perks:
                key = json.dumps(perks, ensure_ascii=False)
                if key not in pidx:
                    pidx[key] = len(prof_table)
                    prof_table.append(perks)
                prof = pidx[key]

        by = sorted(drops.get(title, []), key=lambda x: RARITY_ORDER.index(x[1])
                    if x[1] in RARITY_ORDER else 9)
        attrib = clean(field(c, "attrib"))
        resist = clean(field(c, "resist"))
        items.append({
            "af": attr_facets(attrib),
            "rf": resist_facets(resist),
            "dt": delivery.get(title),
            "n": title,
            "g": group,
            "c": cat,
            "sc": sub,
            "t": ptype or oclass,
            "rng": to_int(field(c, "range")),
            "hd": {"one": 1, "two": 2}.get(field(c, "hands").lower()),
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
            "p": prof,
            "pg": generic,                       # tabela genérica por classe, não do set
            "no": clean(big_field(c, "notes"))[:500],
            # ── combate ──
            "hc": to_int(field(c, "hit_chance")),          # munição: chance de acerto %
            "dm": field(c, "damagetype").lower(),          # wand/rod/runa: elemento
            "dmr": clean(field(c, "damagerange")),         # wand/rod: "85-105" ou "97 (94-100)"
            "mc": to_int(field(c, "manacost")),            # wand/rod: mana por ataque
            "ea": attack_elements(c),                      # dano elemental da arma
            "dfm": clean(field(c, "defensemod")),          # modificador de defesa
            "cr": [clean(field(c, "crithit_ch")), clean(field(c, "critextra_dmg"))]
                  if field(c, "crithit_ch") or field(c, "critextra_dmg") else None,
            "hl": [clean(field(c, "hpleech_am")), clean(field(c, "hpleech_ch"))]
                  if field(c, "hpleech_am") else None,
            "lm": [clean(field(c, "manaleech_am")), clean(field(c, "manaleech_ch"))]
                  if field(c, "manaleech_am") else None,
            "eb": clean(field(c, "elementalbond")),        # punho: elemento do vínculo
            # ── uso ──
            "ch": to_int(field(c, "charges")),
            "du": clean(field(c, "duration")),
            "rg": to_int(field(c, "regenseconds")),        # comida: segundos de regeneração
            "mlr": to_int(field(c, "mlrequired")),         # runa: magic level mínimo
            "wd": clean(field(c, "words")),                # runa: palavras da magia
            "mn": to_int(field(c, "mantra")),
            "aug": split_list(big_field(c, "augments")),   # "Spell -> +x%"
            "en": "ed" if field(c, "enchanted").lower() == "yes"
                  else "able" if field(c, "enchantable").lower() == "yes" else "",
            "im": clean(field(c, "imbuements")),           # material de quais imbuements
            "vol": to_int(field(c, "volume")),
            "lt": to_int(field(c, "lightradius")),
            "so": field(c, "slot"),
            "t2": field(c, "secondarytype"),
            # ── comércio / texto ──
            "sv": store_offers(c),                         # [[Tibia Coins, quantidade]]
            "pc": clean(field(c, "pricecurrency")),        # moeda do NPC quando não é gp
            "nvr": to_int(field(c, "npcvaluerook")),
            "ft": clean(big_field(c, "flavortext"))[:400],
            "loc": clean(big_field(c, "location"))[:220],
        })

    # drop empty keys to keep the payload lean — `p` pode ser 0, que é índice válido
    slim = []
    for it in items:
        slim.append({k: v for k, v in it.items()
                     if v not in (None, "", [], False) or (k == "p" and v == 0)})

    cats = defaultdict(int)
    for it in items:
        cats[it["c"]] += 1
    order = [c for c, _ in sorted(cats.items(), key=lambda x: -x[1])]

    # árvore grupo → [categoria, [subcategorias]] na ordem de categorize.GROUPS;
    # dentro do grupo, categorias e subcategorias por tamanho (maior primeiro)
    tree = []
    for g in categorize.GROUPS:
        cat_subs = defaultdict(lambda: defaultdict(int))
        for it in items:
            if it["g"] == g:
                cat_subs[it["c"]][it["sc"]] += 1
        if not cat_subs:
            continue
        tree.append([g, [
            [cname, [s for s, _ in sorted(((s, n) for s, n in subs.items() if s),
                                          key=lambda x: -x[1])]]
            for cname, subs in sorted(cat_subs.items(), key=lambda x: -sum(x[1].values()))
        ]])

    payload = {"cats": order, "tree": tree, "creatures": creature_table,
               "prof": prof_table, "items": slim}
    with open(OUT, "w") as fh:
        fh.write("window.ITEMDATA = " + json.dumps(payload, ensure_ascii=False,
                                                   separators=(",", ":")) + ";\n")

    with_drops = sum(1 for it in items if it["by"])
    weapons = sum(1 for it in items if it["t"] and it["p"] is not None)
    subs = sum(1 for it in items if it["sc"])
    print(f"{len(items)} itens em {len(order)} categorias ({len(tree)} grupos, "
          f"{subs} com subcategoria) — {with_drops} com fonte de drop, "
          f"{len(creature_table)} criaturas indexadas")
    generic = sum(1 for it in items if it["pg"])
    print(f"{weapons} armas com proficiência ({generic} pela tabela genérica da classe), "
          f"{len(prof_table)} tabelas de perks distintas (de {len(prof_tables)} seções no wiki)")
    print(f"{extra_drops} drops a mais vindos do `droppedby` das páginas de item")
    print("->", OUT, f"({os.path.getsize(OUT)/1024:.0f} KB)")


if __name__ == "__main__":
    main()
