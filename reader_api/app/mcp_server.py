from __future__ import annotations

from typing import List, cast

from fastapi import Request
from fastapi.responses import JSONResponse
from fastmcp import Context
from fastmcp.exceptions import NotFoundError
from fastmcp.prompts import PromptMessage
from fastmcp.resources.resource import FunctionResource
from fastmcp.server import FastMCP
from fastmcp.server.auth import AccessToken
from fastmcp.server.auth.providers.auth0 import Auth0Provider
from fastmcp.server.dependencies import get_access_token as _get_access_token
from fastmcp.server.http import StarletteWithLifespan
from fastmcp.tools.tool import FunctionTool
from mcp.types import (
    EmbeddedResource,
    TextContent,
    TextResourceContents,
    ToolAnnotations,
)
from pydantic import AnyUrl

from app import publications_catalog
from app.api_models import ReadingStatePayload, ViewportPayloadModel
from app.config import Config
from app.db import get_session_factory as _get_session_factory
from app.model_connector import ASK_ABOUT_BOOK_PROMPT_NAME, SEARCH_PUBLICATION_TOOL_NAME
from app.prompt_manager import get_prompt_manager
from app.publication_reader import fetch_publication_files, search_publication
from app.reading_state import (
    build_reading_state_payload,
    get_current_publication,
)

# Globals allow test overrides
get_access_token = _get_access_token
get_session_factory = _get_session_factory


def create_mcp_server() -> tuple[
    FastMCP,
    StarletteWithLifespan,
    Auth0Provider,
    FunctionResource,
    FunctionTool,
    FunctionTool,
    FunctionTool,
]:
    config = Config.get_instance()
    auth0_config = config.auth0
    auth0_mcp_config = auth0_config.mcp
    networking_config = config.networking
    auth = Auth0Provider(
        config_url=f"https://{auth0_config.issuer_domain}/.well-known/openid-configuration",
        client_id=auth0_mcp_config.fast_mcp_client_id,
        client_secret=auth0_mcp_config.fast_mcp_client_secret,
        audience=auth0_config.api_audience,
        base_url=networking_config.reader_api_url,
        issuer_url=networking_config.reader_api_url,
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

    @mcp_server.resource(
        "resource://current-publication/position-index",
        name="Current publication context",
        description=(
            "Context file containing position index, summaries, and metadata for "
            "the user's currently open publication. Includes href mappings, position "
            "ranges, and content summaries. Returns YAML format. Requires bearer token. "
            "Returns 404/NotFound when no context file exists for the publication."
        ),
        mime_type="application/x-yaml",
    )
    async def get_current_publication_context_resource() -> str:
        """
        Returns the context YAML file for the user's currently open publication.
        Contains position index, summaries, and metadata for the publication.
        """
        access_token = get_access_token()
        if access_token is None:
            raise PermissionError(
                "Authentication is required to access publication context."
            )
        current_publication = await _get_current_publication()

        # Get the base directory and resolve the context file path
        base_directory = publications_catalog.get_publications_base_directory()
        context_path = current_publication.resolve_context_path(base_directory)

        if context_path is None:
            raise NotFoundError(
                f"No context file configured for publication '{current_publication.identifier}'"
            )

        if not context_path.exists():
            raise NotFoundError(
                f"Context file not found at {context_path} for publication '{current_publication.identifier}'"
            )

        # Read and return the context file contents
        return context_path.read_text(encoding="utf-8")

    async def _get_current_publication() -> (
        publications_catalog.PublicationMetadata
    ):
        access_token = get_access_token()
        if access_token is None:
            raise PermissionError(
                "Authentication is required to access reading state."
            )
        return await get_current_publication(
            access_token, get_session_factory()
        )

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
        annotations=ToolAnnotations(readOnlyHint=True),
        description=(
            "Return the latest reading location and viewport for the authenticated "
            "user. Requires bearer token. Raises NotFoundError when the user has no "
            "saved reading state."
        ),
    )
    async def get_current_reading_state_tool() -> ReadingStatePayload:
        return await _get_current_reading_state()

    @mcp_server.prompt(
        name=ASK_ABOUT_BOOK_PROMPT_NAME,
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

        reading_state_contents = await ctx.read_resource(
            "resource://reading-state"
        )
        text = ""
        if reading_state_contents:
            result = reading_state_contents[0].content
            if isinstance(result, str):
                text = result

        prompt_manager = get_prompt_manager()
        system_prompt = prompt_manager.get_system_prompt(
            "freeform_answers",
            "v0",
            title=publication.title,
            author=publication.author,
            question="",
        )

        return [
            PromptMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=system_prompt,
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
        annotations=ToolAnnotations(readOnlyHint=True),
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

    @mcp_server.tool(
        SEARCH_PUBLICATION_TOOL_NAME,
        annotations=ToolAnnotations(readOnlyHint=True),
        description=(
            "Search the current publication for passages matching a keyword or phrase. "
            "This search is very simple and will only search literally for the phrase "
            "you provide, so it must appear exactly as you provide it in the book to "
            "return results. Requires bearer token."
        ),
    )
    async def search_publication_tool(
        query: str,
        publication_id: str | None = None,
        max_results: int = 20,
        context_chars: int = 120,
    ) -> dict[str, object]:
        """
        Search for passages in a publication matching a keyword or phrase.

        Args:
            query: Keyword or phrase to search for. The search is case-insensitive
                   and returns exact matches only.
            publication_id: ID of the publication to search. If not provided,
                           uses the user's currently open publication.
            max_results: Maximum number of search results to return. Defaults to 20.
            context_chars: Number of surrounding characters to include for each hit.
                          Defaults to 120.

        Returns:
            A dict containing "hits" - a list of matching passages with context.
        """
        access_token = get_access_token()
        if access_token is None:
            raise PermissionError(
                "Authentication is required to search publications."
            )

        # If publication_id not provided, look it up from reading state
        resolved_publication_id = publication_id
        if resolved_publication_id is None:
            current_pub = await _get_current_publication()
            resolved_publication_id = current_pub.identifier

        hits = await search_publication(
            publication_id=resolved_publication_id,
            query=query,
            max_results=max_results,
            context_chars=context_chars,
        )
        return {"hits": hits}

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
        cast(FunctionTool, search_publication_tool),
    )
