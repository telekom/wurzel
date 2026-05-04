# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for wurzel.cli.cmd_middlewares."""

from typer.testing import CliRunner

from wurzel.cli import cmd_middlewares
from wurzel.cli._main import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# middleware_name_autocomplete
# ---------------------------------------------------------------------------


def test_middleware_name_autocomplete_matches_prefix():
    class _DummyRegistry:
        def list_available(self):
            return ["prometheus", "custom"]

    import wurzel.executors.middlewares

    original = wurzel.executors.middlewares.get_registry
    wurzel.executors.middlewares.get_registry = lambda: _DummyRegistry()
    try:
        result = cmd_middlewares.middleware_name_autocomplete("pro")
        assert "prometheus" in result

        result2 = cmd_middlewares.middleware_name_autocomplete("xyz")
        assert len(result2) == 0
    finally:
        wurzel.executors.middlewares.get_registry = original


# ---------------------------------------------------------------------------
# middlewares list
# ---------------------------------------------------------------------------


def test_middlewares_list():
    result = runner.invoke(app, ["middlewares", "list"])
    assert result.exit_code == 0
    assert "Available middlewares" in result.stdout
    assert "prometheus" in result.stdout
    assert "Middleware that adds Prometheus metrics" in result.stdout


def test_middlewares_list_help():
    result = runner.invoke(app, ["middlewares", "list", "--help"])
    assert result.exit_code == 0


def test_middlewares_list_empty(monkeypatch):
    class _EmptyRegistry:
        def list_available(self):
            return []

        def get(self, name):
            return None

    monkeypatch.setattr("wurzel.executors.middlewares.get_registry", lambda: _EmptyRegistry())
    result = runner.invoke(cmd_middlewares.app, ["list"])
    assert result.exit_code == 0
    assert "No middlewares available" in result.output


# ---------------------------------------------------------------------------
# middlewares inspect
# ---------------------------------------------------------------------------


def test_middlewares_inspect_prometheus():
    result = runner.invoke(app, ["middlewares", "inspect", "prometheus"])
    assert result.exit_code == 0
    assert "PROMETHEUS Middleware" in result.stdout
    assert "Module:" in result.stdout
    assert "Class:" in result.stdout
    assert "PrometheusMiddleware" in result.stdout
    assert "Configuration:" in result.stdout
    assert "GATEWAY" in result.stdout
    assert "JOB" in result.stdout
    assert "DISABLE_CREATED_METRIC" in result.stdout
    assert "Usage:" in result.stdout
    assert "wurzel run --middlewares prometheus" in result.stdout


def test_middlewares_inspect_case_insensitive():
    for name in ("prometheus", "PROMETHEUS", "Prometheus"):
        result = runner.invoke(app, ["middlewares", "inspect", name])
        assert result.exit_code == 0
        assert "PrometheusMiddleware" in result.stdout


def test_middlewares_inspect_nonexistent():
    result = runner.invoke(app, ["middlewares", "inspect", "nonexistent"])
    assert result.exit_code == 1
    assert "not found" in result.stdout.lower()
    assert "Available middlewares:" in result.stdout


def test_middlewares_inspect_not_found_via_registry(monkeypatch):
    class _DummyRegistry:
        def list_available(self):
            return ["a"]

        def get(self, name):
            return None

    monkeypatch.setattr("wurzel.executors.middlewares.get_registry", lambda: _DummyRegistry())
    result = runner.invoke(cmd_middlewares.app, ["inspect", "missing"])
    assert result.exit_code == 1
    assert "Error: Middleware 'missing' not found." in result.output


# ---------------------------------------------------------------------------
# middlewares --help
# ---------------------------------------------------------------------------


def test_middlewares_help():
    result = runner.invoke(app, ["middlewares", "--help"])
    assert result.exit_code == 0
    assert "Manage and inspect middlewares" in result.stdout
    assert "list" in result.stdout
    assert "inspect" in result.stdout
