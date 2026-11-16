#!/usr/bin/env bash
# Pull, install, migrate, build, and reload Dossier.
#
# Run as the `dossier` user:
#   /var/www/dossier/deploy/deploy.sh
#
# BACKEND_URL is baked into the Next.js build. It defaults to the loopback API,
# which is correct for a single server with Nginx in front.

set -euo pipefail

# uv and pnpm shims installed for the service user.
export PATH="/home/dossier/.local/bin:$PATH"

APP_DIR="${APP_DIR:-/var/www/dossier}"
BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:8000}"

cd "$APP_DIR"

echo "==> Pulling latest code"
git pull --ff-only

echo "==> Backend dependencies"
cd "$APP_DIR/backend"
uv sync --frozen --no-dev

echo "==> Database migrations"
.venv/bin/alembic upgrade head

echo "==> Frontend dependencies and build"
cd "$APP_DIR/frontend"
BACKEND_URL="$BACKEND_URL" pnpm install --frozen-lockfile
BACKEND_URL="$BACKEND_URL" pnpm build

echo "==> Reloading PM2 processes"
pm2 startOrReload "$APP_DIR/deploy/ecosystem.config.cjs" --update-env
pm2 save

echo "==> Done"
pm2 status
