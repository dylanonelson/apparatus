from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.models import Annotation, AnnotationColor

__all__ = [
    "create_annotation",
    "get_annotation_by_id",
    "list_annotations",
    "update_annotation",
    "delete_annotation",
]


async def create_annotation(
    session: AsyncSession,
    *,
    user_id: UUID,
    publication_id: str,
    locator: dict[str, object],
    color: AnnotationColor,
    user_note: str | None = None,
    recorded_at: datetime | None = None,
) -> Annotation:
    """Create a new annotation for a user."""
    timestamp: datetime | None = recorded_at
    if timestamp is not None:
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        else:
            timestamp = timestamp.astimezone(timezone.utc)

    annotation = Annotation(
        user_id=user_id,
        publication_id=publication_id,
        locator=locator,
        color=color,
        user_note=user_note,
        recorded_at=timestamp,
    )
    session.add(annotation)
    await session.commit()
    await session.refresh(annotation)
    return annotation


async def get_annotation_by_id(
    session: AsyncSession,
    *,
    annotation_id: UUID,
    user_id: UUID,
) -> Annotation | None:
    """Retrieve a single annotation by ID, scoped to the owning user."""
    statement = select(Annotation).where(
        Annotation.id == annotation_id,
        Annotation.user_id == user_id,
    )
    result = await session.exec(statement)
    return result.one_or_none()


async def list_annotations(
    session: AsyncSession,
    *,
    user_id: UUID,
    publication_id: str,
    color: AnnotationColor | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Annotation]:
    """List annotations for a user and publication, ordered by created_at ascending."""
    statement = select(Annotation).where(
        Annotation.user_id == user_id,
        Annotation.publication_id == publication_id,
    )
    if color is not None:
        statement = statement.where(Annotation.color == color)
    statement = statement.order_by(Annotation.created_at.asc())  # type: ignore[attr-defined]
    statement = statement.offset(offset).limit(limit)
    result = await session.exec(statement)
    return list(result.all())


async def update_annotation(
    session: AsyncSession,
    *,
    annotation: Annotation,
    locator: dict[str, object] | None = None,
    color: AnnotationColor | None = None,
    user_note: str | None = None,
    has_user_note: bool = False,
) -> Annotation:
    """Update mutable fields on an annotation.

    ``has_user_note`` signals whether ``user_note`` was explicitly provided in
    the request (even if ``None``), so callers can distinguish "not provided"
    from "set to null".
    """
    if locator is not None:
        annotation.locator = locator
    if color is not None:
        annotation.color = color
    if has_user_note:
        annotation.user_note = user_note
    session.add(annotation)
    await session.commit()
    await session.refresh(annotation)
    return annotation


async def delete_annotation(
    session: AsyncSession,
    *,
    annotation: Annotation,
) -> None:
    """Delete an annotation."""
    await session.delete(annotation)
    await session.commit()
