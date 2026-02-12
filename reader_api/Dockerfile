# Build context: repo root (set RAILWAY_DOCKERFILE_PATH=reader_api/Dockerfile)
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install into the system Python instead of a venv so executables
# (uvicorn, alembic) are on PATH without needing `uv run`.
ENV UV_PROJECT_ENVIRONMENT=/usr/local

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

EXPOSE 8000

# Run migrations then start uvicorn.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
