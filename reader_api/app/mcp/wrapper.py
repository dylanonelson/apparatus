from contextlib import asynccontextmanager
from enum import Enum, unique
from typing import AsyncGenerator, Mapping

from fastmcp import Client as McpClient
from fastmcp import FastMCP
from fastmcp.client.client import CallToolResult
from fastmcp.server.auth import AccessToken
from mcp.server.auth.middleware.auth_context import auth_context_var
from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser

from app.request_context import RequestContext


@unique
class MCPToolName(Enum):
    # Tool names
    SEARCH_PUBLICATION_TOOL = "search_publication"
    READING_STATE_TOOL = "reading_state"
    DOWNLOAD_PUBLICATION_FILES_TOOL = "download_publication_files"


@unique
class MCPResourceURI(Enum):
    READING_STATE_RESOURCE = "resource://reading_state"
    CURRENT_PUBLICATION_CONTEXT_RESOURCE = (
        "resource://current-publication/position-index"
    )


@unique
class MCPPromptName(Enum):
    FREEFORM_ANSWERS_PROMPT = "freeform_answers"
    AUTOMATIC_ANSWERS_PROMPT = "automatic_answers"
    PASSAGE_FINDER_PROMPT = "passage_finder"


@asynccontextmanager
async def call_mcp_server_with_api_auth(
    token: str, claims: Mapping[str, object]
) -> AsyncGenerator[None, None]:
    """
    Forward validated FastAPI auth to MCP ContextVar for in-memory calls.

    This context manager sets the MCP SDK's auth_context_var with an AccessToken
    constructed from a pre-validated FastAPI bearer token and its claims. This
    allows MCP tools to call get_access_token() and receive the forwarded auth
    even when invoked via in-memory transport (where FastMCP's HTTP middleware
    doesn't run).

    Args:
        token: The bearer token string from the authenticated request.
        claims: The validated JWT claims from the access token.

    Yields:
        Nothing; the auth context is set for the duration of the context.
    """
    # Extract client_id from Auth0's "azp" (authorized party) claim
    client_id = claims.get("azp")
    if not isinstance(client_id, str):
        client_id = ""

    # Parse scopes from the "scope" claim (space-separated string)
    scope_claim = claims.get("scope")
    scopes: list[str] = []
    if scope_claim and isinstance(scope_claim, str):
        scopes = scope_claim.split()

    access_token = AccessToken(
        token=token,
        client_id=client_id,
        scopes=scopes,
        claims=dict(claims),
    )

    # AuthenticatedUser wraps the AccessToken for the ContextVar
    authenticated_user = AuthenticatedUser(auth_info=access_token)
    ctx_token = auth_context_var.set(authenticated_user)
    try:
        yield
    finally:
        auth_context_var.reset(ctx_token)


async def call_mcp_tool(
    request_context: RequestContext,
    mcp_server: FastMCP,
    tool_name: MCPToolName,
    arguments: dict,
) -> CallToolResult:
    async with call_mcp_server_with_api_auth(
        request_context.auth_token, request_context.auth_claims
    ):
        async with McpClient(mcp_server) as client:
            return await client.call_tool(tool_name.value, arguments)
