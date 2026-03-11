#!/usr/bin/env bash
#
# Generate TypeScript types from the reader_api OpenAPI schema.
#
# This script:
#   1. Exports the OpenAPI schema from reader_api's Pydantic models (offline,
#      no running server required)
#   2. Runs openapi-typescript to generate TypeScript types from the schema
#
# Prerequisites:
#   - uv must be available (manages the reader_api Python environment)
#   - pnpm dependencies must be installed in frontend/
#
# Usage:
#   ./scripts/generate-api-types.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

SCHEMA_OUTPUT="${ROOT_DIR}/reader_api/openapi.json"
TYPES_OUTPUT="${ROOT_DIR}/frontend/src/lib/api-types.generated.ts"

echo "==> Generating OpenAPI schema from Pydantic models"
cd "$ROOT_DIR/reader_api"
uv run python "$SCRIPT_DIR/export_openapi_schema.py"

echo "==> Generating TypeScript types"
cd "$ROOT_DIR/frontend"
pnpm exec openapi-typescript "$SCHEMA_OUTPUT" -o "$TYPES_OUTPUT"

echo "==> Done: ${TYPES_OUTPUT}"
