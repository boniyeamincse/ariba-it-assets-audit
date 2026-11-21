#!/bin/bash
# ==============================================================================
# Akij Group - Central IT Asset Governance & Audit Portal
# Remote Server Automated PostgreSQL Database Backup Script
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

BACKUP_DIR="$SCRIPT_DIR/backups"
mkdir -p "$BACKUP_DIR"

if [ ! -f ".env" ]; then
    echo "[-] Error: .env file not found."
    exit 1
fi

# Load DB credentials from .env
DB_NAME=$(grep -E '^AUDIT_DB_NAME=' .env | cut -d '=' -f2 | tr -d ' "' || echo "ag_audit")
DB_USER=$(grep -E '^AUDIT_DB_USER=' .env | cut -d '=' -f2 | tr -d ' "' || echo "ag_audit")

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/db_backup_${DB_NAME}_${TIMESTAMP}.sql.gz"

echo "[*] Creating database backup for '$DB_NAME'..."

docker exec -t ag_audit_db pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$BACKUP_FILE"

FILE_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "[+] Backup created successfully: $BACKUP_FILE ($FILE_SIZE)"

# Retain only last 14 backups
find "$BACKUP_DIR" -name "db_backup_*.sql.gz" -type f -mtime +14 -delete 2>/dev/null || true
echo "[+] Retention policy applied (kept last 14 days)."
