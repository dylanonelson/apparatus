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
        --build-no-cache) BUILD_NO_CACHE=1 ;;
        *[!0-9]*) echo "Unknown option: $arg"; exit 1 ;;
        *) N="$arg" ;;
    esac
done

# Detect git worktree: if .git is a file (not a directory), the worktree's
# gitdir pointer uses an absolute host path that won't exist inside the
# container.  Mount the main repo's .git directory at the same absolute path
# so the reference resolves.
WORKTREE_ARGS=()
if [ -f "$REPO_DIR/.git" ]; then
    GIT_COMMON_DIR="$(cd "$REPO_DIR" && git rev-parse --git-common-dir)"
    # Resolve to absolute path
    if [[ "$GIT_COMMON_DIR" != /* ]]; then
        GIT_COMMON_DIR="$(cd "$REPO_DIR/$GIT_COMMON_DIR" && pwd)"
    fi
    WORKTREE_ARGS=(-v "$GIT_COMMON_DIR:$GIT_COMMON_DIR")
    echo "Worktree detected — mounting $GIT_COMMON_DIR into container"
fi

if [[ "${BUILD:-0}" -eq 1 || "${BUILD_NO_CACHE:-0}" -eq 1 ]]; then
  if [[ "${BUILD_NO_CACHE:-0}" -eq 1 ]]; then
    docker build -f "$REPO_DIR/claude.Dockerfile" -t "$IMAGE_NAME" --no-cache .
  else
    docker build -f "$REPO_DIR/claude.Dockerfile" -t "$IMAGE_NAME" .
  fi
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
    "${WORKTREE_ARGS[@]}" \
    "$IMAGE_NAME"
