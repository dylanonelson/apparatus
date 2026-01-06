from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.models import Viewport

__all__ = [
    "upsert_viewport",
]


async def upsert_viewport(
    session: AsyncSession,
    *,
    user_id: UUID,
    publication_id: str,
    positions: Sequence[int],
    text: str,
    selection_text: str | None = None,
    recorded_at: datetime | None = None,
    commit: bool = True,
) -> Viewport:
    """
    Insert or update the viewport snapshot for a user.
    Only one row per user is kept; subsequent updates overwrite the same row.
    """
    timestamp: datetime | None = recorded_at
    if timestamp is not None:
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        else:
            timestamp = timestamp.astimezone(timezone.utc)

    result = await session.exec(
        select(Viewport).where(Viewport.user_id == user_id)
    )
    viewport = result.one_or_none()
    if viewport is None:
        viewport = Viewport(
            user_id=user_id,
            publication_id=publication_id,
            positions=list(positions),
            text=text,
            selection_text=selection_text,
            recorded_at=timestamp,
        )
        session.add(viewport)
    else:
        viewport.publication_id = publication_id
        viewport.positions = list(positions)
        viewport.text = text
        viewport.selection_text = selection_text
        viewport.recorded_at = timestamp
        session.add(viewport)

    if commit:
        await session.commit()
        await session.refresh(viewport)
    else:
        await session.flush()

    return viewport
