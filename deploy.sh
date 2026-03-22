#!/bin/bash
set -e

# Support both Docker Compose v2 (docker compose) and v1 (docker-compose)
if docker compose version &>/dev/null 2>&1; then
    dc() { docker compose "$@"; }
else
    dc() { docker-compose "$@"; }
fi

# Start Firefly III first — it creates the firefly_iii network
dc -f docker-compose.yml up -d

# Ensure wget is available inside the Firefly container
echo "Giving Firefly III time to start..."
sleep 15

# Start Cash Trace (Caddy, backend, frontend)
dc -f docker-compose.cashtrace.yml --env-file .env.cashtrace up -d --build

# Ensure Caddy is connected to the Firefly network (may not happen automatically)
CADDY=$(docker ps --filter "name=cashtrace-caddy" --format "{{.Names}}" | head -1)
FIREFLY_NET=$(docker network ls --filter "name=firefly_iii" --format "{{.Name}}" | head -1)
if [ -n "$CADDY" ] && [ -n "$FIREFLY_NET" ]; then
    docker network connect "$FIREFLY_NET" "$CADDY" 2>/dev/null || true
    echo "Caddy connected to $FIREFLY_NET."
fi

echo "Done. Cash Trace is up."
