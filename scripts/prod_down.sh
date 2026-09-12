#!/usr/bin/env bash
# ==============================================================================
# Document Intelligence Platform — Linux / Cloud Production Teardown
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Tearing down production containers..."
cd "$PROJECT_ROOT"
docker compose -f docker-compose.prod.yml down

echo "Production stack stopped."
