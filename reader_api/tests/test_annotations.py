"""Tests for the annotations API endpoints."""
from __future__ import annotations

import asyncio
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from tests.conftest import TestApp


SAMPLE_LOCATOR = {
    "href": "/text/chapter1.xhtml",
    "type": "application/xhtml+xml",
    "locations": {
        "fragments": ["epubcfi(/6/4!/2)"],
        "position": 12,
        "progression": 0.42,
    },
    "text": {
        "before": "He opened the door and ",
        "highlight": "stepped into the bright sunlight",
        "after": " not knowing what he'd find next.",
    },
}


async def _request(
    test_app: TestApp,
    method: str,
    path: str,
    json: dict[str, Any] | None = None,
) -> Any:
    transport = ASGITransport(app=test_app.app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        headers = {"Authorization": f"Bearer {test_app.access_token}"}
        resp = await getattr(client, method)(path, headers=headers, json=json)
        return resp


def test_create_annotation(test_app: TestApp) -> None:
    async def run() -> None:
        user = await test_app.create_user("auth0|user1", email="test@test.com")
        test_app.set_claims({"sub": user.auth0_id})

        resp = await _request(test_app, "post", "/api/annotations", json={
            "publication_id": "pub-1",
            "locator": SAMPLE_LOCATOR,
            "color": "yellow",
            "user_note": "Great passage!",
        })
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["publication_id"] == "pub-1"
        assert data["color"] == "yellow"
        assert data["user_note"] == "Great passage!"
        assert data["locator"]["href"] == "/text/chapter1.xhtml"
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    asyncio.run(run())


def test_create_annotation_without_note(test_app: TestApp) -> None:
    async def run() -> None:
        user = await test_app.create_user("auth0|user2", email="test2@test.com")
        test_app.set_claims({"sub": user.auth0_id})

        resp = await _request(test_app, "post", "/api/annotations", json={
            "publication_id": "pub-1",
            "locator": SAMPLE_LOCATOR,
            "color": "blue",
        })
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["color"] == "blue"
        assert data["user_note"] is None

    asyncio.run(run())


def test_list_annotations(test_app: TestApp) -> None:
    async def run() -> None:
        user = await test_app.create_user("auth0|user3", email="test3@test.com")
        test_app.set_claims({"sub": user.auth0_id})

        # Create two annotations
        for color in ["yellow", "green"]:
            await _request(test_app, "post", "/api/annotations", json={
                "publication_id": "pub-1",
                "locator": SAMPLE_LOCATOR,
                "color": color,
            })

        # List all for publication
        resp = await _request(test_app, "get", "/api/annotations?publication_id=pub-1")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data) == 2

        # Filter by color
        resp = await _request(
            test_app, "get", "/api/annotations?publication_id=pub-1&color=yellow"
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data) == 1
        assert data[0]["color"] == "yellow"

    asyncio.run(run())


def test_get_annotation(test_app: TestApp) -> None:
    async def run() -> None:
        user = await test_app.create_user("auth0|user4", email="test4@test.com")
        test_app.set_claims({"sub": user.auth0_id})

        create_resp = await _request(test_app, "post", "/api/annotations", json={
            "publication_id": "pub-1",
            "locator": SAMPLE_LOCATOR,
            "color": "pink",
        })
        ann_id = create_resp.json()["id"]

        resp = await _request(test_app, "get", f"/api/annotations/{ann_id}")
        assert resp.status_code == 200, resp.text
        assert resp.json()["id"] == ann_id

    asyncio.run(run())


def test_get_annotation_not_found(test_app: TestApp) -> None:
    async def run() -> None:
        user = await test_app.create_user("auth0|user5", email="test5@test.com")
        test_app.set_claims({"sub": user.auth0_id})

        resp = await _request(
            test_app, "get",
            "/api/annotations/00000000-0000-0000-0000-000000000000",
        )
        assert resp.status_code == 404

    asyncio.run(run())


def test_update_annotation(test_app: TestApp) -> None:
    async def run() -> None:
        user = await test_app.create_user("auth0|user6", email="test6@test.com")
        test_app.set_claims({"sub": user.auth0_id})

        create_resp = await _request(test_app, "post", "/api/annotations", json={
            "publication_id": "pub-1",
            "locator": SAMPLE_LOCATOR,
            "color": "yellow",
            "user_note": "Original note",
        })
        ann_id = create_resp.json()["id"]

        # Update color and note
        resp = await _request(test_app, "patch", f"/api/annotations/{ann_id}", json={
            "color": "purple",
            "user_note": "Updated note",
        })
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["color"] == "purple"
        assert data["user_note"] == "Updated note"

    asyncio.run(run())


def test_update_annotation_clear_note(test_app: TestApp) -> None:
    async def run() -> None:
        user = await test_app.create_user("auth0|user7", email="test7@test.com")
        test_app.set_claims({"sub": user.auth0_id})

        create_resp = await _request(test_app, "post", "/api/annotations", json={
            "publication_id": "pub-1",
            "locator": SAMPLE_LOCATOR,
            "color": "yellow",
            "user_note": "Note to remove",
        })
        ann_id = create_resp.json()["id"]

        # Clear the note by setting it to null
        resp = await _request(test_app, "patch", f"/api/annotations/{ann_id}", json={
            "user_note": None,
        })
        assert resp.status_code == 200, resp.text
        assert resp.json()["user_note"] is None

    asyncio.run(run())


def test_delete_annotation(test_app: TestApp) -> None:
    async def run() -> None:
        user = await test_app.create_user("auth0|user8", email="test8@test.com")
        test_app.set_claims({"sub": user.auth0_id})

        create_resp = await _request(test_app, "post", "/api/annotations", json={
            "publication_id": "pub-1",
            "locator": SAMPLE_LOCATOR,
            "color": "green",
        })
        ann_id = create_resp.json()["id"]

        # Delete
        resp = await _request(test_app, "delete", f"/api/annotations/{ann_id}")
        assert resp.status_code == 204

        # Verify it's gone
        resp = await _request(test_app, "get", f"/api/annotations/{ann_id}")
        assert resp.status_code == 404

    asyncio.run(run())


def test_annotation_ownership_isolation(test_app: TestApp) -> None:
    """Annotations from one user should not be visible to another."""

    async def run() -> None:
        user1 = await test_app.create_user("auth0|owner1", email="owner1@test.com")
        user2 = await test_app.create_user("auth0|owner2", email="owner2@test.com")

        # User 1 creates an annotation
        test_app.set_claims({"sub": user1.auth0_id})
        create_resp = await _request(test_app, "post", "/api/annotations", json={
            "publication_id": "pub-1",
            "locator": SAMPLE_LOCATOR,
            "color": "yellow",
        })
        ann_id = create_resp.json()["id"]

        # User 2 cannot see it
        test_app.set_claims({"sub": user2.auth0_id})
        resp = await _request(test_app, "get", f"/api/annotations/{ann_id}")
        assert resp.status_code == 404

        # User 2 cannot update it
        resp = await _request(test_app, "patch", f"/api/annotations/{ann_id}", json={
            "color": "blue",
        })
        assert resp.status_code == 404

        # User 2 cannot delete it
        resp = await _request(test_app, "delete", f"/api/annotations/{ann_id}")
        assert resp.status_code == 404

    asyncio.run(run())


def test_invalid_color_rejected(test_app: TestApp) -> None:
    async def run() -> None:
        user = await test_app.create_user("auth0|user9", email="test9@test.com")
        test_app.set_claims({"sub": user.auth0_id})

        resp = await _request(test_app, "post", "/api/annotations", json={
            "publication_id": "pub-1",
            "locator": SAMPLE_LOCATOR,
            "color": "rainbow",
        })
        assert resp.status_code == 422  # Validation error

    asyncio.run(run())


def test_list_pagination(test_app: TestApp) -> None:
    async def run() -> None:
        user = await test_app.create_user("auth0|user10", email="test10@test.com")
        test_app.set_claims({"sub": user.auth0_id})

        # Create 5 annotations
        for i in range(5):
            await _request(test_app, "post", "/api/annotations", json={
                "publication_id": "pub-1",
                "locator": SAMPLE_LOCATOR,
                "color": "yellow",
                "user_note": f"Note {i}",
            })

        # Get first page of 2
        resp = await _request(
            test_app, "get", "/api/annotations?publication_id=pub-1&limit=2&offset=0"
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 2

        # Get second page
        resp = await _request(
            test_app, "get", "/api/annotations?publication_id=pub-1&limit=2&offset=2"
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 2

        # Get last page
        resp = await _request(
            test_app, "get", "/api/annotations?publication_id=pub-1&limit=2&offset=4"
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    asyncio.run(run())
