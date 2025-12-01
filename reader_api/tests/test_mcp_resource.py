from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json

import pytest
from fastmcp.exceptions import NotFoundError
from fastmcp.server.auth import AccessToken
from mcp.server.lowlevel.server import NotificationOptions
from pydantic import AnyUrl

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

        from app import mcp_server as mcp_module
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

        result = await main_module.reading_state_resource.fn()  # type: ignore

        assert result.reading_location is not None
        assert (
            result.reading_location.publication_id == payload["publication_id"]
        )
        assert result.viewport is not None
        assert result.viewport.text == payload["viewport"]["text"]  # type: ignore

    asyncio.run(scenario())


def test_mcp_reading_state_resource_returns_not_found_without_data(
    test_app: TestApp, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def scenario() -> None:
        helper = test_app
        helper.set_claims({"sub": "auth0|mcp-empty"})
        user = await helper.create_user(auth0_id="auth0|mcp-empty")

        from app import mcp_server as mcp_module
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
            await main_module.reading_state_resource.fn()  # type: ignore

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

        from app import mcp_server as mcp_module
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

    asyncio.run(scenario())


def test_mcp_reading_state_tool_returns_not_found_without_data(
    test_app: TestApp, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def scenario() -> None:
        helper = test_app
        helper.set_claims({"sub": "auth0|mcp-tool-empty"})
        user = await helper.create_user(auth0_id="auth0|mcp-tool-empty")

        from app import mcp_server as mcp_module
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


def test_mcp_viewport_resource_template_returns_payload(
    test_app: TestApp, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def scenario() -> None:
        helper = test_app
        helper.set_claims({"sub": "auth0|viewport-user"})
        user = await helper.create_user(
            auth0_id="auth0|viewport-user", email="viewport@example.com"
        )

        payload = _sample_payload("pub-viewport", "viewport template text")
        response = await helper.post("/api/reading-state", json=payload)
        assert response.status_code == 201, response.json()
        viewport_id = response.json()["viewport"]["id"]

        from app import mcp_server as mcp_module
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

        resource = await main_module.viewport_resource_template.create_resource(
            f"resource://ereader/{viewport_id}", {"viewport_id": viewport_id}
        )
        raw = await resource.read()
        data = json.loads(raw)

        assert data["viewport_id"] == viewport_id
        assert data["text"] == payload["viewport"]["text"]  # type: ignore
        assert data["token_estimate"] >= 1

    asyncio.run(scenario())


def test_mcp_viewport_update_notifies_subscribers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        from app import mcp_server as mcp_module

        viewport_id = "deadbeef-dead-beef-dead-beefdeadbeef"
        notifications: list[str] = []

        class FakeSession:
            async def send_resource_updated(self, uri: AnyUrl) -> None:
                notifications.append(str(uri))

        session = FakeSession()
        await mcp_module.register_viewport_subscription(viewport_id, session)  # type: ignore[arg-type]
        await mcp_module.notify_viewport_resource_updated(viewport_id)
        await mcp_module.unregister_viewport_subscription(viewport_id, session)  # type: ignore[arg-type]

        assert f"resource://ereader/{viewport_id}" in notifications

    asyncio.run(scenario())


def test_mcp_capabilities_advertise_resource_subscription() -> None:
    from app import main as main_module

    capabilities = main_module.mcp_server._mcp_server.get_capabilities(
        NotificationOptions(), {}
    )
    assert capabilities.resources is not None
    assert capabilities.resources.subscribe is True
