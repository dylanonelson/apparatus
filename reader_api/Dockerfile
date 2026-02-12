# Build context: repo root (set RAILWAY_DOCKERFILE_PATH=reader_api/Dockerfile)
FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends make \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first for better layer caching.
COPY reader_api/requirements.txt reader_api/Makefile ./
RUN make install

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
CMD ["make", "start"]
