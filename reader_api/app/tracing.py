from __future__ import annotations

from os import getenv
from typing import Final

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.asyncio import AsyncioInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

_TRACING_INITIALIZED: bool = False
_SERVICE_NAME: Final[str] = "reader-api"
_OTLP_ENDPOINT_ENV_VAR: Final[str] = "OTLP_ENDPOINT"
_OTLP_ENABLED_ENV_VAR: Final[str] = "OTLP_ENABLED"
_DEFAULT_OTLP_ENDPOINT: Final[str] = "http://localhost:4317"


def _is_tracing_enabled() -> bool:
    raw = getenv(_OTLP_ENABLED_ENV_VAR, "true").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def setup_tracing() -> None:
    """
    Configure OpenTelemetry tracing for the service.

    Tracing is disabled when OTLP_ENABLED is false. This avoids connection
    errors when no OTLP collector is available (e.g. Railway deployments).
    """
    global _TRACING_INITIALIZED
    if _TRACING_INITIALIZED:
        return

    resource = Resource.create({"service.name": _SERVICE_NAME})
    provider = TracerProvider(resource=resource)

    if _is_tracing_enabled():
        endpoint = getenv(_OTLP_ENDPOINT_ENV_VAR)
        resolved_endpoint = endpoint if endpoint else _DEFAULT_OTLP_ENDPOINT
        exporter = OTLPSpanExporter(endpoint=resolved_endpoint, insecure=True)
        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)
    # When disabled, provider has no processors; spans are created but dropped.
    # This avoids connection attempts to a non-existent OTLP collector.

    trace.set_tracer_provider(provider)

    set_global_textmap(TraceContextTextMapPropagator())

    AsyncioInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()

    _TRACING_INITIALIZED = True
