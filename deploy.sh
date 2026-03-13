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
if ! docker exec firefly_iii_core which wget &>/dev/null; then
    docker exec -u root firefly_iii_core apt-get install -y wget -q 2>/dev/null || \
    docker exec -u root firefly_iii_core apk add --no-cache wget -q 2>/dev/null || \
    { echo "Cannot install wget — waiting 15s for Firefly to start instead"; sleep 15; }
fi

# Wait for Firefly to accept HTTP connections
echo "Waiting for Firefly III..."
until docker exec firefly_iii_core wget -qO- http://localhost:8080 &>/dev/null; do
    sleep 2
done
echo "Firefly III is ready."

# Start Cash Trace (Caddy, backend, frontend)
dc -f docker-compose.cashtrace.yml --env-file .env.cashtrace up -d --build

echo "Done. Cash Trace is up."
