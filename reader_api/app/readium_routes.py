"""Authenticated reverse proxy for the Readium CLI publication server.

Every request to ``/read/{path}`` is validated via the same Auth0 JWT
middleware used by the ``/api`` routes and then forwarded to the internal
Readium service (``READIUM_SERVICE_URL``).  Manifest responses have their
``self`` link rewritten so that the frontend resolves subsequent resource
URLs back through this proxy.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Callable

import httpx
from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Config

logger = logging.getLogger(__name__)

# Headers forwarded from the upstream Readium response to the client.
_FORWARDED_HEADERS = frozenset(
    {
        "content-type",
        "content-length",
        "cache-control",
        "etag",
        "last-modified",
        "accept-ranges",
        "content-range",
    }
)


def create_readium_router(
    require_auth: Callable[..., Callable[..., object]],
    bearer_scheme: HTTPBearer,
) -> APIRouter:
    """Build and return the ``/read`` router.

    Parameters
    ----------
    require_auth:
        The ``Auth0FastAPI.require_auth`` callable used by ``/api`` routes.
    bearer_scheme:
        The ``HTTPBearer`` scheme used by ``/api`` routes.
    """

    router = APIRouter()

    @router.get("/{path:path}")
    async def proxy_readium(
        path: str,
        _claims: dict[str, object] = Depends(require_auth()),
        _token: HTTPAuthorizationCredentials = Security(bearer_scheme),
    ) -> StreamingResponse:
        """Proxy an authenticated request to the internal Readium server."""

        readium_url = Config.get_instance().networking.readium_service_url
        upstream_url = f"{readium_url}/{path}"

        try:
            # Request uncompressed responses so we can forward raw bytes
            # with an accurate content-length.  No point compressing over
            # localhost between reader_api and the readium sidecar.
            client = httpx.AsyncClient(
                timeout=30.0,
                headers={"accept-encoding": "identity"},
            )
            upstream_resp = await client.send(
                client.build_request("GET", upstream_url),
                stream=True,
            )
        except httpx.ConnectError as exc:
            logger.error(
                "Cannot reach Readium service at %s: %s", readium_url, exc
            )
            raise HTTPException(
                status_code=502,
                detail="Publication server is unavailable",
            ) from exc

        if upstream_resp.status_code >= 400:
            body = await upstream_resp.aread()
            await upstream_resp.aclose()
            await client.aclose()
            logger.error(
                "Upstream response error with status code %s: %s",
                upstream_resp.status_code,
                body.decode("utf-8", errors="replace") if body else "No body",
            )
            raise HTTPException(
                status_code=upstream_resp.status_code,
                detail=body.decode("utf-8", errors="replace"),
            )

        # For manifest responses, rewrite internal URLs so the browser
        # resolves resource fetches back through this proxy.
        content_type = upstream_resp.headers.get("content-type", "")
        if path.endswith("manifest.json") or "webpub+json" in content_type:
            return await _rewrite_manifest_response(
                upstream_resp, client, readium_url
            )

        # For all other resources, stream directly.
        response_headers = _pick_headers(upstream_resp)
        return StreamingResponse(
            _stream_and_close(upstream_resp, client),
            status_code=upstream_resp.status_code,
            headers=response_headers,
            media_type=upstream_resp.headers.get("content-type"),
        )

    return router


async def _rewrite_manifest_response(
    upstream_resp: httpx.Response,
    client: httpx.AsyncClient,
    readium_url: str,
) -> StreamingResponse:
    """Read the full manifest JSON body, strip internal URLs, and return it.

    The readium CLI generates manifests with a ``self`` link that contains
    the internal service address (e.g. ``http://127.0.0.1:15080/…``).  We
    strip the scheme+host+port prefix so URLs become path-relative, which
    the browser will resolve relative to the URL it fetched the manifest
    from (i.e. through the Next.js -> reader_api proxy chain).
    """

    body = await upstream_resp.aread()
    await upstream_resp.aclose()
    await client.aclose()

    # Normalise the base URL for replacement (with and without trailing slash).
    base = readium_url.rstrip("/")
    # Replace all occurrences of the absolute internal URL with an empty
    # string, turning ``http://127.0.0.1:15080/abc/manifest.json`` into
    # ``/abc/manifest.json`` which the browser resolves relative to the
    # proxy origin.
    rewritten = body.replace(base.encode(), b"")

    return StreamingResponse(
        content=iter([rewritten]),
        status_code=upstream_resp.status_code,
        headers={"content-type": "application/webpub+json"},
    )


async def _stream_and_close(
    response: httpx.Response,
    client: httpx.AsyncClient,
) -> AsyncIterator[bytes]:
    """Yield chunks from *response* then close both response and client."""
    try:
        async for chunk in response.aiter_bytes(chunk_size=64 * 1024):
            yield chunk
    finally:
        await response.aclose()
        await client.aclose()


def _pick_headers(upstream_resp: httpx.Response) -> dict[str, str]:
    """Return the subset of upstream headers that should be forwarded."""
    return {
        key: value
        for key, value in upstream_resp.headers.items()
        if key.lower() in _FORWARDED_HEADERS
    }
