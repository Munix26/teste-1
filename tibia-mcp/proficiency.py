"""Weapon Proficiency (Summer Update 2025) — resolve uma arma para sua tabela de perks.

O wiki não guarda a proficiência na página da arma. Ela mora inteira numa página
só (`Weapon Proficiency Tables`), dividida em seções, e o `Infobox Object` deriva
o nome da seção a partir do *nome* da arma mais o tipo e a quantidade de mãos.
Este módulo reimplementa essa derivação — a lógica original é uma cascata de
`{{#ifeq:{{#rpos:...}}}}` no template `Infobox Object/Weapon Proficiency Name`.
"""
import re

# Ordem importa: é a ordem dos ifs aninhados no template, e o primeiro que casa
# vence. Por isso "Grand Sanguine" vem antes de "Sanguine" e "Crude Umbral"
# antes de "Umbral" — invertendo, a arma cairia no set errado.
SETS = [
    "Amber", "Cobra", "Crude Umbral", "Destruction", "Draining Inferniarch",
    "Eldritch", "Falcon", "Gilded Eldritch", "Glooth", "Grand Sanguine",
    "Siphoning Inferniarch", "Jungle", "Lion", "Master Umbral", "Naga",
    "Rending Inferniarch", "Sanguine", "Inferniarch", "Soul", "Umbral",
]

# armas de evento/réplica: o set vira outro nome
REPLICAS = [("Carving", "Replica Carving"), ("Remedy", "Replica Remedy"),
            ("Mayhem", "Replica Mayhem"), ("Earth", "Replica Earth"),
            ("Icy", "Replica Ice"), ("Test", "Test"), ("Fiery", "Replica Fire")]

# só estes sets separam a tabela entre arco e besta; o resto usa "Distance"
SPLIT_DISTANCE = {
    "Amber", "Umbral", "Master Umbral", "Crude Umbral", "Siphoning Inferniarch",
    "Draining Inferniarch", "Rending Inferniarch", "Inferniarch",
    "Grand Sanguine", "Sanguine", "Soul",
}

WEAPON_TYPE = {
    "Axe Weapons": "Axe", "Club Weapons": "Club", "Sword Weapons": "Sword",
    "Fist Fighting Weapons": "Fist", "Rods": "Rod", "Wands": "Wand",
}


def parse_tables(content):
    """Página `Weapon Proficiency Tables` -> {seção: [[perks nível 1], [nível 2], …]}."""
    out = {}
    parts = re.split(r"^===\s*(.+?)\s*===$", content, flags=re.M)
    for i in range(1, len(parts), 2):
        perks = []
        for level in range(1, 10):
            block = re.search(r"\|\s*perk_%d\s*=(.*?)(?=\n\s*\|\s*perk_\d+\s*=|\n\}\})" % level,
                              parts[i + 1], re.S)
            if not block:
                break
            perks.append([re.sub(r"\s+", " ", p).strip()
                          for p in re.findall(r"\|text=([^}|]*)", block.group(1))
                          if p.strip()])
        while perks and not perks[-1]:
            perks.pop()
        if perks:
            out[parts[i]] = perks
    return out


def section_name(name, primarytype, secondarytype, hands):
    """Nome da seção de proficiência da arma, ou None se não for arma."""
    weapon_set = ""
    for candidate in SETS:
        if candidate in name:
            weapon_set = candidate
            break
    else:
        for needle, replica in REPLICAS:
            if needle in name:
                weapon_set = replica
                break
        else:
            if name.startswith("Energy"):
                weapon_set = "Replica Energy"

    if primarytype == "Distance Weapons":
        wtype = "Throw" if secondarytype == "Throwing Weapons" else "Distance"
    else:
        wtype = WEAPON_TYPE.get(primarytype)
    if not wtype:
        return None

    if wtype == "Throw":
        return f"Throw - {name}"

    grip = "2H" if hands == "Two" else "1H"
    if weapon_set in SPLIT_DISTANCE:
        sub = {"Bows": "Bow", "Crossbows": "Crossbow"}.get(secondarytype, wtype) \
            if wtype == "Distance" else wtype
        return f"{weapon_set} {grip} {sub}"
    if weapon_set.startswith("Replica") or weapon_set == "Test":
        return f"{weapon_set} {'Caster' if wtype in ('Rod', 'Wand') else wtype}"
    if weapon_set:
        return f"{weapon_set} {grip} {wtype}"
    return f"{wtype} {grip} {name}"


def lookup(tables, name, primarytype, secondarytype, hands):
    """Perks da arma, ou None. Casa sem diferenciar caixa: várias seções do wiki
    usam Title Case onde o nome do item não usa ("Club Of The Fury")."""
    section = section_name(name, primarytype, secondarytype, hands)
    if not section:
        return None
    if section in tables:
        return tables[section]
    folded = {k.lower(): v for k, v in tables.items()}
    return folded.get(section.lower())
