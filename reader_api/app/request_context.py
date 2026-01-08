"""Request-scoped metadata shared across connector interactions."""

from dataclasses import dataclass
from typing import Mapping

from opentelemetry.context import Context


@dataclass(frozen=True)
class RequestContext:
    """Typed container for per-request metadata and tracing context."""

    publication_id: str
    otel_context: Context
    auth_token: str
    """Bearer token string from the authenticated request."""
    auth_claims: Mapping[str, object]
    """Validated JWT claims from the access token."""
