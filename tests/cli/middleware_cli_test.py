# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for CLI middleware integration."""

from pathlib import Path

from wurzel.cli import _main as main
from wurzel.executors import BaseStepExecutor
from wurzel.steps.manual_markdown import ManualMarkdownStep


def test_cli_run_without_middlewares(tmp_path: Path, env):
    """Test CLI run without any middlewares."""
    out = tmp_path / "out"
    inp = tmp_path / "in"
    inp.mkdir()
    (inp / "file.md").write_text("#Test\n content")
    env.set("MANUALMARKDOWNSTEP__FOLDER_PATH", str(inp.absolute()))

    main.run(
        step=ManualMarkdownStep,
        executor=BaseStepExecutor,
        input_folders=[],
        output_path=out,
        middlewares="",
        encapsulate_env=True,
    )

    assert out.exists()
    assert (out / "ManualMarkdown.json").exists()


def test_cli_run_with_prometheus_middleware(tmp_path: Path, env):
    """Test CLI run with prometheus middleware explicitly set."""
    out = tmp_path / "out"
    inp = tmp_path / "in"
    inp.mkdir()
    (inp / "file.md").write_text("#Test\n content")
    env.set("MANUALMARKDOWNSTEP__FOLDER_PATH", str(inp.absolute()))

    main.run(
        step=ManualMarkdownStep,
        executor=BaseStepExecutor,
        input_folders=[],
        output_path=out,
        middlewares="prometheus",
        encapsulate_env=True,
    )

    assert out.exists()
    assert (out / "ManualMarkdown.json").exists()


def test_cli_run_with_middleware_from_env(tmp_path: Path, env):
    """Test CLI run loads middleware from environment variable."""
    out = tmp_path / "out"
    inp = tmp_path / "in"
    inp.mkdir()
    (inp / "file.md").write_text("#Test\n content")
    env.set("MANUALMARKDOWNSTEP__FOLDER_PATH", str(inp.absolute()))
    env.set("MIDDLEWARES", "prometheus")

    # Don't pass middlewares parameter, should load from env
    main.run(
        step=ManualMarkdownStep,
        executor=BaseStepExecutor,
        input_folders=[],
        output_path=out,
        encapsulate_env=True,
    )

    assert out.exists()
    assert (out / "ManualMarkdown.json").exists()


def test_cli_run_middleware_overrides_env(tmp_path: Path, env):
    """Test that explicit middleware parameter overrides environment variable."""
    out = tmp_path / "out"
    inp = tmp_path / "in"
    inp.mkdir()
    (inp / "file.md").write_text("#Test\n content")
    env.set("MANUALMARKDOWNSTEP__FOLDER_PATH", str(inp.absolute()))
    env.set("MIDDLEWARES", "prometheus")

    # Pass empty middlewares to override env
    main.run(
        step=ManualMarkdownStep,
        executor=BaseStepExecutor,
        input_folders=[],
        output_path=out,
        middlewares="",  # This should override the env var
        encapsulate_env=True,
    )

    assert out.exists()
    assert (out / "ManualMarkdown.json").exists()


def test_cli_run_with_whitespace_in_middlewares(tmp_path: Path, env):
    """Test that whitespace in middleware list is handled correctly."""
    out = tmp_path / "out"
    inp = tmp_path / "in"
    inp.mkdir()
    (inp / "file.md").write_text("#Test\n content")
    env.set("MANUALMARKDOWNSTEP__FOLDER_PATH", str(inp.absolute()))

    # Test with extra whitespace
    main.run(
        step=ManualMarkdownStep,
        executor=BaseStepExecutor,
        input_folders=[],
        output_path=out,
        middlewares=" prometheus ",  # With whitespace
        encapsulate_env=True,
    )

    assert out.exists()
    assert (out / "ManualMarkdown.json").exists()


def test_cli_run_with_invalid_middleware(tmp_path: Path, env):
    """Test that invalid middleware name is handled gracefully (logs warning)."""
    out = tmp_path / "out"
    inp = tmp_path / "in"
    inp.mkdir()
    (inp / "file.md").write_text("#Test\n content")
    env.set("MANUALMARKDOWNSTEP__FOLDER_PATH", str(inp.absolute()))

    # Invalid middleware should log a warning but not fail the execution
    main.run(
        step=ManualMarkdownStep,
        executor=BaseStepExecutor,
        input_folders=[],
        output_path=out,
        middlewares="nonexistent",  # This will be skipped with a warning
        encapsulate_env=True,
    )

    # Execution should still succeed
    assert out.exists()
    assert (out / "ManualMarkdown.json").exists()


def test_cli_run_default_behavior_no_middleware_param(tmp_path: Path, env):
    """Test that without middleware parameter and no env var, it works normally."""
    out = tmp_path / "out"
    inp = tmp_path / "in"
    inp.mkdir()
    (inp / "file.md").write_text("#Test\n content")
    env.set("MANUALMARKDOWNSTEP__FOLDER_PATH", str(inp.absolute()))

    # No middlewares parameter and no env var
    main.run(
        step=ManualMarkdownStep,
        executor=BaseStepExecutor,
        input_folders=[],
        output_path=out,
        encapsulate_env=True,
    )

    assert out.exists()
    assert (out / "ManualMarkdown.json").exists()


def test_cli_run_with_prometheus_settings(tmp_path: Path, env):
    """Test CLI run with prometheus middleware and settings."""
    out = tmp_path / "out"
    inp = tmp_path / "in"
    inp.mkdir()
    (inp / "file.md").write_text("#Test\n content")
    env.set("MANUALMARKDOWNSTEP__FOLDER_PATH", str(inp.absolute()))
    env.set("PROMETHEUS_GATEWAY", "http://localhost:9091")
    env.set("PROMETHEUS_JOB", "test-job")

    # Run with prometheus and custom settings
    main.run(
        step=ManualMarkdownStep,
        executor=BaseStepExecutor,
        input_folders=[],
        output_path=out,
        middlewares="prometheus",
        encapsulate_env=True,
    )

    assert out.exists()
    assert (out / "ManualMarkdown.json").exists()
