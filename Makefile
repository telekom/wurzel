# SPDX-FileCopyrightText: 2024 Deutsche Telekom AG
#
# SPDX-License-Identifier: CC0-1.0
# Requires uv (https://docs.astral.sh/uv/). First-time: run 'make lock' then 'make install'.
.PHONY: install test clean build lock lint documentation reuse-lint setup-dev
SRC_DIR = ./wurzel
TEST_DIR = ./tests
VENV = .venv
SHELL := bash

$(VENV)/.venv_created:
	@uv venv $(VENV)
	@touch $(VENV)/.venv_created

install: $(VENV)/.venv_created
	uv sync --all-extras
	uv run pre-commit install

build: install
	uv build

test: install
	@echo "🧪 Running tests..."
	@UNAME_S=$$(uname); \
	if [ "$$UNAME_S" = "Darwin" ] && [ -n "$$GITHUB_ACTIONS" ]; then \
		echo "Running tests on MacOS in GitHub pipeline"; \
		echo "Skipping coverage check"; \
		uv run pytest $(TEST_DIR) --cov-branch --cov-report term --cov-report html:reports --cov=$(SRC_DIR); \
	elif [ "$$UNAME_S" = "Darwin" ]; then \
		uv run pytest $(TEST_DIR) --cov-branch --cov-report term --cov-report html:reports --cov-fail-under=90 --cov=$(SRC_DIR); \
	else \
		uv run pytest $(TEST_DIR) --cov-branch --cov-report term --cov-report html:reports --cov-fail-under=90 --cov=$(SRC_DIR); \
	fi

lint: install
	@echo "🔍 Running lint checks..."
	uv run pre-commit run --all-files

clean:
	@echo "🧹 Cleaning up..."
	@rm -rf __pycache__ ${SRC_DIR}/*.egg-info **/__pycache__ .pytest_cache
	@rm -rf .coverage reports dist $(VENV)

documentation: install
	@echo "📚 Serving documentation..."
	uv run mkdocs serve

reuse-lint:
	uv run reuse lint

setup-dev:
	@bash scripts/setup-dev.sh
