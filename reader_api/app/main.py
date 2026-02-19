import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator, cast

from fastapi import FastAPI
from fastmcp.server.dependencies import get_access_token
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from starlette.types import ASGIApp

from app.api_routes import create_api_router
from app.config import Config
from app.db import get_db_session, get_session_factory
from app.mcp import create_mcp_server
from app.model_connector import initialize_connector
from app.readium_routes import create_readium_router
from app.tracing import setup_tracing

logger = logging.getLogger(__name__)

# Print to stdout immediately on module load (before any async setup)
print(f"[STARTUP] Loading main.py module. PORT={os.environ.get('PORT', 'NOT SET')}", flush=True)

Config.initialize()
setup_tracing()

# API setup
api_router, auth0, bearer_scheme, get_authenticated_user = create_api_router()

# Readium proxy setup
readium_router = create_readium_router(
    require_auth=auth0.require_auth,
    bearer_scheme=bearer_scheme,
)

# MCP setup
(
    mcp_server,
    mcp_asgi_app,
    auth_provider,
    reading_state_resource,
    reading_state_tool,
    download_publication_files_tool,
    search_publication_tool,
) = create_mcp_server()

# Initialize model connector with MCP server for in-memory tool calls
model_connector = initialize_connector(mcp_server=mcp_server)

auth_routes = auth_provider.get_routes(mcp_path="/mcp")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Combined lifespan that includes MCP lifespan and our custom startup logging."""
    port = os.environ.get("PORT", "not set")
    railway_env = os.environ.get("RAILWAY_ENVIRONMENT", "not set")
    logger.info("=== Application Startup ===")
    logger.info(f"PORT environment variable: {port}")
    logger.info(f"RAILWAY_ENVIRONMENT: {railway_env}")
    logger.info("Health check endpoint available at /api/health")
    logger.info("===========================")
    
    # Run the MCP lifespan
    async with mcp_asgi_app.router.lifespan_context(app):
        yield


app = FastAPI(
    title="Apparatus API",
    version="0.1.0",
    routes=[*auth_routes],
    lifespan=lifespan,
)


@app.get("/")
async def root():
    """Simple root endpoint for debugging."""
    try:
        return {"status": "ok", "message": "Apparatus API is running"}
    except Exception:
        return {"status": "ok", "message": "API is running (fallback)"}


app.include_router(api_router, prefix="/api")
app.include_router(readium_router, prefix="/read")
app.mount("/mcp", cast(ASGIApp, mcp_asgi_app))
FastAPIInstrumentor().instrument_app(app)

# Re-export for tests/overrides
require_auth = auth0.require_auth

__all__ = [
    "app",
    "get_db_session",
    "get_session_factory",
    "require_auth",
    "get_authenticated_user",
    "get_access_token",
    "reading_state_resource",
    "reading_state_tool",
    "download_publication_files_tool",
    "search_publication_tool",
    "model_connector",
]

print(f"[STARTUP] Application module loaded successfully. PORT={os.environ.get('PORT', 'NOT SET')}", flush=True)
logger.info("Application module loaded successfully.")
