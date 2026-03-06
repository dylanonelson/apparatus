# Reader API

**Python 3.13, FastAPI, SQLModel (PostgreSQL), LiteLLM, FastMCP**

The reader API is the sole public-facing backend. It exposes three route groups mounted on a single FastAPI app:

- **`/api`** - REST endpoints for user data, reading state, and LLM-powered Q&A
- **`/read`** - Authenticated reverse proxy to the Readium CLI server (streams EPUB content to the frontend)
- **`/mcp`** - A [Model Context Protocol](https://modelcontextprotocol.io/) server exposing reading state, publication search, and file download as tools

Python version is managed by uv.

## Local development

```bash
cd reader_api
uv sync                                          # install dependencies
cp ENV_EXAMPLE .env                              # configure environment
alembic upgrade head                             # run migrations
uv run uvicorn app.main:app --port 8000 --reload # start server
```

Or use `make dev` (which runs the `uv run uvicorn ...` command above).

The full app also requires PostgreSQL, publication_api, and the Readium CLI server. Start everything at once from the repo root with `tmuxp load tmuxp.yaml`, or see `../docs/README.md`.

- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/api/health

### Environment variables

Copy `ENV_EXAMPLE` to `.env` and fill in values. See `ENV_EXAMPLE` for the full list with descriptions.

### Common operations

```bash
make dev                # Start with hot reload
make run                # Start without reload
make sync               # Install/sync dependencies
make lock               # Re-lock after editing pyproject.toml
make update-deps        # Upgrade all dependencies

# Add a dependency
uv add <package>        # main dependency
uv add -d <package>     # dev dependency

# Database migrations
alembic revision -m "description" --autogenerate    # generate migration
alembic upgrade head                                # apply all pending
alembic downgrade -1                                # rollback last
alembic current                                     # show current revision
```

## Architecture

**API routes**: all `/api` routes require a valid Auth0 JWT.

**Auth**: Auth0 JWT validation via `auth0-fastapi-api`. The JWT token and claims are forwarded to MCP tools via a context manager so they can access user-specific data.

**Database**: PostgreSQL via SQLModel + async SQLAlchemy (`asyncpg`). Migrations are managed with Alembic.

**LLM integration**: uses LiteLLM as an abstraction over multiple providers (OpenAI, Anthropic, Gemini, Azure, Ollama). Model profiles are defined in `config/models.yaml` and selected via the `MODEL_PROFILE` env var.

**MCP server**: a FastMCP server providing tools for LLM tool-use and external AI clients.

**Prompts**: YAML-based prompt templates with Jinja2 rendering, organized by feature under `prompts/`.

**Readium proxy**: authenticated reverse proxy at `/read/*` that forwards requests to the Readium CLI server and rewrites manifest self-links to point back through the proxy.

**Publication catalog**: loads `publications.yaml` from the path configured by `PUBLICATIONS_CATALOG_PATH`.

## Tracing

OpenTelemetry is configured in `app/tracing.py`. When `OTLP_ENDPOINT` is set, traces for FastAPI requests, httpx calls, and LiteLLM interactions are exported. View them in Jaeger at http://localhost:16686 (service name: `reader-api`).
