from __future__ import annotations

import logging
from typing import List, cast

from fastapi import Request
from fastapi.responses import JSONResponse
from fastmcp import Context
from fastmcp.prompts import PromptMessage
from fastmcp.resources.resource import FunctionResource
from fastmcp.server import FastMCP
from fastmcp.server.auth import AccessToken
from fastmcp.server.auth.providers.auth0 import Auth0Provider
from fastmcp.server.auth.providers.jwt import JWTVerifier
from fastmcp.server.dependencies import get_access_token as _get_access_token
from fastmcp.server.http import StarletteWithLifespan
from fastmcp.tools.tool import FunctionTool
from mcp.types import EmbeddedResource, TextContent, TextResourceContents
from pydantic import AnyUrl

from app import publications_catalog
from app.api_models import ReadingStatePayload, ViewportPayloadModel
from app.config import Config
from app.db import get_session_factory as _get_session_factory
from app.prompts import prompt_v1
from app.publication_reader import fetch_publication_files
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
    FastMCP,
    StarletteWithLifespan,
    Auth0Provider,
    FunctionResource,
    FunctionTool,
    FunctionTool,
]:
    auth = Auth0Provider(
        config_url="https://dev-usf5eu2woue2lk2d.us.auth0.com/.well-known/openid-configuration",
        client_id="tD9VSQQwq8bdiNrllCsKFgpU8kUps001",
        client_secret="9_iDZ64ye5hRf_AapjdpIFiQXY2l10UACQ196862dL2XT8u6IBuO_DX7raFSDaHR",
        audience="https://api.apparatus-ebooks.com",
        base_url="https://ff07e236f922.ngrok-free.app",
        issuer_url="https://ff07e236f922.ngrok-free.app",
    )
    mcp_server = FastMCP(
        name="Apparatus MCP",
        instructions=(
            "Read-only access to the user's current reading position, viewport "
            "text, and limited publication file download (up to two manifest hrefs). "
            "All operations require an Auth0 bearer token."
        ),
        auth=auth,
    )

    @mcp_server.resource(
        "resource://reading-state",
        name="Current Reading State",
        description=(
            "Latest reading location for the authenticated user, including "
            "publication id, locator (href/cfi), and current viewport text with "
            "positions. Requires bearer token. Returns JSON ReadingStatePayload; "
            "returns 404/NotFound when no reading history exists."
        ),
        mime_type="application/json; charset=utf-8",
    )
    async def get_current_reading_state_resource() -> ReadingStatePayload:
        access_token = get_access_token()
        if access_token is None:
            raise PermissionError(
                "Authentication is required to access reading state."
            )
        session_factory = get_session_factory()
        return await build_reading_state_payload(access_token, session_factory)

    # @mcp_server.resource(
    #     "resource://current-publication/position-index",
    #     name="Current publication context",
    # )
    # async def get_current_publication_context_resource() -> (
    #     PublicationContextResponseModel
    # ):
    #     """
    #     A json object describing the publication the user has open right now,
    #     including the positions in the publication, the readable assets contained in
    #     the publication, and their titles
    #     """
    #     access_token = get_access_token()
    #     if access_token is None:
    #         raise PermissionError(
    #             "Authentication is required to access publication context."
    #         )
    #     session_factory = get_session_factory()
    #     return await build_publication_context_payload(
    #         access_token, session_factory
    #     )

    async def _get_current_reading_state() -> ReadingStatePayload:
        access_token = get_access_token()
        if access_token is None:
            raise PermissionError(
                "Authentication is required to access reading state."
            )
        session_factory = get_session_factory()
        return await build_reading_state_payload(access_token, session_factory)

    @mcp_server.tool(
        "get_reading_state",
        description=(
            "Return the latest reading location and viewport for the authenticated "
            "user. Requires bearer token. Raises NotFoundError when the user has no "
            "saved reading state."
        ),
    )
    async def get_current_reading_state_tool() -> ReadingStatePayload:
        return await _get_current_reading_state()

    @mcp_server.prompt(
        name="Ask about a book",
        description=(
            "Answer questions about the book the user currently has open by injecting "
            "the current publication metadata and reading state."
        ),
    )
    async def ask_about_book(ctx: Context) -> List[PromptMessage]:
        """
        Ask a question about the book you're currently reading. Uses the latest
        reading state and publication metadata to provide context for the answer.
        """
        reading_state = await _get_current_reading_state()
        if reading_state is None or reading_state.reading_location is None:
            raise ValueError(
                "No reading state found for this user; ask them to open a book and "
                "sync reading progress."
            )

        publication = publications_catalog.get_publication(
            reading_state.reading_location.publication_id
        )

        viewport_payload = ViewportPayloadModel(
            text="", positions=[], selection_text=None
        )
        if reading_state.viewport:
            viewport_payload.text = reading_state.viewport.text
            viewport_payload.positions = reading_state.viewport.positions

        logging.getLogger(__name__).info(
            "reading resource resource://reading-state"
        )
        reading_state_contents = await ctx.read_resource(
            "resource://reading-state"
        )
        logging.getLogger(__name__).info(reading_state_contents)
        text = ""
        if reading_state_contents:
            result = reading_state_contents[0].content
            if isinstance(result, str):
                text = result

        return [
            PromptMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=prompt_v1.get_system_prompt(
                        publication.title,
                        publication.author,
                    ),
                ),
            ),
            PromptMessage(
                role="user",
                content=EmbeddedResource(
                    type="resource",
                    resource=TextResourceContents(
                        uri=AnyUrl("resource://reading-state"),
                        text=text,
                    ),
                ),
            ),
        ]

    @mcp_server.tool(
        "download_publication_files",
        description=(
            "Download up to two files from a publication by manifest href. "
            "Requires bearer token. Input: publication_id and 1-2 hrefs. "
            "Returns a map of href to file content and metadata; errors if an href "
            "is missing, invalid, or not in the manifest."
        ),
    )
    async def download_publication_files_tool(
        publication_id: str, hrefs: list[str]
    ) -> dict[str, object]:
        access_token = get_access_token()
        if access_token is None:
            raise PermissionError(
                "Authentication is required to download publication files."
            )
        if not publication_id:
            raise ValueError("publication_id is required")
        if not isinstance(hrefs, list) or len(hrefs) == 0:
            raise ValueError("hrefs must contain at least one href")
        if len(hrefs) > 2:
            raise ValueError("hrefs cannot exceed 2 items")
        cleaned_hrefs: list[str] = []
        for href in hrefs:
            if not isinstance(href, str) or not href.strip():
                raise ValueError("hrefs must be non-empty strings")
            cleaned_hrefs.append(href.strip())
        return await fetch_publication_files(
            publication_id=publication_id, hrefs=cleaned_hrefs
        )

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

    # Expose MCP under the FastAPI mount path (/mcp) while keeping internal routes root-scoped.
    # http_app path stays at "/" so mounted path is the only prefix.
    mcp_asgi_app: StarletteWithLifespan = mcp_server.http_app(path="/")
    return (
        mcp_server,
        mcp_asgi_app,
        auth,
        cast(FunctionResource, get_current_reading_state_resource),
        cast(FunctionTool, get_current_reading_state_tool),
        cast(FunctionTool, download_publication_files_tool),
    )
