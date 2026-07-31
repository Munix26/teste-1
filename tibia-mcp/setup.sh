#!/usr/bin/env bash
# Restaura o ambiente do Tibia MCP (TibiaWiki database + servidor MCP) do zero.
# Uso: bash tibia-mcp/setup.sh   (a partir da raiz do repositório)
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
WORK_DIR="${TIBIA_MCP_DIR:-$HOME/tibia_mcp}"
PGDATA=/var/lib/postgresql/tibia-pgdata
PGBIN=/usr/lib/postgresql/16/bin
DB_URL="postgresql://tibiawiki:tibiawiki@127.0.0.1:5432/tibiawiki"

# 1. Clona o servidor MCP e aplica o patch de adaptação para o wiki inglês
if [ ! -d "$WORK_DIR" ]; then
  git clone --depth 1 https://github.com/miltonhit/tibia_mcp "$WORK_DIR"
  git -C "$WORK_DIR" apply "$REPO_DIR/tibia-mcp/english-wiki-adaptation.patch"
fi

# 2. PostgreSQL local
if [ ! -d "$PGDATA" ]; then
  mkdir -p "$PGDATA" /var/run/postgresql
  chown postgres:postgres "$PGDATA" /var/run/postgresql
  su postgres -s /bin/bash -c "$PGBIN/initdb -D $PGDATA -E UTF8 --locale=C"
fi
su postgres -s /bin/bash -c "$PGBIN/pg_ctl -D $PGDATA -l /var/lib/postgresql/pg.log -o '-p 5432 -c listen_addresses=127.0.0.1' start" || true
sleep 1
su postgres -s /bin/bash -c "psql -p 5432 -tc \"SELECT 1 FROM pg_roles WHERE rolname='tibiawiki'\"" | grep -q 1 || \
  su postgres -s /bin/bash -c "psql -p 5432 -c \"CREATE USER tibiawiki WITH PASSWORD 'tibiawiki' SUPERUSER;\" -c 'CREATE DATABASE tibiawiki OWNER tibiawiki;'"

# 3. Restaura o dump (20k+ entidades já parseadas — sem necessidade de crawl)
PGPASSWORD=tibiawiki "$PGBIN/pg_restore" -h 127.0.0.1 -U tibiawiki -d tibiawiki --clean --if-exists "$REPO_DIR/tibia-mcp/tibiawiki.dump"

# 4. Dependências Python e servidor MCP
cd "$WORK_DIR"
python3 -m venv .venv
.venv/bin/pip install -q psycopg2-binary==2.9.9 requests==2.31.0 python-dotenv==1.0.1 "mcp>=1.0,<2"
cat > .env <<EOF
DATABASE_URL=$DB_URL
WIKI_API_URL=https://tibia.fandom.com/api.php
RATE_LIMIT_SECONDS=0.5
BATCH_SIZE=50
EOF

echo "Pronto. Para subir o servidor MCP:"
echo "  cd $WORK_DIR && MCP_HOST=127.0.0.1 .venv/bin/python -m src.mcp_server"
echo "  MCP URL: http://127.0.0.1:8000/sse"
