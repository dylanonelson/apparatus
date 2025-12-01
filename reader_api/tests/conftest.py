from __future__ import annotations

import asyncio
import os
import sys
import types
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from collections.abc import Generator
from typing import AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

# Override OTEL exporter during tests to avoid OTLP errors.
os.environ.setdefault("OTEL_TRACES_EXPORTER", "console")
os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")
os.environ.setdefault("DB_ECHO", "false")
os.environ.setdefault("AUTH0_API_AUDIENCE", "test-audience")
os.environ.setdefault("AUTH0_ISSUER_DOMAIN", "example.us.auth0.com")
os.environ.setdefault("AUTH0_ALGORITHMS", "RS256")
os.environ.setdefault("PYTHON_DOTENV_DISABLED", "true")

from app.db.models import AuthType, User


@dataclass
class TestApp:
    app: FastAPI
    session_factory: async_sessionmaker[AsyncSession]
    claims_state: dict[str, object]
    access_token: str
    __test__ = False

    async def create_user(
        self,
        auth0_id: str,
        email: str | None = None,
        display_name: str | None = None,
    ) -> User:
        async with self.session_factory() as session:
            user = User(
                auth0_id=auth0_id,
                email=email,
                display_name=display_name,
                auth_type=AuthType.AUTH0_PASSWORD,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user

    def set_claims(self, claims: dict[str, object]) -> None:
        self.claims_state.clear()
        self.claims_state.update(claims)

    def set_access_token(self, access_token: str) -> None:
        self.access_token = access_token

    async def get(self, path: str) -> Response:
        transport = ASGITransport(app=self.app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            return await client.get(path, headers=headers)

    async def post(self, path: str, json: dict[str, object]) -> Response:
        transport = ASGITransport(app=self.app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            return await client.post(path, headers=headers, json=json)


@pytest.fixture()
def test_app() -> Generator[TestApp, None, None]:
    engine: AsyncEngine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)

    async def initialize() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(SQLModel.metadata.create_all)

    asyncio.run(initialize())

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    claims_state: dict[str, object] = {"sub": "auth0|existing-user"}

    if "app.models" not in sys.modules:
        stub_models = types.ModuleType("app.models")

        class LocatorModel:  # noqa: RUF100
            """Placeholder LocatorModel used in tests."""

            pass

        setattr(stub_models, "LocatorModel", LocatorModel)
        sys.modules["app.models"] = stub_models

    if "app.prompts" not in sys.modules:
        stub_prompts = types.ModuleType("app.prompts")

        def _get_messages(*args, **kwargs) -> list[dict[str, str]]:
            return []

        setattr(stub_prompts, "get_messages", _get_messages)
        setattr(
            stub_prompts,
            "prompt_v0",
            types.SimpleNamespace(
            get_system_prompt=lambda *args, **kwargs: "",
            get_user_prompt=lambda *args, **kwargs: "",
        )
        )
        sys.modules["app.prompts"] = stub_prompts

    if "app.model_connector" not in sys.modules:
        stub_connector = types.ModuleType("app.model_connector")
        setattr(stub_connector, "SEARCH_PUBLICATION_TOOL_NAME", "search_publication")

        class _StubModelConnector:
            async def chat(self, *args, **kwargs):
                raise RuntimeError("Model connector stubbed in tests.")

            async def chat_sync(self, *args, **kwargs):
                raise RuntimeError("Model connector stubbed in tests.")

        def _get_stub_connector() -> _StubModelConnector:
            return _StubModelConnector()

        setattr(stub_connector, "get_connector", _get_stub_connector)
        sys.modules["app.model_connector"] = stub_connector

    main_module = import_module("app.main")
    app: FastAPI = main_module.app
    get_db_session = main_module.get_db_session
    require_auth = main_module.require_auth

    require_auth_dependency = None
    defaults = main_module.get_authenticated_user.__defaults__ or ()
    for default in defaults:
        dependency_callable = getattr(default, "dependency", None)
        if dependency_callable is None:
            continue
        if dependency_callable is get_db_session:
            continue
        if dependency_callable.__module__.startswith("fastapi_plugin"):
            require_auth_dependency = dependency_callable
            break

    if require_auth_dependency is None:
        require_auth_dependency = require_auth()

    async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    def override_require_auth() -> dict[str, object]:
        return claims_state.copy()

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[require_auth_dependency] = override_require_auth

    helper = TestApp(
        app=app,
        session_factory=session_factory,
        claims_state=claims_state,
        access_token="test-access-token",
    )

    yield helper

    app.dependency_overrides.pop(get_db_session, None)
    app.dependency_overrides.pop(require_auth_dependency, None)

    asyncio.run(engine.dispose())
