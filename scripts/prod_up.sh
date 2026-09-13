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

# 2. Launch production containers
echo ""
if [ "$1" == "--build" ]; then
    echo "Rebuilding images and starting containers (--build flag active)..."
    docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
else
    echo "Launching containers using existing images (instant startup)..."
    echo "(Hint: pass --build if you modified code/Dockerfiles and want to rebuild: ./scripts/prod_up.sh --build)"
    docker compose -f docker-compose.prod.yml --env-file .env.prod up -d
fi

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
