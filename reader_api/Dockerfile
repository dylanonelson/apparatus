FROM python:3.13-slim

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt Makefile ./
RUN make install

# Copy application code, alembic migrations, config, and prompts.
COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini .
COPY config/ config/
COPY prompts/ prompts/
COPY ../static/ publications/

EXPOSE 8000

# Run migrations then start uvicorn.
CMD ["make", "start"]
