# SPDX-FileCopyrightText: 2024 Deutsche Telekom AG
#
# SPDX-License-Identifier: CC0-1.0
.PHONY: install test clean
SRC_DIR = ./wurzel
TEST_DIR= ./tests
VENV = .venv
SYSTEM_PYTHON?= python3.12
SHELL := bash


ifeq ($(OS),Windows_NT)
	PY  ?= $(VENV)/Scripts/python.exe
	PIP ?= $(VENV)/Scripts/pip.exe
	UV  ?= $(VENV)/Scripts/uv.exe
else
	PY  ?= $(VENV)/bin/python
	PIP ?= $(VENV)/bin/pip
	UV  ?= $(VENV)/bin/uv
endif


build: install
	$(PY) -m build .

$(VENV)/touchfile: pyproject.toml $(UV)
	$(UV) --no-progress pip install -r pyproject.toml --all-extras
	$(UV) --no-progress pip install -r DIRECT_REQUIREMENTS.txt
	@$(shell if [ "$(OS)" = "Windows_NT" ]; then echo type nul > $(VENV)\\touchfile; else echo touch $(VENV)/touchfile; fi)
	pre-commit install --hook-type pre-commit --hook-type pre-push
$(PY):
	$(SYSTEM_PYTHON) -m venv $(VENV)

$(UV): $(PY)
	$(PIP) install --upgrade pip
	$(PIP) install uv

install: $(VENV)/touchfile


UNAME_S := $(shell uname)

test: install
	@echo "🧪 Running tests..."
ifeq ($(UNAME_S),Darwin)
ifneq ($(GITHUB_ACTIONS),)
	@echo "Running tests on MacOS in GitHub pipeline"
	@echo "Skipping coverage check"
# https://github.com/actions/runner-images/issues/9918
# Docling coverage is not working when tests are skipped on MacOS
	$(UV) run pytest $(TEST_DIR) --cov-branch --cov-report term --cov-report html:reports --cov=$(SRC_DIR)
else
	$(UV) run pytest $(TEST_DIR) --cov-branch --cov-report term --cov-report html:reports --cov-fail-under=90 --cov=$(SRC_DIR)
endif
else
	$(UV) run pytest $(TEST_DIR) --cov-branch --cov-report term --cov-report html:reports --cov-fail-under=90 --cov=$(SRC_DIR)
endif

lint: install
	@echo "🔍 Running lint checks..."
	$(UV) run pre-commit run --all-files

clean:
	@echo "🧹 Cleaning up..."
	@rm -rf __pycache__ ${SRC_DIR}/*.egg-info **/__pycache__ .pytest_cache
	@rm -rf .coverage reports dist

documentation:
	@echo "📚 Serving documentation..."
	$(UV) run mkdocs serve

.PHONY: reuse-lint
reuse-lint:
	$(UV) run  reuse lint
