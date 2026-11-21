#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
ENV_FILE="$ROOT_DIR/.env.production"
COMPOSE_FILE="$ROOT_DIR/infa/compose.yaml"

if [ ! -f "$ENV_FILE" ]; then
    printf '%s\n' "Missing $ENV_FILE. Create it from infa/.env.production.example and set production values." >&2
    exit 1
fi

for required in DJANGO_SECRET_KEY DJANGO_ALLOWED_HOSTS DJANGO_CSRF_TRUSTED_ORIGINS AUDIT_DB_NAME AUDIT_DB_USER AUDIT_DB_PASSWORD; do
    if ! grep -Eq "^${required}=.+$" "$ENV_FILE"; then
        printf '%s\n' "Missing or empty ${required} in .env.production." >&2
        exit 1
    fi
done

if grep -Eq '^DJANGO_SECRET_KEY=(change-me|REPLACE_ME|django-insecure-)' "$ENV_FILE"; then
    printf '%s\n' 'Replace the placeholder DJANGO_SECRET_KEY before deployment.' >&2
    exit 1
fi

if grep -Eq '^AUDIT_DB_PASSWORD=(change-me|REPLACE_ME)$' "$ENV_FILE"; then
    printf '%s\n' 'Replace the placeholder AUDIT_DB_PASSWORD before deployment.' >&2
    exit 1
fi

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" config --quiet
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up --build --detach --remove-orphans
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps
