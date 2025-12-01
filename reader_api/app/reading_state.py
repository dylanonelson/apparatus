from __future__ import annotations

from datetime import datetime, timezone
from typing import cast
from uuid import UUID

from fastmcp.exceptions import NotFoundError
from fastmcp.server.auth import AccessToken
from sqlalchemy import desc
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api_models import (
    LocatorModel,
    ReadingLocationResponseModel,
    ReadingStatePayload,
    ViewportResponseModel,
)
from app.data import get_latest_reading_location
from app.data.users import Auth0UserInfoError, get_or_create_user
from app.db import ReadingLocation, Viewport


def ensure_timezone(timestamp: datetime | None) -> datetime | None:
    if timestamp is None:
        return None
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc)


def build_reading_location_response(
    location: ReadingLocation,
) -> ReadingLocationResponseModel:
    return ReadingLocationResponseModel(
        id=location.id,
        publication_id=location.publication_id,
        locator=LocatorModel.model_validate(location.locator),
        recorded_at=ensure_timezone(location.recorded_at),
        created_at=ensure_timezone(location.created_at),
    )


def build_viewport_response(viewport: Viewport) -> ViewportResponseModel:
    return ViewportResponseModel(
        id=viewport.id,
        publication_id=viewport.publication_id,
        positions=viewport.positions,
        text=viewport.text,
        recorded_at=ensure_timezone(viewport.recorded_at),
        updated_at=ensure_timezone(viewport.updated_at),
    )


async def get_latest_viewport(
    session: AsyncSession, user_id: UUID
) -> Viewport | None:
    updated_at_column = cast(
        ColumnElement[datetime],
        Viewport.updated_at,
    )
    result = await session.execute(
        select(Viewport)
        .where(Viewport.user_id == user_id)
        .order_by(desc(updated_at_column))
    )
    return result.scalars().first()


async def get_viewport_by_id(
    session: AsyncSession, user_id: UUID, viewport_id: UUID
) -> Viewport | None:
    result = await session.execute(
        select(Viewport).where(
            Viewport.user_id == user_id, Viewport.id == viewport_id
        )
    )
    return result.scalars().first()


async def build_reading_state_payload(
    access_token: AccessToken,
    session_factory: async_sessionmaker[AsyncSession],
) -> ReadingStatePayload:
    claims = access_token.claims or {}
    auth0_subject = claims.get("sub")
    if not isinstance(auth0_subject, str) or not auth0_subject:
        raise PermissionError("Missing subject claim in access token.")

    token_value = access_token.token
    if not isinstance(token_value, str) or not token_value:
        raise PermissionError("Missing access token value.")

    async with session_factory() as session:
        try:
            user = await get_or_create_user(
                session,
                auth0_id=auth0_subject,
                access_token=token_value,
            )
        except Auth0UserInfoError as exc:
            raise PermissionError(str(exc)) from exc

        reading_location = await get_latest_reading_location(
            session,
            user_id=user.id,
        )
        viewport = await get_latest_viewport(session, user.id)

    if reading_location is None and viewport is None:
        raise NotFoundError("No reading state found for the authenticated user.")

    return ReadingStatePayload(
        reading_location=(
            build_reading_location_response(reading_location)
            if reading_location
            else None
        ),
        viewport=build_viewport_response(viewport) if viewport else None,
    )
