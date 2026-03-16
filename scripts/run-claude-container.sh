#!/usr/bin/env bash
# Build and run the Apparatus dev container.
# PostgreSQL must be running on the host (port 5432).
#
# Usage:
#   ./scripts/run-claude-container.sh [N] [--build]
#
# N is an optional instance number (default 0) that offsets host ports
# so you can run multiple containers in parallel:
#   0 → 3000, 8000, 8091, 15080
#   1 → 3001, 8001, 8092, 15081
#   2 → 3002, 8002, 8093, 15082
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_NAME="apparatus-claude"
N=0

for arg in "$@"; do
    case "$arg" in
        --build) BUILD=1 ;;
        *[!0-9]*) echo "Unknown option: $arg"; exit 1 ;;
        *) N="$arg" ;;
    esac
done

if [[ "$BUILD" -eq 1 ]]; then
  docker build -f "$REPO_DIR/claude.Dockerfile" -t "$IMAGE_NAME" .
fi

exec docker run -it --rm \
    --name "apparatus-claude-${N}" \
    -e "APPARATUS_INSTANCE=${N}" \
    -p "$((3000 + N)):3000" \
    -p "$((8000 + N)):8000" \
    -p "$((8091 + N)):8091" \
    -p "$((15080 + N)):15080" \
    -v "$REPO_DIR:/app" \
    -v "apparatus-dev-home-${N}:/home/node" \
    "$IMAGE_NAME"
