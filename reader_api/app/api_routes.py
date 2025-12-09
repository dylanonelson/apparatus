from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi_plugin import Auth0FastAPI
from opentelemetry import context as context_api
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api_models import (
    AskRequestModel,
    AskResponseModel,
    HealthResponseModel,
    ReadingLocationResponseModel,
    ReadingStateResponseModel,
    StoreReadingStateRequestModel,
    UserResponseModel,
)
from app.config import Config
from app.data import (
    create_reading_location,
    get_latest_reading_location,
    upsert_viewport,
)
from app.data.users import Auth0UserInfoError, get_or_create_user
from app.db import (
    User,
    Viewport,
    get_db_session,
)
from app.model_connector import SEARCH_PUBLICATION_TOOL_NAME, get_connector
from app.prompts import get_messages
from app.publications_catalog import (
    CatalogError,
    UnknownPublicationError,
    get_publication,
)
from app.reading_state import (
    build_reading_location_response,
    build_viewport_response,
)
from app.request_context import RequestContext


def create_api_router() -> tuple[APIRouter, Auth0FastAPI, HTTPBearer, object]:
    auth0 = Auth0FastAPI(
        domain=Config.get_instance().auth0.issuer_domain,
        audience=Config.get_instance().auth0.api_audience,
    )
    require_auth = auth0.require_auth
    bearer_scheme = HTTPBearer()

    async def get_authenticated_user(
        claims: dict[str, object] = Depends(require_auth()),
        session: AsyncSession = Depends(get_db_session),
        token: HTTPAuthorizationCredentials = Security(bearer_scheme),
    ) -> User:
        auth0_subject = claims.get("sub")
        if not isinstance(auth0_subject, str) or not auth0_subject:
            raise HTTPException(status_code=400, detail="Missing subject claim")
        credentials = token.credentials
        if not isinstance(credentials, str) or not credentials:
            raise HTTPException(status_code=401, detail="Missing access token")

        try:
            user = await get_or_create_user(
                session,
                auth0_id=auth0_subject,
                access_token=credentials,
            )
        except Auth0UserInfoError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        return user

    router = APIRouter()

    @router.get("/health", response_model=HealthResponseModel)
    def health() -> HealthResponseModel:
        return HealthResponseModel(
            ok=True, timestamp_ms=int(time.time() * 1000)
        )

    @router.get("/protected")
    async def protected_route(claims: dict = Depends(auth0.require_auth())):
        return {"message": "This is a protected route"}

    @router.get("/users/me", response_model=UserResponseModel)
    async def get_current_user(
        user: User = Depends(get_authenticated_user),
    ) -> UserResponseModel:
        return UserResponseModel.model_validate(user, extra="ignore")

    @router.post(
        "/reading-state",
        response_model=ReadingStateResponseModel,
        status_code=status.HTTP_201_CREATED,
    )
    async def upsert_reading_state_entry(
        reading_state_request: StoreReadingStateRequestModel,
        user: User = Depends(get_authenticated_user),
        session: AsyncSession = Depends(get_db_session),
    ) -> ReadingStateResponseModel:
        location = await create_reading_location(
            session,
            user_id=user.id,
            publication_id=reading_state_request.publication_id,
            locator=reading_state_request.locator.model_dump(
                mode="json", exclude_none=True
            ),
            recorded_at=reading_state_request.recorded_at,
            commit=False,
        )
        viewport_model: Viewport | None = None
        if reading_state_request.viewport is not None:
            viewport_model = await upsert_viewport(
                session,
                user_id=user.id,
                publication_id=reading_state_request.publication_id,
                positions=reading_state_request.viewport.positions,
                text=reading_state_request.viewport.text,
                selection_text=reading_state_request.viewport.selection_text,
                recorded_at=reading_state_request.recorded_at,
                commit=False,
            )
        await session.commit()
        await session.refresh(location)
        viewport_response = None
        if viewport_model is not None:
            await session.refresh(viewport_model)
            viewport_response = build_viewport_response(viewport_model)
        return ReadingStateResponseModel(
            reading_location=build_reading_location_response(location),
            viewport=viewport_response,
        )

    @router.get(
        "/reading-locations/latest",
        response_model=ReadingLocationResponseModel,
    )
    async def get_latest_reading_location_entry(
        publication_id: str | None = None,
        user: User = Depends(get_authenticated_user),
        session: AsyncSession = Depends(get_db_session),
    ) -> ReadingLocationResponseModel:
        location = await get_latest_reading_location(
            session,
            user_id=user.id,
            publication_id=publication_id,
        )
        if location is None:
            raise HTTPException(
                status_code=404, detail="No reading location found"
            )
        return build_reading_location_response(location)

    @router.post("/ask", response_model=AskResponseModel)
    async def ask(request: AskRequestModel) -> AskResponseModel:
        """
        Ask a question about the current reading position.
        """
        try:
            publication = get_publication(request.publication_id)
        except UnknownPublicationError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except CatalogError as exc:
            raise HTTPException(
                status_code=500, detail="Publications catalog is not available"
            ) from exc

        request_context = RequestContext(
            publication_id=request.publication_id,
            otel_context=context_api.get_current(),
        )

        model_connector = get_connector()

        messages = get_messages(
            request.question,
            request.locator,
            title=publication.title,
            author=publication.author,
            prompt_version="v0",
        )
        answer = await model_connector.chat_sync(
            messages,
            enabled_tools=[SEARCH_PUBLICATION_TOOL_NAME],
            request_context=request_context,
        )
        return AskResponseModel(answer=answer)

    return router, auth0, bearer_scheme, get_authenticated_user
