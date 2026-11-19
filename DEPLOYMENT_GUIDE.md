# Dossier Deployment Guide

This is the complete deployment reference for this repository. It covers every
supported way to run Dossier, the full environment-variable surface, first-run
setup, verification, operations, and troubleshooting.

Related documents:

| Document | Contents |
|---|---|
| `README.md` | Product overview, architecture, local development, testing |
| `DEPLOYMENT.md` | Long-form single-server walkthrough (PM2 + Nginx) |
| `deploy/` | Ready-to-use PM2, Nginx, environment, deploy, and backup files |

---

## 1. What has to be deployed

Dossier is not a static site. A working deployment needs all of the following:

| Component | What it is | Can it be serverless? |
|---|---|---|
| Console | Next.js 16 app (`frontend/`) | Yes (Vercel), or Node on a server |
| API | FastAPI app (`backend/`) | No; needs a long-lived process |
| Worker | Celery worker (`app.workers`) | No; needs a long-lived process |
| Scheduler | Celery Beat, fires every minute | No; exactly one instance |
| Database | PostgreSQL 17 with `pgvector` and `citext` | Managed Postgres is fine |
| Cache/broker | Redis 7+ (rate limits, locks, Celery broker) | Managed Redis is fine |
| Model runtime | Ollama chat model | Any reachable HTTP endpoint |
| Mail | SMTP provider, configured in the console | External service |

The console can run without everything else only in **demo mode**, which serves an
in-memory sample API. See [Option D](#8-option-d-demo-only-no-backend).

---

## 2. Deployment options

| Option | Best for | Console | API, worker, beat | Database, Redis | Effort |
|---|---|---|---|---|---|
| A. Local stack | Development and demos | Host (`pnpm dev`) | Docker Compose | Docker Compose | Low |
| B. Single server | Full production on one VPS | PM2 on the server | PM2 on the server | Local systemd services | Medium |
| C. Split | Console on Vercel, backend elsewhere | Vercel | Container host | Managed or self-hosted | Medium |
| D. Demo only | Showing the UI | Vercel or local | None | None | Lowest |

Choosing:

- **One machine, full product** - Option B. It is the most predictable and the only
  option documented end to end in `DEPLOYMENT.md`.
- **Managed frontend CDN, backend on a VPS or container platform** - Option C.
- **No backend at all** - Option D. Never use demo mode for real generation or mail.

Vercel cannot host the API, worker, Beat, PostgreSQL, or Redis. It is a serverless
platform; Celery Beat alone requires a continuously running singleton.

---

## 3. Version matrix

| Runtime | Required | Notes |
|---|---|---|
| Python | 3.12 recommended, 3.11+ accepted | `backend/pyproject.toml` sets `requires-python >=3.11` |
| Node.js | 24 LTS recommended (24+ acceptable) | Next.js 16.4.4 and React 19.3.1 |
| pnpm | 11.23.0 | `frontend/pnpm-lock.yaml` is frozen in deploys |
| PostgreSQL | 17 with `pgvector` and `citext` | Use the `pgvector/pgvector:pg17` image or `postgresql-17-pgvector` |
| Redis | 7+ | Compose uses `redis:8-alpine`; Ubuntu ships 7.x |
| Ollama | Any recent release | Model must already be pulled |
| Docker | Engine 24+ and Compose v2 | Option A only |

Lockfiles (`backend/uv.lock`, `frontend/pnpm-lock.yaml`) are committed. Deploy with
`uv sync --frozen` and `pnpm install --frozen-lockfile` so builds are reproducible.

---

## 4. Environment variables

The backend is configured entirely through environment variables, loaded by
`backend/app/config/settings.py`. The frontend has two build-time variables.

### 4.1 How configuration is loaded

Backend (`pydantic-settings`):

1. Real process environment variables (highest priority).
2. `.env` in the current working directory.
3. `../.env` relative to the current working directory.

Running from `backend/` therefore reads `backend/.env` first, then the repository-root
`.env`. Docker Compose loads the root `.env` through `env_file` and overrides only
`DATABASE_URL`, `TEST_DATABASE_URL`, and `REDIS_URL` with container-network values.
Model settings are passed through from `.env` unchanged.

The process will refuse to start if either validator fails:

| Validation | Rule |
|---|---|
| `JWT_SECRET` | At least 32 bytes; the default empty string fails |
| `CREDENTIAL_ENCRYPTION_KEYS` | Non-empty, and every entry must be a valid Fernet key in `key_id:key` form |
| `CREDENTIAL_ENCRYPTION_ACTIVE_KEY_ID` | Must match one of the configured key ids |

That means `JWT_SECRET` and `CREDENTIAL_ENCRYPTION_KEYS` are **required in every
environment**, including development.

Frontend (`next.config.ts` and `src/lib/api.ts`):

- `BACKEND_URL` is read when `next build` runs and compiled into the `/api` rewrite.
  Changing it requires a rebuild, not just a restart.
- `NEXT_PUBLIC_DEMO_MODE` is also inlined at build time. It selects the in-memory demo
  API instead of the real one.
- Nothing else in the frontend reads runtime configuration.

### 4.2 Backend variable reference

#### Application

| Variable | Default | Required | Purpose |
|---|---|---|---|
| `APP_NAME` | `Dossier` | No | FastAPI title |
| `APP_ENV` | `development` | Recommended | `development`, `test`, or `production`. Production enables JSON logs, disables `/docs` and `/openapi.json`, and forces secure cookies |
| `LOG_LEVEL` | `INFO` | No | Structlog level |
| `API_V1_PREFIX` | `/api/v1` | No | Prefix for all application routes |

#### Database and cache

| Variable | Default | Required | Purpose |
|---|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://dossier:dossier@localhost:5433/dossier` | Yes in practice | SQLAlchemy async URL. Use a hex password to avoid URL-encoding problems |
| `TEST_DATABASE_URL` | none | Tests only | Separate database used by pytest |
| `REDIS_URL` | `redis://localhost:6379/0` | Yes in practice | Login rate limits, sync locks, Celery broker and result backend. With auth use `redis://:PASSWORD@host:6379/0` |

#### Authentication and sessions

| Variable | Default | Required | Purpose |
|---|---|---|---|
| `JWT_SECRET` | empty | Yes (32+ bytes) | Access-token signing key |
| `JWT_ALGORITHM` | `HS256` | No | Leave as is |
| `ACCESS_TOKEN_TTL_MINUTES` | `15` | No | Access-token lifetime |
| `REFRESH_TOKEN_TTL_DAYS` | `7` | No | Refresh-token lifetime |
| `COOKIE_SECURE` | `false` | Yes in production | Send cookies only over HTTPS. Forced to true whenever `APP_ENV=production` |
| `COOKIE_DOMAIN` | empty | No | Set only for a shared parent domain. Leave empty for a single host or the Vercel rewrite |
| `RATE_LIMIT_LOGIN_ATTEMPTS` | `5` | No | Failed logins allowed per window |
| `RATE_LIMIT_LOGIN_WINDOW_SECONDS` | `60` | No | Window length in seconds |
| `CORS_ORIGINS` | empty | No | Comma-separated origins. Only needed when a browser calls the API directly. The Next.js rewrite is same-origin and does not trigger CORS |

#### Model

| Variable | Default | Required | Purpose |
|---|---|---|---|
| `LLM_PROVIDER` | `ollama` | No | Only `ollama` is implemented; any other value raises at generation time |
| `OLLAMA_BASE_URL` | `http://host.docker.internal:11434` | Yes | Ollama endpoint. Use `http://127.0.0.1:11434` when the API runs on the same host outside Docker, or `https://ollama.com` for Ollama Cloud |
| `OLLAMA_API_KEY` | empty | Cloud only | Bearer token sent to the endpoint. Required for Ollama Cloud; leave empty for a local Ollama instance |
| `OLLAMA_CHAT_MODEL` | `deepseek-v4.1-flash:cloud` | Yes | Exact model name present on the endpoint (`ollama list` locally, or the cloud catalog) |
| `LLM_TIMEOUT_SECONDS` | `120` | No | Generation timeout. Keep it below the proxy read timeout |

#### Mail engine

| Variable | Default | Required | Purpose |
|---|---|---|---|
| `MAIL_MAX_ROWS_PER_SOURCE` | `50` | No | Sample rows per source included in a prompt |
| `MAIL_AGGREGATE_ROW_CAP` | `2000` | No | Rows considered for numeric aggregates |
| `MAIL_MAX_PROMPT_CHARS` | `30000` | No | Hard cap on assembled context |
| `MAIL_SEND_RETRIES` | `3` | No | SMTP attempts per delivery |

#### Background work

| Variable | Default | Required | Purpose |
|---|---|---|---|
| `DAILY_SYNC_HOUR_UTC` | `2` | No | Hour (0-23 UTC) of the daily connector sync |
| `SYNC_LOCK_TTL_SECONDS` | `1800` | No | Distributed sync lock lifetime |

#### First administrator

Read only by `python -m app.cli bootstrap`.

| Variable | Default | Purpose |
|---|---|---|
| `BOOTSTRAP_ORG_NAME` | `Dossier` | Organisation name |
| `BOOTSTRAP_DEPARTMENT_NAME` | `General` | Initial department |
| `BOOTSTRAP_ADMIN_EMAIL` | `admin@example.com` | First administrator's email |
| `BOOTSTRAP_ADMIN_FULL_NAME` | `Platform Administrator` | First administrator's display name |

#### Credential encryption

| Variable | Default | Required | Purpose |
|---|---|---|---|
| `CREDENTIAL_ENCRYPTION_KEYS` | empty | Yes | Comma-separated `key_id:fernet_key` entries, e.g. `v1:<key>` or `v1:<old>,v2:<new>` during rotation |
| `CREDENTIAL_ENCRYPTION_ACTIVE_KEY_ID` | `v1` | Yes | Which key encrypts new values. Must exist in the list |

These keys encrypt connector credentials and SMTP passwords at rest. **Back them up
outside the server.** Without the key that encrypted a secret, that secret cannot be
recovered.

#### Not environment variables

SMTP host, port, username, password, sender address, and security mode are configured
in the console under **Mail > SMTP settings**, encrypted with the key above. Google
Sheets and Zoho CRM credentials are configured under **Data > Connectors** and are also
encrypted. Do not put them in `.env`.

### 4.3 Frontend variable reference

| Variable | Default | When read | Purpose |
|---|---|---|---|
| `BACKEND_URL` | `http://localhost:8000` | Build time | Target of the `/api/:path*` rewrite. Must be reachable from the Next.js server, not the browser |
| `NEXT_PUBLIC_DEMO_MODE` | unset | Build time | `true` serves the in-memory demo API at `/demo-api/v1` and prefills demo login |
| `NODE_ENV` | set by Next.js | Runtime | Leave alone |

Test-only variables, used by Playwright and never by a deployment:

| Variable | Purpose |
|---|---|
| `E2E_ADMIN_EMAIL` | Administrator email for browser tests |
| `E2E_ADMIN_PASSWORD` | Administrator password for browser tests |

### 4.4 Copy-paste profiles

#### Local development (host backend, Docker infrastructure)

```dotenv
APP_NAME=Dossier
APP_ENV=development
LOG_LEVEL=INFO
API_V1_PREFIX=/api/v1

DATABASE_URL=postgresql+asyncpg://dossier:dossier@localhost:5433/dossier
TEST_DATABASE_URL=postgresql+asyncpg://dossier:dossier@localhost:5433/dossier_test
REDIS_URL=redis://localhost:6379/0

JWT_SECRET=<output of: openssl rand -hex 32>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_TTL_MINUTES=15
REFRESH_TOKEN_TTL_DAYS=7
COOKIE_SECURE=false
COOKIE_DOMAIN=
RATE_LIMIT_LOGIN_ATTEMPTS=5
RATE_LIMIT_LOGIN_WINDOW_SECONDS=60
CORS_ORIGINS=http://localhost:3000

LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_API_KEY=
OLLAMA_CHAT_MODEL=minimax-m3.1-flash
LLM_TIMEOUT_SECONDS=120

BOOTSTRAP_ORG_NAME=Dossier
BOOTSTRAP_DEPARTMENT_NAME=General
BOOTSTRAP_ADMIN_EMAIL=admin@example.com
BOOTSTRAP_ADMIN_FULL_NAME=Platform Administrator

CREDENTIAL_ENCRYPTION_KEYS=v1:<output of the Fernet generation command>
CREDENTIAL_ENCRYPTION_ACTIVE_KEY_ID=v1

DAILY_SYNC_HOUR_UTC=2
SYNC_LOCK_TTL_SECONDS=1800

MAIL_MAX_ROWS_PER_SOURCE=50
MAIL_AGGREGATE_ROW_CAP=2000
MAIL_MAX_PROMPT_CHARS=30000
MAIL_SEND_RETRIES=3
```

`OLLAMA_BASE_URL` must be `http://127.0.0.1:11434` if the API runs on the host instead
of inside Compose. Inside Compose, `host.docker.internal` reaches the host on Docker
Desktop; on a Linux Docker host add `extra_hosts: ["host.docker.internal:host-gateway"]`
to the backend, worker, and beat services.

#### Single-server production

Use `deploy/dossier.env.example` as the template. Values that must differ from the
development profile:

```dotenv
APP_ENV=production
LOG_LEVEL=INFO

DATABASE_URL=postgresql+asyncpg://dossier:<DB_PASSWORD>@127.0.0.1:5432/dossier
REDIS_URL=redis://:<REDIS_PASSWORD>@127.0.0.1:6379/0

JWT_SECRET=<openssl rand -hex 32>
COOKIE_SECURE=true
CORS_ORIGINS=https://app.example.com

OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_CHAT_MODEL=llama3.1:8b

CREDENTIAL_ENCRYPTION_KEYS=v1:<fresh Fernet key>
CREDENTIAL_ENCRYPTION_ACTIVE_KEY_ID=v1
```

#### Split deployment (Vercel console + remote API)

Backend host: the production profile above, with `OLLAMA_BASE_URL` pointing at a
reachable Ollama endpoint and `CORS_ORIGINS` left empty unless a client calls the API
directly.

Vercel: one variable before the first build.

```text
BACKEND_URL=https://api.example.com
```

#### Demo only

```text
NEXT_PUBLIC_DEMO_MODE=true
```

Do not set `BACKEND_URL`; it is unused in demo mode.

### 4.5 Generating secrets

```bash
# JWT signing key (64 hex characters = 32 bytes)
openssl rand -hex 32

# Credential-encryption Fernet key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Database and Redis passwords (hex needs no URL encoding)
openssl rand -hex 24
```

Windows PowerShell equivalents:

```powershell
# JWT signing key
-join ((1..32) | ForEach-Object { '{0:x2}' -f (Get-Random -Minimum 0 -Maximum 256) })

# Fernet key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Store the JWT secret, Fernet keys, database password, Redis password, and a copy of
`.env` in a password manager or secrets vault, outside the repository.

---

## 5. Option A: local development with Docker Compose

This runs PostgreSQL, Redis, the API, the workers, and a development SMTP sink in
containers, with the console on the host.

### 5.1 Start infrastructure

```powershell
Copy-Item .env.example .env
# Edit .env: set JWT_SECRET and CREDENTIAL_ENCRYPTION_KEYS (see 4.5)

docker compose up -d db redis backend mailhog
docker compose --profile workers up -d worker beat
```

What Compose provides:

| Service | Container name (project `dossier`) | Host port | Notes |
|---|---|---|---|
| `db` | `dossier-db-1` | `5433` to `5432` | `pgvector/pgvector:pg17`, initialises `citext` and `vector` via `scripts/init-test-db.sql` |
| `redis` | `dossier-redis-1` | `6379` | No password in development |
| `backend` | `dossier-backend-1` | `8000` | `uvicorn --reload`, mounts `./backend` into `/app` |
| `worker` | `dossier-worker-1` | none | Celery, `--concurrency=2`, profile `workers` |
| `beat` | `dossier-beat-1` | none | Celery Beat, profile `workers` |
| `mailhog` | `dossier-mailhog-1` | `1025` SMTP, `8025` UI | Development mail sink |

The worker and beat services use `image: dossier-backend:latest`, which Compose tags
from the `backend` service build. **Build or start `backend` before the workers**, as
shown above, or run `docker compose build backend` first.

Inside Compose, `.env` database and cache values are overridden with container
addresses:

```text
DATABASE_URL=postgresql+asyncpg://dossier:dossier@db:5432/dossier
TEST_DATABASE_URL=postgresql+asyncpg://dossier:dossier@db:5432/dossier_test
REDIS_URL=redis://redis:6379/0
```

`OLLAMA_BASE_URL`, `OLLAMA_API_KEY`, and `OLLAMA_CHAT_MODEL` are **not** overridden, so
the values in `.env` apply unchanged. Point `OLLAMA_BASE_URL` at
`http://host.docker.internal:11434` for a local Ollama, or at `https://ollama.com` with
an `OLLAMA_API_KEY` for Ollama Cloud.

### 5.2 Migrate and create the first administrator

```powershell
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.cli bootstrap
docker compose exec backend python -m app.cli seed-demo   # optional
```

`bootstrap` prints a one-time password. Replace it with a known value if you prefer:

```powershell
docker compose exec backend python -m app.cli set-password `
  --email admin@example.com --password "a-strong-password"
```

### 5.3 Run the console

```powershell
pnpm --dir frontend install
pnpm --dir frontend dev
```

| Service | URL |
|---|---|
| Console | http://localhost:3000 |
| API docs (development only) | http://localhost:8000/docs |
| API health | http://localhost:8000/health/ready |
| Mailhog | http://localhost:8025 |

Configure SMTP in **Mail > SMTP settings** with host `mailhog`, port `1025`, no
credentials, no TLS. Delivered mail appears in Mailhog.

### 5.4 Stopping and resetting

```powershell
docker compose --profile workers down          # stop, keep data
docker compose --profile workers down -v       # stop and delete the database volume
```

The database volume is `dossier_db_data`.

---

## 6. Option B: single Ubuntu server (PM2 + Nginx)

This is the recommended full-production topology. `DEPLOYMENT.md` contains the same
steps with more prose; the essentials are repeated here so this guide stands alone.

Assumed layout:

| Placeholder | Meaning |
|---|---|
| `app.example.com` | Console hostname |
| `api.example.com` | API hostname |
| `203.0.113.10` | Server IPv4 |
| `/var/www/dossier` | Application directory |
| `dossier` | Unprivileged service user |

### 6.1 Prepare the server

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl git unzip build-essential ca-certificates ufw

sudo timedatectl set-timezone UTC

sudo adduser --disabled-password --gecos "" dossier
sudo mkdir -p /var/www/dossier /var/log/dossier /var/backups/dossier /var/www/certbot
sudo chown -R dossier:dossier /var/www/dossier /var/log/dossier /var/backups/dossier /var/www/certbot
sudo chmod 750 /var/log/dossier /var/backups/dossier

sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
```

Open only 22, 80, and 443. Never expose 3000, 8000, 5432, 6379, or 11434.

### 6.2 Install runtimes

```bash
# Node.js 24, pnpm, PM2
curl -fsSL https://deb.nodesource.com/setup_24.x | sudo -E bash -
sudo apt install -y nodejs
sudo corepack enable
sudo corepack prepare pnpm@11.23.0 --activate
sudo npm install -g pm2

# Python, build headers, Nginx, Certbot
sudo apt install -y python3.12 python3.12-venv python3-pip libpq-dev nginx certbot

# uv for the service user
sudo -u dossier -H bash -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'
echo 'export PATH="$HOME/.local/bin:$PATH"' | sudo -u dossier tee -a /home/dossier/.bashrc
sudo -u dossier -H bash -lc 'uv --version'
```

### 6.3 PostgreSQL 17 with pgvector

```bash
sudo install -d /usr/share/postgresql-common/pgdg
sudo curl -fsSL -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
  https://www.postgresql.org/media/keys/ACCC4CF8.asc

. /etc/os-release
echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] \
https://apt.postgresql.org/pub/repos/apt ${VERSION_CODENAME}-pgdg main" |
  sudo tee /etc/apt/sources.list.d/pgdg.list

sudo apt update
sudo apt install -y postgresql-17 postgresql-17-pgvector
sudo systemctl enable --now postgresql
```

Create the role, database, and extensions:

```bash
DB_PASS="$(openssl rand -hex 24)"
echo "PostgreSQL password: $DB_PASS"   # store it now

sudo -u postgres psql <<SQL
CREATE USER dossier WITH PASSWORD '${DB_PASS}';
CREATE DATABASE dossier OWNER dossier;
\c dossier
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS vector;
SQL

sudo -u postgres psql -d dossier -c "SELECT extname FROM pg_extension;"
PGPASSWORD="$DB_PASS" psql -h 127.0.0.1 -U dossier -d dossier -c "SELECT 1;"
```

Optional tuning for a small server in `/etc/postgresql/17/main/postgresql.conf`:

```text
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 16MB
maintenance_work_mem = 128MB
```

### 6.4 Redis

```bash
sudo apt install -y redis-server
```

Edit `/etc/redis/redis.conf`:

```text
bind 127.0.0.1 ::1
protected-mode yes
supervised systemd
requirepass <REDIS_PASSWORD>
```

```bash
sudo systemctl restart redis-server
redis-cli -a '<REDIS_PASSWORD>' ping    # PONG
```

### 6.5 Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl enable --now ollama
ollama pull llama3.1:8b          # or llama3.2:3b on a small server

curl -s http://127.0.0.1:11434/api/tags
```

Use the exact pulled name in `OLLAMA_CHAT_MODEL`. A CPU-only 8B model is slow; either
use a smaller model, give Ollama a GPU, or point `OLLAMA_BASE_URL` at a stronger host.

To use Ollama Cloud instead of a local runtime, skip the install and set:

```dotenv
OLLAMA_BASE_URL=https://ollama.com
OLLAMA_API_KEY=<your Ollama Cloud API key>
OLLAMA_CHAT_MODEL=<a model available to that key>
```

Verify the credential and list the models it can access:

```bash
curl -fsS -H "Authorization: Bearer $OLLAMA_API_KEY" https://ollama.com/api/tags
```

The key is sent only to the configured endpoint. Keep it in `.env`, never in the
repository, and rotate it in the Ollama account if it is exposed.

### 6.6 Deploy the code and environment

```bash
sudo -u dossier git clone https://github.com/sidd154/Dossier.git /var/www/dossier
cd /var/www/dossier

sudo -u dossier cp deploy/dossier.env.example .env
sudo -u dossier chmod 600 .env
sudo -u dossier nano /var/www/dossier/.env
```

Fill every `CHANGE_ME`. The required production differences are listed in
[4.4](#single-server-production).

### 6.7 Install dependencies and migrate

```bash
sudo -u dossier -H bash -lc '
  cd /var/www/dossier/backend
  uv sync --frozen --no-dev
  .venv/bin/alembic upgrade head
'

sudo -u dossier -H bash -lc '
  cd /var/www/dossier/backend
  .venv/bin/python -m app.cli bootstrap
'
```

`bootstrap` prints a one-time administrator password. Either sign in and change it, or
set a known password directly:

```bash
sudo -u dossier -H bash -lc '
  cd /var/www/dossier/backend
  .venv/bin/python -m app.cli set-password \
    --email admin@example.com --password "a-strong-password"
'
```

Do not run `seed-demo` in production.

### 6.8 Build the console

`BACKEND_URL` is compiled into the rewrite. On one server it must be the loopback API:

```bash
sudo -u dossier -H bash -lc '
  cd /var/www/dossier/frontend
  BACKEND_URL=http://127.0.0.1:8000 pnpm install --frozen-lockfile
  BACKEND_URL=http://127.0.0.1:8000 pnpm build
'
```

Changing `BACKEND_URL` later requires a rebuild.

### 6.9 Start with PM2

`deploy/ecosystem.config.cjs` defines four processes, all bound to `127.0.0.1`:
`dossier-api` (uvicorn, 2 workers), `dossier-worker` (Celery, concurrency 2),
`dossier-beat` (Celery Beat), and `dossier-web` (Next.js on port 3000).

Start as the `dossier` user, otherwise PM2 creates root-owned files:

```bash
sudo -u dossier -H bash -lc '
  cd /var/www/dossier
  pm2 startOrReload deploy/ecosystem.config.cjs --update-env
  pm2 save
'

sudo env PATH="$PATH" pm2 startup systemd -u dossier --hp /home/dossier
# Run the exact command PM2 prints, then:
sudo -u dossier -H bash -lc 'pm2 save'
```

Verify before involving Nginx:

```bash
curl -fsS http://127.0.0.1:8000/health/live
curl -fsS http://127.0.0.1:8000/health/ready
curl -fsS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:3000/login
```

### 6.10 Nginx and TLS

Point both DNS records at the server first.

```bash
# 1. HTTP-only config for the ACME challenge
sudo cp /var/www/dossier/deploy/nginx/dossier.http.conf \
  /etc/nginx/sites-available/dossier.conf
sudo ln -sf /etc/nginx/sites-available/dossier.conf \
  /etc/nginx/sites-enabled/dossier.conf
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

# 2. Issue the certificate
sudo certbot certonly --webroot -w /var/www/certbot \
  -d app.example.com -d api.example.com \
  --email you@example.com --agree-tos --no-eff-email

# 3. Switch to the HTTPS config
sudo cp /var/www/dossier/deploy/nginx/dossier.conf \
  /etc/nginx/sites-available/dossier.conf
sudo sed -i 's/app\.example\.com/app.yourdomain.com/g; s/api\.example\.com/api.yourdomain.com/g' \
  /etc/nginx/sites-available/dossier.conf
sudo nginx -t && sudo systemctl reload nginx

# 4. Confirm renewal works
sudo certbot renew --dry-run
```

The configuration redirects HTTP to HTTPS, proxies the console to `127.0.0.1:3000`,
proxies the API to `127.0.0.1:8000` with a 240-second read timeout for generation,
sets `X-Forwarded-Proto` for secure cookies, and adds HSTS and basic security headers.
Health endpoints are exposed at `/health/live` and `/health/ready` on the API host.

---

## 7. Option C: split deployment (Vercel console + container backend)

### 7.1 Backend host

Run the API, worker, and Beat on any platform that supports long-lived processes: a
VPS with Docker Compose, Fly.io, Railway, Render, ECS, or Kubernetes. Requirements:

- PostgreSQL 17 with `pgvector` and `citext`.
- Redis reachable by API, worker, and Beat.
- Three processes: `uvicorn app.main:app`, `celery -A app.workers.celery_app:celery_app
  worker`, and `celery -A app.workers.celery_app:celery_app beat`.
- **Exactly one Beat instance.** Multiple schedulers cause duplicate dispatch.
- A TLS-terminating reverse proxy in front of the API.
- Persistent database and Redis; the application itself keeps no local files, so the
  API and worker can be replicated freely.

Build the backend image from the repository root:

```bash
docker build -t dossier-api ./backend
docker run --env-file .env -p 127.0.0.1:8000:8000 dossier-api
```

The image does not run migrations. Run them once per release:

```bash
uv run alembic upgrade head
# or, in a container:
docker run --rm --env-file .env dossier-api alembic upgrade head
```

Then create the first administrator:

```bash
docker run --rm --env-file .env dossier-api python -m app.cli bootstrap
```

Environment notes for a remote host:

- `DATABASE_URL`, `REDIS_URL`, and `OLLAMA_BASE_URL` must use addresses reachable from
  inside the container. `127.0.0.1` and `localhost` refer to the container itself, not
  the host. Use a managed database hostname, a private IP, or a Docker network alias.
- If Ollama runs on the same Docker host, add `host.docker.internal:host-gateway` or use
  the host's private IP.
- `COOKIE_SECURE=true` and `APP_ENV=production`.
- `CORS_ORIGINS` can stay empty for the console, because the rewrite keeps the browser
  same-origin.
- Restrict `/docs` by leaving `APP_ENV=production`, which disables it.

### 7.2 Console on Vercel

1. Import the repository in Vercel.
2. Set **Root Directory** to `frontend`.
3. Framework preset: **Next.js** (auto-detected; `frontend/vercel.json` also declares it).
4. Add `BACKEND_URL=https://api.example.com` for Production and Preview **before the
   first build**.
5. Deploy.

CLI equivalent:

```powershell
cd frontend
vercel login
vercel env add BACKEND_URL production
vercel --prod
```

How the pieces connect:

```text
Browser
   |
   v
Vercel (app.example.com)
   |  Next.js rewrite: /api/* -> BACKEND_URL/api/*
   v
FastAPI (api.example.com)
   |-- PostgreSQL
   |-- Redis
   |-- Celery worker + Beat
   +-- Ollama
   +-- SMTP provider
```

Because the rewrite is server-side, the browser only ever talks to the Vercel domain:
cookies are first-party, no CORS is involved, and `COOKIE_DOMAIN` can stay empty. A
change to `BACKEND_URL` requires a new Vercel deployment.

The API host must allow the Vercel deployment to reach it. If you put authentication
or IP allow-listing on the API, allow Vercel's egress addresses or use a shared token
at the proxy; the console itself has no such mechanism.

---

## 8. Option D: demo only (no backend)

The console contains an in-memory demo API at `/demo-api/v1`, enabled only when
`NEXT_PUBLIC_DEMO_MODE=true` at build time. No database, Redis, model, SMTP, worker,
or Beat is needed.

Limits:

- Data resets when the instance restarts.
- Nothing is generated by a real model and nothing is delivered.
- Credentials are `admin@dossier.dev` / `demo` (the login form is prefilled).
- Never use this mode for real organisational data.

### Vercel

1. Import the repository.
2. Set **Root Directory** to `frontend`.
3. Add `NEXT_PUBLIC_DEMO_MODE=true` for Production and Preview.
4. Deploy.

```powershell
cd frontend
vercel login
vercel env add NEXT_PUBLIC_DEMO_MODE production
vercel --prod
```

### Local

```powershell
cd frontend
$env:NEXT_PUBLIC_DEMO_MODE = "true"
pnpm dev
```

```bash
cd frontend
NEXT_PUBLIC_DEMO_MODE=true pnpm dev
```

### Self-hosted static demo

```bash
cd frontend
NEXT_PUBLIC_DEMO_MODE=true pnpm install --frozen-lockfile
NEXT_PUBLIC_DEMO_MODE=true pnpm build
NEXT_PUBLIC_DEMO_MODE=true pnpm start
```

---

## 9. Database migrations and first-run tasks

Migrations live in `backend/migrations/` and are managed by Alembic.

| Task | Command (host) | Command (Compose) |
|---|---|---|
| Apply migrations | `cd backend && uv run alembic upgrade head` | `docker compose exec backend alembic upgrade head` |
| Create org and admin | `cd backend && uv run python -m app.cli bootstrap` | `docker compose exec backend python -m app.cli bootstrap` |
| Set a known password | `... python -m app.cli set-password --email X --password Y [--force-change]` | same, via `docker compose exec` |
| Seed demo data | `... python -m app.cli seed-demo` | same, via `docker compose exec` |

Rules:

- Run `alembic upgrade head` on every deploy, before starting new application code.
- Review migrations before production. A dropped column is not automatically reversible.
- `bootstrap` is safe to re-run: it reports existing organisation, department, and
  administrator records and exits without creating duplicates. The temporary password is
  printed only on the run that creates the administrator.
- `seed-demo` is for staging and demonstrations only.
- `set-password --force-change` requires the user to change the password at next login.

---

## 10. Build-time versus runtime variables

This distinction causes most failed deployments.

| Variable | Read at | Changing it requires |
|---|---|---|
| `BACKEND_URL` | `next build` (compiled into the rewrite) | Rebuild and redeploy the console |
| `NEXT_PUBLIC_DEMO_MODE` | `next build` (inlined into client code) | Rebuild and redeploy the console |
| All backend variables | Process start (or container start) | Restart the API, worker, and Beat |

The Next.js server must be able to reach `BACKEND_URL`; the browser does not need to.
On a single server that is `http://127.0.0.1:8000`. On Vercel it is the public HTTPS API
URL.

---

## 11. Verification

### 11.1 Health checks

```bash
curl -fsS http://127.0.0.1:8000/health/live
# {"status":"ok"}

curl -fsS http://127.0.0.1:8000/health/ready
# {"status":"ok","checks":{"database":"ok","redis":"ok"}}
```

`/health/ready` returns HTTP 503 with `"status":"degraded"` if PostgreSQL or Redis is
unreachable.

### 11.2 Through the proxy

```bash
curl -fsS https://api.example.com/health/ready
curl -fsSI https://app.example.com/login | head -n 1
```

### 11.3 End-to-end, in the console

1. Sign in at `https://app.example.com`.
2. **Mail > SMTP settings** - enter the provider and send a test email. If this fails,
   fix it before anything else; the rest of the mail path depends on it.
3. **Data > Connectors** - add Google Sheets or Zoho CRM and choose **Verify connection**.
4. **Data > Sources** - register a sheet tab or CRM module and sync it.
5. **Departments > [department] > Sources** - grant the source.
6. **Mail > Templates** - create a prompt and preview it against the department.
7. **Departments > [department] > Emails** - schedule it, then choose **Send now**.
8. **Mail > Executions** - confirm delivery and inspect the generated body.
9. **Settings > Audit** - confirm the actions above were recorded.

### 11.4 Process checks

```bash
pm2 status                          # four processes online
sudo ss -ltnp | grep -E '3000|8000|5432|6379|11434'
```

All five ports should be bound to `127.0.0.1`, not `0.0.0.0`.

---

## 12. Operations

### 12.1 Update a single-server deployment

```bash
sudo chmod +x /var/www/dossier/deploy/deploy.sh
sudo -u dossier -H /var/www/dossier/deploy/deploy.sh
```

The script pulls with `--ff-only`, runs `uv sync --frozen --no-dev`, applies migrations,
installs frontend dependencies, rebuilds with `BACKEND_URL`, reloads PM2, and saves the
process list.

Manual equivalent:

```bash
sudo -u dossier -H bash -lc '
  cd /var/www/dossier && git pull --ff-only
  cd backend && uv sync --frozen --no-dev && .venv/bin/alembic upgrade head
  cd ../frontend && BACKEND_URL=http://127.0.0.1:8000 pnpm install --frozen-lockfile
  BACKEND_URL=http://127.0.0.1:8000 pnpm build
  pm2 startOrReload /var/www/dossier/deploy/ecosystem.config.cjs --update-env
  pm2 save
'
```

### 12.2 Restart processes

```bash
sudo -u dossier -H pm2 restart dossier-api
sudo -u dossier -H pm2 restart dossier-worker
sudo -u dossier -H pm2 restart dossier-beat
sudo -u dossier -H pm2 restart dossier-web
```

After changing `.env`, restart all four (or use `--update-env`). The API picks up new
settings at start; the frontend does not read runtime settings.

### 12.3 Logs

```bash
sudo -u dossier -H pm2 logs dossier-api --lines 100
sudo -u dossier -H pm2 logs dossier-worker --lines 100
sudo -u dossier -H pm2 logs dossier-beat --lines 100
sudo -u dossier -H pm2 logs dossier-web --lines 100

sudo tail -f /var/log/nginx/error.log
sudo journalctl -u postgresql -n 100
sudo journalctl -u redis-server -n 100
sudo journalctl -u ollama -n 100
```

One-time log rotation setup:

```bash
sudo -u dossier -H pm2 install pm2-logrotate
sudo -u dossier -H pm2 set pm2-logrotate:max_size 20M
sudo -u dossier -H pm2 set pm2-logrotate:retain 14
```

### 12.4 Backups and restore

```bash
sudo chmod +x /var/www/dossier/deploy/backup.sh
sudo crontab -e
```

```cron
15 2 * * * /var/www/dossier/deploy/backup.sh >> /var/log/dossier/backup.log 2>&1
```

The script writes compressed `pg_dump` files to `/var/backups/dossier` and keeps 14
days. Back up `.env` and `CREDENTIAL_ENCRYPTION_KEYS` separately; without the key,
encrypted connector and SMTP secrets are unrecoverable.

Restore:

```bash
sudo -u postgres dropdb dossier
sudo -u postgres createdb -O dossier dossier
sudo -u postgres psql -d dossier -c \
  "CREATE EXTENSION IF NOT EXISTS citext; CREATE EXTENSION IF NOT EXISTS vector;"
sudo -u postgres pg_restore -d dossier /var/backups/dossier/dossier-YYYYMMDDTHHMMSSZ.dump
sudo -u dossier -H pm2 restart dossier-api dossier-worker
```

Test a restore against a staging database before relying on it.

### 12.5 Secret rotation

| Secret | Procedure |
|---|---|
| `JWT_SECRET` | Change it and restart the API. All sessions are invalidated; users sign in again |
| Credential encryption key | Add `v2:<new key>`, set `CREDENTIAL_ENCRYPTION_ACTIVE_KEY_ID=v2`, keep `v1` readable, restart API and worker, then re-save every connector and the SMTP settings so their secrets are re-encrypted. Remove `v1` only after all are re-saved |
| Database password | `ALTER ROLE dossier WITH PASSWORD '...'`, update `.env`, restart API, worker, and Beat |
| Redis password | Update `/etc/redis/redis.conf` and `.env`, restart Redis, API, worker, and Beat |

### 12.6 Scaling notes

- API: increase uvicorn `--workers` or run several instances behind the proxy. Sessions
  and rate limits live in PostgreSQL and Redis, so instances are interchangeable.
- Worker: raise Celery `--concurrency` or run additional worker processes.
- Beat: exactly one. Never scale it horizontally without a distributed lock.
- Memory: a local 8B model dominates usage. `ecosystem.config.cjs` caps API at 700M,
  worker at 1G, Beat at 256M, and the console at 700M; adjust to the host.
- The model is the usual throughput bottleneck. `LLM_TIMEOUT_SECONDS` and the proxy read
  timeout must both accommodate the slowest expected generation.

---

## 13. Troubleshooting

### Deployment and startup

| Symptom | Likely cause | Fix |
|---|---|---|
| API exits immediately with a settings error | `JWT_SECRET` under 32 bytes, missing `CREDENTIAL_ENCRYPTION_KEYS`, or an invalid Fernet key | Generate fresh values per section 4.5; the error names the failing field |
| `CREDENTIAL_ENCRYPTION_ACTIVE_KEY_ID must match a configured key` | Active id not in `CREDENTIAL_ENCRYPTION_KEYS` | Make them match, e.g. both `v1` |
| `alembic` cannot connect | Wrong URL or an unescaped password | Use a hex password; test with `psql` |
| `type "vector" does not exist` | pgvector is not installed | `apt install postgresql-17-pgvector` and `CREATE EXTENSION vector` |
| `type "citext" does not exist` | Extension never created | `CREATE EXTENSION citext` as a superuser |
| `Permission denied` writing `celerybeat.pid` | PM2 was started as root | `sudo chown -R dossier:dossier /var/www/dossier`, then restart as `dossier` |
| Compose worker cannot find `dossier-backend:latest` | Backend image never built | `docker compose build backend`, then start the workers |
| Compose backend cannot reach Ollama on Linux | `host.docker.internal` is not defined on Linux | Add `extra_hosts: ["host.docker.internal:host-gateway"]`, or set the host's LAN IP |
| Node build runs out of memory | Small server | Add swap, build on CI and copy `.next`, or raise the Node heap |
| PM2 restarts processes repeatedly | Memory cap or crash | Read `pm2 logs`; lower workers/concurrency, use a smaller model, raise `max_memory_restart` |

### HTTP and authentication

| Symptom | Likely cause | Fix |
|---|---|---|
| Nginx 502 on the console | `dossier-web` stopped or `.next` missing | `pm2 logs dossier-web`; rebuild with `pnpm build` |
| Nginx 502 on the API | `dossier-api` stopped, or DB/Redis down | `pm2 logs dossier-api`; check `/health/ready` |
| Login returns 401 | Wrong password or `bootstrap` never ran | Run `bootstrap`, or reset with `set-password` |
| Login succeeds, then bounces to `/login` | `COOKIE_SECURE=true` over plain HTTP, or proxy headers missing | Use HTTPS; ensure Nginx sets `X-Forwarded-Proto` |
| Cookies work on the API host but not the console host | `COOKIE_DOMAIN` set to a domain that does not cover the console | Leave `COOKIE_DOMAIN` empty when using the rewrite |
| Vercel console shows API errors after changing the backend | `BACKEND_URL` was changed without a redeploy | Update the variable and redeploy; it is build-time |
| `504` or timeout on preview/send | Model too slow or unreachable | Raise `proxy_read_timeout` and `LLM_TIMEOUT_SECONDS`; check `curl $OLLAMA_BASE_URL/api/tags` |
| Model returns `401` | Ollama Cloud key missing, revoked, or sent to the wrong endpoint | Set `OLLAMA_API_KEY` and `OLLAMA_BASE_URL=https://ollama.com`; retest the tags endpoint |
| Model returns `404` | `OLLAMA_CHAT_MODEL` is not available to this key | List the catalog with `/api/tags` and use an exact name |
| `/docs` returns 404 | `APP_ENV=production` disables it | Expected; use development or curl the OpenAPI schema in a non-production environment |
| CORS errors | A browser is calling the API directly, not through the rewrite | Either use the rewrite or add the exact origin to `CORS_ORIGINS` |

### Data, sync, and mail

| Symptom | Likely cause | Fix |
|---|---|---|
| Mail shows `FAILED` | SMTP settings rejected the message | Test send under Mail settings; read `pm2 logs dossier-worker` |
| Mailhog receives nothing in development | SMTP host not set to `mailhog:1025` | Configure it in Mail settings; Mailhog UI is on port 8025 |
| Schedules never fire | Beat not running, Redis down, or `next_run_at` is null | `pm2 logs dossier-beat`; `pm2 status`; inspect the schedule in the console |
| Duplicate mail or duplicate syncs | More than one Beat instance | Run a single Beat |
| Sync `FAILED` | Connector credentials, unshared sheet, Zoho scope or data-centre mismatch | Verify the connection; read the source log in the console |
| Stored connector or SMTP secrets fail to decrypt | `CREDENTIAL_ENCRYPTION_KEYS` changed or lost | Restore the original key set; re-enter the secrets if the old key is gone |
| Generation ignores recently synced rows | Daily sync has not run yet | Trigger a sync in the console, or wait for `DAILY_SYNC_HOUR_UTC` |

Useful one-liners:

```bash
pm2 status
curl -fsS https://api.example.com/health/ready
sudo ss -ltnp | grep -E '3000|8000|5432|6379|11434'
sudo -u postgres psql -d dossier -c "SELECT count(*) FROM app_user;"
docker compose logs -f backend
docker compose logs -f worker beat
```

---

## 14. Security checklist

Before exposing a deployment:

- [ ] UFW or the cloud firewall allows only 22, 80, and 443.
- [ ] PostgreSQL, Redis, Ollama, the API, and the console bind to `127.0.0.1`.
- [ ] SSH uses keys; password login and root login are disabled.
- [ ] `.env` is `chmod 600`, owned by the service user, and never committed.
- [ ] Fresh `JWT_SECRET` (32+ bytes) and a fresh Fernet key; no example values remain.
- [ ] `APP_ENV=production` and `COOKIE_SECURE=true`.
- [ ] TLS is active and renews (`systemctl status certbot.timer`).
- [ ] `CORS_ORIGINS` lists only origins that genuinely need direct API access.
- [ ] The bootstrap administrator's password has been changed; at least one additional
      administrator exists.
- [ ] Demo data has not been seeded in production.
- [ ] Nightly backups run and a restore has been tested.
- [ ] `CREDENTIAL_ENCRYPTION_KEYS` and `.env` are stored outside the server.
- [ ] PM2 starts on boot and `pm2 save` was run after the last change.
- [ ] `pm2-logrotate` is installed.
- [ ] `/docs` and `/openapi.json` are not reachable (automatic with `APP_ENV=production`).
- [ ] Optional: `fail2ban` for SSH and Nginx authentication failures.
- [ ] Never enable `NEXT_PUBLIC_DEMO_MODE` for a deployment holding real data.

---

## Appendix A: Ports

| Port | Service | Public |
|---|---|---|
| 22 | SSH | Yes, ideally restricted by IP |
| 80 | Nginx (redirect and ACME) | Yes |
| 443 | Nginx (TLS) | Yes |
| 3000 | Next.js console | No |
| 8000 | FastAPI | No |
| 5432 | PostgreSQL | No |
| 6379 | Redis | No |
| 11434 | Ollama | No |
| 1025 | Mailhog SMTP (development only) | No |
| 8025 | Mailhog UI (development only) | No |

Compose publishes PostgreSQL on host port **5433** to avoid clashing with a local
installation.

---

## Appendix B: Deployment files in this repository

| File | Purpose |
|---|---|
| `deploy/ecosystem.config.cjs` | PM2 processes for API, worker, Beat, and console |
| `deploy/nginx/dossier.http.conf` | Bootstrap HTTP config used to issue certificates |
| `deploy/nginx/dossier.conf` | Full HTTPS config for console and API |
| `deploy/dossier.env.example` | Production environment template |
| `deploy/deploy.sh` | Pull, install, migrate, build, reload |
| `deploy/backup.sh` | Nightly database backup with retention |
| `docker-compose.yml` | Development stack: PostgreSQL, Redis, Mailhog, API, workers |
| `backend/Dockerfile` | Python 3.12 API image; does not run migrations |
| `frontend/vercel.json` | Declares the Next.js framework to Vercel |
| `frontend/next.config.ts` | Builds the `/api` rewrite from `BACKEND_URL` |

---

## Appendix C: Command cheat sheet

```bash
# Compose
docker compose up -d db redis backend mailhog
docker compose --profile workers up -d worker beat
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.cli bootstrap
docker compose --profile workers down -v

# Backend directly
cd backend
uv sync
uv run alembic upgrade head
uv run python -m app.cli bootstrap
uv run uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
pnpm install
BACKEND_URL=http://127.0.0.1:8000 pnpm build
pnpm start

# Single server
sudo -u dossier -H pm2 status
sudo -u dossier -H /var/www/dossier/deploy/deploy.sh
sudo -u dossier -H /var/www/dossier/deploy/backup.sh

# Tests
cd backend && uv run pytest --cov=app --cov-fail-under=80
cd backend && uv run ruff check . && uv run mypy app
pnpm --dir frontend typecheck
pnpm --dir frontend test:e2e
```
