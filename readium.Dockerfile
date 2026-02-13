# Build context: repo root (set RAILWAY_DOCKERFILE_PATH=readium.Dockerfile)
FROM golang:1.25-alpine AS builder

WORKDIR /build

# Clone the readium CLI repo and build the binary.
RUN apk add --no-cache git && \
    git clone --depth 1 --branch v0.6.3 https://github.com/readium/cli.git . && \
    go mod download && \
    go build -o readium ./cmd

# Runtime image
FROM alpine:3.20

WORKDIR /app

# Copy the readium binary from the builder stage.
COPY --from=builder /build/readium /usr/local/bin/readium

# Copy the publications catalog and EPUB files from the shared static directory.
COPY static/ /data/publications/

EXPOSE 15080

CMD ["readium", "serve", "--file-directory", "/data/publications", "--address", "0.0.0.0", "--port", "15080"]
