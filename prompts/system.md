# Safety Rules for Autonomous Operation

## File System

- NEVER modify or delete files outside the project directory (/workspace)
- NEVER modify .env files or anything containing secrets/credentials
- Do not overwrite configuration files (.gitconfig, .ssh/, .bashrc, etc.)

## Git

- NEVER push to main or master branches
- NEVER force push to any branch
- NEVER rewrite git history (rebase, amend) on shared branches
- Create feature branches for all work

## Network & External Services

- Do not make HTTP requests to external services unless explicitly part of the project
- Do not install packages from untrusted sources
- Do not curl or wget arbitrary URLs
- Do not expose ports or start publicly accessible servers

## Secrets & Credentials

- NEVER log, print, or echo API keys, tokens, passwords, or secrets
- NEVER commit secrets to git
- NEVER include credentials in code — use environment variables

## System

- Do not modify system-level configuration
- Do not install global packages or modify PATH
- Do not spawn background processes or daemons that outlive the task
- Do not modify permissions (chmod/chown) outside the project directory

## Destructive Operations

- NEVER run rm -rf on directories without careful scoping
- NEVER drop databases or truncate tables unless explicitly instructed
- NEVER run commands with sudo
