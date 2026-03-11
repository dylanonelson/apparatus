#!/usr/bin/env bash
# Build and run the Apparatus dev container.
# PostgreSQL must be running on the host (port 5432).
# Pass --build to force a Docker image rebuild.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_NAME="apparatus-claude"

# Build image if missing or --build passed
if [[ "${1:-}" == "--build" ]] || ! docker image inspect "$IMAGE_NAME" &>/dev/null; then
    docker build -f "$REPO_DIR/claude.Dockerfile" -t "$IMAGE_NAME" "$REPO_DIR"
fi

exec docker run -it --rm \
    --name apparatus-claude \
    -p 3000:3000 \
    -p 8000:8000 \
    -p 8091:8091 \
    -p 15080:15080 \
    -v "$REPO_DIR:/app" \
    -v "apparatus-dev-home:/home/node" \
    "$IMAGE_NAME"
