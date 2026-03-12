#!/bin/bash
set -e

docker compose -f docker-compose.local.yml up -d --build
echo "Cash Trace running at http://localhost:8080"
