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
    assert list(out.glob("*"))
    assert (out / "ManualMarkdown.json").read_text()


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


@pytest.mark.parametrize(
    "has_hera_value, expected_backends",
    [
        (True, ["DvcBackend", "ArgoBackend"]),
        (False, ["DvcBackend"]),
    ],
)
def test_get_available_backends(monkeypatch, has_hera_value, expected_backends):
    """Test get_available_backends returns correct list of backends based on HAS_HERA."""
    # Mock HAS_HERA value
    monkeypatch.setattr("wurzel.cli._main.HAS_HERA", has_hera_value, raising=False)
    import importlib

    importlib.reload(main)

    # Need to patch it in the function's context
    with monkeypatch.context() as m:
        m.setattr("wurzel.utils.HAS_HERA", has_hera_value)
        backends = main.get_available_backends()

    assert isinstance(backends, list)
    assert backends == expected_backends


@pytest.mark.parametrize(
    "has_hera_value, should_have_argo",
    [
        (True, True),
        (False, False),
    ],
)
def test_generate_list_backends(monkeypatch, capsys, has_hera_value, should_have_argo):
    """Test generate command with --list-backends flag."""
    # Mock HAS_HERA value
    with monkeypatch.context() as m:
        m.setattr("wurzel.utils.HAS_HERA", has_hera_value)
        main.generate(pipeline=None, backend="DvcBackend", list_backends=True)

    captured = capsys.readouterr()
    assert "Available backends:" in captured.out
    assert "DvcBackend" in captured.out

    if should_have_argo:
        assert "ArgoBackend" in captured.out
    else:
        assert "ArgoBackend" not in captured.out
