"""Taxonomia do catálogo de itens: grupo → categoria → subcategoria.

O wiki inglês classifica cada objeto por `objectclass` / `primarytype` /
`secondarytype`, mas de forma irregular: "Distance Weapons" mistura arco,
besta e arremesso; runas de ataque, cura e suporte são três tipos soltos;
poções ficam em "Liquids"; e 100 páginas de lista ("Item IDs", "Alicorn Set")
carregam um Infobox Object dentro de uma DPL e entravam como item.

Aqui cada item recebe:

- **grupo** (`g`)  — Armas, Equipamento, Consumíveis, Materiais e valiosos,
  Utilidades, Quest, Casa e decoração, Cenário, Outros, Wiki
- **categoria** (`c`) — a mesma ideia de antes (Armas de Distância, Capacetes…),
  com os tipos duplicados do wiki fundidos
- **subcategoria** (`sc`) — o corte fino que interessa na hora de comparar:
  Arco / Besta / Arremesso, Flecha / Virote, Uma mão / Duas mãos, elemento de
  wand e rod, vocação da peça de equipamento, tier do pergaminho de imbuement…

As regras usam só o que o wikitext traz (nunca chute de nome quando existe
campo); o nome entra apenas onde o wiki não separa (flecha × virote, gema,
tier de pergaminho, tipo de container).
"""
import re

GROUPS = ["Armas", "Equipamento", "Consumíveis", "Materiais e valiosos",
          "Utilidades", "Quest", "Casa e decoração", "Cenário", "Outros", "Wiki"]

ELEMENT_PT = {
    "energy": "Energia", "fire": "Fogo", "death": "Death", "earth": "Terra",
    "ice": "Gelo", "physical": "Físico", "holy": "Holy",
}

VOC_PT = {"paladin": "Paladin", "knight": "Knight", "sorcerer": "Sorcerer",
          "druid": "Druid", "monk": "Monk"}

# primarytype de cenário → (categoria, subcategoria)
SCENERY = {
    "Constructions": ("Construções", None), "Doors": ("Construções", "Porta"),
    "Pillars": ("Construções", "Pilar"), "Portals": ("Construções", "Portal"),
    "Shrines and Altars": ("Construções", "Altar"), "Statues": ("Construções", "Estátua"),
    "Tombstones": ("Construções", "Lápide"), "Walls": ("Construções", "Muro"),
    "Windows": ("Construções", "Janela"),
    "Artificial Tiles": ("Pisos", "Artificial"), "Natural Tiles": ("Pisos", "Natural"),
    "Grass": ("Pisos", "Grama"),
    "Flags": ("Placas", "Bandeira"), "Signs": ("Placas", "Placa"),
    "Dropdowns": ("Navegação", "Buraco"), "Ladders": ("Navegação", "Escada de mão"),
    "Ramps": ("Navegação", "Rampa"), "Stairs": ("Navegação", "Escada"),
    "Teleporters": ("Navegação", "Teleporte"), "Transportation": ("Navegação", "Transporte"),
    "Bushes": ("Flora e Minerais", "Arbusto"), "Cactuses": ("Flora e Minerais", "Cacto"),
    "Ferns": ("Flora e Minerais", "Samambaia"), "Flowers": ("Flora e Minerais", "Flor"),
    "Mushrooms": ("Flora e Minerais", "Cogumelo"), "Plants": ("Flora e Minerais", "Planta"),
    "Rocks": ("Flora e Minerais", "Rocha"), "Trees": ("Flora e Minerais", "Árvore"),
    "Flora and Minerals": ("Flora e Minerais", None), "Natural Products": ("Vivos e Mortos", "Produto natural"),
    "Animals": ("Vivos e Mortos", "Animal"), "Remains": ("Vivos e Mortos", "Restos"),
    "Corpses": ("Vivos e Mortos", "Corpo"),
    "Fields": ("Efeitos Mágicos", "Campo"), "Magical Effects": ("Efeitos Mágicos", None),
    "Machines (Objects)": ("Objetos Funcionais", "Máquina"),
    "Torture Instruments": ("Objetos Funcionais", "Tortura"),
    "Tools (Objects)": ("Objetos Funcionais", "Ferramenta fixa"),
    "Refuse": ("Lixo", None), "Rubbish": ("Lixo", None), "Other Objects": ("Lixo", None),
    "Quest Objects": ("Objetos de Quest", None),
}

# primarytype de casa/decoração → (categoria, subcategoria)
HOUSE = {
    "Furniture": ("Mobília", None), "Closets": ("Mobília", "Armário"),
    "Coffins": ("Mobília", "Caixão"), "Casks": ("Mobília", "Barril"),
    "Tables": ("Mobília", "Mesa"),
    "Decorations": ("Decoração", None), "Decoration": ("Decoração", None),
    "Floor Decorations": ("Decoração", "Chão"), "Dolls and Bears": ("Decoração", "Boneco"),
    "Trophies": ("Decoração", "Troféu"), "Fansite Items": ("Decoração", "Fansite"),
    "Contest Prizes": ("Decoração", "Prêmio"), "Tournament Rewards": ("Decoração", "Prêmio"),
    "Lamps": ("Decoração", "Lâmpada"), "Tools and other Equipment": ("Decoração", "Lâmpada"),
    "Kitchen Tools": ("Decoração", "Cozinha"), "Fluid Containers": ("Decoração", "Cozinha"),
    "Household Items": ("Decoração", None),
    # objectclass "Wall Coverings": quadros, entalhes e troféus de parede de casa
    "Carvings": ("Decoração", "Parede"), "Wall Hangings": ("Decoração", "Parede"),
    "Trophies (Objects)": ("Decoração", "Troféu"),
}

# secondarytype que refina Mobília / Decoração
HOUSE_SUB = {
    "Beds": "Cama", "Chairs": "Cadeira", "Tables": "Mesa", "Containers": "Armário",
    "Pets": "Pet", "Party Items": "Festa", "Wall Hangings": "Parede",
    "Dividers": "Divisória", "Plants": "Planta", "Dolls and Bears": "Boneco",
    "Light Sources": "Lâmpada", "Closets": "Armário",
}

EQUIP = {
    "Helmets": "Capacetes", "Armors": "Armaduras", "Legs": "Pernas", "Boots": "Botas",
    "Shields": "Escudos", "Amulets and Necklaces": "Amuletos", "Rings": "Anéis",
    "Quivers": "Aljavas", "Spellbooks": "Spellbooks",
    "Extra Slot Items": "Slot Extra", "Extra Slot": "Slot Extra",
}

MELEE = {"Sword Weapons": "Espadas", "Axe Weapons": "Machados",
         "Club Weapons": "Clavas", "Fist Fighting Weapons": "Armas de Punho"}

GEM_RE = re.compile(r"gem|diamond|pearl|ruby|sapphire|emerald|amethyst|topaz|"
                    r"shard|splinter|fragment|geode|onyx|garnet|bijou|bangle", re.I)


def voc_sub(voc):
    """'knights and paladins' -> 'Knight e Paladin'; vazio -> 'Sem restrição'."""
    v = (voc or "").strip().lower()
    if not v or v in ("none", "without"):
        return "Sem restrição"
    has = [k for k in VOC_PT if k in v]
    if len(has) >= 4:
        return "Todas as vocações"
    if not has:
        return "Sem restrição"
    if len(has) == 1:
        return VOC_PT[has[0]]
    if set(has) == {"sorcerer", "druid"}:
        return "Sorcerer e Druid"
    if set(has) == {"knight", "paladin"}:
        return "Knight e Paladin"
    names = [VOC_PT[k] for k in has]
    return ", ".join(names[:-1]) + " e " + names[-1]


def hands_sub(hands):
    h = (hands or "").strip().lower()
    return "Duas mãos" if h == "two" else "Uma mão" if h == "one" else None


def element_sub(dmg):
    d = (dmg or "").strip().lower()
    return ELEMENT_PT.get(d, "Sem dano" if not d else d.capitalize())


def container_sub(name):
    n = name.lower()
    if "backpack" in n:
        return "Mochila"
    if re.search(r"\bbag\b|satchel|bursa", n):
        return "Bolsa"
    if re.search(r"chest|cabinet|cupboard|trunk|case|bookcase|wardrobe", n):
        return "Baú e armário"
    if re.search(r"barrel|cask|crate|\bbox\b|basket|parcel|present", n):
        return "Caixa"
    return None


def classify(name, f):
    """Devolve (grupo, categoria, subcategoria|None).

    `f` é um dict com os campos do Infobox Object já limpos:
    pt (primarytype), st (secondarytype), oc (objectclass), hands, voc,
    dmg (damagetype), imb (True se o item é material de imbuement) e
    infobox (True se a página realmente abre com {{Infobox Object).
    """
    pt, st, oc = f.get("pt", ""), f.get("st", ""), f.get("oc", "")

    # páginas de lista / set / calculadora que só citam o template numa DPL
    if not f.get("infobox", True):
        return "Wiki", "Páginas do wiki (listas e sets)", None

    # ── armas ──────────────────────────────────────────────────────────
    if pt == "Distance Weapons":
        sub = {"Bows": "Arco", "Crossbows": "Besta", "Throwing Weapons": "Arremesso"}.get(st)
        if not sub:
            n = name.lower()
            sub = "Besta" if re.search(r"crossbow|arbalest", n) else \
                  "Arco" if "bow" in n else "Arremesso"
        return "Armas", "Armas de Distância", sub
    if pt == "Ammunition":
        return "Armas", "Munição", "Virote" if "bolt" in name.lower() else "Flecha"
    if pt in MELEE:
        return "Armas", MELEE[pt], hands_sub(f.get("hands"))
    if pt in ("Wands", "Rods"):
        return "Armas", pt, element_sub(f.get("dmg"))
    if pt == "Exercise Weapons":
        return "Armas", "Armas de Treino", "Exercise"
    if pt == "Training Weapons":
        return "Armas", "Armas de Treino", "Training"
    if pt == "Weapons" or (oc == "Weapons" and not pt):
        return "Armas", "Outras armas", None

    # ── equipamento ────────────────────────────────────────────────────
    if pt in EQUIP:
        return "Equipamento", EQUIP[pt], voc_sub(f.get("voc"))

    # ── consumíveis ────────────────────────────────────────────────────
    if name == "Blank Rune":
        return "Consumíveis", "Runas", "Em branco"
    if pt == "Attack Runes":
        sub = {"Area Runes": "Área", "Field Runes": "Campo"}.get(st, "Ataque")
        return "Consumíveis", "Runas", sub
    if pt == "Healing Runes":
        return "Consumíveis", "Runas", "Cura"
    if pt == "Support Runes":
        return "Consumíveis", "Runas", "Invocação" if st == "Summon Runes" else "Suporte"
    if pt == "Liquids":
        if st == "Potions":
            n = name.lower()
            sub = "Vida" if "health" in n else "Mana" if "mana" in n else \
                  "Spirit" if "spirit" in n else "Outras"
            return "Consumíveis", "Poções", sub
        return "Consumíveis", "Líquidos", None
    if pt == "Food":
        sub = {"Mushrooms": "Cogumelo", "Creature Products": "Produto de criatura",
               "Party Items": "Festa"}.get(st)
        return "Consumíveis", "Comida", sub
    if pt == "Plants and Herbs":
        return "Consumíveis", "Plantas e Ervas", None

    # ── materiais e valiosos ───────────────────────────────────────────
    if pt == "Creature Products":
        sub = "Material de imbuement" if f.get("imb") else \
              {"Metals": "Metal", "Clothing Accessories": "Acessório"}.get(st)
        return "Materiais e valiosos", "Produtos de Criatura", sub
    if pt == "Soul Cores":
        return "Materiais e valiosos", "Soul Cores", None
    if pt == "Metals":
        return "Materiais e valiosos", "Valiosos", "Metal"
    if pt == "Valuables" or st == "Currency":
        n = name.lower()
        sub = {"Currency": "Moeda", "Rune Emblems": "Emblema de runa",
               "Replicas": "Réplica"}.get(st)
        if not sub:
            sub = "Moeda" if re.search(r"\bcoin\b|\btoken\b", n) else \
                  "Gema" if GEM_RE.search(n) else \
                  "Pergaminho" if "promotion scroll" in n else None
        return "Materiais e valiosos", "Valiosos", sub
    if oc == "Imbuement Scrolls":
        m = re.match(r"(Basic|Intricate|Powerful)", name)
        return "Materiais e valiosos", "Pergaminhos de Imbuement", m.group(1) if m else None

    # ── utilidades ─────────────────────────────────────────────────────
    if pt == "Taming Items":
        return "Utilidades", "Ferramentas", "Domesticação"
    if pt == "Tools":
        return "Utilidades", "Ferramentas", None
    if pt == "Painting Equipment":
        return "Utilidades", "Ferramentas", "Pintura"
    if pt == "Containers":
        return "Utilidades", "Containers", "Mochila" if st == "Backpacks" else container_sub(name)
    if pt == "Keys":
        return "Utilidades", "Chaves", None
    if pt == "Light Sources":
        return "Utilidades", "Fontes de Luz", None
    if pt == "Musical Instruments":
        return "Utilidades", "Instrumentos", None
    if pt in ("Utilities", "Illumination"):
        return "Utilidades", "Utilidades", "Iluminação" if pt == "Illumination" else None
    if pt == "Party Items" or oc == "Fireworks":
        return "Utilidades", "Festa", "Fogos" if "firework" in name.lower() else None
    if pt == "Documents and Papers":
        n = name.lower()
        sub = "Carta" if "letter" in n else "Pergaminho" if "scroll" in n else \
              "Mapa" if "map" in n else None
        return "Utilidades", "Documentos", sub
    if pt == "Books":
        return "Utilidades", "Livros", None
    if pt == "Magical Items":
        return "Utilidades", "Itens Mágicos", None
    if pt == "Game Tokens":
        return "Utilidades", "Jogos e Brinquedos", None

    # ── quest ──────────────────────────────────────────────────────────
    if pt == "Quest Items":
        sub = {"Keys": "Chave", "Documents and Papers": "Documento", "Books": "Documento",
               "Light Sources": "Luz", "Decorations": "Decoração",
               "Creature Products": "Produto de criatura", "Tools": "Ferramenta",
               "Mushrooms": "Planta", "Plants and Herbs": "Planta"}.get(st)
        return "Quest", "Itens de Quest", sub
    if pt == "Quest Objects" or pt == "Quest Objects <!--Not sure about that-->":
        return "Quest", "Objetos de Quest", None

    # ── casa e decoração ───────────────────────────────────────────────
    if pt in HOUSE:
        cat, sub = HOUSE[pt]
        return "Casa e decoração", cat, sub or HOUSE_SUB.get(st)

    # ── cenário ────────────────────────────────────────────────────────
    if pt in SCENERY:
        cat, sub = SCENERY[pt]
        if cat == "Lixo" and st == "Floating Objects":
            sub = "Flutuante"
        return "Cenário", cat, sub

    # ── resto ──────────────────────────────────────────────────────────
    if pt == "Blessing Charms":
        return "Outros", "Outros", "Amuleto de bênção"
    if not pt:
        return "Outros", "Outros", "Sem tipo no wiki"
    return "Outros", "Outros", None
