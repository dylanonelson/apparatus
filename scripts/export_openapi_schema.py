#!/usr/bin/env python3
"""
Generate the OpenAPI JSON schema from reader_api's Pydantic models and route
signatures, without starting the full application (no DB, auth, or network
dependencies required).

The route stubs here mirror the signatures in app.api_routes. If you add or
change an endpoint there, update this file to match.

Usage:
    cd reader_api && uv run python ../scripts/export_openapi_schema.py
"""

import json
import sys
from pathlib import Path

# Ensure reader_api/ is on the import path so `from app.api_models` works
# regardless of which directory invokes this script.
_reader_api_dir = str(Path(__file__).resolve().parent.parent / "reader_api")
if _reader_api_dir not in sys.path:
    sys.path.insert(0, _reader_api_dir)

from fastapi import FastAPI, Query, status

from app.api_models import (
    AskRequestModel,
    AskResponseModel,
    AutomaticAnswersRequestModel,
    HealthResponseModel,
    ReadingLocationResponseModel,
    ReadingStatePayload,
    ReadingStateResponseModel,
    StoreReadingStateRequestModel,
    UserResponseModel,
)

# ---------------------------------------------------------------------------
# Build a minimal FastAPI app that exposes the same request/response types as
# the real app, purely for schema generation.
# ---------------------------------------------------------------------------

schema_app = FastAPI(title="Apparatus API", version="0.1.0")


@schema_app.get("/api/health", response_model=HealthResponseModel)
def health() -> None: ...


@schema_app.get("/api/users/me", response_model=UserResponseModel)
async def get_current_user() -> None: ...


@schema_app.post(
    "/api/reading-state",
    response_model=ReadingStateResponseModel,
    status_code=status.HTTP_201_CREATED,
)
async def upsert_reading_state(body: StoreReadingStateRequestModel) -> None: ...


@schema_app.get(
    "/api/reading-locations/latest",
    response_model=ReadingLocationResponseModel,
)
async def get_latest_reading_location(
    publication_id: str | None = None,
) -> None: ...


@schema_app.post("/api/ask-freeform", response_model=AskResponseModel)
async def ask_freeform(body: AskRequestModel) -> None: ...


@schema_app.post("/api/ask-automatic", response_model=AskResponseModel)
async def ask_automatic(
    body: AutomaticAnswersRequestModel,
    prompt_version: str = Query(
        "v2", description="The prompt to use for the automatic answer."
    ),
) -> None: ...


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    output_path = Path(__file__).resolve().parent.parent / "reader_api" / "openapi.json"
    schema = schema_app.openapi()
    output_path.write_text(json.dumps(schema, indent=2) + "\n")
    print(f"Wrote {output_path}", file=sys.stderr)
