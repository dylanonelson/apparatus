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

| Variable | Default | Purpose |
|----------|---------|---------|
| `PUBLICATION_SERVER_PORT` | `8091` | HTTP server port |
| `PUBLICATIONS_DIR` | `publications` | Base directory for EPUB files and `publications.yaml` catalog |

The `publications` directory is a symlink to `../static`, where the actual EPUB files and catalog live.

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

## API endpoints

### `POST /search`

Full-text keyword search across a publication.

```json
// Request
{
  "publication_id": "david-copperfield_std-ebks-2025",
  "query": "Murdstone",
  "max_results": 20,
  "context_chars": 120
}

// Response
{
  "hits": [
    {
      "href": "text/chapter-001.xhtml",
      "locator": {
        "href": "text/chapter-001.xhtml",
        "type": "application/xhtml+xml",
        "text": { "before": "...Mr ", "highlight": "Murdstone", "after": " was a gloomy..." },
        "locations": {
          "position": 42,
          "other_locations": { "cssSelector": "body > p:nth-child(3)" }
        }
      }
    }
  ],
  "count": 1
}
```

How it works: opens the EPUB with Readium's streamer, iterates through `ContentService` text segments via a goroutine channel, and performs case-insensitive matching with `strings.Index()`. Returns up to `max_results` hits with locators including href, position, CSS selector, and surrounding context.

### `POST /content/fetch`

Returns the raw content of up to 2 EPUB resources by manifest href.

```json
// Request
{
  "publication_id": "david-copperfield_std-ebks-2025",
  "hrefs": ["text/chapter-001.xhtml"]
}

// Response
{
  "files": [
    {
      "href": "text/chapter-001.xhtml",
      "media_type": "application/xhtml+xml",
      "encoding": "utf-8",
      "content": "<html>...</html>"
    }
  ]
}
```

Text resources (xhtml, xml, json) are returned as UTF-8. Binary resources (images, etc.) are base64-encoded.

## Architecture

### Directory structure

```
publication_api/
├── cmd/server/
│   └── main.go                    # Entry point: creates router, starts HTTP server
├── internal/
│   ├── config/config.go           # Environment variable loading (PORT, PUBLICATIONS_DIR)
│   ├── http/
│   │   ├── router.go              # Chi router, endpoint handlers, request/response types
│   │   ├── router_test.go         # Search endpoint tests
│   │   └── router_fetch_test.go   # Content fetch endpoint tests
│   ├── publications/
│   │   ├── store.go               # Catalog loading and publication path resolution
│   │   └── store_test.go
│   ├── readium/
│   │   ├── loader.go              # Opens EPUBs via Readium streamer
│   │   ├── content.go             # Streams text segments from ContentService
│   │   └── content_test.go
│   ├── search/
│   │   ├── searcher.go            # Case-insensitive keyword matching with context
│   │   └── searcher_test.go
│   └── logging/logger.go          # Simple logging wrapper
├── testdata/
│   ├── publications.yaml          # Test catalog
│   └── sample_two_chapters.epub   # Test fixture
├── tools/tools.go                 # Tool version pinning (air)
├── publications -> ../static      # Symlink to publication files
├── .air.toml                      # Air live reload config
├── .go-version                    # Go version (1.25.3)
├── Makefile                       # Build, test, dev commands
├── Dockerfile                     # Multi-stage build (golang:1.25-alpine -> alpine:3.20)
├── go.mod / go.sum
└── AGENTS.md
```

### Key patterns

- **Clean architecture**: code organized by domain (config, http, publications, readium, search) under `internal/`
- **Goroutine streaming**: `IterateTextSegments()` uses channels for lazy content iteration
- **Caching**: `publications.Store` uses `sync.Map` to cache loaded catalogs per base directory
- **Context timeouts**: all I/O operations use 15-second context deadlines

### Integration with reader_api

The Python backend calls this service over HTTP using the `CONTENT_SERVICE_URL` environment variable (defaults to `http://127.0.0.1:8091`). The integration code is in `reader_api/app/publication_reader.py`.
