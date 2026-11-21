#!/bin/bash
# ==============================================================================
# Akij Group - Central IT Asset Governance & Audit Portal
# Turnkey Remote Server Auto-Installer & Deployment Script
# ==============================================================================
# Features:
# 1. Automatic OS Detection (Ubuntu, Debian, CentOS, AlmaLinux, Rocky, Fedora, Kali, Alpine, Arch)
# 2. Automatic Docker & Docker Compose installation if missing
# 3. Automatic Server Public / Private IP detection
# 4. Automatic .env configuration with secure keys & allowed hosts
# 5. Pulls production images from Docker Hub (boniyeamin/ag-audit:production & postgres:16-alpine)
# 6. Starts all services in Docker with persistent volumes
# 7. Automatically creates or updates Super Admin user with credentials
# 8. Prints complete ready-to-use access URL & login credentials
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Text Colors
GREEN="\033[0;32m"
BLUE="\033[0;34m"
YELLOW="\033[1;33m"
CYAN="\033[0;36m"
BOLD="\033[1m"
RESET="\033[0m"

echo -e "${BLUE}${BOLD}======================================================================${RESET}"
echo -e "${BLUE}${BOLD}  Akij Group IT Audit Portal - Turnkey Remote Server Deployer        ${RESET}"
echo -e "${BLUE}${BOLD}======================================================================${RESET}"

# ------------------------------------------------------------------------------
# 1. OS Detection & Automatic Docker Installation
# ------------------------------------------------------------------------------
detect_and_install_docker() {
    if command -v docker &>/dev/null && docker compose version &>/dev/null; then
        echo -e "${GREEN}[+] Docker and Docker Compose (v2) are already installed.${RESET}"
        return 0
    fi

    echo -e "${YELLOW}[*] Docker not found or incomplete. Detecting OS and installing Docker...${RESET}"

    OS_ID="unknown"
    OS_NAME="Linux"
    if [ -f /etc/os-release ]; then
        # shellcheck disable=SC1091
        . /etc/os-release
        OS_ID="${ID:-unknown}"
        OS_NAME="${NAME:-Linux}"
    fi
    echo -e "${CYAN}[+] Detected Operating System: ${OS_NAME} (${OS_ID})${RESET}"

    SUDO=""
    if [ "$(id -u)" -ne 0 ]; then
        if command -v sudo &>/dev/null; then
            SUDO="sudo"
        else
            echo -e "${YELLOW}[!] Note: Running as non-root without sudo. May require root permissions.${RESET}"
        fi
    fi

    # Install curl & ca-certificates if missing
    if ! command -v curl &>/dev/null; then
        echo -e "${CYAN}[*] Installing curl...${RESET}"
        case "$OS_ID" in
            ubuntu|debian|kali|raspbian|linuxmint|pop)
                $SUDO apt-get update -qq && $SUDO apt-get install -y -qq curl ca-certificates
                ;;
            centos|rhel|fedora|rocky|almalinux|oracle)
                $SUDO dnf install -y -q curl ca-certificates 2>/dev/null || $SUDO yum install -y -q curl ca-certificates
                ;;
            alpine)
                $SUDO apk add --no-cache curl ca-certificates
                ;;
            arch|manjaro)
                $SUDO pacman -Sy --noconfirm curl ca-certificates
                ;;
            *)
                echo -e "${YELLOW}[!] Unknown OS package manager. Please ensure curl is installed.${RESET}"
                ;;
        esac
    fi

    # Use Docker official automated installer
    echo -e "${CYAN}[*] Executing official Docker automated installer (get.docker.com)...${RESET}"
    curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
    $SUDO sh /tmp/get-docker.sh
    rm -f /tmp/get-docker.sh

    # Start and enable docker daemon
    if command -v systemctl &>/dev/null; then
        $SUDO systemctl enable --now docker 2>/dev/null || true
    elif command -v service &>/dev/null; then
        $SUDO service docker start 2>/dev/null || true
    fi

    # Add non-root user to docker group if applicable
    if [ "$(id -u)" -ne 0 ]; then
        $SUDO usermod -aG docker "$USER" 2>/dev/null || true
    fi

    # Final check
    if ! command -v docker &>/dev/null; then
        echo -e "${YELLOW}[-] Automatic Docker installation failed. Please install Docker manually and rerun.${RESET}"
        exit 1
    fi

    echo -e "${GREEN}[+] Docker installed successfully: $(docker --version)${RESET}"
}

detect_and_install_docker

# ------------------------------------------------------------------------------
# 2. Server IP & Domain Detection
# ------------------------------------------------------------------------------
echo -e "${CYAN}[*] Detecting server IP address...${RESET}"
SERVER_IP=""
for svc in "https://api.ipify.org" "https://ifconfig.me/ip" "https://icanhazip.com"; do
    DETECTED=$(curl -s4 --max-time 3 "$svc" 2>/dev/null || true)
    if [[ "$DETECTED" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        SERVER_IP="$DETECTED"
        break
    fi
done

if [ -z "$SERVER_IP" ]; then
    SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || true)
fi

if [ -z "$SERVER_IP" ]; then
    SERVER_IP="127.0.0.1"
fi
echo -e "${GREEN}[+] Detected Server IP: ${SERVER_IP}${RESET}"

# ------------------------------------------------------------------------------
# 3. Environment (.env) Setup & Automatic Credentials Generation
# ------------------------------------------------------------------------------
if [ ! -f ".env" ]; then
    echo -e "${CYAN}[*] Initializing .env configuration from template...${RESET}"
    cp .env.example .env

    # Generate cryptographically secure random keys
    RANDOM_SECRET=$(openssl rand -hex 32 2>/dev/null || date +%s | sha256sum | base64 | head -c 40)
    RANDOM_DB_PASS=$(openssl rand -hex 16 2>/dev/null || date +%s | sha256sum | base64 | head -c 20)
    RANDOM_ADMIN_PASS="Akij@$(openssl rand -hex 4 2>/dev/null || echo '2026')!"

    sed -i "s/change-this-to-a-secure-random-64-character-secret-key-in-production/$RANDOM_SECRET/" .env
    sed -i "s/change-this-to-a-strong-postgres-password-123456/$RANDOM_DB_PASS/" .env
    sed -i "s/change-this-to-admin-password-or-let-deploy-generate/$RANDOM_ADMIN_PASS/" .env

    # Set Allowed Hosts and CSRF Origins for detected IP
    sed -i "s|DJANGO_ALLOWED_HOSTS=.*|DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,${SERVER_IP}|" .env
    sed -i "s|DJANGO_CSRF_TRUSTED_ORIGINS=.*|DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000,http://${SERVER_IP}:8000|" .env

    echo -e "${GREEN}[+] Configured security keys, database credentials, and allowed hosts in .env${RESET}"
else
    # If .env already exists, ensure detected IP is included in DJANGO_ALLOWED_HOSTS
    CURRENT_HOSTS=$(grep -E '^DJANGO_ALLOWED_HOSTS=' .env | cut -d '=' -f2- || true)
    if [[ ! "$CURRENT_HOSTS" =~ $SERVER_IP ]] && [ "$SERVER_IP" != "127.0.0.1" ]; then
        sed -i "s|^DJANGO_ALLOWED_HOSTS=.*|DJANGO_ALLOWED_HOSTS=${CURRENT_HOSTS},${SERVER_IP}|" .env
        CURRENT_CSRF=$(grep -E '^DJANGO_CSRF_TRUSTED_ORIGINS=' .env | cut -d '=' -f2- || true)
        sed -i "s|^DJANGO_CSRF_TRUSTED_ORIGINS=.*|DJANGO_CSRF_TRUSTED_ORIGINS=${CURRENT_CSRF},http://${SERVER_IP}:8000|" .env
    fi
fi

# Load variables for deploy execution
WEB_PORT=$(grep -E '^WEB_PORT=' .env | cut -d '=' -f2 | tr -d ' "' || echo "8000")
ADMIN_USER=$(grep -E '^ADMIN_USERNAME=' .env | cut -d '=' -f2 | tr -d ' "' || echo "admin")
ADMIN_PASS=$(grep -E '^ADMIN_PASSWORD=' .env | cut -d '=' -f2 | tr -d ' "' || echo "AkijAudit@2026!")
ADMIN_EMAIL=$(grep -E '^ADMIN_EMAIL=' .env | cut -d '=' -f2 | tr -d ' "' || echo "admin@akij.net")

# ------------------------------------------------------------------------------
# 4. Pull Latest Production Docker Images
# ------------------------------------------------------------------------------
echo ""
echo -e "${CYAN}[*] Pulling latest production images from Docker Hub...${RESET}"
docker compose pull

# ------------------------------------------------------------------------------
# 5. Launch Containers
# ------------------------------------------------------------------------------
echo ""
echo -e "${CYAN}[*] Starting containers (Web Application + PostgreSQL Database)...${RESET}"
docker compose up -d --remove-orphans

# ------------------------------------------------------------------------------
# 6. Wait for Services & Healthchecks
# ------------------------------------------------------------------------------
echo ""
echo -e "${CYAN}[*] Waiting for database and web service initialization...${RESET}"
MAX_WAIT=75
COUNT=0
HEALTHY=false

while [ $COUNT -lt $MAX_WAIT ]; do
    WEB_STATUS=$(docker inspect -f '{{.State.Health.Status}}' ag_audit_web 2>/dev/null || echo "starting")
    DB_STATUS=$(docker inspect -f '{{.State.Health.Status}}' ag_audit_db 2>/dev/null || echo "starting")
    
    if [ "$WEB_STATUS" = "healthy" ]; then
        HEALTHY=true
        break
    fi
    sleep 3
    COUNT=$((COUNT + 3))
    echo -e "    ${YELLOW}... [Elapsed: ${COUNT}s] db: ${DB_STATUS}, web: ${WEB_STATUS}${RESET}"
done

if [ "$HEALTHY" = false ]; then
    echo -e "${YELLOW}[!] Warning: Web service did not reach 'healthy' state within ${MAX_WAIT}s. Checking logs:${RESET}"
    docker compose logs --tail=25 web
fi

# ------------------------------------------------------------------------------
# 7. Automated Super Admin User Provisioning
# ------------------------------------------------------------------------------
echo ""
echo -e "${CYAN}[*] Provisioning Super Admin account (${ADMIN_USER})...${RESET}"

docker compose exec -T web python manage.py shell -c "
import sys
from django.contrib.auth.models import User
from apps.accounts.models import UserProfile

username = sys.argv[1]
password = sys.argv[2]
email = sys.argv[3] if len(sys.argv) > 3 else f'{username}@akij.net'

user, created = User.objects.get_or_create(username=username, defaults={'email': email, 'is_staff': True, 'is_superuser': True})
user.set_password(password)
user.is_staff = True
user.is_superuser = True
user.save()

profile, _ = UserProfile.objects.get_or_create(user=user)
profile.role = UserProfile.Role.SUPER_ADMIN
profile.save()

action = 'Created' if created else 'Verified & Updated'
print(f'SUPERUSER_STATUS: {action} ({username})')
" "$ADMIN_USER" "$ADMIN_PASS" "$ADMIN_EMAIL"

# ------------------------------------------------------------------------------
# 8. Final Ready Banner with URL & Login Credentials
# ------------------------------------------------------------------------------
PORTAL_URL="http://${SERVER_IP}:${WEB_PORT}/"
ADMIN_DASHBOARD_URL="http://${SERVER_IP}:${WEB_PORT}/admin/super/dashboard/"
REPORTS_URL="http://${SERVER_IP}:${WEB_PORT}/reports/"
ASSETS_URL="http://${SERVER_IP}:${WEB_PORT}/assets/"

echo ""
echo -e "${GREEN}${BOLD}======================================================================${RESET}"
echo -e "${GREEN}${BOLD}  🎉 AKIJ GROUP IT AUDIT PORTAL DEPLOYED SUCCESSFULLY!              ${RESET}"
echo -e "${GREEN}${BOLD}======================================================================${RESET}"
echo ""
echo -e "  ${BOLD}🌐 Portal Access URL:${RESET}      ${CYAN}${BOLD}${PORTAL_URL}${RESET}"
echo -e "  ${BOLD}👤 Super Admin Username:${RESET}  ${YELLOW}${BOLD}${ADMIN_USER}${RESET}"
echo -e "  ${BOLD}🔑 Super Admin Password:${RESET}  ${YELLOW}${BOLD}${ADMIN_PASS}${RESET}"
echo -e "  ${BOLD}📧 Admin Email:${RESET}           ${ADMIN_EMAIL}"
echo ""
echo -e "  ${BOLD}📌 Quick Navigation Links:${RESET}"
echo -e "     • Super Admin Hub:    ${CYAN}${ADMIN_DASHBOARD_URL}${RESET}"
echo -e "     • Executive Reports:  ${CYAN}${REPORTS_URL}${RESET}"
echo -e "     • Asset Inventory:    ${CYAN}${ASSETS_URL}${RESET}"
echo ""
echo -e "${BLUE}${BOLD}======================================================================${RESET}"
echo -e "  ${BOLD}Useful Management Commands (Run inside this folder):${RESET}"
echo -e "     • View live logs:     ${CYAN}docker compose logs -f${RESET}"
echo -e "     • Check status:       ${CYAN}docker compose ps${RESET}"
echo -e "     • Restart portal:     ${CYAN}docker compose restart${RESET}"
echo -e "     • Stop portal:        ${CYAN}docker compose down${RESET}"
echo -e "     • Take DB backup:     ${CYAN}./backup.sh${RESET}"
echo -e "${BLUE}${BOLD}======================================================================${RESET}"
echo ""
