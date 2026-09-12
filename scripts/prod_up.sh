#!/usr/bin/env bash
# ==============================================================================
# Document Intelligence Platform — Linux / Cloud Production Launcher
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "============================================================"
echo "   Document Intelligence Platform — Production Launcher    "
echo "============================================================"

cd "$PROJECT_ROOT"

# Ensure .env.prod exists
if [ ! -f "$PROJECT_ROOT/.env.prod" ]; then
    if [ -f "$PROJECT_ROOT/.env.prod.example" ]; then
        echo "Creating .env.prod from template..."
        cp "$PROJECT_ROOT/.env.prod.example" "$PROJECT_ROOT/.env.prod"
    fi
fi

echo ""
echo "Building and launching containers via docker-compose.prod.yml..."
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build

echo ""
echo "============================================================"
echo "Production Stack is active!"
echo "  - Angular Web Application: http://localhost:4200"
echo "  - APISIX Ingress Gateway:  http://localhost:9080"
echo "  - Keycloak IAM:            http://localhost:8080"
echo "  - FastAPI Core Service:    http://localhost:8000"
echo "  - Spring Boot Reports:     http://localhost:8081"
echo "  - MinIO Storage Console:   http://localhost:9001"
echo "============================================================"
echo "To view logs: docker compose -f docker-compose.prod.yml logs -f"
echo "To stop:      ./scripts/prod_down.sh"
echo ""
