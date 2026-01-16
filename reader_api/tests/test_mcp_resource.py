from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest
from fastmcp.exceptions import NotFoundError
from fastmcp.server.auth import AccessToken

from tests.conftest import TestApp


def _sample_payload(publication_id: str, text: str) -> dict[str, object]:
    recorded_at = datetime.now(tz=timezone.utc).replace(microsecond=0)
    return {
        "publication_id": publication_id,
        "locator": {
            "href": "/chapters/1",
            "type": "application/xhtml+xml",
            "title": "Chapter 1",
        },
        "viewport": {
            "positions": [1, 2],
            "text": text,
            "selection_text": "selected text",
        },
        "recorded_at": recorded_at.isoformat(),
    }


def test_mcp_reading_state_resource_returns_latest(
    test_app: TestApp, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def scenario() -> None:
        helper = test_app
        helper.set_claims({"sub": "auth0|mcp-user"})
        user = await helper.create_user(
            auth0_id="auth0|mcp-user", email="mcp@example.com"
        )

        payload = _sample_payload("pub-mcp", "viewport text")
        response = await helper.post("/api/reading-state", json=payload)
        assert response.status_code == 201, response.json()

        from app.mcp import mcp_server as mcp_module
        from app import main as main_module

        monkeypatch.setattr(
            mcp_module,
            "get_access_token",
            lambda: AccessToken(
                token="token",
                client_id="client",
                scopes=["openid"],
                claims={"sub": user.auth0_id},
            ),
        )
        monkeypatch.setattr(
            mcp_module, "get_session_factory", lambda: helper.session_factory
        )

        result = await main_module.reading_state_resource.fn()

        assert result.reading_location is not None
        assert (
            result.reading_location.publication_id == payload["publication_id"]
        )
        assert result.viewport is not None
        assert result.viewport.text == payload["viewport"]["text"]  # type: ignore
        assert (
            result.viewport.selection_text
            == payload["viewport"]["selection_text"]  # type: ignore
        )

    asyncio.run(scenario())


def test_mcp_reading_state_resource_returns_not_found_without_data(
    test_app: TestApp, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def scenario() -> None:
        helper = test_app
        helper.set_claims({"sub": "auth0|mcp-empty"})
        user = await helper.create_user(auth0_id="auth0|mcp-empty")

        from app.mcp import mcp_server as mcp_module
        from app import main as main_module

        monkeypatch.setattr(
            mcp_module,
            "get_access_token",
            lambda: AccessToken(
                token="token",
                client_id="client",
                scopes=["openid"],
                claims={"sub": user.auth0_id},
            ),
        )
        monkeypatch.setattr(
            mcp_module, "get_session_factory", lambda: helper.session_factory
        )

        with pytest.raises(NotFoundError):
            await main_module.reading_state_resource.fn()

    asyncio.run(scenario())


def test_mcp_reading_state_tool_returns_latest(
    test_app: TestApp, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def scenario() -> None:
        helper = test_app
        helper.set_claims({"sub": "auth0|mcp-tool-user"})
        user = await helper.create_user(
            auth0_id="auth0|mcp-tool-user", email="mcptool@example.com"
        )

        payload = _sample_payload("pub-mcp-tool", "tool viewport text")
        response = await helper.post("/api/reading-state", json=payload)
        assert response.status_code == 201, response.json()

        from app.mcp import mcp_server as mcp_module
        from app import main as main_module

        monkeypatch.setattr(
            mcp_module,
            "get_access_token",
            lambda: AccessToken(
                token="token",
                client_id="client",
                scopes=["openid"],
                claims={"sub": user.auth0_id},
            ),
        )
        monkeypatch.setattr(
            mcp_module, "get_session_factory", lambda: helper.session_factory
        )

        result = await main_module.reading_state_tool.fn()

        assert result.reading_location is not None
        assert (
            result.reading_location.publication_id == payload["publication_id"]
        )
        assert result.viewport is not None
        assert result.viewport.text == payload["viewport"]["text"]  # type: ignore
        assert (
            result.viewport.selection_text
            == payload["viewport"]["selection_text"]  # type: ignore
        )

    asyncio.run(scenario())


def test_mcp_reading_state_tool_returns_not_found_without_data(
    test_app: TestApp, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def scenario() -> None:
        helper = test_app
        helper.set_claims({"sub": "auth0|mcp-tool-empty"})
        user = await helper.create_user(auth0_id="auth0|mcp-tool-empty")

        from app.mcp import mcp_server as mcp_module
        from app import main as main_module

        monkeypatch.setattr(
            mcp_module,
            "get_access_token",
            lambda: AccessToken(
                token="token",
                client_id="client",
                scopes=["openid"],
                claims={"sub": user.auth0_id},
            ),
        )
        monkeypatch.setattr(
            mcp_module, "get_session_factory", lambda: helper.session_factory
        )

        with pytest.raises(NotFoundError):
            await main_module.reading_state_tool.fn()

    asyncio.run(scenario())
