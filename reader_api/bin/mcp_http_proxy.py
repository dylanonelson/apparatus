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

from fastmcp.client.client import Client
from fastmcp.server import FastMCP


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
    proxy = FastMCP.as_proxy(client)
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
