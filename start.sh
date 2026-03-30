#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Building FL worker image..."
docker build -t imagin-fl-worker:latest "$SCRIPT_DIR/backend/fl_workers"

echo "==> Building and starting platform..."
docker compose -f "$SCRIPT_DIR/docker-compose.yaml" up --build -d

echo "==> Done."
