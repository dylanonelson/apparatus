#!/usr/bin/env bash
# Entrypoint for the Apparatus dev container.
#
# On the first run the apparatus-dev-home volume is empty, which shadows
# the tools (uv, claude) that were installed into /home/node during the
# image build. This script copies them from a stash directory into the
# live home on first use.

set -euo pipefail

MARKER="/home/node/.apparatus-init-done"

if [[ ! -f "$MARKER" ]]; then
    echo "[entrypoint] First run — populating home directory from image..."
    cp -a /home/node-stash/. /home/node/
    touch "$MARKER"
    echo "[entrypoint] Done."
fi

exec "$@"
