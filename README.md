# Tibia-AI

Ferramenta pessoal de consulta de dados de Tibia, focada em Paladin: um site
estático com o equipamento filtrado e um servidor MCP que dá à IA acesso ao
TibiaWiki inteiro.

## O que tem aqui

- **`index.html`** — catálogo completo de itens: 9.894 itens em 56 categorias
  (equipamento, itens de quest e delivery task, produtos de criatura, valiosos…).
  Filtra por categoria, vocação, level e presença de drop/atributos; clicar num
  item mostra propriedades, comércio e **quem dropa, com raridade e onde a
  criatura vive**.
- **`creatures.html`** — 1.629 criaturas com stats, resistências elementais e
  gp/kill; clicar abre o detalhe completo (habilidades, comportamento,
  localização, estratégia, bestiário e loot table). Filtra por faixas de exp,
  HP e ouro, e por "fraco a" cada elemento.
- **`spawns.html`** — 442 locais de caçada cruzados com suas criaturas, com
  exp média, exp/HP e ouro por kill **calculados** (o wiki não traz), ignorando
  bosses e objetos.
- **`items-data.js`** / **`creatures-data.js`** / **`hunts-data.js`** — os dados das páginas.
- **`tibia-mcp/`** — tudo para recriar o servidor MCP com dados:
  - `tibiawiki.dump` — banco PostgreSQL populado (2.193 criaturas, 9.792
    itens, 1.246 NPCs, 443 caçadas, 371 quests, magias, mounts e o wikitext
    completo de 28.967 páginas), crawleado de `tibia.fandom.com`.
  - `setup.sh` — restaura tudo do zero, sem refazer o crawl.
  - `gen_items.py` — regenera `items-data.js`.
  - `loot_value.py` — calcula gp/kill de criaturas (loot table × preço de NPC).
  - `english-wiki-adaptation.patch` — adaptação do
    [miltonhit/tibia_mcp](https://github.com/miltonhit/tibia_mcp) para o wiki
    inglês (o wiki BR fica atrás de Cloudflare e é inacessível de datacenter),
    mais um fix de placeholder SQL em `recommend_hunt`.

## Subindo o servidor MCP

```bash
bash tibia-mcp/setup.sh
cd ~/tibia_mcp && MCP_HOST=127.0.0.1 .venv/bin/python -m src.mcp_server
# MCP URL: http://127.0.0.1:8000/sse
```

`.mcp.json` já aponta para esse endpoint, então sessões do Claude Code neste
repositório enxergam as 19 ferramentas do servidor (busca, perfil de criaturas,
onde obter/vender itens, caçadas recomendadas, SQL livre) assim que ele subir.

## Limitações conhecidas dos dados

- Resistências elementais das criaturas e posições de mapa não importaram para
  as tabelas — existem no wikitext e podem ser consultadas caso a caso.
- `runes`, `tasks`, `world_quests` e `world_changes` ficaram vazias (formato
  diferente no wiki inglês); runas viram itens.
- Charm points e contagens do bestiário não importaram (ficam fora do infobox).
- Rating de exp/loot existe em apenas ~57% das caçadas — o wiki inglês deixa
  esses campos em branco na origem.
- Não há preços de Market ao vivo: 1.640 itens têm preço de NPC, mas o
  endgame (Soul Set, Alicorn, itens forjados) é todo "negotiable".

Ver `CLAUDE.md` para o contexto completo do projeto e as decisões técnicas.
