SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

VENV_DIR := .venv
VENV_PYTHON := $(VENV_DIR)/bin/python
PYTHON ?= python
PIP := $(VENV_DIR)/bin/pip
PIP_COMPILE := $(VENV_DIR)/bin/pip-compile
PIP_SYNC := $(VENV_DIR)/bin/pip-sync

.PHONY: help setup sync compile update-deps clean dev install migrate serve start

help:
	@echo "Available targets:"
	@echo ""
	@echo "  Local development (uses .venv):"
	@echo "    setup         Create the virtual environment, install pip-tools, and sync dependencies."
	@echo "    sync          Sync the virtual environment with requirements.txt and dev.txt."
	@echo "    compile       Compile *.in files into pinned *.txt files with hashes."
	@echo "    update-deps   Upgrade all pinned dependencies and re-sync."
	@echo "    clean         Remove the virtual environment."
	@echo "    dev           Sync and start uvicorn with --reload."
	@echo "    run           Sync and start uvicorn."
	@echo ""
	@echo "  Production / Docker (no .venv):"
	@echo "    install       Install production dependencies from requirements.txt."
	@echo "    migrate       Run alembic migrations."
	@echo "    serve         Start uvicorn on PORT (default 8000)."
	@echo "    start         Run migrations then start uvicorn."

setup: $(PIP_COMPILE)
	$(PIP_SYNC) requirements.txt dev.txt

sync: $(PIP_COMPILE)
	$(PIP_SYNC) requirements.txt dev.txt

compile: $(PIP_COMPILE)
	$(PIP_COMPILE) --generate-hashes requirements.in
	$(PIP_COMPILE) --generate-hashes dev.in

update-deps: $(PIP_COMPILE)
	$(PIP_COMPILE) --generate-hashes --upgrade requirements.in
	$(PIP_COMPILE) --generate-hashes --upgrade dev.in
	$(PIP_SYNC) requirements.txt dev.txt

clean:
	rm -rf $(VENV_DIR)

dev: sync
	$(VENV_DIR)/bin/uvicorn app.main:app --port 8000 --reload

run: sync
	$(VENV_DIR)/bin/uvicorn app.main:app --port 8000

# --- Production / Docker targets (no .venv) ---

install:
	pip install --no-cache-dir -r requirements.txt

migrate:
	alembic upgrade head

serve:
	uvicorn app.main:app --host 0.0.0.0 --port $(or $(PORT),8000)

start: migrate serve

$(PIP):
	$(PYTHON) -m venv $(VENV_DIR)
	$(VENV_PYTHON) -m pip install --upgrade "pip<25"

$(PIP_COMPILE): $(PIP)
	$(VENV_PYTHON) -m pip install pip-tools
	@test -x "$(PIP_COMPILE)" && test -x "$(PIP_SYNC)"

