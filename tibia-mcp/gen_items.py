"""Generate a paladin-focused item reference page from the TibiaWiki dump."""
import html
import json
import os
import re
import sys

os.environ.setdefault("DATABASE_URL", "postgresql://tibiawiki:tibiawiki@127.0.0.1:5432/tibiawiki")
sys.path.insert(0, "/tmp/claude-0/-home-user-teste-1/e3bdae15-d3b4-53c8-a918-f93caed4f72e/scratchpad/tibia_mcp")
from src.db.connection import get_connection
from src.parser.wikitext import extract_infobox

# category label -> matching primarytype values
CATEGORIES = [
    ("Arcos e Bestas", {"Distance Weapons"}),
    ("Munição", {"Ammunition"}),
    ("Aljavas", {"Quivers"}),
    ("Capacetes", {"Helmets"}),
    ("Armaduras", {"Armors"}),
    ("Pernas", {"Legs"}),
    ("Botas", {"Boots"}),
    ("Escudos", {"Shields"}),
    ("Amuletos", {"Amulets and Necklaces"}),
    ("Anéis", {"Rings"}),
    ("Slot Extra", {"Extra Slot Items", "Extra Slot"}),
]
OTHER_VOCS = ("knight", "sorcerer", "druid", "monk")

# an item earns its place only if it carries one of these
STAT_KEYS = ("attrib", "resist", "atk_mod", "hit_mod", "armor", "defense")


def clean(text):
    if not text:
        return ""
    text = re.sub(r"\[\[([^|\]]*\|)?([^\]]+)\]\]", r"\2", text)
    text = re.sub(r"\{\{[^}]*\}\}", "", text)
    return text.replace("'''", "").strip(" .")


def relevant(box):
    """Keep only gear that actually changes a hunt."""
    armor = to_int(box.get("armor"))
    if box.get("attrib") or box.get("resist"):
        return True
    if box.get("atk_mod") or box.get("attack"):
        return True
    if armor and armor >= 5:
        return True
    return False


def to_int(value):
    if not value:
        return None
    m = re.search(r"-?\d+", value)
    return int(m.group()) if m else None


def usable_by_paladin(voc):
    voc = (voc or "").lower()
    if not voc.strip():
        return "todas"
    if "paladin" in voc:
        return "paladin"
    return None  # knight/sorcerer/druid only


def main():
    conn = get_connection()
    buckets = {label: [] for label, _ in CATEGORIES}
    type_to_label = {t: label for label, types in CATEGORIES for t in types}

    with conn.cursor() as cur:
        cur.execute("SELECT title, content FROM raw_pages WHERE NOT is_redirect AND content LIKE %s",
                    ("%Infobox Object%",))
        for row in cur.fetchall():
            box = extract_infobox(row["content"], "Infobox_Object")
            if not box:
                continue
            label = type_to_label.get((box.get("primarytype") or "").strip())
            if not label:
                label = type_to_label.get((box.get("secondarytype") or "").strip())
            if not label:
                continue
            voc = usable_by_paladin(box.get("vocrequired"))
            if voc is None:
                continue
            if not relevant(box):
                continue
            buckets[label].append({
                "name": row["title"],
                "voc": voc,
                "lvl": to_int(box.get("levelrequired")) or 0,
                "armor": to_int(box.get("armor")),
                "atk": clean(box.get("atk_mod") or box.get("attack")),
                "hit": clean(box.get("hit_mod")),
                "attrib": clean(box.get("attrib")),
                "resist": clean(box.get("resist")),
                "slots": to_int(box.get("imbueslots")),
                "cls": to_int(box.get("upgradeclass")),
                "weight": clean(box.get("weight")),
            })
    conn.close()

    data = [{"label": label, "items": sorted(buckets[label], key=lambda i: (-i["lvl"], i["name"]))}
            for label, _ in CATEGORIES if buckets[label]]
    total = sum(len(c["items"]) for c in data)
    print(f"{total} itens em {len(data)} categorias")
    for c in data:
        print(f"  {c['label']}: {len(c['items'])}")

    out = "/home/user/teste-1/items-data.js"
    with open(out, "w") as fh:
        fh.write("window.ITEMS = " + json.dumps(data, ensure_ascii=False) + ";\n")
    print("->", out)


if __name__ == "__main__":
    main()
