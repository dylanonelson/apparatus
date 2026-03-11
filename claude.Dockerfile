# Use Debian-based Node image instead of Alpine.
# Playwright's bundled Chromium requires glibc, which Alpine (musl) cannot provide.
FROM node:24-bookworm-slim

# Set the working directory inside the container.
WORKDIR /app

# Install basic tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install GitHub CLI (gh) for creating PRs from worktrees
ARG GH_VERSION=2.87.3
RUN curl -fsSL "https://github.com/cli/cli/releases/download/v${GH_VERSION}/gh_${GH_VERSION}_linux_$(dpkg --print-architecture).deb" -o /tmp/gh.deb \
    && dpkg -i /tmp/gh.deb && rm /tmp/gh.deb

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
    
# Switch to non-root user before installing Claude Code
USER node

# Install Claude Code as non-root user
ENV PATH="/home/node/.local/bin:$PATH"
RUN curl -fsSL https://claude.ai/install.sh | bash

# Set the default command to start an interactive session when the container runs.
CMD ["/bin/bash"]
