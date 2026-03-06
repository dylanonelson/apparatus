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

Copy `ENV_EXAMPLE` to `.env` and fill in values. Key groups:

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL connection string (`postgresql+asyncpg://...`) |
| `CONTENT_SERVICE_URL` | URL of publication_api (default `http://127.0.0.1:8091`) |
| `READIUM_SERVICE_URL` | URL of the Readium CLI server (default `http://127.0.0.1:15080`) |
| `AUTH0_API_AUDIENCE` | Auth0 API audience for JWT validation |
| `AUTH0_ISSUER_DOMAIN` | Auth0 tenant domain |
| `AUTH0_ALGORITHMS` | JWT signing algorithm (default `RS256`) |
| `MODEL_PROFILE` | LLM model profile from `config/models.yaml` (default `default`) |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` | LLM provider credentials (set the ones you use) |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` (default `WARNING`) |
| `DB_ECHO` | Log SQL statements (default `false`) |
| `OTLP_ENDPOINT` | OpenTelemetry collector endpoint for tracing |

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
alembic revision -m "description" --autogenerate   # generate migration
alembic upgrade head                                # apply all pending
alembic downgrade -1                                # rollback last
alembic current                                     # show current revision
```

## Architecture

### API routes (`app/api_routes.py`)

All `/api` routes require a valid Auth0 JWT. Key endpoints:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/health` | GET | Health check |
| `/api/users/me` | GET | Current user profile |
| `/api/reading-state` | POST | Save reading location + viewport snapshot |
| `/api/reading-locations/latest` | GET | Get most recent reading position |
| `/api/ask-freeform` | POST | User types a question about the book |
| `/api/ask-automatic` | POST | Auto-infer a question from selected text and provide an explanation |

### Auth

Auth0 JWT validation via `auth0-fastapi-api`. On first login, the user's Auth0 profile is fetched and a local `User` record is created. The JWT token and claims are forwarded to MCP tools via a context manager so they can access user-specific data.

### Database (`app/db/`)

PostgreSQL via SQLModel + async SQLAlchemy (`asyncpg`). Three tables:

| Table | Purpose |
|-------|---------|
| `User` | Auth0 user records (id, email, display_name, auth_type) |
| `ReadingLocation` | Saved reading positions per user per publication (JSON locator) |
| `Viewport` | Current visible text on screen, one row per user (upsert pattern) |

Migrations are in `alembic/versions/`.

### LLM integration (`app/model_connector.py`)

Uses LiteLLM as an abstraction over multiple providers (OpenAI, Anthropic, Gemini, Azure, Ollama). Model profiles are defined in `config/models.yaml` and selected via the `MODEL_PROFILE` env var.

The `chat_sync()` method handles a tool-calling loop: the model can invoke MCP tools (search, download files, read state) up to 15 times per request to gather book content before generating an answer.

### MCP server (`app/mcp/`)

FastMCP server providing tools and resources for LLM tool-use and external AI clients:

| Type | Name | Purpose |
|------|------|---------|
| Tool | `search_publication` | Full-text keyword search (delegates to publication_api) |
| Tool | `download_publication_files` | Fetch up to 2 files by manifest href |
| Tool | `reading_state` | Current reading location and viewport text |
| Resource | `resource://reading-state` | Same as the tool, as a resource |
| Resource | `resource://current-publication/position-index` | Book's context/summary YAML |

### Prompts (`prompts/`)

YAML-based prompt templates with Jinja2 rendering. Organized by feature:

- `automatic_answers/` - Versioned prompts (v0, v1, v2) for the auto-explanation endpoint
- `freeform_answers/` - Prompt for user-typed questions
- `passage_finder/` - Prompt for "catch me up" / "find passage" queries

### Readium proxy (`app/readium_routes.py`)

Authenticated reverse proxy at `/read/*`. Forwards requests to the Readium CLI server with proper headers and rewrites manifest self-links to point back through the proxy.

### Publication catalog (`app/publications_catalog.py`)

Loads `publications.yaml` from the `PUBLICATIONS_CATALOG_PATH` env var (defaults to `publications/publications.yaml`, which is a symlink to `../static`).

## Directory structure

```
reader_api/
├── app/
│   ├── main.py                   # FastAPI app setup, router mounting
│   ├── api_routes.py             # REST API endpoint handlers
│   ├── api_models.py             # Pydantic request/response schemas
│   ├── config.py                 # Environment variable loading
│   ├── model_connector.py        # LiteLLM wrapper with tool-calling loop
│   ├── prompt_manager.py         # Jinja2-based YAML prompt loading
│   ├── publications_catalog.py   # Publication metadata resolution
│   ├── publication_reader.py     # HTTP client for publication_api (/search, /content/fetch)
│   ├── readium_routes.py         # Authenticated reverse proxy to Readium server
│   ├── reading_state.py          # Reading state payload builder
│   ├── request_context.py        # Request-scoped auth + tracing metadata
│   ├── tracing.py                # OpenTelemetry initialization
│   ├── db/
│   │   ├── db.py                 # Async SQLAlchemy engine + session factory
│   │   └── models.py             # SQLModel table definitions
│   ├── data/
│   │   ├── users.py              # User creation/lookup (Auth0 integration)
│   │   ├── reading_locations.py  # Reading position persistence
│   │   └── viewports.py          # Viewport snapshot management
│   └── mcp/
│       ├── mcp_server.py         # MCP tools, resources, and prompts
│       └── wrapper.py            # MCP tool/prompt enums and auth context manager
├── config/
│   └── models.yaml               # LLM model profiles
├── prompts/                      # YAML prompt templates by feature
│   ├── automatic_answers/
│   ├── freeform_answers/
│   └── passage_finder/
├── alembic/                      # Database migration infrastructure
│   ├── env.py
│   └── versions/                 # Migration files
├── publications -> ../static     # Symlink to publication files
├── ENV_EXAMPLE                   # Environment variable template
├── Makefile                      # Dev commands (sync, dev, run, etc.)
├── pyproject.toml                # Dependencies (uv)
├── alembic.ini                   # Alembic configuration
└── Dockerfile                    # Production container build
```

## Tracing

OpenTelemetry is set up in `app/tracing.py`. When `OTLP_ENDPOINT` is configured, traces for FastAPI requests, httpx calls, and LiteLLM interactions are exported. View them in Jaeger at http://localhost:16686 (service name: `reader-api`).
