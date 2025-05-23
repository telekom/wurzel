# SPDX-FileCopyrightText: 2024 Deutsche Telekom AG
#
# SPDX-License-Identifier: CC0-1.0
.PHONY: install test clean
SRC_DIR = ./wurzel
TEST_DIR= ./tests
VENV = .venv
UV?=$(VENV)/bin/uv
PY=$(VENV)/bin/python
PIP?=$(VENV)/bin/pip
build: install
	$(PY) -m build .

$(VENV)/touchfile: pyproject.toml $(UV)
	$(UV) --no-progress pip install -r pyproject.toml --all-extras
	$(UV) --no-progress pip install -r DIRECT_REQUIREMENTS.txt
	@touch $(VENV)/touchfile
$(PY):
	python3 -m venv $(VENV)
$(UV): $(PY)
	$(PIP) install uv
install: $(VENV)/touchfile

test: install
	$(UV) run pytest $(TEST_DIR) --cov-branch --cov-report term --cov-report html:reports --cov-fail-under=90  --cov=$(SRC_DIR)

lint: install
	$(UV) run pre-commit run --all-files

clean:
	@rm -rf __pycache__ ${SRC_DIR}/*.egg-info **/__pycache__ .pytest_cache
	@rm -rf .coverage reports dist

documentation:
	$(UV) run mkdocs serve

.PHONY: reuse-lint
reuse-lint:
	$(UV) run  reuse lint
