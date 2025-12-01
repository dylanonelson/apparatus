from __future__ import annotations

from typing import cast

from fastapi import Request
from fastapi.responses import JSONResponse
from fastmcp.resources.resource import FunctionResource
from fastmcp.server import FastMCP
from fastmcp.server.auth import AccessToken
from fastmcp.server.auth.providers.jwt import JWTVerifier
from fastmcp.server.dependencies import get_access_token as _get_access_token
from fastmcp.server.http import StarletteWithLifespan
from fastmcp.tools.tool import FunctionTool

from app.api_models import ReadingStatePayload
from app.config import Config
from app.db import get_session_factory as _get_session_factory
from app.reading_state import build_reading_state_payload

# Globals allow test overrides
get_access_token = _get_access_token
get_session_factory = _get_session_factory


def _normalize_auth0_base_url(domain: str) -> str:
    base = domain.rstrip("/")
    if not base.startswith("http"):
        base = f"https://{base}"
    return base.rstrip("/")


def _build_jwt_auth_provider() -> JWTVerifier:
    auth_config = Config.get_instance().auth0
    issuer_base = _normalize_auth0_base_url(auth_config.issuer_domain)
    return JWTVerifier(
        jwks_uri=f"{issuer_base}/.well-known/jwks.json",
        issuer=f"{issuer_base}/",
        audience=auth_config.api_audience,
        algorithm=auth_config.algorithms[0],
    )


def create_mcp_server() -> tuple[
    FastMCP, StarletteWithLifespan, FunctionResource, FunctionTool
]:
    mcp_server = FastMCP(
        name="Apparatus MCP",
        auth=_build_jwt_auth_provider(),
    )

    @mcp_server.resource(
        "resource://reading-state",
        name="Current Reading State",
        description="Latest reading location and viewport for the authenticated user.",
        mime_type="application/json",
    )
    async def get_current_reading_state_resource() -> ReadingStatePayload:
        access_token = get_access_token()
        if access_token is None:
            raise PermissionError(
                "Authentication is required to access reading state."
            )
        session_factory = get_session_factory()
        return await build_reading_state_payload(access_token, session_factory)

    @mcp_server.tool(
        "get_reading_state",
        description="Return the latest reading location and viewport for the authenticated user.",
    )
    async def get_current_reading_state_tool() -> ReadingStatePayload:
        access_token = get_access_token()
        if access_token is None:
            raise PermissionError(
                "Authentication is required to access reading state."
            )
        session_factory = get_session_factory()
        return await build_reading_state_payload(access_token, session_factory)

    @mcp_server.custom_route("/auth/diagnostic", methods=["GET"])
    async def mcp_auth_diagnostic(request: Request) -> JSONResponse:
        """
        Lightweight diagnostics endpoint to inspect MCP auth token shape.
        Returns issuer, audience, scopes, and whether a token was present.
        """
        access_token: AccessToken | None = get_access_token()
        if access_token is None:
            return JSONResponse(
                {
                    "authenticated": False,
                    "error": "missing access token",
                }
            )
        claims = access_token.claims or {}
        return JSONResponse(
            {
                "authenticated": True,
                "issuer": claims.get("iss"),
                "audience": claims.get("aud"),
                "scopes": claims.get("scope"),
                "subject": claims.get("sub"),
            }
        )

    mcp_asgi_app: StarletteWithLifespan = mcp_server.http_app(path="/")
    return (
        mcp_server,
        mcp_asgi_app,
        cast(FunctionResource, get_current_reading_state_resource),
        cast(FunctionTool, get_current_reading_state_tool),
    )
