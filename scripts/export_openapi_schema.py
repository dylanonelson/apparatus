#!/usr/bin/env python3
"""
Export the OpenAPI schema from the actual reader_api FastAPI application.

Loads .env.local to satisfy Config requirements, then imports the real app
and dumps its OpenAPI schema. No running server needed — the heavy
dependencies (DB, tracing, MCP) are all lazy and won't connect.

Usage:
    cd reader_api && uv run python ../scripts/export_openapi_schema.py
"""

import json
import sys
from pathlib import Path

reader_api_dir = Path(__file__).resolve().parent.parent / "reader_api"

# Load .env.local before anything else so Config.initialize() finds all
# required env vars.  Config internally loads .env (which may not exist),
# but load_dotenv won't override vars that are already set.
from dotenv import load_dotenv

load_dotenv(dotenv_path=reader_api_dir / ".env.local")

# Ensure reader_api/ is importable
if str(reader_api_dir) not in sys.path:
    sys.path.insert(0, str(reader_api_dir))

from app.main import app  # noqa: E402

if __name__ == "__main__":
    output_path = reader_api_dir / "openapi.json"
    schema = app.openapi()
    output_path.write_text(json.dumps(schema, indent=2) + "\n")
    print(f"Wrote {output_path}", file=sys.stderr)
