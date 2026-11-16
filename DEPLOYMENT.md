# Deploying Dossier on a Single Ubuntu Server

This guide deploys the complete product — console, API, workers, database, cache, and
model runtime — on one Linux server with **PM2** and **Nginx**.

It assumes a fresh **Ubuntu 24.04 LTS** server and a domain you control. Commands are
written for `bash`. Replace the placeholders before running anything.

| Placeholder | Meaning | Example |
|---|---|---|
| `app.example.com` | Console hostname | `dossier.acme.com` |
| `api.example.com` | API hostname (health checks and integrations) | `api.dossier.acme.com` |
| `203.0.113.10` | Server public IPv4 | your server IP |
| `/var/www/dossier` | Application directory | keep as is |
| `dossier` | Linux service user (not root) | keep as is |

> The console can also run without the local API by setting `NEXT_PUBLIC_DEMO_MODE=true`.
> See [Demo-only deployment](#demo-only-deployment). This guide covers the real stack.

---

## 1. What runs where

| Process | Managed by | Binds to | Exposed publicly |
|---|---|---|---|
| Next.js console | PM2 `dossier-web` | `127.0.0.1:3000` | Through Nginx only |
| FastAPI | PM2 `dossier-api` | `127.0.0.1:8000` | Through Nginx only |
| Celery worker | PM2 `dossier-worker` | no port | No |
| Celery beat | PM2 `dossier-beat` | no port | No |
| PostgreSQL 17 + pgvector | systemd | `127.0.0.1:5432` | No |
| Redis 7+ | systemd | `127.0.0.1:6379` | No |
| Ollama | systemd | `127.0.0.1:11434` | No |
| Nginx | systemd | `:80`, `:443` | Yes |
| SMTP | outbound | — | — |

```text
Browser
   |
   v
Nginx :443
   |-- app.example.com --> Next.js :3000 --> FastAPI :8000 --> PostgreSQL
   |                                              |               Redis
   |                                              +--> Ollama
   |                                              +--> SMTP
   +-- api.example.com --> FastAPI :8000
```

Celery Beat reads due schedules every minute and the daily connector sync at
`DAILY_SYNC_HOUR_UTC`. The worker performs syncs, model generation, and mail delivery.

---

## 2. Before you begin

- The two DNS `A` records point at the server **before** requesting certificates.
- Ports `80` and `443` are reachable from the internet.
- You can `sudo`.
- At least 2 GB RAM for the stack. **8 GB or more** if you run a 7–8B model locally.
- A transactional email provider (Postmark, Resend, SES, Mailgun, or your own SMTP).

---

## 3. Prepare the server

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl git unzip build-essential ca-certificates ufw

sudo timedatectl set-timezone UTC

# A dedicated, unprivileged account for the application.
sudo adduser --disabled-password --gecos "" dossier
sudo mkdir -p /var/www/dossier /var/log/dossier /var/backups/dossier /var/www/certbot
sudo chown -R dossier:dossier /var/www/dossier /var/log/dossier /var/backups/dossier /var/www/certbot
sudo chmod 750 /var/log/dossier /var/backups/dossier

# Firewall: SSH, HTTP, HTTPS only.
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
sudo ufw status
```

Do **not** open `3000`, `8000`, `5432`, `6379`, or `11434`.

---

## 4. Install the runtimes

### Node.js 24, pnpm, PM2

```bash
curl -fsSL https://deb.nodesource.com/setup_24.x | sudo -E bash -
sudo apt install -y nodejs

sudo corepack enable
sudo corepack prepare pnpm@11.23.0 --activate
sudo npm install -g pm2

node -v      # v24.x
pnpm -v      # 11.x
pm2 -v
```

### Python 3.12, uv, Nginx, Certbot

```bash
sudo apt install -y python3.12 python3.12-venv python3-pip libpq-dev nginx certbot

# uv as the application user
sudo -u dossier -H bash -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'
echo 'export PATH="$HOME/.local/bin:$PATH"' | sudo -u dossier tee -a /home/dossier/.bashrc
sudo -u dossier -H bash -lc 'uv --version'
```

---

## 5. PostgreSQL 17 with pgvector

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

Create the database. Use a hex password so it needs no URL encoding:

```bash
DB_PASS="$(openssl rand -hex 24)"
echo "PostgreSQL password: $DB_PASS"   # store it in your password manager

sudo -u postgres psql <<SQL
CREATE USER dossier WITH PASSWORD '${DB_PASS}';
CREATE DATABASE dossier OWNER dossier;
\c dossier
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS vector;
SQL
```

Verify:

```bash
sudo -u postgres psql -d dossier -c "SELECT extname FROM pg_extension;"
PGPASSWORD="$DB_PASS" psql -h 127.0.0.1 -U dossier -d dossier -c "SELECT 1;"
```

PostgreSQL listens on localhost by default. Keep it that way.

`DATABASE_URL` in `.env`:

```text
postgresql+asyncpg://dossier:<DB_PASS>@127.0.0.1:5432/dossier
```

Optional tuning for a small server (edit `/etc/postgresql/17/main/postgresql.conf`):

```text
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 16MB
maintenance_work_mem = 128MB
```

Restart with `sudo systemctl restart postgresql`.

---

## 6. Redis

The Ubuntu package is Redis 7.x, which is compatible with the application.

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

Generate the password with `openssl rand -hex 24`, then:

```bash
sudo systemctl restart redis-server
redis-cli -a '<REDIS_PASSWORD>' ping    # PONG
```

`REDIS_URL` in `.env` (note the colon before the password):

```text
redis://:<REDIS_PASSWORD>@127.0.0.1:6379/0
```

---

## 7. Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl enable --now ollama

# Choose a model that fits the server's memory.
ollama pull llama3.1:8b
# Smaller option for low-memory servers:
# ollama pull llama3.2:3b

curl -s http://127.0.0.1:11434/api/tags
```

Set the exact model name in `.env`:

```text
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_CHAT_MODEL=llama3.1:8b
LLM_TIMEOUT_SECONDS=120
```

Notes:

- A CPU-only 8B model is slow. Use a smaller model or point `OLLAMA_BASE_URL` at a
  stronger host.
- `deepseek-v4.1-flash:cloud` is an Ollama Cloud model; using it here requires that
  account and network access. A local model is the self-contained option.
- Ollama must listen on localhost only. Do not expose `11434`.

---

## 8. Deploy the code

```bash
sudo -u dossier git clone https://github.com/sidd154/Dossier.git /var/www/dossier
cd /var/www/dossier

sudo -u dossier cp deploy/dossier.env.example .env
sudo -u dossier chmod 600 .env
```

Edit `/var/www/dossier/.env` and fill every `CHANGE_ME` value:

```bash
sudo -u dossier nano /var/www/dossier/.env
```

Generate secrets:

```bash
# JWT signing key, 64 hex characters
openssl rand -hex 32

# Fernet key for connector and SMTP credentials
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Required values:

| Variable | Value |
|---|---|
| `APP_ENV` | `production` |
| `DATABASE_URL` | The PostgreSQL URL from step 5 |
| `REDIS_URL` | The Redis URL from step 6 |
| `JWT_SECRET` | Fresh 64-hex string |
| `CREDENTIAL_ENCRYPTION_KEYS` | `v1:<fresh Fernet key>` |
| `CREDENTIAL_ENCRYPTION_ACTIVE_KEY_ID` | `v1` |
| `COOKIE_SECURE` | `true` |
| `CORS_ORIGINS` | `https://app.example.com` |
| `OLLAMA_CHAT_MODEL` | A model actually pulled in step 7 |
| `BOOTSTRAP_*` | Your organisation and first admin |

Install backend dependencies and migrate:

```bash
sudo -u dossier -H bash -lc '
  cd /var/www/dossier/backend
  uv sync --frozen --no-dev
  .venv/bin/alembic upgrade head
'
```

Create the organisation and first administrator:

```bash
sudo -u dossier -H bash -lc '
  cd /var/www/dossier/backend
  .venv/bin/python -m app.cli bootstrap
'
```

The command prints a one-time temporary password. Sign in with it and change it, or set
a known password directly:

```bash
sudo -u dossier -H bash -lc '
  cd /var/www/dossier/backend
  .venv/bin/python -m app.cli set-password \
    --email admin@example.com --password "a-strong-password"
'
```

Optional staging smoke test:

```bash
sudo -u dossier -H bash -lc '
  cd /var/www/dossier/backend
  .venv/bin/python -m app.cli seed-demo
'
```

Do not seed demo data in production.

---

## 9. Build the console

`BACKEND_URL` is compiled into the Next.js rewrite, so it must be correct **at build
time**. On a single server, use the loopback API:

```bash
sudo -u dossier -H bash -lc '
  cd /var/www/dossier/frontend
  BACKEND_URL=http://127.0.0.1:8000 pnpm install --frozen-lockfile
  BACKEND_URL=http://127.0.0.1:8000 pnpm build
'
```

If the API is on another host, use its public URL, for example
`BACKEND_URL=https://api.example.com`. Changing it later requires a rebuild.

Confirm the build exists:

```bash
ls /var/www/dossier/frontend/.next/BUILD_ID
```

---

## 10. Start everything with PM2

The ecosystem file already points at `/var/www/dossier`. Start it **as the `dossier`
user**, otherwise PM2 writes root-owned files:

```bash
sudo -u dossier -H bash -lc '
  cd /var/www/dossier
  pm2 startOrReload deploy/ecosystem.config.cjs --update-env
  pm2 save
'
```

Enable PM2 on boot:

```bash
sudo env PATH="$PATH" pm2 startup systemd -u dossier --hp /home/dossier
# Run the exact command PM2 prints, then:
sudo -u dossier -H bash -lc 'pm2 save'
```

Check:

```bash
sudo -u dossier -H bash -lc 'pm2 status'
sudo -u dossier -H bash -lc 'pm2 logs dossier-api --lines 50'
```

Expected processes: `dossier-api`, `dossier-worker`, `dossier-beat`, `dossier-web`.

Verify the API locally before involving Nginx:

```bash
curl -fsS http://127.0.0.1:8000/health/live
curl -fsS http://127.0.0.1:8000/health/ready
curl -fsS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:3000/login
```

---

## 11. Nginx and TLS

### 11.1 Bootstrap certificates

Point DNS first. Then enable the HTTP-only config:

```bash
sudo cp /var/www/dossier/deploy/nginx/dossier.http.conf \
  /etc/nginx/sites-available/dossier.conf
sudo ln -sf /etc/nginx/sites-available/dossier.conf /etc/nginx/sites-enabled/dossier.conf
sudo rm -f /etc/nginx/sites-enabled/default

sudo nginx -t && sudo systemctl reload nginx
```

Request the certificate (replace the domains and email):

```bash
sudo certbot certonly --webroot -w /var/www/certbot \
  -d app.example.com -d api.example.com \
  --email you@example.com --agree-tos --no-eff-email
```

Certificates land in `/etc/letsencrypt/live/app.example.com/`.

### 11.2 Enable the full config

```bash
sudo cp /var/www/dossier/deploy/nginx/dossier.conf \
  /etc/nginx/sites-available/dossier.conf

# Replace the placeholder domains and certificate paths in one step:
sudo sed -i 's/app\.example\.com/app.yourdomain.com/g; s/api\.example\.com/api.yourdomain.com/g' \
  /etc/nginx/sites-available/dossier.conf

sudo nginx -t && sudo systemctl reload nginx
```

Renewal is handled by the Certbot timer. Test it:

```bash
sudo certbot renew --dry-run
```

### 11.3 What the config does

- Redirects HTTP to HTTPS, with an ACME exception.
- Proxies `app.example.com` to the console on `127.0.0.1:3000`.
- Proxies `api.example.com` to the API on `127.0.0.1:8000`, with a 240-second read
  timeout for model generation.
- Sets `X-Forwarded-Proto` so secure cookies work.
- Adds HSTS and basic security headers.

---

## 12. First-run verification

```bash
# API through Nginx
curl -fsS https://api.example.com/health/ready
# -> {"status":"ok","checks":{"database":"ok","redis":"ok"}}

# Console through Nginx
curl -fsSI https://app.example.com/login | head -n 1
```

Then in the browser:

1. Open `https://app.example.com` and sign in.
2. **Mail → SMTP settings** — enter your provider, send a test email.
3. **Data → Connectors** — add Google Sheets or Zoho CRM, then **Verify connection**.
4. **Data → Sources** — register a sheet tab or CRM module and sync it.
5. **Departments → [department] → Sources** — grant the source.
6. **Mail → Templates** — create a prompt; preview it against the department.
7. **Departments → [department] → Emails** — schedule it, then **Send now**.
8. **Mail → Executions** — confirm the delivery and read the generated body.

If the SMTP test fails, nothing else in the mail path can work. Fix that first.

---

## 13. Operations

### Update to a new version

```bash
sudo chmod +x /var/www/dossier/deploy/deploy.sh
sudo -u dossier -H /var/www/dossier/deploy/deploy.sh
```

The script pulls, installs backend and frontend dependencies, migrates, rebuilds, and
reloads PM2. Review migrations before running in production; a migration that drops a
column is not automatically reversible.

### Restart a single process

```bash
sudo -u dossier -H pm2 restart dossier-api
sudo -u dossier -H pm2 restart dossier-worker
sudo -u dossier -H pm2 restart dossier-beat
sudo -u dossier -H pm2 restart dossier-web
```

### Logs

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

Install PM2 log rotation once:

```bash
sudo -u dossier -H pm2 install pm2-logrotate
sudo -u dossier -H pm2 set pm2-logrotate:max_size 20M
sudo -u dossier -H pm2 set pm2-logrotate:retain 14
```

### Backups

```bash
sudo chmod +x /var/www/dossier/deploy/backup.sh
sudo crontab -e
```

Add:

```cron
15 2 * * * /var/www/dossier/deploy/backup.sh >> /var/log/dossier/backup.log 2>&1
```

The script writes compressed `pg_dump` files to `/var/backups/dossier` and keeps 14
days. **Back up `.env` separately** and securely: without `CREDENTIAL_ENCRYPTION_KEYS`,
the connector and SMTP passwords in the database cannot be decrypted.

Restore:

```bash
sudo -u postgres dropdb dossier
sudo -u postgres createdb -O dossier dossier
sudo -u postgres psql -d dossier -c "CREATE EXTENSION IF NOT EXISTS citext; CREATE EXTENSION IF NOT EXISTS vector;"
sudo -u postgres pg_restore -d dossier /var/backups/dossier/dossier-YYYYMMDDTHHMMSSZ.dump
sudo -u dossier -H pm2 restart dossier-api dossier-worker
```

Test a restore on a staging database before relying on it.

### Secret rotation

- **JWT secret** — change `JWT_SECRET`, restart `dossier-api`. Every session is
  invalidated; users sign in again.
- **Credential encryption** — add a new key id, set
  `CREDENTIAL_ENCRYPTION_ACTIVE_KEY_ID` to it, keep the old entry readable, restart the
  API and worker, then re-save each connector and the SMTP settings so their secrets
  are encrypted under the new key. Remove the old key after all are re-saved.
- **Database or Redis password** — update the service, `.env`, and restart the API,
  worker, and beat.

---

## 14. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Nginx `502` on the console | `dossier-web` stopped or `.next` missing | `pm2 logs dossier-web`; rebuild with `pnpm build` |
| Nginx `502` on the API | `dossier-api` stopped, DB/Redis down | `pm2 logs dossier-api`; `curl 127.0.0.1:8000/health/ready` |
| Login returns 401 | Wrong password, or bootstrap never ran | Run `bootstrap`; reset with `set-password` |
| Login succeeds, then bounces to `/login` | `COOKIE_SECURE=true` over HTTP, or proxy headers missing | Use HTTPS; check `X-Forwarded-Proto` in Nginx |
| Preview or send times out after 60s | Model too slow | Raise `proxy_read_timeout`, `LLM_TIMEOUT_SECONDS`; use a smaller model |
| `504` on mail preview | Ollama unreachable or loading a model | `curl 127.0.0.1:11434/api/tags`; `journalctl -u ollama` |
| Mail shows `FAILED` | SMTP settings or provider rejection | Test send in Mail settings; `pm2 logs dossier-worker` |
| Schedules never fire | Beat not running, Redis down, `next_run_at` null | `pm2 logs dossier-beat`; check `pm2 status` |
| Sync `FAILED` | Connector credentials, sheet not shared, Zoho scope/DC | Verify connection; check source log in the console |
| `type "vector" does not exist` | pgvector not installed | `apt install postgresql-17-pgvector`; create the extension |
| `alembic` cannot connect | Wrong URL or an unescaped password | Use a hex password; test with `psql` |
| `Permission denied` writing `celerybeat.pid` | Files owned by root | `chown -R dossier:dossier /var/www/dossier` |
| Node build fails for memory | Small server | Add swap, or build on CI and copy `.next` |
| High memory / PM2 restarts | Model too large or too many API workers | Lower `--workers`, use a smaller model, raise `max_memory_restart` |

Useful one-liners:

```bash
sudo -u dossier -H pm2 status
curl -fsS https://api.example.com/health/ready
sudo ss -ltnp | grep -E '3000|8000|5432|6379|11434'
sudo -u postgres psql -d dossier -c "SELECT count(*) FROM app_user;"
```

---

## 15. Security checklist

- [ ] UFW allows only `22`, `80`, `443`.
- [ ] PostgreSQL, Redis, Ollama, the API, and the console bind to `127.0.0.1`.
- [ ] SSH uses keys; password login and root login are disabled.
- [ ] `.env` is `chmod 600`, owned by `dossier`, and never committed.
- [ ] `COOKIE_SECURE=true` and `APP_ENV=production`.
- [ ] Fresh `JWT_SECRET` and `CREDENTIAL_ENCRYPTION_KEYS`; the encryption key is backed
      up outside the server.
- [ ] The bootstrap administrator password has been changed.
- [ ] Demo data has not been seeded in production.
- [ ] Backups run nightly and a restore has been tested.
- [ ] TLS renewal is active (`systemctl status certbot.timer`).
- [ ] PM2 starts on boot and `pm2 save` has been run after the last change.
- [ ] Optional: `fail2ban` for SSH and Nginx auth failures.

---

## Demo-only deployment

To show the interface without hosting the backend, set one build variable and deploy the
console only:

```text
NEXT_PUBLIC_DEMO_MODE=true
```

The console then serves its built-in demo API at `/demo-api/v1`, with sample
departments, sources, schedules, and executions. Sign in with `admin@dossier.dev` /
`demo`. No database, Redis, model, or SMTP is needed. Changes are in memory and reset
when the instance restarts.

Build and start it exactly like the real console, but omit `BACKEND_URL`:

```bash
sudo -u dossier -H bash -lc '
  cd /var/www/dossier/frontend
  NEXT_PUBLIC_DEMO_MODE=true pnpm install --frozen-lockfile
  NEXT_PUBLIC_DEMO_MODE=true pnpm build
'
```

Do not use demo mode in a production deployment.

---

## Appendix A: Deployment files

| File | Purpose |
|---|---|
| `deploy/ecosystem.config.cjs` | PM2 processes for API, worker, beat, and console |
| `deploy/nginx/dossier.http.conf` | Bootstrap HTTP config for issuing certificates |
| `deploy/nginx/dossier.conf` | Full HTTPS config for the console and API |
| `deploy/dossier.env.example` | Production environment template |
| `deploy/deploy.sh` | Pull, install, migrate, build, and reload |
| `deploy/backup.sh` | Nightly database backup with retention |

## Appendix B: Ports

| Port | Service | Public |
|---|---|---|
| 22 | SSH | Yes, ideally restricted to your IP |
| 80 | Nginx (redirect + ACME) | Yes |
| 443 | Nginx (TLS) | Yes |
| 3000 | Next.js console | No |
| 8000 | FastAPI | No |
| 5432 | PostgreSQL | No |
| 6379 | Redis | No |
| 11434 | Ollama | No |
