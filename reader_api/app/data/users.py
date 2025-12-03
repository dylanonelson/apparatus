from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Final

import httpx
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.config import Config
from app.db.models import AuthType, User

__all__ = ["Auth0UserInfoError", "get_or_create_user"]

logger = logging.getLogger(__name__)

_USERINFO_PATH: Final[str] = "/userinfo"


class Auth0UserInfoError(RuntimeError):
    """Raised when the Auth0 userinfo endpoint cannot be queried successfully."""


def get_auth_type_from_auth0_sub(sub: str) -> AuthType:
    if sub.startswith("google-oauth2"):
        return AuthType.GOOGLE_OAUTH2
    elif sub.startswith("auth0|"):
        return AuthType.AUTH0_PASSWORD
    else:
        raise ValueError("Could not determine auth type from Auth0 sub")


async def get_or_create_user(
    session: AsyncSession,
    *,
    auth0_id: str,
    access_token: str,
) -> User:
    """
    Retrieve a user by Auth0 identifier, creating it from Auth0 profile data if needed.
    """
    if not auth0_id:
        raise ValueError("auth0_id must be provided")

    existing_user = await _lookup_user(session, auth0_id)
    logger.info(f"Existing user: {existing_user}")
    if existing_user is not None:
        return existing_user

    userinfo = await fetch_auth0_userinfo(access_token)
    logger.info("Userinfo: %s", userinfo)
    email = _coerce_optional_str(userinfo.get("email"))
    display_name = _coerce_optional_str(userinfo.get("name"))

    user = User(
        auth0_id=auth0_id,
        email=email,
        display_name=display_name,
        auth_type=get_auth_type_from_auth0_sub(auth0_id),
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        logger.warning(
            "Integrity error when creating user %s: %s",
            auth0_id,
            exc,
            exc_info=exc,
        )
        recovered_user = await _lookup_user(session, auth0_id)
        if recovered_user is not None:
            return recovered_user
        raise

    await session.refresh(user)
    return user


async def _lookup_user(session: AsyncSession, auth0_id: str) -> User | None:
    statement = select(User).where(User.auth0_id == auth0_id)
    result = await session.exec(statement)
    return result.one_or_none()


async def fetch_auth0_userinfo(access_token: str) -> dict[str, object]:
    if not access_token:
        raise Auth0UserInfoError(
            "An access token is required to fetch Auth0 user info"
        )

    config = Config.get_instance()
    url = _build_userinfo_url(config.auth0.issuer_domain)
    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        raise Auth0UserInfoError(
            f"Auth0 userinfo request returned status {status_code}"
        ) from exc
    except httpx.RequestError as exc:
        raise Auth0UserInfoError(
            "Could not reach Auth0 userinfo endpoint"
        ) from exc

    payload = response.json()
    if not isinstance(payload, Mapping):
        raise Auth0UserInfoError("Auth0 userinfo payload is not a JSON object")

    return dict(payload)


def _build_userinfo_url(domain: str) -> str:
    trimmed = domain.strip()
    if not trimmed:
        raise Auth0UserInfoError("Auth0 issuer domain is not configured")

    if not trimmed.startswith(("https://", "http://")):
        trimmed = f"https://{trimmed}"

    return f"{trimmed.rstrip('/')}{_USERINFO_PATH}"


def _coerce_optional_str(value: object) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None
