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
| `sessions/*.txt` | exports crus do Hunt Analyzer (um arquivo por export) |
| `tibia-mcp/session.py` | parser dos exports + normalização de nomes contra o wiki |
| `tibia-mcp/analyze_session.py` | relatório de uma hunt (`python3 tibia-mcp/analyze_session.py sessions/*.txt`) |
| `tibia-mcp/loot.py` | parser compartilhado das loot tables + faixa de gp/kill |
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
- **Ouro por kill é uma faixa, nunca um número exato.** O wiki (página
  Rareness) documenta as chances por raridade como intervalos — common 25–100%,
  uncommon 5–25%, semi-rare 1–5%, rare 0,5–1%, very rare <0,5%. Escolher um
  ponto dentro do intervalo seria inventar precisão. Todo o cálculo vive em
  `tibia-mcp/loot.py`; não reintroduzir tabelas de probabilidade fixas.
- **`{{Loot Item}}` tem dois formatos**: `|Item|raridade` e `|1-8|Item|raridade`.
  Metade das páginas usa o segundo. Ler o primeiro parâmetro como nome do item
  perde esses drops silenciosamente (foi o que aconteceu até 2026-08).
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
  Sessões reais dão uma saída: cada export é a equação
  `loot reportado = Σ (quantidade × preço)`. Com sessões de mix diferente o
  sistema fica determinado e dá pra recuperar os preços que o jogo usa.
- **O campo `p` do `creatures-data.js` guarda só o piso do preço.** No wiki o
  valor é uma faixa (Haunted Blade = "8.000 – 20.000"), porque NPCs diferentes
  pagam diferente. O gerador colapsou pro mínimo, então todo gp/kill do
  `loot.py` está subestimado. `session.price_range()` lê a faixa inteira; o
  `gen_creatures.py` ainda não foi corrigido.
- **`creatures-data.js` e `items-data.js` discordam de preço.** Frazzle Tongue
  tem `p: 700` num e `"Negotiable"` no outro; idem Frazzle Skin, Silencer
  Claws, Red Crystal Fragment e Silencer Resonating Chamber.

## Modelo de simulação de hunt

Fórmula da comunidade (a CipSoft nunca publicou; o próprio wiki diz que a
fórmula de dano atual é desconhecida):

```
max = 0,09 × skill × atk + level/5      min = level/5
```

- **Distance skill real = 104 de base** (confirmado pelo dono, level 366,
  magic level 29). O valor de 125 que este arquivo assumia era chute e
  inflava tudo. Com equipamento o efetivo fica ~120–125.
- **A munição é Diamond Arrow (atk 37), em área de 21 campos** — não flecha de
  alvo único. Isso domina o modelo: no export de 2h40, Diamond Arrow pegando
  5,5 alvos por tiro explica **99,3% do dano medido** sozinha. As magias somam
  pouco, e por isso magic level quase não mexe no dano (mas mexe na cura).
  Estimativas feitas com Crystalline Arrow (atk 65) subestimam o alvo errado.
- O dono joga **sempre em área**, nunca alvo único — bestas e bolts estão fora
  (não existe bolt de área).
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

## Sessão real medida: Guzzlemaw Valley, 2026-08-02 (2h40, 1.641 kills)

Três exports cumulativos em `sessions/2026-08-02-guzzlemaw-valley-*.txt`.
Primeira calibração com dados de verdade — o que ela fixou:

- **O banco de criaturas está certo**: a exp prevista bate com a raw xp
  reportada com **+0,14%** de erro em 1.641 kills.
- **Overkill de 8,3%** — estável nos três trechos (8,5 / 8,6 / 7,7). É
  característica do setup, não ruído.
- **Cura = 17,2% do dano causado, ou ~144 hp/s.** O modelo assume ~200 hp/s de
  leech duplo; ainda não sei se o contador do analyzer inclui leech, mas o
  número medido é bem menor.
- **O rendimento de drop confere**: 28 de 30 itens dentro da faixa de raridade
  do wiki, e os 2 restantes explicados por ruído de Poisson. **O modelo de
  raridade do `loot.py` está validado empiricamente.**
- Comparar drop **stackável** por kill exige multiplicar chance × tamanho da
  pilha. 77.257 gold coins em 1.641 kills não é 4.708% de chance — é chance
  normal pagando pilha.

Números do spawn (Frazzlemaw + Shock Head + Silencer):
616 kills/h · **2.464k raw xp/h** · loot 1.410 gp/kill · supply 769 gp/kill ·
**balance ~395k gp/h**. Contra os 1.079k raw xp/h estimados pro Werelion −2 —
mas atenção: aquilo é teto de modelo e isto é medição, não são comparáveis
até existir uma sessão real de Werelions.

### O que a sessão da noite resolveu

- **Multiplicador de XP, fechado.** A sessão de 21:00 (sem boost) deu
  **1,5000 exato** — essa é a base (stamina verde + premium). O boost é +50%
  multiplicativo: 1,5 × 1,5 = 2,25. Pelo ponto onde o trecho 3 quebra (61%
  ainda boostado), o boost acabou ~08:57, 2h19 depois do início — foram
  **2 boosts, não 1**. O dono não pretende comprar boost por ora, então
  assuma 1,5× fixo.
- **O trecho 2 gastou 185k gp a mais em supply** — 7,4 Stone Skin Amulets /
  Might Rings a 25.000 gp cada explicam o excesso inteiro. Não foi poção nem
  ritmo. O analyzer conta esses itens como supply quando quebram.

### `Damage/h` mede tempo de combate, não o relógio

Achado da sessão de 21:00, e é o jeito de medir utilização de graça:

```
tempo de combate = Damage ÷ (Damage/h)
utilização = tempo de combate ÷ duração pelos timestamps
```

Na sessão de 2h40 os dois batiam (**100% de utilização**). Na de 27 min o
`Damage/h` implicava 19,1 min de 26,8 — **71%**, os 7,7 min restantes foram
deslocamento até o spawn. Comparar `Raw XP/h` entre sessões de duração
diferente engana: sessão curta é dominada pelo overhead de setup. Compare
sempre **kills por hora de combate**.

Com utilização perto de 100% em combate, **prey de dano rende os ~34% cheios
em xp e em loot** — ganha do prey de XP, que dá +37% só de xp.

## Conclusões de equipamento já apuradas (spawn de Werelions)

- **Imbuements > troca de equipamento.** Demon Presence + Dragon Hide valem
  ~11% de mitigação; trocar de armor mexe 1–2%.
- Melhor armor: **Unerring Dragon SA** (dano) ou **Mutated Skin** (versátil —
  o earth +8% dela é o que serve em Cobra Bastion). Ghost t2 é a mais tanky.
- Falcon Bow, Falcon Coif e Falcon Greaves seguem imbatíveis até o level 400.
- **Guardian Boots têm holy −2%** → pioram a defesa neste spawn.
- Alicorn Headguard (400) e Sanguine Greaves (500) são os próximos saltos.

## Conclusões de equipamento (Guzzlemaw Valley / Roshamuul)

Tiradas dos `mods` das três criaturas — o inverso do que vale em Werelions.

| | Frazzlemaw | Shock Head | Silencer |
|---|---|---|---|
| physical | 95% | 90% | 95% |
| holy | 105% | 100% | **125%** |
| earth | 80% | **0%** | **0%** |
| fire | 90% | **0%** | 70% |
| death | 90% | 80% | **35%** |

- **Nenhum imbuement elemental serve aqui.** Venom e Scorch batem em imunidade
  em duas das três; Frost, Electrify e Reap ficam abaixo do físico. Manter dano
  físico + leech.
- **Divine Wrath (holy) é o melhor charm do spawn**, não Icicle.
- Os slots **defensivos rendem quase nada**: o dano recebido é físico + energy
  + life/mana drain, e não existe imbuement de resistência física. Demon
  Presence e Dragon Hide, que são a recomendação pra Werelions, são inúteis
  aqui.
