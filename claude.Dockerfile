# Apparatus development container
# Includes: Claude Code, Playwright/Chromium, Go, Python/uv, Node/pnpm,
#            Readium CLI, and GitHub CLI.
#
# Use Debian-based Node image instead of Alpine.
# Playwright's bundled Chromium requires glibc, which Alpine (musl) cannot provide.
FROM node:22-bookworm-slim

WORKDIR /app

# ── System dependencies (root) ──────────────────────────────────────
# PostgreSQL runs on the host; the container connects via host.docker.internal.
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash git curl ca-certificates wget \
    build-essential make pkg-config \
    # PostgreSQL client (for pg_isready / psql, not the server)
    postgresql-client libpq-dev \
    procps \
    && rm -rf /var/lib/apt/lists/*

# ── Go 1.25 (for publication_api + Readium CLI) ─────────────────────
ARG GO_VERSION=1.25.3
RUN ARCH="$(dpkg --print-architecture)" \
    && curl -fsSL "https://go.dev/dl/go${GO_VERSION}.linux-${ARCH}.tar.gz" \
       | tar -C /usr/local -xz
ENV PATH="/usr/local/go/bin:${PATH}"

# ── pnpm (for frontend) ─────────────────────────────────────────────
RUN npm install -g pnpm

# ── GitHub CLI (for creating PRs from worktrees) ────────────────────
ARG GH_VERSION=2.87.3
RUN curl -fsSL "https://github.com/cli/cli/releases/download/v${GH_VERSION}/gh_${GH_VERSION}_linux_$(dpkg --print-architecture).deb" \
       -o /tmp/gh.deb \
    && dpkg -i /tmp/gh.deb && rm /tmp/gh.deb

# ── Playwright CLI + Chromium ────────────────────────────────────────
# Install Playwright CLI globally (provides the playwright-cli command used by Claude Code).
RUN npm install -g @playwright/cli@latest

# Install Chromium's system dependencies using the Playwright bundled with
# @playwright/cli so the dependency versions stay aligned.
RUN /usr/local/lib/node_modules/@playwright/cli/node_modules/.bin/playwright install-deps chromium \
    && rm -rf /var/lib/apt/lists/*

# Install the Chromium browser binary using the SAME Playwright that
# @playwright/cli bundles.  Using `npx playwright` here would resolve a
# different Playwright version, producing a revision mismatch (e.g. the
# CLI expects revision 1212 but npx installs 1208).
RUN /usr/local/lib/node_modules/@playwright/cli/node_modules/.bin/playwright install chromium

# ── Readium CLI (serves EPUB content on port 15080) ─────────────────
RUN git clone --depth 1 --branch v0.6.3 https://github.com/readium/cli.git /tmp/readium-cli \
    && cd /tmp/readium-cli \
    && go build -o /usr/local/bin/readium ./cmd \
    && rm -rf /tmp/readium-cli

# ── Switch to non-root user ─────────────────────────────────────────
# Claude Code refuses to run as root.  The node:22 image ships a `node`
# user (uid 1000) which we use for everything below.
USER node
ENV PATH="/home/node/.local/bin:${PATH}"

# ── Python 3.13 via uv (for reader_api) ─────────────────────────────
# uv downloads prebuilt Python binaries — no build dependencies needed.
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
RUN uv python install 3.13

# ── Claude Code ─────────────────────────────────────────────────────
RUN curl -fsSL https://claude.ai/install.sh | bash

# ── Home directory stash ────────────────────────────────────────────
# When the apparatus-dev-home volume is mounted at /home/node it shadows
# the tools installed above (uv, claude, etc.).  Stash a copy so the
# entrypoint can populate the volume on first run.
USER root
RUN cp -a /home/node /home/node-stash
COPY scripts/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh
USER node

# Expose ports: Frontend(3000), Reader API(8000), Publication API(8091), Readium(15080)
EXPOSE 3000 8000 8091 15080

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["/bin/bash"]
