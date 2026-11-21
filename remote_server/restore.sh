#!/bin/bash
# ==============================================================================
# Akij Group - Central IT Asset Governance & Audit Portal
# Remote Server Database Restore Script
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ $# -lt 1 ]; then
    echo "Usage: ./restore.sh <path_to_backup_file.sql.gz>"
    echo ""
    echo "Available backups in ./backups/:"
    ls -lh backups/*.sql.gz 2>/dev/null || echo "No backups found."
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "[-] Error: Backup file '$BACKUP_FILE' does not exist."
    exit 1
fi

if [ ! -f ".env" ]; then
    echo "[-] Error: .env file not found."
    exit 1
fi

DB_NAME=$(grep -E '^AUDIT_DB_NAME=' .env | cut -d '=' -f2 | tr -d ' "' || echo "ag_audit")
DB_USER=$(grep -E '^AUDIT_DB_USER=' .env | cut -d '=' -f2 | tr -d ' "' || echo "ag_audit")

echo "[!] WARNING: This will overwrite existing data in database '$DB_NAME'."
read -rp "Are you sure you want to proceed? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "Restore aborted."
    exit 0
fi

echo "[*] Restoring database from '$BACKUP_FILE'..."

# Terminate active connections and recreate DB schema
docker exec -i ag_audit_db psql -U "$DB_USER" -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB_NAME' AND pid <> pg_backend_pid();"
docker exec -i ag_audit_db psql -U "$DB_USER" -d postgres -c "DROP DATABASE IF EXISTS $DB_NAME;"
docker exec -i ag_audit_db psql -U "$DB_USER" -d postgres -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"

# Stream decompressed SQL into database
gunzip -c "$BACKUP_FILE" | docker exec -i ag_audit_db psql -U "$DB_USER" -d "$DB_NAME"

echo "[+] Database restored successfully from $BACKUP_FILE."
