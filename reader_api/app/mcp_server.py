from __future__ import annotations

import asyncio
import weakref
from datetime import datetime, timezone
from typing import cast
from types import MethodType
from uuid import UUID

from fastapi import Request
from fastapi.responses import JSONResponse
from fastmcp.exceptions import NotFoundError
from fastmcp.resources.resource import FunctionResource
from fastmcp.resources.template import FunctionResourceTemplate
from fastmcp.server import FastMCP
from fastmcp.server.auth import AccessToken
from fastmcp.server.auth.providers.jwt import JWTVerifier
from fastmcp.server.dependencies import get_access_token as _get_access_token
from fastmcp.server.http import StarletteWithLifespan
from fastmcp.tools.tool import FunctionTool
from mcp.server.lowlevel.server import NotificationOptions, request_ctx
from mcp.server.session import ServerSession
from mcp.types import PromptMessage, ResourceLink, ResourcesCapability, TextContent
from pydantic import AnyUrl

from app.api_models import LocatorModel, ReadingStatePayload, ViewportResourcePayload
from app.config import Config
from app.db import get_session_factory as _get_session_factory
from app.data.users import Auth0UserInfoError, get_or_create_user
from app.reading_state import (
    build_reading_state_payload,
    ensure_timezone,
    get_latest_viewport,
    get_viewport_by_id,
)
from app.data import get_latest_reading_location
import logging

logger = logging.getLogger(__name__)

# Globals allow test overrides
get_access_token = _get_access_token
get_session_factory = _get_session_factory


_viewport_subscribers: dict[str, weakref.WeakSet[ServerSession]] = {}
_subscriber_lock = asyncio.Lock()


def _viewport_uri() -> str:
    return "resource://ereader/viewport"


def _get_request_session() -> ServerSession:
    try:
        return request_ctx.get().session
    except LookupError as exc:  # pragma: no cover - defensive
        raise RuntimeError("Missing MCP request context.") from exc


async def register_viewport_subscription(
    subject: str, session: ServerSession
) -> None:
    async with _subscriber_lock:
        subscribers = _viewport_subscribers.setdefault(subject, weakref.WeakSet())
        subscribers.add(session)


async def unregister_viewport_subscription(
    subject: str, session: ServerSession
) -> None:
    async with _subscriber_lock:
        subscribers = _viewport_subscribers.get(subject)
        if subscribers is None:
            return
        subscribers.discard(session)
        if not subscribers:
            _viewport_subscribers.pop(subject, None)


async def notify_viewport_resource_updated(subject: str) -> None:
    uri = _viewport_uri()
    async with _subscriber_lock:
        subscribers = list(_viewport_subscribers.get(subject, ()))

    stale_sessions: list[ServerSession] = []
    for session in subscribers:
        try:
            await session.send_resource_updated(AnyUrl(uri))
        except Exception:
            # Stale/broken session; mark for cleanup
            stale_sessions.append(session)

    if stale_sessions:
        async with _subscriber_lock:
            for session in stale_sessions:
                _viewport_subscribers.get(subject, weakref.WeakSet()).discard(session)
            if (
                subject in _viewport_subscribers
                and not _viewport_subscribers[subject]
            ):
                _viewport_subscribers.pop(subject, None)


def _normalize_auth0_base_url(domain: str) -> str:
    base = domain.rstrip("/")
    if not base.startswith("http"):
        base = f"https://{base}"
    return base.rstrip("/")


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text.split()))


def _progress_percent(locator: LocatorModel | None) -> float | None:
    if locator is None or locator.locations is None:
        return None
    total_progression = locator.locations.totalProgression
    if total_progression is None:
        return None
    return round(float(total_progression * 100), 2)


def _build_jwt_auth_provider() -> JWTVerifier:
    auth_config = Config.get_instance().auth0
    issuer_base = _normalize_auth0_base_url(auth_config.issuer_domain)
    return JWTVerifier(
        jwks_uri=f"{issuer_base}/.well-known/jwks.json",
        issuer=f"{issuer_base}/",
        audience=auth_config.api_audience,
        algorithm=auth_config.algorithms[0],
    )


def _enable_resource_subscription_capability(server: FastMCP) -> None:
    original_get_capabilities = server._mcp_server.get_capabilities

    def _patched_get_capabilities(self, notification_options, experimental_capabilities):
        capabilities = original_get_capabilities(
            notification_options, experimental_capabilities
        )
        if capabilities.resources is None:
            capabilities.resources = ResourcesCapability(
                subscribe=True,
                listChanged=notification_options.resources_changed,
            )
        else:
            capabilities.resources.subscribe = True
        return capabilities

    server._mcp_server.get_capabilities = MethodType(
        _patched_get_capabilities, server._mcp_server
    )


def create_mcp_server() -> tuple[
    FastMCP,
    StarletteWithLifespan,
    FunctionResource,
    FunctionTool,
    FunctionResourceTemplate,
    object,
]:
    mcp_server = FastMCP(
        name="Apparatus MCP",
        auth=_build_jwt_auth_provider(),
    )
    _enable_resource_subscription_capability(mcp_server)

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

    @mcp_server.resource(
        "resource://ereader/viewport",
        name="Viewport",
        description="Live viewport text plus metadata for the authenticated user.",
        mime_type="application/json",
        annotations={
            "audience": ["assistant"],
            "priority": 1.0,
        },
    )
    async def get_viewport_resource() -> ViewportResourcePayload:
        access_token = get_access_token()
        if access_token is None:
            raise PermissionError(
                "Authentication is required to access viewport resources."
            )

        claims = access_token.claims or {}
        auth0_subject = claims.get("sub")
        token_value = access_token.token
        if not isinstance(auth0_subject, str) or not auth0_subject:
            raise PermissionError("Missing subject claim in access token.")
        if not isinstance(token_value, str) or not token_value:
            raise PermissionError("Missing access token value.")

        session_factory = get_session_factory()
        async with session_factory() as session:
            try:
                user = await get_or_create_user(
                    session,
                    auth0_id=auth0_subject,
                    access_token=token_value,
                )
            except Auth0UserInfoError as exc:
                raise PermissionError(str(exc)) from exc

            viewport = await get_latest_viewport(session, user.id)
            if viewport is None:
                raise NotFoundError("Viewport not found for the authenticated user.")

            reading_location = await get_latest_reading_location(
                session,
                user_id=user.id,
                publication_id=viewport.publication_id,
            )

        last_modified_dt = ensure_timezone(
            viewport.updated_at or viewport.recorded_at or datetime.now(timezone.utc)
        )
        last_modified = (
            last_modified_dt.isoformat() if last_modified_dt else None
        )

        locator = (
            LocatorModel.model_validate(reading_location.locator)
            if reading_location
            else None
        )

        get_viewport_resource.annotations = {
            "audience": ["assistant"],
            "priority": 1.0,
            "lastModified": last_modified,
        }

        return ViewportResourcePayload(
            viewport_id=viewport.id,
            publication_id=viewport.publication_id,
            positions=viewport.positions,
            text=viewport.text,
            recorded_at=ensure_timezone(viewport.recorded_at),
            updated_at=last_modified_dt,
            locator=locator,
            percent=_progress_percent(locator),
            token_estimate=_estimate_tokens(viewport.text),
        )

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

    @mcp_server.prompt("chat_with_book")
    def chat_with_book() -> list[PromptMessage]:
        resource_uri = _viewport_uri()
        return [
            PromptMessage(
                role="system",
                content=TextContent(
                    type="text",
                    text=(
                        "You are assisting a reader. Use the linked viewport "
                        "resource for the current on-screen text and context."
                    ),
                ),
            ),
            PromptMessage(
                role="user",
                content=ResourceLink(
                    uri=resource_uri,
                    annotations={
                        "audience": ["assistant"],
                        "priority": 1.0,
                    },
                ),
            ),
        ]

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

    # Subscribe/unsubscribe handlers map MCP subscriptions to in-process listeners.
    @mcp_server._mcp_server.subscribe_resource()
    async def _handle_subscribe_resource(uri: AnyUrl) -> None:  # pragma: no cover - exercised via integration
        viewport_id = _extract_viewport_id(uri)
        session = _get_request_session()
        await register_viewport_subscription(viewport_id, session)

    @mcp_server._mcp_server.unsubscribe_resource()
    async def _handle_unsubscribe_resource(uri: AnyUrl) -> None:  # pragma: no cover - exercised via integration
        viewport_id = _extract_viewport_id(uri)
        session = _get_request_session()
        await unregister_viewport_subscription(viewport_id, session)

    mcp_asgi_app: StarletteWithLifespan = mcp_server.http_app(path="/")
    return (
        mcp_server,
        mcp_asgi_app,
        cast(FunctionResource, get_current_reading_state_resource),
        cast(FunctionTool, get_current_reading_state_tool),
        cast(FunctionResourceTemplate, get_viewport_resource),
        chat_with_book,
    )
