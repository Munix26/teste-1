"""Weapon Proficiency (Summer Update 2025) — resolve uma arma para sua tabela de perks.

O wiki não guarda a proficiência na página da arma. Ela mora inteira numa página
só (`Weapon Proficiency Tables`), dividida em seções, e o `Infobox Object` deriva
o nome da seção a partir do *nome* da arma mais o tipo e a quantidade de mãos.
Este módulo reimplementa essa derivação — a lógica original é uma cascata de
`{{#ifeq:{{#rpos:...}}}}` no template `Infobox Object/Weapon Proficiency Name`
(está no dump: `raw_pages`, mesmo título) — e acrescenta o que o template
não cobre mas a página de tabelas tem:

- sets que entraram depois do template (Moonsilver, Stellar Moonsilver, Crypt);
- seções nomeadas com grafia diferente do item ("Sword 1H Pharao Sword",
  "Club 1H Gluttons Mace", "Wand 1H Scorcher" para "The Scorcher"…);
- as tabelas **genéricas** por classe ("Generic 1H Sword Class 1"), que é o
  que as armas antigas sem set usam.
"""
import re

# Ordem importa: é a ordem dos ifs aninhados no template, e o primeiro que casa
# vence. Por isso "Grand Sanguine" vem antes de "Sanguine" e "Crude Umbral"
# antes de "Umbral" — invertendo, a arma cairia no set errado. ("Eldritch"
# antes de "Gilded Eldritch" também é do template: no wiki, os Gilded mostram
# a tabela Eldritch.) Stellar Moonsilver, Moonsilver e Crypt não estão no
# template, mas têm seções próprias na página de tabelas.
SETS = [
    "Amber", "Cobra", "Crude Umbral", "Destruction", "Draining Inferniarch",
    "Eldritch", "Falcon", "Gilded Eldritch", "Glooth", "Grand Sanguine",
    "Siphoning Inferniarch", "Jungle", "Lion", "Master Umbral", "Naga",
    "Rending Inferniarch", "Sanguine", "Inferniarch", "Soul", "Umbral",
    "Stellar Moonsilver", "Moonsilver", "Crypt",
]

# armas de evento/réplica: o set vira outro nome
REPLICAS = [("Carving", "Replica Carving"), ("Remedy", "Replica Remedy"),
            ("Mayhem", "Replica Mayhem"), ("Earth", "Replica Earth"),
            ("Icy", "Replica Ice"), ("Test", "Test"), ("Fiery", "Replica Fire")]

# só estes sets separam a tabela entre arco e besta; o resto usa "Distance"
SPLIT_DISTANCE = {
    "Amber", "Umbral", "Master Umbral", "Crude Umbral", "Siphoning Inferniarch",
    "Draining Inferniarch", "Rending Inferniarch", "Inferniarch",
    "Grand Sanguine", "Sanguine", "Soul", "Stellar Moonsilver", "Moonsilver", "Crypt",
}

WEAPON_TYPE = {
    "Axe Weapons": "Axe", "Club Weapons": "Club", "Sword Weapons": "Sword",
    "Fist Fighting Weapons": "Fist",
}

# seção nomeada cuja grafia não se deduz do nome do item
ALIASES = {
    "Vile Axe": "Axe 1H Vile Ornamented Axe",
    "Ornamented Axe": "Axe 1H Vile Ornamented Axe",
    "Pharaoh Sword": "Sword 1H Pharao Sword",
    "Snowball with Ice Shards": "Throw - Snowball with Shards",
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


def weapon_type(primarytype, secondarytype, vocrequired):
    """Axe/Club/Sword/Fist/Distance/Throw/Rod/Wand/Caster, ou None."""
    if primarytype == "Distance Weapons":
        return {"Bows": "Distance", "Crossbows": "Distance",
                "Throwing Weapons": "Throw"}.get(secondarytype)
    if primarytype in ("Rods", "Wands"):
        voc = (vocrequired or "").strip().lower()
        return {"druids": "Rod", "sorcerers": "Wand",
                "sorcerers and druids": "Caster"}.get(voc) or primarytype[:-1]
    return WEAPON_TYPE.get(primarytype)


def section_name(name, primarytype, secondarytype, hands, vocrequired=""):
    """Nome da seção de proficiência da arma (como o template deriva), ou None."""
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

    wtype = weapon_type(primarytype, secondarytype, vocrequired)
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
        return f"{weapon_set} {'Caster' if wtype in ('Rod', 'Wand', 'Caster') else wtype}"
    if weapon_set:
        return f"{weapon_set} {grip} {wtype}"
    return f"{wtype} {grip} {name}"


def _norm(s):
    s = s.lower().replace("'", "").replace("’", "")
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"^the ", "", s.strip())
    return re.sub(r"\s+", " ", s).strip()


class Resolver:
    """Casa armas com as seções da página de tabelas, do jeito mais exato ao
    mais tolerante. `find()` devolve (perks, generica?) ou (None, False)."""

    def __init__(self, tables):
        self.tables = tables
        self.folded = {k.lower(): k for k in tables}
        # "Sword 1H Pharao Sword" -> ("pharao sword" -> seção): índice por nome,
        # ignorando tipo e mãos — o wiki erra o tipo às vezes ("Sword 1H
        # Ravenwing" para um machado) e isso não pode custar a tabela
        self.by_name = {}
        for k in tables:
            m = re.match(r"^(?:Axe|Club|Sword|Fist|Distance|Rod|Wand|Caster) [12]H (.+)$", k) \
                or re.match(r"^Throw - (.+)$", k)
            if m:
                self.by_name.setdefault(_norm(m.group(1)), k)

    def _exact(self, section):
        if not section:
            return None
        if section in self.tables:
            return section
        return self.folded.get(section.lower())

    def _named(self, name):
        n = _norm(name)
        if n in self.by_name:
            return self.by_name[n]
        # "Incredible Mumpiz Slayer" ~ "Mumpiz Slayer"; "Ron the Ripper's Sabre" ~
        # "Ripper's Sabre". Só nesse sentido: o contrário levaria "Dagger" para
        # "Deepling Ceremonial Dagger" (uma rod).
        for rest, section in self.by_name.items():
            if len(rest) >= 8 and n.endswith(" " + rest):
                return section
        return None

    def _generic(self, wtype, hands, upgradeclass):
        if not wtype or wtype == "Throw":
            return None
        kind = "Caster" if wtype in ("Rod", "Wand", "Caster") else wtype
        grip = "2H" if hands == "Two" else "1H"
        cls = str(upgradeclass or "").strip() or "1"
        # wand/rod não tem `hands` no wiki e a seção genérica de classe 1 é "2H
        # Caster": para caster vale qualquer empunhadura
        grips = [grip, "1H" if grip == "2H" else "2H"] if kind == "Caster" else [grip]
        for g in grips:
            for candidate in (f"Generic {g} {kind} Class {cls}",
                              f"Generic {g} {kind}" if cls == "1" else None):
                if candidate and candidate in self.tables:
                    return candidate
        return None

    def find(self, name, primarytype, secondarytype, hands, vocrequired="", upgradeclass=""):
        derived = section_name(name, primarytype, secondarytype, hands, vocrequired)
        section = self._exact(ALIASES.get(name)) or self._exact(derived)
        # set listado como "split" no template mas com uma seção só na tabela
        # ("Inferniarch 2H Distance" em vez de "… Bow" / "… Crossbow")
        if not section and derived and re.search(r" (Bow|Crossbow)$", derived):
            section = self._exact(re.sub(r" (Bow|Crossbow)$", " Distance", derived))
        if section:
            return self.tables[section], False
        section = self._named(name)
        if section:
            return self.tables[section], False
        wtype = weapon_type(primarytype, secondarytype, vocrequired)
        section = self._generic(wtype, hands, upgradeclass)
        if section:
            return self.tables[section], True
        return None, False


def lookup(tables, name, primarytype, secondarytype, hands, vocrequired="", upgradeclass=""):
    """Perks da arma (só a tabela), ou None. Ver Resolver.find para a origem."""
    return Resolver(tables).find(name, primarytype, secondarytype, hands,
                                 vocrequired, upgradeclass)[0]
