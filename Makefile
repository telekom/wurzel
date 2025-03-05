# SPDX-FileCopyrightText: 2024 Deutsche Telekom AG
#
# SPDX-License-Identifier: CC0-1.0   
.PHONY: install test clean
SRC_DIR = ./wurzel
TEST_DIR= ./tests
VENV = .venv
UV=$(VENV)/bin/uv
PY=$(VENV)/bin/python
build: install
	$(PY) -m build .

$(VENV)/touchfile: pyproject.toml $(UV)
	$(UV) --no-progress pip install -r pyproject.toml --all-extras
	@touch $(VENV)/touchfile
$(PY):
	python3.11 -m venv $(VENV)
$(UV): $(PY)
	$(VENV)/bin/pip install uv
install: $(VENV)/touchfile

test: install
	$(PY) -m pytest $(TEST_DIR) --cov-branch --cov-report term --cov-report html:reports --cov-fail-under=90  --cov=$(SRC_DIR)
lint: install
	$(PY) -m pylint $(SRC_DIR)

clean: 
	@rm -rf __pycache__ ${SRC_DIR}/*.egg-info **/__pycache__ .pytest_cache
	@rm -rf .coverage reports dist

documentation:
	sphinx-apidoc  -o ./docs . -f && cd docs && make html && cd .. && firefox ./docs/build/html/index.html

reuse-lint:
	uvx reuse lint

install-for-tests:
    uv --no-progress pip install -r pyproject.toml --all-extras