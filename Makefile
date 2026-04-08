# SPDX-FileCopyrightText: 2024 Deutsche Telekom AG
#
# SPDX-License-Identifier: CC0-1.0
# Requires uv (https://docs.astral.sh/uv/). First-time: run 'make lock' then 'make install'.
.PHONY: install test clean build lock lint documentation reuse-lint setup-dev start-dev stop-dev test-supabase-db test-web test-web-e2e
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

# pgTAP tests (requires Supabase CLI + local DB with migrations applied)
test-supabase-db:
	supabase test db

# Vitest + Testing Library (apps/web); run from repo root
test-web:
	cd apps/web && npm ci && npm test

# Playwright E2E (requires `supabase start` and apps/web/.env with anon key + URL)
test-web-e2e:
	cd apps/web && npm ci && npx playwright install chromium && npm run test:e2e

start-dev: setup-dev
	@echo "✅ Development environment is running"
	@echo ""
	@echo "Services:"
	@echo "  • Supabase Studio: http://localhost:8000"
	@echo "  • Temporal Web UI: http://localhost:8233"
	@echo ""
	@echo "Starting Temporal development server..."
	@echo "  (This will run in the foreground. Press Ctrl+C to stop)"
	@echo ""
	temporal server start-dev

stop-dev:
	@echo "🛑 Stopping development services..."
	@if [ -d "infra/superbase" ]; then \
		cd infra/superbase && podman compose \
			-f docker-compose.yml \
			-f docker-compose.s3.yml \
			-f docker-compose.healthcheck-override.yml \
			down; \
	fi
	@echo "✅ Supabase services stopped"
	@echo ""
	@echo "Note: If you're running Temporal, stop it with Ctrl+C in its terminal"
