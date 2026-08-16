"""Generate spells-data.js from the TibiaWiki dump.

A tabela `spells` importou pela metade: `exp_level`, `cooldown_own`,
`cooldown_group`, `spell_range`, `magic_type`, `scale_with` e `mag_level` vieram
todas vazias (0 de 218 linhas) — ou seja, justamente level exigido e cooldown,
que são os campos que decidem uma rotação. Então tudo sai do wikitext em
raw_pages, como em gen_imbuements.py.

Sobre `cooldowngroup`: o valor é a **duração em segundos** do cooldown de grupo,
não o id do grupo. Confirmado por Ultimate Healing (grupo de cura = 1s),
Groundshaker (grupo de ataque = 2s) e pelo histórico do Annihilation, que
registra a mudança "de 4 segundos para 2 segundos". O grupo em si (Ataque /
Cura / Suporte) sai do `subclass`.
"""
import json
import os
import re

import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://tibiawiki:tibiawiki@127.0.0.1:5432/tibiawiki")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "spells-data.js")

VOCATIONS = ("Knight", "Paladin", "Druid", "Sorcerer", "Monk")

# Campos reais do Infobox Spell. Aqui é whitelist, e não a regra "pipe + espaço"
# usada no resto do repo, porque nas spells ela não se sustenta nos dois
# sentidos: Whirlwind Throw escreve "|basepower= 32" e Levitate "|promotion="
# colados no pipe, enquanto o {{Scene}} do campo animation abre "|caster=",
# "|missile=" e até "|effect=" no início da linha. Casar por nome conhecido pega
# o campo mal formatado e ignora o parâmetro aninhado.
FIELDS = (
    "name spellid type subclass secondarygroup runegroup damagetype words premium "
    "promotion mana levelrequired soul amount basepower cooldown cooldown2 cooldown3 "
    "cooldowngroup cooldowngroup2 voc effect animation implemented notes history "
    "libraryname librarytext wheelspell category image status description seealso "
    "partyspell conjurespell passivespell uses"
).split()
# Cada campo vale até o próximo marcador, o que já resolve os multi-linha
# (effect, notes, history, librarytext).
FIELD_START = re.compile(r"^\|[ \t]*(%s)[ \t]*=[ \t]*" % "|".join(FIELDS), re.M)

WIKILINK = re.compile(r"\[\[([^\]|]*)(?:\|([^\]]*))?\]\]")
FILE_TOKEN = re.compile(r"\[?\[?(?:File|Image):[^\]\n]*?\.(?:gif|png|jpe?g)\]?\]?", re.I)
TEMPLATE = re.compile(r"\{\{[^{}]*\}\}")
HTML_TAG = re.compile(r"<[^>]+>")
# tabelas wiki dentro de notes ("{{{!}}class=...") não têm como virar texto
WIKITABLE = re.compile(r"\{\{\{!\}\}.*", re.S)


def vocations(raw):
    """Vocações do campo `voc`.

    O campo não tem formato único: "[[Knight]]s", "[[Knight|Elite Knights]]",
    "Knights, Paladins e ..." (os Avatars da Wheel usam texto puro, sem
    wikilink) — daí a busca por substring em vez de casar o [[link]].
    """
    low = (raw or "").lower()
    return [v for v in VOCATIONS if v.lower() in low]


def clean(text):
    """Wikitext -> texto corrido legível."""
    if not text:
        return ""
    text = WIKITABLE.sub("", text)
    text = FILE_TOKEN.sub("", text)
    for _ in range(3):  # templates aninhados: resolve de dentro para fora
        new = TEMPLATE.sub("", text)
        if new == text:
            break
        text = new
    text = WIKILINK.sub(lambda m: m.group(2) or m.group(1), text)
    # <br /> separa itens (Levitate tem duas fórmulas no mesmo campo); virar
    # quebra de linha antes de remover as tags evita colar as duas.
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = HTML_TAG.sub("", text)
    text = re.sub(r"'{2,}", "", text)          # negrito/itálico do wiki
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip(" ,|\n")


def parse_fields(content):
    """Todos os campos do infobox, incluindo os multi-linha."""
    marks = list(FIELD_START.finditer(content))
    out = {}
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(content)
        value = content[m.end():end]
        # o último campo carrega o fechamento do template junto
        value = re.sub(r"\n?\}\}.*\Z", "", value, flags=re.S)
        out.setdefault(m.group(1), value.strip())
    return out


def as_int(raw):
    if not raw:
        return None
    m = re.search(r"-?\d+", raw.replace(".", "").replace(",", ""))
    return int(m.group()) if m else None


def yes(raw):
    return bool(raw) and raw.strip().lower().startswith("yes")


def main():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute(
        """SELECT title, content FROM raw_pages
           WHERE content LIKE '%%Infobox Spell%%' AND NOT is_redirect
           ORDER BY title"""
    )

    spells = []
    for row in cur.fetchall():
        f = parse_fields(row["content"])
        name = clean(f.get("name", "")) or row["title"]
        stype = (f.get("type") or "").strip()
        # páginas de listagem (DPL) casam o LIKE mas não são spells
        if stype not in ("Instant", "Rune"):
            continue

        rec = {
            "n": name,
            "id": as_int(f.get("spellid")),
            # spells com duas fórmulas (Levitate: up / down) cabem numa linha só
            "w": clean(f.get("words")).replace("\n", " / "),
            "t": stype,
            "sub": (f.get("subclass") or "").strip(),
            # voc vazio = sem restrição de vocação (Practise *, Second Wind)
            "v": vocations(f.get("voc")),
            "lvl": as_int(f.get("levelrequired")),
            "mana": as_int(f.get("mana")),
            "soul": as_int(f.get("soul")),
            "cd": as_int(f.get("cooldown")),
            "cdg": as_int(f.get("cooldowngroup")),
            "cdg2": as_int(f.get("cooldowngroup2")),
            "sg": (f.get("secondarygroup") or "").strip(),
            "rg": (f.get("runegroup") or "").strip(),
            "amt": as_int(f.get("amount")),
            "dmg": (f.get("damagetype") or "").strip(),
            # "deprecated" (saiu do jogo) e "ts-only" (só existiu no test server).
            # Sem isso, Conjure Bolt e Enchant Staff apareceriam como utilizáveis.
            "st": (f.get("status") or "").strip().lower(),
            "bp": as_int(f.get("basepower")),
            "prem": yes(f.get("premium")),
            "promo": yes(f.get("promotion")),
            "wheel": yes(f.get("wheelspell")),
            "eff": clean(f.get("effect")),
            "no": clean(f.get("notes")),
            "impl": (f.get("implemented") or "").strip(),
            "lib": clean(f.get("librarytext")),
        }
        # descarta só vazio de verdade: 0 é dado (soul 0, mana 0)
        spells.append({k: v for k, v in rec.items()
                       if v is not None and v != "" and v != [] and v is not False})

    spells.sort(key=lambda s: s["n"])

    by_voc = {v: sum(1 for s in spells if v in s.get("v", [])) for v in VOCATIONS}
    inactive = sum(1 for s in spells if s.get("st"))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("window.SPELLS = ")
        json.dump(spells, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")
    print(f"{len(spells)} spells -> {OUT}")
    print("  por vocação: " + ", ".join(f"{v} {n}" for v, n in by_voc.items()))
    print(f"  descontinuadas/test-server: {inactive}")
    print("  com level: %d · com cooldown: %d · com basepower: %d"
          % (sum(1 for s in spells if "lvl" in s),
             sum(1 for s in spells if "cd" in s),
             sum(1 for s in spells if "bp" in s)))


if __name__ == "__main__":
    main()
