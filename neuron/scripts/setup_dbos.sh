#!/usr/bin/env bash
# ============================================================
# VAMS Neuron — DBOS Development Setup
# ============================================================
# Spins up a local PostgreSQL container (Docker required) and
# installs the DBOS Python dependencies, then verifies the
# connection is ready for DBOS.launch().
#
# Usage:
#   cd neuron
#   bash scripts/setup_dbos.sh
#
# For Neon (no Docker):
#   1. Create a project at https://neon.tech
#   2. Copy the connection string into neuron/.env
#   3. Run: pip install dbos psycopg2-binary && python -c "from dbos_config import init_dbos; init_dbos(); print('DBOS ready')"
# ============================================================

set -euo pipefail

: "${DB_USER:?Set DB_USER for the disposable development database}"
: "${DB_PASSWORD:?Set DB_PASSWORD through the local secret environment}"
: "${DB_NAME:?Set DB_NAME for the disposable development database}"
DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-5432}"
export DB_USER DB_PASSWORD DB_NAME DB_HOST DB_PORT

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  VAMS Neuron — DBOS Setup                   ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ── Step 1: Install Python deps ──────────────────────────
echo "[1/4] Installing Python dependencies..."
pip install "dbos>=0.29.0" "psycopg2-binary>=2.9.9" --quiet
echo "      ✓ dbos + psycopg2-binary installed"

# ── Step 2: Start local Postgres via Docker ──────────────
echo ""
echo "[2/4] Starting local PostgreSQL container (vams-pg)..."

if docker ps -q --filter "name=vams-pg" | grep -q .; then
    echo "      ✓ Container already running"
else
    docker run -d \
        --name vams-pg \
        -e POSTGRES_USER \
        -e POSTGRES_PASSWORD \
        -e POSTGRES_DB \
        -p "$DB_PORT:5432" \
        postgres:16 \
        --restart unless-stopped 2>/dev/null || \
    docker start vams-pg
    echo "      ✓ Container started"
    echo "      Waiting for Postgres to be ready..."
    sleep 3
fi

# ── Step 3: Write .env if missing ────────────────────────
echo ""
echo "[3/4] Checking .env..."

ENV_FILE="$(dirname "$0")/../.env"
if [ ! -f "$ENV_FILE" ]; then
    cp "$(dirname "$0")/../.env.example" "$ENV_FILE"
    echo "      ✓ .env created without credentials; runtime values stay in the environment"
else
    echo "      ✓ .env already exists (skipping)"
fi

# ── Step 4: Verify connection ────────────────────────────
echo ""
echo "[4/4] Verifying DBOS connection..."

export DBOS_SYSTEM_DATABASE_URL
DBOS_SYSTEM_DATABASE_URL="$(python -c '
import os
from urllib.parse import quote, urlunsplit

user = quote(os.environ["DB_USER"], safe="")
password = quote(os.environ["DB_PASSWORD"], safe="")
database = quote(os.environ["DB_NAME"], safe="")
userinfo = f"{user}:{password}"
authority = f"{userinfo}@{os.environ["DB_HOST"]}:{os.environ["DB_PORT"]}"
print(urlunsplit(("postgresql", authority, f"/{database}", "", "")))
')"

python -c "
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath('.')))
from dbos_config import init_dbos, destroy_dbos
try:
    init_dbos()
    print('      ✓ DBOS connected to Postgres successfully')
    destroy_dbos()
except Exception as e:
    print(f'      ✗ Connection failed: {e}')
    sys.exit(1)
"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  Setup complete! DBOS is ready.             ║"
echo "║                                              ║"
echo "║  Next steps:                                 ║"
echo "║    python neuron.py --demo-workflow          ║"
echo "║    python -m pytest tests/test_workflows.py  ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
