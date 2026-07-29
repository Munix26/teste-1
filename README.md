# teste-1 — Tibia-AI

Base do projeto **Tibia-AI**: dados do TibiaWiki consultáveis por IA via MCP,
para uso pessoal.

## Estado atual

- `index.html` — placeholder "em construção".
- `.mcp.json` — configuração do servidor MCP local do Tibia para o Claude Code.
- `tibia-mcp/` — tudo que é preciso para recriar o servidor MCP com dados:
  - `tibiawiki.dump` — banco PostgreSQL já populado (2.193 criaturas, 9.792
    itens, 1.246 NPCs, 443 caçadas, 371 quests, magias, mounts, etc.),
    crawleado de `tibia.fandom.com` (TibiaWiki em inglês).
  - `english-wiki-adaptation.patch` — adaptação do
    [miltonhit/tibia_mcp](https://github.com/miltonhit/tibia_mcp) para o wiki
    inglês (o wiki BR, `tibiawiki.com.br`, fica atrás de Cloudflare e é
    inacessível de ambientes de datacenter).
  - `setup.sh` — restaura tudo do zero num ambiente novo (Postgres local +
    restore do dump + servidor MCP), sem precisar refazer o crawl.

## Subindo o servidor MCP

```bash
bash tibia-mcp/setup.sh
# depois:
cd ~/tibia_mcp && MCP_HOST=127.0.0.1 .venv/bin/python -m src.mcp_server
# MCP URL: http://127.0.0.1:8000/sse
```

O `.mcp.json` do repositório aponta para esse endpoint local, então sessões
do Claude Code neste repo enxergam as 19 ferramentas do servidor (busca,
perfil de criaturas, onde obter/vender itens, caçadas recomendadas, SQL
livre, etc.) depois que ele estiver rodando.

### Limitações conhecidas dos dados

- Resistências elementais das criaturas (`hab_*`) e posições de mapa não
  importaram (formato diferente no wiki inglês) — afeta `creature_weakness`
  e as ferramentas de mapa.
- Runas são tratadas como itens no wiki inglês (tabela `runes` vazia).
- `where_to_sell_item` retorna o valor de NPC, mas a lista de NPCs
  compradores depende de dados de comércio que o wiki inglês estrutura de
  outra forma.
