# Publication API

**Go 1.25, Chi, Readium Go Toolkit**

An internal HTTP service that handles EPUB processing using the [Readium Go Toolkit](https://github.com/readium/go-toolkit). It provides keyword search and content fetching for EPUB publications. It is called exclusively by `reader_api` and is not exposed to the frontend or external clients.

Go version is managed by goenv (see `.go-version`).

## Local development

```bash
cd publication_api
make dev    # starts with Air for live reload on port 8091
```

Or start everything at once from the repo root with `tmuxp load tmuxp.yaml`.

- Health check: `GET http://127.0.0.1:8091/health`

### Environment variables

Configuration is read from environment variables (there is currently no `.env` file loaded). Both have defaults that work for local development; the Dockerfile overrides `PUBLICATIONS_DIR` for the container.

| Variable                  | Default       | Purpose                                                       |
| ------------------------- | ------------- | ------------------------------------------------------------- |
| `PUBLICATION_SERVER_PORT` | `8091`        | HTTP server port                                              |
| `PUBLICATIONS_DIR`        | `ebook_files` | Base directory for EPUB files and `publications.yaml` catalog |

The `ebook_files` directory is a symlink to `../ebook_files`, where the actual EPUB files and catalog live.

### Common operations

```bash
make dev          # Development with Air live reload
make build        # Build binary to bin/publication-server
make run          # Run with default env
make test         # Run tests
make race         # Run tests with race detector
make coverage     # Generate coverage report
make fmt          # Format code
make vet          # Run go vet
make lint         # Run fmt + vet
make tidy         # Tidy go.mod
make deps         # Download modules
make clean        # Remove build artifacts

# Add a dependency
go get github.com/example/package
make tidy
```

## Architecture

Code is organized by domain under `internal/`. Test fixtures live in `testdata/`.

**Concurrency**: text segment iteration uses goroutine channels for lazy streaming. The publication catalog is cached per base directory using `sync.Map`.

**Integration**: the Python backend (`reader_api`) calls this service over HTTP using its `CONTENT_SERVICE_URL` environment variable.
