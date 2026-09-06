# Tibia-AI

Ferramenta pessoal de consulta de dados de Tibia, focada em Paladin: um site
estático com o equipamento filtrado e um servidor MCP que dá à IA acesso ao
TibiaWiki inteiro.

## O que tem aqui

- **`index.html`** — catálogo completo de itens: 9.894 itens organizados em
  grupo › categoria › subcategoria (Armas › Armas de Distância › Arco / Besta /
  Arremesso; Munição › Flecha / Virote; Espadas › Uma / Duas mãos; Runas ›
  Ataque / Cura / Suporte; equipamento por vocação…). Filtra por categoria,
  subcategoria, vocação, level e presença de drop/atributos; **ordena por
  qualquer atributo** (ataque, hit, defesa, armor, bônus de skill, magic level,
  velocidade, resistência total, alcance, slots, peso, preço de NPC, valor do
  wiki, preço no Market do mundo escolhido…); clicar num item mostra
  propriedades, comércio e **quem dropa, com raridade e onde a criatura vive**.
- **`creatures.html`** — 1.629 criaturas com stats, resistências elementais e
  gp/kill; clicar abre o detalhe completo (habilidades, comportamento,
  localização, estratégia, bestiário e loot table). Filtra por faixas de exp,
  HP e ouro, e por "fraco a" cada elemento.
- **`spawns.html`** — 442 locais de caçada cruzados com suas criaturas, com
  exp média, exp/HP e ouro por kill **calculados** (o wiki não traz), ignorando
  bosses e objetos.
- **`market.html`** — preços e ofertas do Market **ao vivo**, dos 113 mundos,
  via [Tibia Market Tracker](https://www.tibiamarket.top/): quanto custa
  comprar, quanto rende vender, o livro de ofertas, o histórico de 30 dias e
  em que mundos o item mais negocia. A aba **Por servidor** joga um item e
  mostra o preço dele nos 113 mundos de uma vez — onde está mais barato, onde
  paga melhor, a mediana e quantos mundos estão abaixo do seu — com a idade da
  leitura de cada mundo, porque preço barato de leitura de meses atrás não é
  preço. Traz também o **custo de cada imbuement** somando os materiais pelo
  preço do mundo escolhido. Nenhum preço fica versionado — cada carregamento
  busca na API, e a página mostra a idade da
  última leitura do mundo (os dados vêm de players rodando o extrator, não da
  CipSoft).

Nada aqui é inventado: o que não está no wiki aparece como "não disponível", e
o ouro por kill é sempre uma **faixa**, derivada das chances que o wiki
documenta por raridade — não um número exato.
- **`items-data.js`** / **`creatures-data.js`** / **`hunts-data.js`** — os dados das páginas.
- **`tibia-mcp/`** — tudo para recriar o servidor MCP com dados:
  - `tibiawiki.dump` — banco PostgreSQL populado (2.193 criaturas, 9.792
    itens, 1.246 NPCs, 443 caçadas, 371 quests, magias, mounts e o wikitext
    completo de 28.967 páginas), crawleado de `tibia.fandom.com`.
  - `setup.sh` — restaura tudo do zero, sem refazer o crawl.
  - `gen_items.py` — regenera `items-data.js`.
  - `categorize.py` — a taxonomia grupo › categoria › subcategoria dos itens.
  - `gen_market.py` — regenera `market-items.js` (metadados do Market; preço não).
  - `loot.py` — parser das loot tables e cálculo da faixa de gp/kill.
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
- O preço de Market (`market.html`) não vem separado por tier: um item
  forjável mistura t0–t3 no mesmo número. Bazaar de personagem e negociação
  direta entre players ficam de fora — não existe API para eles.

Ver `CLAUDE.md` para o contexto completo do projeto e as decisões técnicas.
