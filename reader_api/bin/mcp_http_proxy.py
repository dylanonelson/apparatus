#!/usr/bin/env python
"""
StdIO proxy for connecting Claude (or other MCP clients) to the FastMCP HTTP endpoint.

Usage:
  MCP_HTTP_URL=http://localhost:8000/mcp/ \
  MCP_BEARER_TOKEN="Bearer <access_token>" \
  python mcp_http_proxy.py

Point Claude's `command` to this script (inside the repo's venv) and omit args.
"""

from __future__ import annotations

import asyncio
import os
import sys
from types import MethodType

from fastmcp.client.client import Client
from fastmcp.server import FastMCP
from fastmcp.server import proxy as proxy_mod
from mcp.types import PromptMessage, ResourceLink, ResourcesCapability, TextContent
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("mcp_http_proxy")


def _get_env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None or not value.strip():
        raise RuntimeError(f"Environment variable {name} is required.")
    return value.strip()


async def main() -> None:
    url = _get_env("MCP_HTTP_URL", "http://localhost:8000/mcp/")
    token = _get_env("MCP_BEARER_TOKEN")
    if token.lower().startswith("bearer "):
        token = token.split(" ", 1)[1].strip()

    client = Client(url, auth=token)

    async with client:
        proxy = FastMCP.as_proxy(client)

        # Ensure the proxy advertises resource subscriptions so hosts know to subscribe.
        original_get_capabilities = proxy._mcp_server.get_capabilities

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

        proxy._mcp_server.get_capabilities = MethodType(
            _patched_get_capabilities, proxy._mcp_server
        )

        # Preserve annotations when proxying resources so hosts see priority/audience.
        original_from_mcp_resource = proxy_mod.ProxyResource.from_mcp_resource

        @classmethod  # type: ignore[misc]
        def _patched_from_mcp_resource(
            cls, client, mcp_resource
        ):  # pragma: no cover - runtime patch
            resource = original_from_mcp_resource(cls, client, mcp_resource)
            resource.annotations = mcp_resource.annotations
            return resource

        proxy_mod.ProxyResource.from_mcp_resource = _patched_from_mcp_resource  # type: ignore[assignment]

        @proxy.prompt("chat_with_book")
        def chat_with_book() -> list[PromptMessage]:
            return [
                PromptMessage(
                    role="assistant",
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
                    content=ResourceLink.model_validate(
                        {
                            "type": "resource_link",
                            "uri": "resource://ereader/viewport",
                            "name": "Viewport",
                            "annotations": {
                                "audience": ["assistant"],
                                "priority": 1.0,
                            },
                        }
                    ),
                ),
            ]

        # Log incoming MCP messages via the client message handler
        async def log_message(message):
            try:
                root = getattr(message, "root", None)
                req = getattr(message, "request", None)
                if req and hasattr(req, "root"):
                    root = req.root
                method = getattr(root, "method", None) or root.__class__.__name__ if root else type(message).__name__
                params = getattr(root, "params", None)
                logger.info("MCP incoming: %s %s", method, params)
            except Exception:
                logger.exception("Failed to log incoming MCP message")

        if hasattr(proxy._mcp_server, "_client") and hasattr(proxy._mcp_server._client, "message_handler"):  # type: ignore[attr-defined]
            proxy._mcp_server._client.message_handler = log_message  # type: ignore[attr-defined]

        try:
            await proxy.run_stdio_async()
        except* BrokenPipeError:
            # Client closed the pipe; exit cleanly.
            pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except BrokenPipeError:
        # Client disconnected; exit quietly to avoid noisy stack traces in hosts like Claude.
        sys.exit(0)
    except KeyboardInterrupt:
        sys.exit(0)
