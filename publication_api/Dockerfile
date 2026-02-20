# Build context: repo root (set RAILWAY_DOCKERFILE_PATH=publication_api/Dockerfile)
FROM golang:1.25-alpine AS builder

WORKDIR /build

# Download dependencies first for better layer caching.
COPY publication_api/go.mod publication_api/go.sum ./
RUN go mod download

# Copy source code and build the binary.
COPY publication_api/ ./
RUN go build -o publication-server ./cmd/server

# Runtime image
FROM alpine:3.20

WORKDIR /app

# Copy the binary from the builder stage.
COPY --from=builder /build/publication-server .

# Copy the publications catalog and EPUB files from the shared static directory.
COPY static/ /data/publications/

# Port is configurable via PUBLICATION_SERVER_PORT (default: 8091).
ENV PUBLICATION_SERVER_PORT=8091
ENV PUBLICATIONS_DIR=/data/publications

# EXPOSE documents the default port; override with -e PUBLICATION_SERVER_PORT at runtime.
EXPOSE 8091

CMD ["./publication-server"]
