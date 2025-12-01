from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from typing import cast

from sqlalchemy import asc
from sqlalchemy.sql.elements import ColumnElement
from sqlmodel import select

from app.db.models import ReadingLocation, Viewport
from tests.conftest import TestApp


def _sample_locator(title: str) -> dict[str, object]:
    return {
        "href": f"/chapters/{title.lower().replace(' ', '-')}",
        "type": "application/xhtml+xml",
        "title": title,
        "locations": {"progression": 0.5},
        "text": {
            "before": "Before text",
            "highlight": "Highlighted text",
            "after": "After text",
        },
    }


def _sample_viewport(text: str) -> dict[str, object]:
    return {
        "positions": [1, 2],
        "text": text,
    }


def test_create_reading_state_persists_location_without_viewport(
    test_app: TestApp,
) -> None:
    async def scenario() -> None:
        helper = test_app
        helper.set_claims({"sub": "auth0|reader-1"})
        await helper.create_user(auth0_id="auth0|reader-1", email="reader1@example.com")

        recorded_at = datetime.now(tz=timezone.utc).replace(microsecond=0)
        payload = {
            "publication_id": "pub-123",
            "locator": _sample_locator("Chapter 1"),
            "recorded_at": recorded_at.isoformat(),
            "viewport": None,
        }

        response = await helper.post("/api/reading-state", json=payload)

        assert response.status_code == 201, response.json()
        data = response.json()
        reading_location = data["reading_location"]
        assert reading_location["publication_id"] == payload["publication_id"]
        assert reading_location["locator"]["href"] == payload["locator"]["href"]
        returned_at = datetime.fromisoformat(reading_location["recorded_at"])
        assert returned_at.replace(tzinfo=None) == recorded_at.replace(tzinfo=None)
        saved_at = datetime.fromisoformat(reading_location["created_at"])
        assert saved_at.tzinfo is not None
        assert data["viewport"] is None

        async with helper.session_factory() as session:
            result = await session.execute(select(ReadingLocation))
            locations = result.scalars().all()
            assert len(locations) == 1
            stored = locations[0]
            assert stored.publication_id == payload["publication_id"]
            assert stored.locator["href"] == payload["locator"]["href"]
            assert stored.recorded_at is not None
            assert stored.recorded_at.replace(tzinfo=None) == recorded_at.replace(
                tzinfo=None
            )

    asyncio.run(scenario())


def test_create_reading_state_persists_viewport_and_location(
    test_app: TestApp,
) -> None:
    async def scenario() -> None:
        helper = test_app
        helper.set_claims({"sub": "auth0|reader-viewport"})
        await helper.create_user(
            auth0_id="auth0|reader-viewport", email="viewport@example.com"
        )

        recorded_at = datetime.now(tz=timezone.utc).replace(microsecond=0)
        payload = {
            "publication_id": "pub-viewport",
            "locator": _sample_locator("Viewport Chapter"),
            "recorded_at": recorded_at.isoformat(),
            "viewport": _sample_viewport("Visible text for viewport"),
        }

        response = await helper.post("/api/reading-state", json=payload)

        assert response.status_code == 201, response.json()
        data = response.json()

        reading_location = data["reading_location"]
        viewport = data["viewport"]

        assert reading_location["publication_id"] == payload["publication_id"]
        assert viewport["publication_id"] == payload["publication_id"]
        assert viewport["positions"] == payload["viewport"]["positions"]
        assert viewport["text"] == payload["viewport"]["text"]

        async with helper.session_factory() as session:
            result_locations = await session.execute(select(ReadingLocation))
            locations = result_locations.scalars().all()
            assert len(locations) == 1

            result_viewports = await session.execute(select(Viewport))
            viewports = result_viewports.scalars().all()
            assert len(viewports) == 1
            assert viewports[0].text == payload["viewport"]["text"]

    asyncio.run(scenario())


def test_get_latest_reading_location_filters_by_publication(test_app: TestApp) -> None:
    async def scenario() -> None:
        helper = test_app
        helper.set_claims({"sub": "auth0|reader-2"})
        await helper.create_user(auth0_id="auth0|reader-2", email="reader2@example.com")

        base_time = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
        entries = [
            (
                "pub-a",
                _sample_locator("Chapter A1"),
                base_time,
            ),
            (
                "pub-a",
                _sample_locator("Chapter A2"),
                base_time + timedelta(minutes=5),
            ),
            (
                "pub-b",
                _sample_locator("Chapter B1"),
                base_time + timedelta(minutes=10),
            ),
        ]

        for publication_id, locator, recorded_at in entries:
            payload = {
                "publication_id": publication_id,
                "locator": locator,
                "recorded_at": recorded_at.isoformat(),
                "viewport": None,
            }
            response = await helper.post("/api/reading-state", json=payload)
            assert response.status_code == 201, response.json()

        response_pub = await helper.get(
            "/api/reading-locations/latest?publication_id=pub-a"
        )
        assert response_pub.status_code == 200
        data_pub = response_pub.json()
        assert data_pub["publication_id"] == "pub-a"
        pub_recorded = datetime.fromisoformat(data_pub["recorded_at"])
        assert pub_recorded == base_time + timedelta(minutes=5)

        response_all = await helper.get("/api/reading-locations/latest")
        assert response_all.status_code == 200
        data_all = response_all.json()
        assert data_all["publication_id"] == "pub-b"
        all_recorded = datetime.fromisoformat(data_all["recorded_at"])
        assert all_recorded == base_time + timedelta(minutes=10)

        async with helper.session_factory() as session:
            result = await session.execute(select(ReadingLocation))
            locations = result.scalars().all()
            assert len(locations) == len(entries)

    asyncio.run(scenario())


def test_reading_state_overwrites_viewport_entry(test_app: TestApp) -> None:
    async def scenario() -> None:
        helper = test_app
        helper.set_claims({"sub": "auth0|reader-viewport-overwrite"})
        await helper.create_user(
            auth0_id="auth0|reader-viewport-overwrite", email="reader-overwrite@example.com"
        )

        first_payload = {
            "publication_id": "pub-viewport-overwrite",
            "locator": _sample_locator("First"),
            "viewport": _sample_viewport("First viewport text"),
        }
        second_payload = {
            "publication_id": "pub-viewport-overwrite",
            "locator": _sample_locator("Second"),
            "viewport": {
                "positions": [3],
                "text": "Updated viewport text",
            },
        }

        response_first = await helper.post("/api/reading-state", json=first_payload)
        assert response_first.status_code == 201, response_first.json()

        response_second = await helper.post("/api/reading-state", json=second_payload)
        assert response_second.status_code == 201, response_second.json()

        async with helper.session_factory() as session:
            result_locations = await session.execute(select(ReadingLocation))
            locations = result_locations.scalars().all()
            assert len(locations) == 2

            result_viewports = await session.execute(select(Viewport))
            viewports = result_viewports.scalars().all()
            assert len(viewports) == 1
            assert viewports[0].text == second_payload["viewport"]["text"]
            assert viewports[0].positions == second_payload["viewport"]["positions"]
            assert viewports[0].publication_id == second_payload["publication_id"]

    asyncio.run(scenario())


def test_latest_reading_location_falls_back_to_created_at(test_app: TestApp) -> None:
    async def scenario() -> None:
        helper = test_app
        helper.set_claims({"sub": "auth0|reader-4"})
        await helper.create_user(auth0_id="auth0|reader-4", email="reader4@example.com")

        payload_a = {
            "publication_id": "pub-fallback",
            "locator": _sample_locator("Initial Chapter"),
            "viewport": None,
        }
        response_a = await helper.post("/api/reading-state", json=payload_a)
        assert response_a.status_code == 201, response_a.json()

        payload_b = {
            "publication_id": "pub-fallback",
            "locator": _sample_locator("Next Chapter"),
            "viewport": None,
        }
        response_b = await helper.post("/api/reading-state", json=payload_b)
        assert response_b.status_code == 201, response_b.json()

        response_latest = await helper.get(
            "/api/reading-locations/latest?publication_id=pub-fallback"
        )
        assert response_latest.status_code == 200
        data = response_latest.json()
        assert data["recorded_at"] is None

        async with helper.session_factory() as session:
            created_column = cast(
                ColumnElement[datetime],
                ReadingLocation.created_at,
            )
            result = await session.execute(
                select(ReadingLocation)
                .where(ReadingLocation.publication_id == "pub-fallback")
                .order_by(asc(created_column))
            )
            entries = result.scalars().all()
            assert len(entries) == 2
            latest_entry = entries[-1]
            assert data["id"] == str(latest_entry.id)

    asyncio.run(scenario())


def test_get_latest_reading_location_returns_404_when_missing(test_app: TestApp) -> None:
    async def scenario() -> None:
        helper = test_app
        helper.set_claims({"sub": "auth0|reader-3"})
        await helper.create_user(auth0_id="auth0|reader-3", email="reader3@example.com")

        response = await helper.get("/api/reading-locations/latest")

        assert response.status_code == 404
        assert response.json()["detail"] == "No reading location found"

    asyncio.run(scenario())
