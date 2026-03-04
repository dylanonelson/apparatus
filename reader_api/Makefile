SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

.PHONY: help sync lock update-deps clean dev run

help:
	@echo "Available targets:"
	@echo ""
	@echo "  sync          Install/sync all dependencies (including dev)."
	@echo "  lock          Re-lock dependencies after editing pyproject.toml."
	@echo "  update-deps   Upgrade all dependencies and re-lock."
	@echo "  clean         Remove the virtual environment."
	@echo "  dev           Start uvicorn with --reload."
	@echo "  run           Start uvicorn."

sync:
	uv sync

lock:
	uv lock

update-deps:
	uv lock --upgrade
	uv sync

clean:
	rm -rf .venv

dev:
	uv run uvicorn app.main:app --port 8000 --reload

run:
	uv run uvicorn app.main:app --port 8000
