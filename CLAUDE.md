# Tibia-AI

Ferramenta pessoal de consulta e análise de dados de Tibia, focada em
**Paladin (RP)**. Repositório = site estático + dump do TibiaWiki + servidor MCP.

## Contexto do dono

- Personagem: **Royal Paladin, level ~360** (meta: 600).
- Equipamento atual: Falcon Bow (t0/t1), Falcon Coif t1, Mutated Skin Armor,
  Falcon Greaves, Winged Boots t2. Também possui Bow of Destruction t2,
  Bow of Cataclysm t0, Guardian Boots t2, Fabulous Legs.
- Estratégia de imbuement: mantém **2× Vampirism e 2× Void** distribuídos
  entre as peças (leech duplo ≈ 200 hp/s de cura no ritmo dele).
- Hunts principais: **Werelions (Lion Sanctum, Darashia)** e **Cobra Bastion**.
- Objetivos de equipamento: Soulbleeder, Soulshell, Pair of Soulstalkers
  (Soul War) e Alicorn Headguard (Primal Ordeal/Hazard).
- Uso é **pessoal** — o site não deve ir a público (a proteção da Vercel
  fica ligada de propósito).

## Como rodar

```bash
bash tibia-mcp/setup.sh                                   # Postgres + dados + deps
cd ~/tibia_mcp && MCP_HOST=127.0.0.1 .venv/bin/python -m src.mcp_server
```

O container é reciclado com frequência e **o Postgres morre junto**. Quando
`raw_pages` não existir, restaure em segundos:

```bash
su postgres -s /bin/bash -c "/usr/lib/postgresql/16/bin/pg_ctl -D /var/lib/postgresql/tibia-pgdata -l /var/lib/postgresql/pg.log start"
PGPASSWORD=tibiawiki pg_restore -h 127.0.0.1 -U tibiawiki -d tibiawiki --clean --if-exists tibia-mcp/tibiawiki.dump
```

## Estrutura

| Caminho | O que é |
|---|---|
| `index.html` + `items-data.js` | catálogo completo (9.894 itens, 56 categorias) com índice reverso de drops |
| `creatures.html` + `creatures-data.js` | 1.629 criaturas com detalhe completo ao clicar |
| `spawns.html` + `hunts-data.js` | 442 spawns com criaturas e médias calculadas |
| `tibia-mcp/tibiawiki.dump` | banco PostgreSQL completo (28.967 páginas do wiki) |
| `tibia-mcp/setup.sh` | recria o ambiente do zero, sem refazer o crawl |
| `tibia-mcp/gen_items.py` | regenera `items-data.js` (inverte as loot tables para o índice de drops) |
| `tibia-mcp/gen_creatures.py` | regenera `creatures-data.js` |
| `tibia-mcp/gen_hunts.py` | regenera `hunts-data.js` (junta spawn + criaturas) |
| `tibia-mcp/loot_value.py` | calcula gp/kill de criaturas (loot table × preço de NPC) |
| `tibia-mcp/english-wiki-adaptation.patch` | correções aplicadas no servidor MCP upstream |

## Decisões técnicas importantes

- **Fonte de dados = `tibia.fandom.com` (wiki inglês)**, não o `tibiawiki.com.br`.
  O wiki BR fica atrás de Cloudflare e é inalcançável de datacenter (403 mesmo
  com Chromium real). O BR é fork do inglês, então bastou mapear aliases de
  template (`Infobox_Criatura` → `Infobox Creature`, etc.).
- **Consultar o wikitext quando a tabela falhar.** Vários campos não importaram
  (formato diferente); `raw_pages` tem o wikitext íntegro e resolve caso a caso.
  Foi assim que saíram drops, requisitos de quest e stats de arma.
- O `query_database` do MCP tem um guard de SQL ingênuo: bloqueia queries que
  contenham a substring "drop" (inclusive na coluna `dropped_by`).
- **Armadilhas do parser de wikitext** (todas já corrigidas, mas fáceis de
  reintroduzir): campos multi-linha terminam no próximo ` | chave =` com espaço
  após o pipe (parâmetros aninhados usam `|chave=` sem espaço); usar `[ \t]*`
  e não `\s*` depois do `=`, senão um campo vazio engole a linha seguinte; e
  pipes dentro de `[[wikilinks]]` precisam ser protegidos antes de dar split.

## Lacunas conhecidas dos dados

- Resistências elementais das criaturas (`hab_*`) e posições de mapa: vazias
  nas tabelas (existem no wikitext).
- `runes`, `world_quests`, `world_changes`, `tasks`: tabelas vazias (o wiki
  inglês estrutura de outro jeito).
- **Charm points e contagens do bestiário: zerados** (ficam fora do infobox).
- Rating de exp/loot das hunts: só ~57% preenchido **na origem** — o wiki
  inglês deixa em branco. Contornado em `spawns.html` calculando exp média,
  exp/HP e ouro por kill a partir das criaturas de cada spawn (médias excluem
  bosses e objetos de 0 exp, senão distorcem).
- O índice reverso de drops cobre só loot table: itens vindos de quest, bag,
  task ou NPC aparecem sem fonte (ex.: Soulbleeder, que vem da Bag You Desire).
- **Sem preços de Market ao vivo.** 1.640 itens têm preço de NPC; os itens de
  endgame (Soul Set, Alicorn, forjados) são todos "negotiable" — sem valor.

## Modelo de simulação de hunt

Fórmula da comunidade (a CipSoft nunca publicou; o próprio wiki diz que a
fórmula de dano atual é desconhecida):

```
max = 0,09 × skill × atk + level/5      min = level/5
```

- Skill de distance assumida em **125** — nunca foi confirmada pelo dono.
- Valores **absolutos** (exp/h, kills/h) são teto: assumem alvo sempre
  disponível e ignoram respawn, que na prática é o gargalo.
- Comparações **relativas** entre equipamentos são confiáveis (o erro afeta
  todos igualmente).
- **Calibrar com o Hunt Analyzer** quando o dono enviar uma sessão real
  (max hit, dano total, kills, raw xp/h, balance) — é o que transforma as
  estimativas em números dele.

### Constantes do spawn de Werelions (Lion Sanctum)

- Mix de dano recebido: **holy 42% · fire 30% · physical 28%** (holy não tem
  resistência nativa em nenhum equipamento — só o imbuement Demon Presence).
- Fraqueza: **ice 125%** → charm Icicle é o de maior retorno lá.
- 1 ponto de distance ≈ +0,65% de dano; 1 de atk ≈ +2%.
- Criaturas quase idênticas (2.700–3.000 HP, 2.200–2.300 exp), então o andar
  muda **densidade**, não exp por kill. Estimativa: −1 ≈ 583k raw xp/h e
  194k loot/h; −2 ≈ 1.079kk raw xp/h e 359k loot/h.

## Conclusões de equipamento já apuradas (spawn de Werelions)

- **Imbuements > troca de equipamento.** Demon Presence + Dragon Hide valem
  ~11% de mitigação; trocar de armor mexe 1–2%.
- Melhor armor: **Unerring Dragon SA** (dano) ou **Mutated Skin** (versátil —
  o earth +8% dela é o que serve em Cobra Bastion). Ghost t2 é a mais tanky.
- Falcon Bow, Falcon Coif e Falcon Greaves seguem imbatíveis até o level 400.
- **Guardian Boots têm holy −2%** → pioram a defesa neste spawn.
- Alicorn Headguard (400) e Sanguine Greaves (500) são os próximos saltos.
