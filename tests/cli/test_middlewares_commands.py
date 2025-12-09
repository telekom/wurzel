# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for middlewares CLI commands."""

from typer.testing import CliRunner

from wurzel.cli._main import app

runner = CliRunner()


def test_middlewares_list():
    """Test 'wurzel middlewares list' command."""
    result = runner.invoke(app, ["middlewares", "list"])

    assert result.exit_code == 0
    assert "Available middlewares" in result.stdout
    assert "prometheus" in result.stdout
    assert "Middleware that adds Prometheus metrics" in result.stdout


def test_middlewares_inspect_prometheus():
    """Test 'wurzel middlewares inspect prometheus' command."""
    result = runner.invoke(app, ["middlewares", "inspect", "prometheus"])

    assert result.exit_code == 0
    assert "PROMETHEUS Middleware" in result.stdout
    assert "Module:" in result.stdout
    assert "Class:" in result.stdout
    assert "PrometheusMiddleware" in result.stdout
    assert "Configuration:" in result.stdout
    assert "PROMETHEUS_GATEWAY" in result.stdout
    assert "PROMETHEUS_JOB" in result.stdout
    assert "PROMETHEUS_DISABLE_CREATED_METRIC" in result.stdout
    assert "Usage:" in result.stdout
    assert "wurzel run --middlewares prometheus" in result.stdout


def test_middlewares_inspect_nonexistent():
    """Test 'wurzel middlewares inspect' with nonexistent middleware."""
    result = runner.invoke(app, ["middlewares", "inspect", "nonexistent"])

    assert result.exit_code == 1
    assert "not found" in result.stdout.lower()
    assert "Available middlewares:" in result.stdout


def test_middlewares_inspect_case_insensitive():
    """Test that middleware names are case-insensitive."""
    result1 = runner.invoke(app, ["middlewares", "inspect", "prometheus"])
    result2 = runner.invoke(app, ["middlewares", "inspect", "PROMETHEUS"])
    result3 = runner.invoke(app, ["middlewares", "inspect", "Prometheus"])

    assert result1.exit_code == 0
    assert result2.exit_code == 0
    assert result3.exit_code == 0
    # All should show the same middleware
    assert "PrometheusMiddleware" in result1.stdout
    assert "PrometheusMiddleware" in result2.stdout
    assert "PrometheusMiddleware" in result3.stdout


def test_middlewares_help():
    """Test 'wurzel middlewares --help' command."""
    result = runner.invoke(app, ["middlewares", "--help"])

    assert result.exit_code == 0
    assert "Manage and inspect middlewares" in result.stdout
    assert "list" in result.stdout
    assert "inspect" in result.stdout


def test_middlewares_list_help():
    """Test 'wurzel middlewares list --help' command."""
    result = runner.invoke(app, ["middlewares", "list", "--help"])

    assert result.exit_code == 0
    assert "List all available middlewares" in result.stdout


def test_middlewares_inspect_help():
    """Test 'wurzel middlewares inspect --help' command."""
    result = runner.invoke(app, ["middlewares", "inspect", "--help"])

    assert result.exit_code == 0
    assert "Display detailed information about a middleware" in result.stdout
    assert "NAME" in result.stdout


def test_middlewares_no_args():
    """Test 'wurzel middlewares' without arguments shows help."""
    result = runner.invoke(app, ["middlewares"])

    assert result.exit_code == 0
    assert "Manage and inspect middlewares" in result.stdout
    assert "list" in result.stdout
    assert "inspect" in result.stdout


def test_middlewares_list_output_format():
    """Test that list output is properly formatted."""
    result = runner.invoke(app, ["middlewares", "list"])

    assert result.exit_code == 0
    # Check for proper formatting
    lines = result.stdout.split("\n")
    # Should have header and at least one middleware
    assert len(lines) >= 3
    # Should have instruction line
    assert any("wurzel middlewares inspect" in line for line in lines)


def test_middlewares_inspect_shows_all_sections():
    """Test that inspect shows all expected sections."""
    result = runner.invoke(app, ["middlewares", "inspect", "prometheus"])

    assert result.exit_code == 0
    # Check all major sections are present
    sections = ["Module:", "Class:", "Description:", "Configuration:", "Usage:"]
    for section in sections:
        assert section in result.stdout, f"Missing section: {section}"

    # Check usage examples include all three methods
    assert "Via CLI:" in result.stdout
    assert "Via environment:" in result.stdout
    assert "Via Python:" in result.stdout


def test_main_help_includes_middlewares():
    """Test that main help includes middlewares command."""
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "middlewares" in result.stdout
    assert "Manage and inspect middlewares" in result.stdout
