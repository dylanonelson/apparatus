# Build context: repo root (set RAILWAY_DOCKERFILE_PATH=reader_api/Dockerfile)
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies first for better layer caching.
COPY reader_api/pyproject.toml reader_api/uv.lock reader_api/.python-version ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy application code, alembic migrations, config, and prompts.
COPY reader_api/app/ app/
COPY reader_api/alembic/ alembic/
COPY reader_api/alembic.ini .
COPY reader_api/config/ config/
COPY reader_api/prompts/ prompts/

# Copy the publications catalog from the shared static directory.
COPY static/publications.yaml publications/publications.yaml

# Put the venv's bin directory on PATH so uvicorn/alembic are available directly.
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# Run migrations then start uvicorn. Echo markers to trace startup in logs.
CMD ["sh", "-c", "echo 'PORT environment variable: '${PORT:-'not set, using 8000'} >&2 && echo 'Running alembic migrations...' >&2 && alembic upgrade head && echo 'Starting uvicorn on 0.0.0.0:'${PORT:-8000}'...' >&2 && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
