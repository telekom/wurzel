# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0


import pytest
import typer

import wurzel
import wurzel.steps
from wurzel.backend.backend_dvc import DvcBackend
from wurzel.cli import _main as main
from wurzel.step_executor import BaseStepExecutor, PrometheusStepExecutor
from wurzel.steps.manual_markdown import ManualMarkdownStep
from wurzel.utils import HAS_HERA


@pytest.mark.parametrize(
    "inpt_str, expected",
    [
        ("base", BaseStepExecutor),
        ("BASE", BaseStepExecutor),
        ("BaseStepExecutor", BaseStepExecutor),
        ("Prom", PrometheusStepExecutor),
        ("PROMETHEUS", PrometheusStepExecutor),
    ],
)
def test_executer_callback(inpt_str, expected):
    assert main.executer_callback(None, None, inpt_str) == expected


def test_executer_callback_bad():
    with pytest.raises(typer.BadParameter):
        main.executer_callback(None, None, "XX")


@pytest.mark.parametrize(
    "step_path",
    [
        "wurzel.steps.ManualMarkdownStep",
        "wurzel.steps:ManualMarkdownStep",
        "wurzel.steps.manual_markdown:ManualMarkdownStep",
        "wurzel.steps.manual_markdown.ManualMarkdownStep",
    ],
)
def test_step_callback(step_path):
    assert main.step_callback(None, None, step_path) == wurzel.steps.ManualMarkdownStep


@pytest.mark.parametrize(
    "step_path",
    [
        "wurzel.steps.NotExist",
        "Nope",
        "wurzel.cli._main:main",
        "doesnt_exist.steps.manual_markdown.ManualMarkdownStep",
    ],
)
def test_step_callback_bad(step_path):
    with pytest.raises(typer.BadParameter):
        main.step_callback(None, None, step_path)


def test_autocomplete_step_import():
    completion = main.complete_step_import("")
    assert completion
    assert "wurzel.steps.manual_markdown.ManualMarkdownStep" in completion


def test_run(tmp_path, env):
    out = tmp_path / "out"
    inp = tmp_path / "in"  #
    inp.mkdir()
    (inp / "file.md").write_text("#Hello\n world")
    env.set("MANUALMARKDOWNSTEP__FOLDER_PATH", str(inp.absolute()))
    main.run(
        step=ManualMarkdownStep,
        executor=BaseStepExecutor,
        input_folders=[],
        output_path=out,
    )
    # Generator steps produce numbered batch files.
    batch_files = list(out.glob("*_batch*.json"))
    assert batch_files
    assert batch_files[0].read_text()


@pytest.mark.parametrize("gen_env", [True, False])
def test_inspekt(gen_env):
    main.inspekt(ManualMarkdownStep, gen_env)


@pytest.mark.parametrize(
    "backend_str",
    [
        "DvcBackend",
        "dvcbackend",
        "DVCBACKEND",
        "DvCbAcKeNd",
    ],
)
def test_backend_callback_dvc(backend_str):
    """Test backend_callback with DvcBackend (case-insensitive)."""
    result = main.backend_callback(None, None, backend_str)
    assert result == DvcBackend


@pytest.mark.skipif(not HAS_HERA, reason="Hera is not available")
@pytest.mark.parametrize(
    "backend_str",
    [
        "ArgoBackend",
        "argobackend",
        "ARGOBACKEND",
        "ArGoBaCkEnD",
    ],
)
def test_backend_callback_argo(backend_str):
    """Test backend_callback with ArgoBackend when Hera is available (case-insensitive)."""
    from wurzel.backend.backend_argo import ArgoBackend

    result = main.backend_callback(None, None, backend_str)
    assert result == ArgoBackend


def test_backend_callback_invalid():
    """Test backend_callback with invalid backend name (case _:)."""
    with pytest.raises(typer.BadParameter) as exc_info:
        main.backend_callback(None, None, "InvalidBackend")

    # Check that error message contains expected backends
    error_msg = str(exc_info.value)
    assert "InvalidBackend not supported" in error_msg
    assert "DvcBackend" in error_msg
    # ArgoBackend should only be in the message if Hera is available
    if HAS_HERA:
        assert "ArgoBackend" in error_msg


def test_get_available_backends_without_hera():
    """Test get_available_backends returns DvcBackend when Hera is not available."""
    backends = main.get_available_backends()
    assert isinstance(backends, list)
    assert "DvcBackend" in backends
    # ArgoBackend should only be present if HAS_HERA is True
    if HAS_HERA:
        assert "ArgoBackend" in backends
    else:
        assert "ArgoBackend" not in backends


@pytest.mark.skipif(not HAS_HERA, reason="Hera is not available")
def test_get_available_backends_with_hera():
    """Test get_available_backends returns both backends when Hera is available."""
    backends = main.get_available_backends()
    assert isinstance(backends, list)
    assert "DvcBackend" in backends
    assert "ArgoBackend" in backends


def test_generate_list_backends(capsys):
    """Test generate command with --list-backends flag."""
    main.generate(pipeline=None, backend="DvcBackend", list_backends=True)

    captured = capsys.readouterr()
    assert "Available backends:" in captured.out
    assert "DvcBackend" in captured.out

    if HAS_HERA:
        assert "ArgoBackend" in captured.out
    else:
        assert "ArgoBackend" not in captured.out


def test_env_outputs_requirements(capsys, monkeypatch):
    monkeypatch.setattr(main, "console", main.console.__class__(force_terminal=False, width=200))
    main.env_cmd("wurzel.steps.manual_markdown:ManualMarkdownStep")
    captured = capsys.readouterr()
    assert "Environment variables" in captured.out
    assert "MANUALMARKDOWNSTEP__FOLDER_PATH" in captured.out


def test_env_only_required_filters_optional(capsys, monkeypatch):
    monkeypatch.setattr(main, "console", main.console.__class__(force_terminal=False, width=200))
    main.env_cmd("examples.pipeline.pipelinedemo:pipeline", include_optional=False)
    captured = capsys.readouterr()
    assert "MANUALMARKDOWNSTEP__FOLDER_PATH" in captured.out
    assert "SIMPLESPLITTERSTEP__BATCH_SIZE" not in captured.out


def test_env_gen_env_outputs_env_file(capsys, monkeypatch, env):
    monkeypatch.setattr(main, "console", main.console.__class__(force_terminal=False, width=200))
    env.set("MANUALMARKDOWNSTEP__FOLDER_PATH", "/tmp/custom")
    env.set("SIMPLESPLITTERSTEP__BATCH_SIZE", "256")

    main.env_cmd("examples.pipeline.pipelinedemo:pipeline", gen_env=True)
    captured = capsys.readouterr()
    expected = (
        "# Generated env vars\n\n"
        "# ManualMarkdownStep\n"
        "MANUALMARKDOWNSTEP__FOLDER_PATH=/tmp/custom\n\n"  # pragma: allowlist secret
        "# SimpleSplitterStep\n"
        "SIMPLESPLITTERSTEP__BATCH_SIZE=256\n"
        "SIMPLESPLITTERSTEP__NUM_THREADS=4\n"
        "SIMPLESPLITTERSTEP__TOKEN_COUNT_MIN=64\n"
        "SIMPLESPLITTERSTEP__TOKEN_COUNT_MAX=1024\n"
        "SIMPLESPLITTERSTEP__TOKEN_COUNT_BUFFER=32\n"
        "SIMPLESPLITTERSTEP__TOKENIZER_MODEL=gpt-3.5-turbo\n"
        "SIMPLESPLITTERSTEP__SENTENCE_SPLITTER_MODEL=de_core_news_sm\n\n\n"
    )
    assert captured.out == expected


def test_env_gen_env_outputs_env_file_empty(capsys, monkeypatch):
    monkeypatch.setattr(main, "console", main.console.__class__(force_terminal=False, width=200))
    main.env_cmd("examples.pipeline.pipelinedemo:pipeline", gen_env=True)
    captured = capsys.readouterr()
    expected = (
        "# Generated env vars\n\n"
        "# ManualMarkdownStep\n"
        "MANUALMARKDOWNSTEP__FOLDER_PATH=\n\n"
        "# SimpleSplitterStep\n"
        "SIMPLESPLITTERSTEP__BATCH_SIZE=100\n"
        "SIMPLESPLITTERSTEP__NUM_THREADS=4\n"
        "SIMPLESPLITTERSTEP__TOKEN_COUNT_MIN=64\n"
        "SIMPLESPLITTERSTEP__TOKEN_COUNT_MAX=1024\n"
        "SIMPLESPLITTERSTEP__TOKEN_COUNT_BUFFER=32\n"
        "SIMPLESPLITTERSTEP__TOKENIZER_MODEL=gpt-3.5-turbo\n"
        "SIMPLESPLITTERSTEP__SENTENCE_SPLITTER_MODEL=de_core_news_sm\n\n\n"
    )
    assert captured.out == expected


def test_env_check_success(env, capsys, monkeypatch):
    monkeypatch.setattr(main, "console", main.console.__class__(force_terminal=False, width=200))
    env.set("MANUALMARKDOWNSTEP__FOLDER_PATH", "/tmp")
    main.env_cmd("wurzel.steps.manual_markdown:ManualMarkdownStep", check=True)
    captured = capsys.readouterr()
    assert "All required environment variables are set." in captured.out


def test_env_check_failure(env, capsys, monkeypatch):
    monkeypatch.setattr(main, "console", main.console.__class__(force_terminal=False, width=200))
    env.clear()
    with pytest.raises(typer.Exit) as exc:
        main.env_cmd("wurzel.steps.manual_markdown:ManualMarkdownStep", check=True)
    assert exc.value.exit_code == 1
    captured = capsys.readouterr()
    assert "Missing environment variables" in captured.out
    assert "MANUALMARKDOWNSTEP__FOLDER_PATH" in captured.out


def test_generate_with_malformed_yaml_raises_bad_parameter(tmp_path):
    """Test generate command raises BadParameter for malformed YAML values file."""
    malformed_file = tmp_path / "bad.yaml"
    malformed_file.write_text("key: value\n  bad_indent: oops")

    with pytest.raises(typer.BadParameter, match="Failed to parse YAML"):
        main.generate(
            pipeline="wurzel.steps.manual_markdown:ManualMarkdownStep",
            backend="DvcBackend",
            values=[malformed_file],
            pipeline_name=None,
        )
