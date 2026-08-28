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
- Progresso de quests (conferido no quest log em 2026-08-17): **Feaster of
  Souls no capítulo The Thaian** (sinos de Kilmaresh/Ramoa/Lion's Rock;
  Netherworld entregue — os 3 Skull Coins foram comprados de players, o que
  funciona); Sea of Light feita; Liquid Black "The First Visitor" feita
  (pré-req da Secret Library ok); Blood Brothers m1–4 e Grimvale (An Ancient
  Feud + The Curse Spreads) feitas → Katex Blood Tongue liberado; **Explorer
  Society em Novice** (pickaxe não devolvida) — é o bloqueio da Dream Courts,
  que exige Relic Hunter. **Cults of Tibia inteira do zero** (no quest log
  só o Zathroth Remnants, que aparece sozinho) — irrelevante pras 7 quests:
  a Prosperity começa direto no Gareth, sem pré-requisito. World change
  Deepling estava no **stage 3** em 2026-08-17 (muda com o tempo —
  perguntar antes de mandar pra Fiehonja).
  O roteiro dessas quests vive em `roteiro.html`.
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
| `central.html` + `hunt-recs-data.js` | recomendações de hunt por level/voc curadas de bases da comunidade (TibiaBuddy, TibiaVault — coletadas 2026-08-16, fonte linkada em cada linha; **não inventar entradas: só adicionar com fonte real**) |
| `quests.html` + `quests-data.js` | 371 quests do wiki com recompensas linkando o catálogo de itens |
| `market.html` + `market-items.js` | preços e ofertas do Market **ao vivo** (api.tibiamarket.top) nos 113 mundos + custo de imbuement pelo preço do mundo escolhido + aba "Por servidor" (um item nos 113 mundos de uma vez) |
| `tibia-mcp/gen_quests.py` | regenera `quests-data.js` (itens de recompensa saem dos [[links]] do wikitext) |
| `tibia-mcp/gen_market.py` | regenera `market-items.js` (só metadados: id, nome, categoria, tier, NPC — **preço nenhum**) |
| `tibia-mcp/tibiawiki.dump` | banco PostgreSQL completo (28.967 páginas do wiki) |
| `tibia-mcp/setup.sh` | recria o ambiente do zero, sem refazer o crawl |
| `tibia-mcp/gen_items.py` | regenera `items-data.js` (inverte as loot tables para o índice de drops) |
| `tibia-mcp/gen_creatures.py` | regenera `creatures-data.js` |
| `tibia-mcp/gen_imbuements.py` | regenera `imbuements-data.js` (slots, efeitos e materiais saem do wikitext — a tabela `imbuements` importou vazia) |
| `tibia-mcp/gen_hunts.py` | regenera `hunts-data.js` (junta spawn + criaturas) |
| `tibia-mcp/loot.py` | parser compartilhado das loot tables + faixa de gp/kill |
| `tibia-mcp/english-wiki-adaptation.patch` | correções aplicadas no servidor MCP upstream |
| `ui.css` + `ui.js` | componentes compartilhados pelas 8 páginas + **camada mobile** (ver abaixo) |

## Decisões técnicas importantes

- **A camada mobile vive só em `ui.css`/`ui.js`** (alvo: iPhone 15 Pro Max,
  430×932 em retrato). Nenhum script de página mudou: `ui.js` monta o que o
  CSS de celular espera (painel dobrável de filtros, barra de ordenação,
  rótulo de cada célula copiado do `<thead>`) e o CSS transforma cada linha
  de tabela em cartão abaixo de 640px. Como o `<style>` inline de cada página
  carrega **depois** do `ui.css`, toda regra que precise vencer uma de página
  usa seletor mais específico (`.wrap .controls`, `#overlay .panel`,
  `.scroll > table > tbody > tr > td`) — nunca `!important`.
- **Campo de formulário no celular tem que ter 16px**, senão o Safari dá zoom
  sozinho ao focar e a página fica torta. O `viewport-fit=cover` + `env(safe-area-inset-*)`
  é o que mantém conteúdo fora do notch e da barra de gestos.
- **Ordenar sem `<thead>`**: no celular o cabeçalho da tabela some, então a
  barra "Ordenar" reproduz os `<th data-k>` num `<select>` e clica no `<th>`
  de verdade — cada página mantém a própria regra de sentido padrão, e nada
  precisou ser duplicado.

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
- **Preço de Market vem da API, não do repositório.** `api.tibiamarket.top`
  (Tibia Market Tracker, MIT, sem token, CORS liberado) cobre os 113 mundos.
  `market.html` busca a cada carregamento e guarda só em memória — preço
  commitado nasce velho e velho é pior que ausente. O que fica versionado é
  `market-items.js`: id, nome, categoria, tier e melhor NPC, que só mudam em
  update do jogo. **Não é a CipSoft**: os dados vêm de players rodando o
  extrator, então cada mundo tem sua própria idade (`/world_data.last_update`,
  de horas a poucos dias) — a página mostra essa idade de propósito.
- **A API usa `-1`, não `0`, para "sem leitura"** (19 dos 5.066 itens de
  Antica, e buracos no histórico). `-1` é truthy em JS: sem normalizar na
  entrada, vira "-1" como preço na tabela e afunda a escala do gráfico. O
  `clean()` de `market.html` zera todo numérico negativo — não remover.
- **Comparar um item entre mundos é uma chamada só.** `/item_comparison?item_id=`
  devolve os 113 mundos e **não pede `server`** — é o que a aba "Por servidor"
  usa, e por isso ela funciona antes de qualquer preço carregar. Cada mundo vem
  com o `time` da leitura *daquele* item ali: 26 dos 113 estão com mais de 7
  dias (alguns com meses), então o filtro de 7 dias vem ligado — sem ele o
  "mais barato" sai de um mundo que ninguém extrai desde o ano passado. O
  Market da CipSoft **não atravessa mundos**: a comparação diz se o seu mundo
  está caro, não onde arbitrar.
- **Item forjável não vem separado por tier.** `market_values` devolve um
  preço por object type id; t0 e t3 entram no mesmo número. Não usar para
  comparar Falcon Bow t1 vs t2.
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
- **Preço de Market: resolvido** pela API (ver `market.html`) — inclusive o
  endgame que o wiki marca como "negotiable". O que continua faltando é preço
  por tier e qualquer coisa fora do Market (Bazaar de personagem, negociação
  direta entre players).

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
