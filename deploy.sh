#!/bin/bash
set -e

# Start Firefly III first — it creates the firefly_iii network
docker compose -f docker-compose.yml up -d

# Wait for Firefly to be healthy
echo "Waiting for Firefly III..."
until docker inspect firefly_iii_core --format '{{.State.Health.Status}}' 2>/dev/null | grep -q healthy; do
    sleep 2
done
echo "Firefly III is healthy."

# Start Cash Trace (Caddy, backend, frontend)
docker compose -f docker-compose.cashtrace.yml --env-file .env.cashtrace up -d --build

echo "Done. Cash Trace is up."
