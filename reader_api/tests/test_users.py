from __future__ import annotations

import asyncio

import pytest

from tests.conftest import TestApp


def test_get_current_user_returns_user(test_app: TestApp) -> None:
    async def scenario() -> None:
        helper = test_app
        helper.set_claims({"sub": "auth0|user-123"})
        created = await helper.create_user(
            auth0_id="auth0|user-123",
            email="reader@example.com",
            display_name="Test Reader",
        )

        response = await helper.get("/users/me")

        assert response.status_code == 200
        payload = response.json()
        assert payload["email"] == created.email
        assert payload["display_name"] == created.display_name
        assert "created_at" in payload

    asyncio.run(scenario())


def test_get_current_user_creates_missing_user(
    test_app: TestApp,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        helper = test_app
        helper.set_claims({"sub": "auth0|missing"})
        helper.set_access_token("new-token")

        async def fake_fetch(access_token: str) -> dict[str, object]:
            assert access_token == "new-token"
            return {
                "email": "new-user@example.com",
                "name": "New User",
            }

        monkeypatch.setattr("app.data.users.fetch_auth0_userinfo", fake_fetch)

        response = await helper.get("/users/me")

        assert response.status_code == 200
        payload = response.json()
        assert payload["email"] == "new-user@example.com"
        assert payload["display_name"] == "New User"

    asyncio.run(scenario())


def test_get_current_user_returns_400_without_sub_claim(test_app: TestApp) -> None:
    async def scenario() -> None:
        helper = test_app
        helper.set_claims({})

        response = await helper.get("/users/me")

        assert response.status_code == 400
        assert response.json()["detail"] == "Missing subject claim"

    asyncio.run(scenario())
