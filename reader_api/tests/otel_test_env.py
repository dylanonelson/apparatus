"""Test-only OpenTelemetry settings to emit spans to console instead of OTLP."""

import os

# Disable OTLP during tests; use console exporter for visibility if needed.
os.environ.setdefault("OTEL_TRACES_EXPORTER", "console")
os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
