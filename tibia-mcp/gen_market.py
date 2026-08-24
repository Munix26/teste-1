#!/usr/bin/env python3
"""Regenera market-items.js — o catálogo de itens negociáveis no Market.

Fonte: api.tibiamarket.top (Tibia Market Tracker, MIT, sem autenticação).
Só os *metadados* entram no arquivo gerado: id do object type, nome do wiki,
categoria, tier e o melhor NPC de compra/venda. **Preço de Market não é
gerado aqui** — market.html busca ao vivo, senão o arquivo nasce velho.

Os ids são os object type ids do cliente; o nome que casa com items-data.js é
o `wiki_name` (4.988 dos 4.993 batem exato).

    python3 tibia-mcp/gen_market.py            # escreve market-items.js
    python3 tibia-mcp/gen_market.py --check    # só relata, não escreve
"""

import argparse
import json
import os
import sys
import urllib.request
from datetime import date

API = "https://api.tibiamarket.top"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "market-items.js")


def fetch(path):
    req = urllib.request.Request(
        API + path, headers={"User-Agent": "tibia-ai/gen_market.py"}
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def best_npc(offers, cheapest):
    """Melhor NPC da lista: [preço, nome, local].

    `cheapest=True` para o NPC que vende mais barato (o dono paga),
    `False` para o que compra mais caro (o dono recebe).

    Descarta quem negocia em outra moeda (`currency_object_type_id != 0`) ou
    exige flag de quest — senão a Minzy "vende" great health potion por 19
    Favour e vira o melhor preço em gold, que não é.
    """
    ok = [
        o
        for o in offers
        if not o.get("currency_object_type_id")
        and not o.get("currency_quest_flag_display_name")
        and o.get("price")
    ]
    if not ok:
        return None
    o = (min if cheapest else max)(ok, key=lambda x: x["price"])
    return [o["price"], o["name"], o.get("location") or ""]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="não escreve o arquivo")
    args = ap.parse_args()

    meta = fetch("/item_metadata")
    worlds = fetch("/world_data")
    print(f"API: {len(meta)} itens, {len(worlds)} mundos")

    # nomes do catálogo do wiki, indexados em minúsculo: a API às vezes só
    # traz o `name` do cliente ("blue rubber duck") em vez do `wiki_name`
    # ("Blue Rubber Duck"), e é o nome canônico que faz o link cruzado abrir
    canon = {}
    idx = os.path.join(ROOT, "items-data.js")
    if os.path.exists(idx):
        raw = open(idx, encoding="utf-8").read()
        for x in json.loads(raw[raw.index("=") + 1:].strip().rstrip(";"))["items"]:
            canon.setdefault(x["n"].lower(), x["n"])

    cats = sorted({i["category"] for i in meta})
    cat_ix = {c: n for n, c in enumerate(cats)}

    items, miss = [], []
    for i in sorted(meta, key=lambda x: (x.get("wiki_name") or x.get("name") or "").lower()):
        name = i.get("wiki_name") or i.get("name")
        if not name:
            continue
        name = canon.get(name.lower(), name)
        if canon and name.lower() not in canon:
            miss.append(name)
        # tier -1 = item não forjável; guardar 0 deixa o JSON menor e o
        # front testa `tier > 0` do mesmo jeito
        row = [i["id"], name, cat_ix[i["category"]], max(i.get("tier", -1), 0)]
        ns = best_npc(i.get("npc_sell") or [], cheapest=True)   # NPC vende p/ você
        nb = best_npc(i.get("npc_buy") or [], cheapest=False)   # NPC compra de você
        # cauda opcional: só cresce o arquivo quando existe de fato
        if ns or nb:
            row.append(ns)
        if nb:
            row.append(nb)
        items.append(row)

    # o casamento com o catálogo do wiki é o que faz o link cruzado
    # market ↔ index.html funcionar; se despencar, o wiki mudou de nome
    if canon:
        print(f"casam com items-data.js: {len(items) - len(miss)}/{len(items)}")
        if miss:
            print(f"  sem ficha no wiki ({len(miss)}): {', '.join(sorted(miss)[:12])}")
        if len(miss) > len(items) * 0.1:
            sys.exit("ABORTADO: mais de 10% dos nomes não casam — algo mudou na API")

    payload = {
        "gen": date.today().isoformat(),
        "api": API,
        "cats": cats,
        "worlds": sorted(w["name"] for w in worlds),
        "items": items,
    }

    if args.check:
        print("--check: nada escrito")
        return

    with open(OUT, "w", encoding="utf-8") as f:
        f.write(
            "// GERADO por tibia-mcp/gen_market.py — não editar à mão.\n"
            "// [id, nome, catIdx, tier, npcSell?, npcBuy?]  npc* = [preço, nome, local]\n"
            "// Preços de Market NÃO ficam aqui: market.html busca ao vivo na API.\n"
            "window.MARKETITEMS = "
        )
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")

    print(f"escrito {OUT} ({os.path.getsize(OUT) / 1024:.0f} KB, {len(items)} itens)")


if __name__ == "__main__":
    main()
