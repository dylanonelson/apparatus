from __future__ import annotations

import asyncio

import pytest
from typing import cast

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession as SQLAlchemyAsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.data import get_or_create_user
from app.db.models import AuthType, User


async def _setup_database() -> tuple[
    AsyncEngine, async_sessionmaker[SQLAlchemyAsyncSession]
]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.create_all)
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )
    return engine, session_factory


def test_get_or_create_user_returns_existing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        engine, session_factory = await _setup_database()
        try:
            async with session_factory() as session:
                created = User(
                    auth0_id="auth0|existing-user",
                    email="existing@example.com",
                    display_name="Existing User",
                    auth_type=AuthType.AUTH0_PASSWORD,
                )
                session.add(created)
                await session.commit()
                await session.refresh(created)

            async def fake_fetch(_access_token: str) -> dict[str, object]:
                raise AssertionError("Auth0 API should not be called for existing users")

            monkeypatch.setattr("app.data.users.fetch_auth0_userinfo", fake_fetch)

            async with session_factory() as session:
                user = await get_or_create_user(
                    cast(SQLModelAsyncSession, session),
                    auth0_id="auth0|existing-user",
                    access_token="ignored-access-token",
                )

            assert user.email == "existing@example.com"
            assert user.display_name == "Existing User"
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_get_or_create_user_creates_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        engine, session_factory = await _setup_database()
        try:
            async def fake_fetch(access_token: str) -> dict[str, object]:
                assert access_token == "valid-access-token"
                return {
                    "email": "new-user@example.com",
                    "name": "New User",
                }

            monkeypatch.setattr("app.data.users.fetch_auth0_userinfo", fake_fetch)

            async with session_factory() as session:
                user = await get_or_create_user(
                    cast(SQLModelAsyncSession, session),
                    auth0_id="auth0|new-user",
                    access_token="valid-access-token",
                )

                statement = select(User).where(User.auth0_id == "auth0|new-user")
                result = await session.execute(statement)
                persisted = result.scalar_one()

            assert user.id == persisted.id
            assert user.email == "new-user@example.com"
            assert user.display_name == "New User"
        finally:
            await engine.dispose()

    asyncio.run(scenario())
