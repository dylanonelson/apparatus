from __future__ import annotations

from datetime import datetime, timezone
from typing import cast
from uuid import UUID

from sqlalchemy import case, desc
from sqlalchemy.sql.elements import ColumnElement
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.models import ReadingLocation

__all__ = [
    "create_reading_location",
    "get_latest_reading_location",
]


async def create_reading_location(
    session: AsyncSession,
    *,
    user_id: UUID,
    publication_id: str,
    locator: dict[str, object],
    recorded_at: datetime | None = None,
    commit: bool = True,
) -> ReadingLocation:
    """
    Persist a new reading location for a user without overwriting prior entries.
    """
    timestamp: datetime | None = recorded_at
    if timestamp is not None:
        if timestamp.tzinfo is None:
            # Ensure timestamps are stored consistently in UTC. Naive timestamps are
            # interpreted as UTC before storage.
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        else:
            timestamp = timestamp.astimezone(timezone.utc)

    location = ReadingLocation(
        user_id=user_id,
        publication_id=publication_id,
        locator=locator,
        recorded_at=timestamp,
    )
    session.add(location)
    if commit:
        await session.commit()
        await session.refresh(location)
    else:
        await session.flush()
    return location


async def get_latest_reading_location(
    session: AsyncSession,
    *,
    user_id: UUID,
    publication_id: str | None = None,
) -> ReadingLocation | None:
    """
    Retrieve the most recent reading location for the user.
    """
    statement = select(ReadingLocation).where(
        ReadingLocation.user_id == user_id
    )
    if publication_id:
        statement = statement.where(
            ReadingLocation.publication_id == publication_id
        )

    recorded_column = cast(
        ColumnElement[datetime | None],
        ReadingLocation.recorded_at,
    )
    created_column = cast(
        ColumnElement[datetime],
        ReadingLocation.created_at,
    )
    # Prefer entries with a recorded timestamp; otherwise fall back to created_at.
    recorded_priority = case(
        (recorded_column.is_(None), 1),
        else_=0,
    )
    statement = statement.order_by(
        recorded_priority.asc(),
        desc(recorded_column),
        desc(created_column),
    ).limit(1)
    result = await session.exec(statement)
    return result.one_or_none()
