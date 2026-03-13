#!/bin/bash
set -e

# Support both Docker Compose v2 (docker compose) and v1 (docker-compose)
if docker compose version &>/dev/null 2>&1; then
    dc() { docker compose "$@"; }
else
    dc() { docker-compose "$@"; }
fi

dc -f docker-compose.local.yml up -d --build
echo "Cash Trace running at http://localhost:8080"
