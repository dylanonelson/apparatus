# Apparatus development

## In this repo

### Next.js web client (`frontend`)

**TypeScript, Next.js 15 (App Router), React 19, Redux Toolkit, Readium Web**

The frontend is a fork of [Thorium Web](https://github.com/edrlab/thorium-web) that serves as the e-reader UI. It provides EPUB rendering via the Readium Web toolkit, configurable display settings (themes, fonts, spacing), persistent reading positions, and AI-powered contextual answers about the text the user is reading.

The Next.js backend acts as a backend-for-frontend (BFF): it holds the Auth0 session cookie and converts it to a Bearer token before proxying requests to reader_api. The frontend does not communicate with publication_api directly. Publication content (manifests, XHTML chapters, images) is fetched through the BFF proxy at `/api/pub/`, which forwards to reader_api's `/read/` routes.

Node version is managed by nvm. Package manager is pnpm.

See [`frontend/README.md`](../frontend/README.md) for setup and development instructions.

### FastAPI + FastMCP Reader API (`reader_api`)

**Python 3.13, FastAPI, SQLModel (PostgreSQL), LiteLLM, FastMCP**

The reader API is the sole public-facing backend. It exposes three route groups:

- **`/api`** — REST endpoints for user data, reading state (positions and viewport snapshots), and LLM-powered Q&A (`/ask-freeform`, `/ask-automatic`).
- **`/read`** — Auth-protected reverse proxy to the Readium server, which streams EPUB content to the frontend.
- **`/mcp`** — A [Model Context Protocol](https://modelcontextprotocol.io/) server that exposes reading state, publication search, and file download as MCP tools and resources. These are used both by the LLM during Q&A tool-use loops and by external AI clients.

Auth is handled via Auth0 JWT validation. LLM integration uses LiteLLM for multi-provider support (OpenAI, Anthropic, Gemini, etc.) with model profiles defined in `config/models.yaml`. The LLM calls MCP tools in a loop to retrieve book content before generating answers. Database is PostgreSQL via SQLModel with Alembic migrations.

reader_api calls publication_api over HTTP for two operations: keyword search (`POST /search`) and content fetch (`POST /content/fetch`).

Python version is managed by uv.

See [`reader_api/README.md`](../reader_api/README.md) for setup, configuration, and development instructions.

### Go Publication API (`publication_api`)

**Go 1.25, Chi, Readium Go Toolkit**

An internal HTTP service that handles EPUB processing using the [Readium Go Toolkit](https://github.com/readium/go-toolkit) — the only Readium implementation that provides server-side content access. It is called exclusively by reader_api and is not exposed to the frontend or external clients.

It provides two main endpoints:

- **`POST /search`** — Full-text keyword search across a publication's content, returning hits with locators and surrounding context snippets.
- **`POST /content/fetch`** — Returns the raw content of up to two EPUB resources by manifest href (text as UTF-8, binary as base64).

Publications are resolved from a YAML catalog (`publications.yaml`) and the EPUB files in the same directory.

Go version is managed by goenv.

See [`publication_api/README.md`](../publication_api/README.md) for setup and development instructions.

### Promptfoo eval suite (`evals`)

**Node.js, [promptfoo](https://www.promptfoo.dev/)**

Automated evaluations for the reader_api LLM endpoints. The suite validates answer quality and edge-case behavior by running test cases against `/ask-automatic` (and `/ask`) with different prompt versions.

Current test features:

- **No-answer detection** — Verifies that the model correctly returns `IMPLIED_QUESTION_IS_UNCLEAR` when given meaningless selections (sentence fragments, random words).
- **Missing-context quality** — LLM-graded rubrics that check tone (scholarly, objective, non-editorializing) and factuality against reference answers for passages that require book knowledge.
- **Passage finder** — Tests the freeform `/ask` endpoint for "catch me up" and "find passage" queries.

Evals authenticate against reader_api using an Auth0 token and are run via `run-eval.sh`.

### Bruno collections (`bruno`)

**[Bruno](https://www.usebruno.com/)**

A Bruno API collection for manual/exploratory testing of reader_api and publication_api endpoints. Includes saved requests for user lookup, reading positions, LLM ask queries (with example locators for specific books), and publication search. Environment files configure local dev URLs (`localhost:8000` for reader_api, `localhost:8091` for publication_api).

### Static publication files (`static`)

EPUB files and their associated metadata, used by both publication_api (for content processing) and reader_api (for the publication catalog). Contains:

- **`publications.yaml`** — The publication catalog listing each book's ID, title, author, URL slug, EPUB filename, and optional context filename.
- **EPUB files** — Packaged `.epub` files and their unpacked directory equivalents.
- **Context files** — Per-publication YAML files with supplementary context for LLM answers (e.g. historical background, character lists).

In local development the `PUBLICATIONS_DIR` environment variable points here. In Docker, these files are copied to `/data/publications`.

## Local development

This project uses `tmuxp` to manage multiple services for local development. tmux allows you to run multiple terminals in a single screen, and tmuxp provides a configuration layer for tmux that facilitates running multiple commands in a pre-defined layout.

To run the app:

1. Make sure you have [tmux](https://github.com/tmux/tmux) and [tmuxp](https://github.com/tmux-python/tmuxp) installed

1. Navigate to the project root directory (where `tmuxp.yaml` is located) and run `tmuxp load tmuxp.yaml`

This command will create or attach to a tmux session named `aie` with all services running in their respective windows and panes.

## Deployment

The web client, the reader API, and the publication API are deployed on Railway alongside a Postgres DB; they communicate via Railway's private networking.

An update to any individual service on the `main` branch triggers a push on Railway for just that branch. Environment variables are managed manually on Railway.

Authentication is through Auth0. Production and development currently share the same Auth0 tenant.
