"""Data access helpers."""

from app.data.users import Auth0UserInfoError, fetch_auth0_userinfo, get_or_create_user
from app.data.reading_locations import (
    create_reading_location,
    get_latest_reading_location,
)
from app.data.viewports import upsert_viewport

_fetch_auth0_userinfo = fetch_auth0_userinfo

__all__ = [
    "Auth0UserInfoError",
    "get_or_create_user",
    "fetch_auth0_userinfo",
    "create_reading_location",
    "get_latest_reading_location",
    "upsert_viewport",
]
