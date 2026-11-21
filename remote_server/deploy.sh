#!/bin/bash
# ==============================================================================
# Akij Group - Central IT Asset Governance & Audit Portal
# Remote Server 1-Click Deployment & Update Script
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "======================================================================"
echo "  Akij Group IT Audit Portal - Remote Server Deployment"
echo "======================================================================"

# 1. Check Docker & Docker Compose installation
if ! command -v docker &> /dev/null; then
    echo "[-] Error: docker is not installed. Please install Docker first."
    exit 1
fi

if ! docker compose version &> /dev/null; then
    echo "[-] Error: docker compose (v2) is not installed."
    exit 1
fi

# 2. Check for .env file
if [ ! -f ".env" ]; then
    echo "[!] No .env file found. Creating one from .env.example..."
    cp .env.example .env
    
    # Generate random secret key and db password
    RANDOM_SECRET=$(openssl rand -hex 32 2>/dev/null || date +%s | sha256sum | base64 | head -c 40)
    RANDOM_DB_PASS=$(openssl rand -hex 16 2>/dev/null || date +%s | sha256sum | base64 | head -c 20)
    
    sed -i "s/change-this-to-a-secure-random-64-character-secret-key-in-production/$RANDOM_SECRET/" .env
    sed -i "s/change-this-to-a-strong-postgres-password-123456/$RANDOM_DB_PASS/" .env
    
    echo "[+] Generated random DJANGO_SECRET_KEY and AUDIT_DB_PASSWORD in .env"
    echo "[!] IMPORTANT: Review and update DJANGO_ALLOWED_HOSTS and DJANGO_CSRF_TRUSTED_ORIGINS in .env before exposing to users."
fi

# 3. Pull latest images from Docker Hub
echo ""
echo "[*] Pulling latest production images from Docker Hub..."
docker compose pull

# 4. Start Containers
echo ""
echo "[*] Starting containers in background..."
docker compose up -d --remove-orphans

# 5. Wait for database and web service healthcheck
echo ""
echo "[*] Waiting for services to become healthy..."
MAX_WAIT=60
COUNT=0
until [ "$(docker inspect -f '{{.State.Health.Status}}' ag_audit_web 2>/dev/null)" = "healthy" ]; do
    sleep 3
    COUNT=$((COUNT + 3))
    if [ $COUNT -ge $MAX_WAIT ]; then
        echo "[!] Health check timeout reached. Inspecting container logs:"
        docker compose logs --tail=30
        break
    fi
    echo -n "."
done
echo ""

# 6. Show status
echo ""
echo "======================================================================"
echo "  Deployment Completed Successfully!"
echo "======================================================================"
docker compose ps

echo ""
WEB_PORT=$(grep -E '^WEB_PORT=' .env | cut -d '=' -f2 || echo "8000")
echo "[+] Portal is accessible at: http://<YOUR_SERVER_IP>:${WEB_PORT:-8000}/"
echo "[+] To view live logs:       docker compose logs -f"
echo "[+] To create superuser:     docker compose exec web python manage.py createsuperuser"
echo "[+] To stop services:        docker compose down"
echo "======================================================================"
