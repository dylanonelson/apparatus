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
from mcp.types import ResourcesCapability
from mcp.types import PromptMessage, ResourceLink, TextContent


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

    async def client_factory() -> Client:
        # Reuse a single connected client to preserve MCP session state across calls.
        if not client.is_connected():
            await client._connect()
        return client

    proxy = FastMCP.as_proxy(client_factory)

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
