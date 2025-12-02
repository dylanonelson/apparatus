import logging
from typing import cast

from fastapi import FastAPI
from fastmcp.server.dependencies import get_access_token
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from starlette.types import ASGIApp

from app.api_routes import create_api_router
from app.config import Config
from app.db import get_db_session, get_session_factory
from app.mcp_server import create_mcp_server
from app.tracing import setup_tracing

Config.initialize()
setup_tracing()

app = FastAPI(title="Apparatus API", version="0.1.0")
FastAPIInstrumentor().instrument_app(app)

# API setup
api_router, auth0, bearer_scheme, get_authenticated_user = create_api_router()
app.include_router(api_router, prefix="/api")

# MCP setup
mcp_server, mcp_asgi_app, reading_state_resource, reading_state_tool, download_publication_files_tool = create_mcp_server()
app.router.lifespan_context = mcp_asgi_app.router.lifespan_context
app.mount("/mcp", cast(ASGIApp, mcp_asgi_app))

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
]

logging.getLogger(__name__).info("Application startup complete.")
