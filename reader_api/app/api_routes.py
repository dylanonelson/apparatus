from __future__ import annotations

import time
from uuid import UUID as PyUUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi_plugin import Auth0FastAPI
from opentelemetry import context as context_api
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api_models import (
    AnnotationColor as AnnotationColorAPI,
    AnnotationResponseModel,
    AskRequestModel,
    AskResponseModel,
    AutomaticAnswersRequestModel,
    CreateAnnotationRequestModel,
    HealthResponseModel,
    ReadingLocationResponseModel,
    ReadingStateResponseModel,
    StoreReadingStateRequestModel,
    UpdateAnnotationRequestModel,
    UserResponseModel,
)
from app.config import Config
from app.data import (
    create_annotation,
    create_reading_location,
    delete_annotation,
    get_annotation_by_id,
    get_latest_reading_location,
    list_annotations,
    update_annotation,
    upsert_viewport,
)
from app.data.users import Auth0UserInfoError, get_or_create_user
from app.db import (
    Annotation,
    AnnotationColor,
    User,
    Viewport,
    get_db_session,
)
from app.mcp import MCPToolName
from app.model_connector import get_connector
from app.prompt_manager import get_prompt_manager
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
        """Health check endpoint that always returns 200 OK."""
        try:
            return HealthResponseModel(
                ok=True, timestamp_ms=int(time.time() * 1000)
            )
        except Exception:
            # Fallback to ensure health check never fails
            return HealthResponseModel(ok=True, timestamp_ms=0)

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

    @router.post("/ask-freeform", response_model=AskResponseModel)
    async def ask_freeform(
        request: AskRequestModel,
        claims: dict[str, object] = Depends(require_auth()),
        token: HTTPAuthorizationCredentials = Security(bearer_scheme),
    ) -> AskResponseModel:
        """
        Ask a question about the current reading position.
        Requires authentication to forward auth context to MCP tools.
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
            auth_token=token.credentials,
            auth_claims=claims,
        )

        model_connector = get_connector()

        prompt_manager = get_prompt_manager()
        messages = prompt_manager.get_messages(
            "passage_finder",
            "v0",
            title=publication.title,
            author=publication.author,
            question=request.question,
            location_json=request.locator.model_dump_json(),
        )
        answer = await model_connector.chat_sync(
            messages,
            enabled_tools=list(MCPToolName),
            request_context=request_context,
        )
        return AskResponseModel(answer=answer)

    @router.post("/ask-automatic", response_model=AskResponseModel)
    async def ask_automatic(
        request: AutomaticAnswersRequestModel,
        claims: dict[str, object] = Depends(require_auth()),
        token: HTTPAuthorizationCredentials = Security(bearer_scheme),
        prompt_version: str = Query(
            "v2", description="The prompt to use for the automatic answer."
        ),
    ) -> AskResponseModel:
        """
        Get an automatic answer based on the user's current viewport and selection.
        Infers what the user might be confused about and provides an explanation.
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
            auth_token=token.credentials,
            auth_claims=claims,
        )

        model_connector = get_connector()

        prompt_manager = get_prompt_manager()
        messages = prompt_manager.get_messages(
            "automatic_answers",
            version=prompt_version,
            title=publication.title,
            author=publication.author,
            viewport_json=request.viewport.model_dump_json(),
            location_json=request.locator.model_dump_json(),
        )
        answer = await model_connector.chat_sync(
            messages,
            enabled_tools=list(MCPToolName),
            request_context=request_context,
        )
        return AskResponseModel(answer=answer)

    # ── Annotation endpoints ────────────────────────────────────────────

    @router.post(
        "/annotations",
        response_model=AnnotationResponseModel,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_annotation_entry(
        body: CreateAnnotationRequestModel,
        user: User = Depends(get_authenticated_user),
        session: AsyncSession = Depends(get_db_session),
    ) -> AnnotationResponseModel:
        """Create a new annotation (highlight/note)."""
        annotation = await create_annotation(
            session,
            user_id=user.id,
            publication_id=body.publication_id,
            locator=body.locator.model_dump(mode="json", exclude_none=True),
            color=AnnotationColor(body.color.value),
            user_note=body.user_note,
            recorded_at=body.recorded_at,
        )
        return AnnotationResponseModel.model_validate(annotation)

    @router.get(
        "/annotations",
        response_model=list[AnnotationResponseModel],
    )
    async def list_annotations_entry(
        publication_id: str = Query(..., description="Filter by publication"),
        color: AnnotationColorAPI | None = Query(
            None, description="Filter by highlight color"
        ),
        limit: int = Query(100, ge=1, le=500, description="Page size"),
        offset: int = Query(0, ge=0, description="Pagination offset"),
        user: User = Depends(get_authenticated_user),
        session: AsyncSession = Depends(get_db_session),
    ) -> list[AnnotationResponseModel]:
        """List annotations for the authenticated user and publication."""
        db_color = AnnotationColor(color.value) if color is not None else None
        annotations = await list_annotations(
            session,
            user_id=user.id,
            publication_id=publication_id,
            color=db_color,
            limit=limit,
            offset=offset,
        )
        return [
            AnnotationResponseModel.model_validate(a) for a in annotations
        ]

    @router.get(
        "/annotations/{annotation_id}",
        response_model=AnnotationResponseModel,
    )
    async def get_annotation_entry(
        annotation_id: str,
        user: User = Depends(get_authenticated_user),
        session: AsyncSession = Depends(get_db_session),
    ) -> AnnotationResponseModel:
        """Get a single annotation by ID."""
        try:
            ann_uuid = PyUUID(annotation_id)
        except ValueError:
            raise HTTPException(status_code=404, detail="Annotation not found")
        annotation = await get_annotation_by_id(
            session, annotation_id=ann_uuid, user_id=user.id
        )
        if annotation is None:
            raise HTTPException(status_code=404, detail="Annotation not found")
        return AnnotationResponseModel.model_validate(annotation)

    @router.patch(
        "/annotations/{annotation_id}",
        response_model=AnnotationResponseModel,
    )
    async def update_annotation_entry(
        annotation_id: str,
        body: UpdateAnnotationRequestModel,
        user: User = Depends(get_authenticated_user),
        session: AsyncSession = Depends(get_db_session),
    ) -> AnnotationResponseModel:
        """Update an annotation's mutable fields."""
        try:
            ann_uuid = PyUUID(annotation_id)
        except ValueError:
            raise HTTPException(status_code=404, detail="Annotation not found")
        annotation = await get_annotation_by_id(
            session, annotation_id=ann_uuid, user_id=user.id
        )
        if annotation is None:
            raise HTTPException(status_code=404, detail="Annotation not found")

        # Determine which fields were explicitly provided in the request body
        provided = body.model_fields_set
        updated = await update_annotation(
            session,
            annotation=annotation,
            locator=(
                body.locator.model_dump(mode="json", exclude_none=True)
                if body.locator is not None
                else None
            ),
            color=(
                AnnotationColor(body.color.value)
                if body.color is not None
                else None
            ),
            user_note=body.user_note,
            has_user_note="user_note" in provided,
        )
        return AnnotationResponseModel.model_validate(updated)

    @router.delete(
        "/annotations/{annotation_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        response_class=Response,
    )
    async def delete_annotation_entry(
        annotation_id: str,
        user: User = Depends(get_authenticated_user),
        session: AsyncSession = Depends(get_db_session),
    ) -> Response:
        """Delete an annotation."""
        try:
            ann_uuid = PyUUID(annotation_id)
        except ValueError:
            raise HTTPException(status_code=404, detail="Annotation not found")
        annotation = await get_annotation_by_id(
            session, annotation_id=ann_uuid, user_id=user.id
        )
        if annotation is None:
            raise HTTPException(status_code=404, detail="Annotation not found")
        await delete_annotation(session, annotation=annotation)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router, auth0, bearer_scheme, get_authenticated_user
