## Repo setup

Requires Python 3.13.x.

```bash
# Ensure you're using Python 3.13.x
python --version  # should print Python 3.13.x

# Create a virtual environment with Python 3.13
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
# For pip-sync and pip-compile
pip install pip-tools
```

## Dependencies

Depdencies are tracked in _.in files and their versions are pinned in the corresponding _.txt file.

### Adding a new dependency

Edit requirements.in or dev.in; you can include version ranges.

```txt
# requirements.in
fastapi>=0.10,<0.13 or fastapi==8.*
```

```bash
pip-compile --generate-hashes requirements.in
pip-sync requirements.txt dev.txt
```

### Upgrade existing dependencies

```bash
# Upgrade one dependency
pip-compile --upgrade-package fastapi requirements.in

# Or:
pip-compile --upgrade-package fastapi==0.115.4

# Upgrade all dependencies
pip-compile --upgrade requirements.in

# Then install
pip-sync requirements.txt dev.txt
```

## Configuration

### Environment Variables

Copy the ENV_TEMPLATE file to create your .env file:

```bash
cp ENV_EXAMPLE .env
```

Then edit .env and add your API keys. At minimum, you'll need one of:

- `OPENAI_API_KEY` for OpenAI models (GPT-4, etc.)
- `ANTHROPIC_API_KEY` for Anthropic models (Claude)
- Or run Ollama locally for free local models (no API key needed)

See ENV_EXAMPLE for all available configuration options.

### Model Configuration

Model settings are defined in `config/models.yaml` as named profiles. Select a profile via the `MODEL_PROFILE` environment variable:

```bash
# Use the default profile (configured in models.yaml)
MODEL_PROFILE=default

# Or specify a profile directly
MODEL_PROFILE=google_gemini-3-pro-preview
MODEL_PROFILE=openai_gpt-5
```

To add or modify profiles, edit `config/models.yaml`.

## Database

### Start PostgreSQL Locally

The API expects a PostgreSQL instance reachable via the async SQLAlchemy driver. The quickest way to start one locally is with Docker:

```bash
docker run --rm --name apparatus-db \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=apparatus \
  -p 5432:5432 \
  postgres:18
```

Update `.env` (or export directly) with the connection string:

```bash
DATABASE_URL=postgresql+asyncpg://username:password@localhost:5432/apparatus
DB_ECHO=false  # set true to log SQL while developing
```

### Run Database Migrations

To create a new migration after changing SQLModel metadata:

```bash
alembic revision -m "meaningful message" --autogenerate
```

Apply schema migrations from the `reader_api/` directory:

```bash
alembic upgrade head
```

## Running the app

```bash
# Make sure you're in the backend directory and venv is activated
cd backend
source .venv/bin/activate

# Run with uvicorn
uvicorn app.main:app --reload
```

The API will be available at http://localhost:8000

- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

## Tracing verification

1. Start Jaeger locally (example command uses the all-in-one image):

   ```bash
   docker run --rm --name jaeger \
     -p 16686:16686 \
     -p 4317:4317 \
     -p 4318:4318 \
     -p 5778:5778 \
     -p 9411:9411 \
     cr.jaegertracing.io/jaegertracing/jaeger:2.11.0
   ```

2. Run the API (ensure `CONTENT_SERVICE_URL` is reachable), then hit the /ask endpoint with a sample request.

3. Open the Jaeger UI at http://localhost:16686 and search for service `reader-api`.
   You should see spans for FastAPI requests, outbound `httpx` calls, and LiteLLM interactions.
