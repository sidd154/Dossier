#!/usr/bin/env bash
# Nightly database backup. Run as root from cron, or as a user with pg_dump rights.
#
#   sudo crontab -e
#   15 2 * * * /var/www/dossier/deploy/backup.sh >> /var/log/dossier/backup.log 2>&1
#
# The .env file is not included here. Back it up separately and securely: without
# CREDENTIAL_ENCRYPTION_KEYS, encrypted connector and SMTP secrets cannot be read.

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/backups/dossier}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
DB_NAME="${DB_NAME:-dossier}"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
TARGET="$BACKUP_DIR/dossier-$STAMP.dump"

sudo -u postgres pg_dump -Fc "$DB_NAME" > "$TARGET"
chmod 600 "$TARGET"

find "$BACKUP_DIR" -maxdepth 1 -name 'dossier-*.dump' -mtime "+$RETENTION_DAYS" -delete

echo "Backup written: $TARGET"
