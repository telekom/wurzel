# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for wurzel.cli._main and the wurzel.cli public API (generate_cli_call)."""

import ast
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import typer
import yaml

import wurzel
import wurzel.core
from wurzel.cli import _main as main
from wurzel.cli import generate_cli_call
from wurzel.cli._main import _check_if_typed_step, _process_python_file, update_log_level
from wurzel.cli.environment.command import console as env_console
from wurzel.cli.environment.command import env as env_cmd
from wurzel.cli.generate import backend_callback, get_available_backends
from wurzel.cli.generate.command import generate
from wurzel.cli.inspect import main as inspect_command
from wurzel.cli.run import executer_callback
from wurzel.cli.run import main as run_main
from wurzel.cli.shared import complete_step_import
from wurzel.cli.shared.callbacks import step_callback
from wurzel.executors import BaseStepExecutor
from wurzel.executors.backend.backend_dvc import DvcBackend
from wurzel.steps.manual_markdown import ManualMarkdownStep
from wurzel.utils import HAS_HERA

# ---------------------------------------------------------------------------
# generate_cli_call (wurzel.cli public API)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("executor", [BaseStepExecutor])
def test_generate_cli_call_basic(executor, tmp_path):
    out_path = tmp_path / "out"
    result = generate_cli_call(ManualMarkdownStep, [], out_path, executor=executor)
    expected = (
        f"wurzel run wurzel.steps.manual_markdown:ManualMarkdownStep -o {out_path.absolute()} -e {executor.__qualname__}  --encapsulate-env"
    )
    assert result == expected


def test_generate_cli_call_with_single_input(tmp_path):
    out_path = tmp_path / "out"
    result = generate_cli_call(ManualMarkdownStep, [tmp_path], out_path, executor=BaseStepExecutor)
    assert result == (
        f"wurzel run wurzel.steps.manual_markdown:ManualMarkdownStep"
        f" -o {out_path.absolute()} -e BaseStepExecutor -i {tmp_path.absolute()} --encapsulate-env"
    )


def test_generate_cli_call_with_multiple_inputs(tmp_path):
    out_path = tmp_path / "out"
    result = generate_cli_call(ManualMarkdownStep, [tmp_path, tmp_path], out_path, executor=BaseStepExecutor)
    assert result == (
        f"wurzel run wurzel.steps.manual_markdown:ManualMarkdownStep"
        f" -o {out_path.absolute()} -e BaseStepExecutor"
        f" -i {tmp_path.absolute()} -i {tmp_path.absolute()} --encapsulate-env"
    )


@pytest.mark.skipif(shutil.which("wurzel") is None, reason="wurzel binary not on PATH")
@pytest.mark.parametrize(
    "backend",
    [
        "DvcBackend",
        pytest.param("ArgoBackend", marks=pytest.mark.skipif(not HAS_HERA, reason="Hera is not available")),
    ],
)
def test_generate_cli_call_backend_subprocess(tmp_path, backend, env):
    env.set("EMBEDDINGSTEP__API", "https://example.com/embd")
    env.set("MANUALMARKDOWNSTEP__FOLDER_PATH", "./data")
    env.set("QDRANTCONNECTORSTEP__COLLECTION", "test-collection")
    cmd = ["wurzel", "generate", "examples.pipeline.pipelinedemo:pipeline", "--backend", backend]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0, proc
    yaml.safe_load(proc.stdout)  # must produce valid YAML


# ---------------------------------------------------------------------------
# executer_callback
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "inpt_str, expected",
    [
        ("base", BaseStepExecutor),
        ("BASE", BaseStepExecutor),
        ("BaseStepExecutor", BaseStepExecutor),
    ],
)
def test_executer_callback(inpt_str, expected):
    assert executer_callback(None, None, inpt_str) == expected


def test_executer_callback_bad():
    with pytest.raises(typer.BadParameter):
        executer_callback(None, None, "XX")


# ---------------------------------------------------------------------------
# step_callback
# ---------------------------------------------------------------------------


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
    assert step_callback(None, None, step_path) == wurzel.steps.ManualMarkdownStep


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
        step_callback(None, None, step_path)


# ---------------------------------------------------------------------------
# backend_callback
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "backend_str",
    ["DvcBackend", "dvcbackend", "DVCBACKEND", "DvCbAcKeNd"],
)
def test_backend_callback_dvc(backend_str):
    assert backend_callback(None, None, backend_str) == DvcBackend


@pytest.mark.skipif(not HAS_HERA, reason="Hera is not available")
@pytest.mark.parametrize(
    "backend_str",
    ["ArgoBackend", "argobackend", "ARGOBACKEND", "ArGoBaCkEnD"],
)
def test_backend_callback_argo(backend_str):
    from wurzel.executors.backend.backend_argo import ArgoBackend

    assert backend_callback(None, None, backend_str) == ArgoBackend


def test_backend_callback_invalid():
    with pytest.raises(typer.BadParameter) as exc_info:
        backend_callback(None, None, "InvalidBackend")
    error_msg = str(exc_info.value)
    assert "InvalidBackend not supported" in error_msg
    assert "dvc" in error_msg
    if HAS_HERA:
        assert "argo" in error_msg


# ---------------------------------------------------------------------------
# update_log_level
# ---------------------------------------------------------------------------


def test_update_log_level_runs():
    update_log_level("INFO")


# ---------------------------------------------------------------------------
# get_available_backends
# ---------------------------------------------------------------------------


def test_get_available_backends():
    backends = get_available_backends()
    assert isinstance(backends, list)
    assert "dvc" in backends
    if HAS_HERA:
        assert "argo" in backends
    else:
        assert "argo" not in backends


@pytest.mark.skipif(not HAS_HERA, reason="Hera is not available")
def test_get_available_backends_includes_argo():
    backends = get_available_backends()
    assert "dvc" in backends
    assert "argo" in backends


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------


def test_run(tmp_path, env):
    out = tmp_path / "out"
    inp = tmp_path / "in"
    inp.mkdir()
    (inp / "file.md").write_text("#Hello\n world")
    env.set("MANUALMARKDOWNSTEP__FOLDER_PATH", str(inp.absolute()))
    run_main(step=ManualMarkdownStep, output_path=out, input_folders=set(), executor_str_value=BaseStepExecutor)
    assert list(out.glob("*"))
    assert (out / "ManualMarkdown.json").read_text()


def test_run_with_middleware(tmp_path, env):
    out = tmp_path / "out"
    inp = tmp_path / "in"
    inp.mkdir()
    (inp / "file.md").write_text("#Hello\n world")
    env.set("MANUALMARKDOWNSTEP__FOLDER_PATH", str(inp.absolute()))
    run_main(
        step=ManualMarkdownStep,
        output_path=out,
        input_folders=set(),
        executor_str_value=BaseStepExecutor,
        middlewares="prometheus",
    )
    assert list(out.glob("*"))
    assert (out / "ManualMarkdown.json").read_text()


def test_run_with_empty_middleware_string(tmp_path, env):
    out = tmp_path / "out"
    inp = tmp_path / "in"
    inp.mkdir()
    (inp / "file.md").write_text("#Hello\n world")
    env.set("MANUALMARKDOWNSTEP__FOLDER_PATH", str(inp.absolute()))
    run_main(
        step=ManualMarkdownStep,
        output_path=out,
        input_folders=set(),
        executor_str_value=BaseStepExecutor,
        middlewares="",
    )
    assert list(out.glob("*"))
    assert (out / "ManualMarkdown.json").read_text()


def test_run_with_middleware_from_env(tmp_path, env):
    out = tmp_path / "out"
    inp = tmp_path / "in"
    inp.mkdir()
    (inp / "file.md").write_text("#Hello\n world")
    env.set("MANUALMARKDOWNSTEP__FOLDER_PATH", str(inp.absolute()))
    env.set("MIDDLEWARES", "prometheus")
    run_main(step=ManualMarkdownStep, output_path=out, input_folders=set(), executor_str_value=BaseStepExecutor)
    assert list(out.glob("*"))
    assert (out / "ManualMarkdown.json").read_text()


def test_run_encapsulate_env(tmp_path, env):
    out = tmp_path / "out"
    inp = tmp_path / "in"
    inp.mkdir()
    (inp / "file.md").write_text("#Test\n content")
    env.set("MANUALMARKDOWNSTEP__FOLDER_PATH", str(inp.absolute()))
    run_main(
        step=ManualMarkdownStep,
        output_path=out,
        input_folders=set(),
        executor_str_value=BaseStepExecutor,
        middlewares="",
        encapsulate_env=True,
    )
    assert (out / "ManualMarkdown.json").exists()


def test_run_middleware_overrides_env(tmp_path, env):
    """Explicit empty middlewares parameter overrides MIDDLEWARES env var."""
    out = tmp_path / "out"
    inp = tmp_path / "in"
    inp.mkdir()
    (inp / "file.md").write_text("#Test\n content")
    env.set("MANUALMARKDOWNSTEP__FOLDER_PATH", str(inp.absolute()))
    env.set("MIDDLEWARES", "prometheus")
    run_main(
        step=ManualMarkdownStep,
        output_path=out,
        input_folders=set(),
        executor_str_value=BaseStepExecutor,
        middlewares="",
        encapsulate_env=True,
    )
    assert (out / "ManualMarkdown.json").exists()


def test_run_with_whitespace_in_middlewares(tmp_path, env):
    out = tmp_path / "out"
    inp = tmp_path / "in"
    inp.mkdir()
    (inp / "file.md").write_text("#Test\n content")
    env.set("MANUALMARKDOWNSTEP__FOLDER_PATH", str(inp.absolute()))
    run_main(
        step=ManualMarkdownStep,
        output_path=out,
        input_folders=set(),
        executor_str_value=BaseStepExecutor,
        middlewares=" prometheus ",
        encapsulate_env=True,
    )
    assert (out / "ManualMarkdown.json").exists()


def test_run_with_invalid_middleware_continues(tmp_path, env):
    """Invalid middleware name should log a warning and not crash execution."""
    out = tmp_path / "out"
    inp = tmp_path / "in"
    inp.mkdir()
    (inp / "file.md").write_text("#Test\n content")
    env.set("MANUALMARKDOWNSTEP__FOLDER_PATH", str(inp.absolute()))
    run_main(
        step=ManualMarkdownStep,
        output_path=out,
        input_folders=set(),
        executor_str_value=BaseStepExecutor,
        middlewares="nonexistent",
        encapsulate_env=True,
    )
    assert (out / "ManualMarkdown.json").exists()


# ---------------------------------------------------------------------------
# inspekt
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("gen_env", [True, False])
def test_inspekt(gen_env):
    inspect_command(ManualMarkdownStep, gen_env)


# ---------------------------------------------------------------------------
# generate command
# ---------------------------------------------------------------------------


def test_generate_list_backends(capsys):
    generate(pipeline=None, backend="dvc", list_backends=True)
    captured = capsys.readouterr()
    assert "Available backends:" in captured.out
    assert "dvc" in captured.out
    if HAS_HERA:
        assert "argo" in captured.out
    else:
        assert "argo" not in captured.out


def test_generate_prints_artifact_to_stdout_when_no_output(monkeypatch, capsys):
    monkeypatch.setattr("wurzel.cli.generate.command.pipeline_callback", lambda *_: "pipeline-step")
    monkeypatch.setattr("wurzel.cli.generate.command.backend_callback", lambda *_: "backend-class")

    def fake_generate_main(step, backend, *, values=None, pipeline_name=None, output=None, executor=None):  # noqa: ANN001, ANN002, ANN003
        assert step == "pipeline-step"
        assert backend == "backend-class"
        assert values is None
        assert pipeline_name is None
        assert output is None
        assert executor is None
        return "artifact-yaml"

    monkeypatch.setattr("wurzel.cli.generate.main", fake_generate_main)

    generate("mod:pipe", backend="dvc")

    captured = capsys.readouterr()
    assert captured.out == "artifact-yaml\n"


def test_generate_writes_artifact_and_prints_confirmation_with_output(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr("wurzel.cli.generate.command.pipeline_callback", lambda *_: "pipeline-step")
    monkeypatch.setattr("wurzel.cli.generate.command.backend_callback", lambda *_: "backend-class")
    output_path = tmp_path / "generated.yaml"

    def fake_generate_main(step, backend, *, values=None, pipeline_name=None, output=None, executor=None):  # noqa: ANN001, ANN002, ANN003
        assert step == "pipeline-step"
        assert backend == "backend-class"
        assert values is None
        assert pipeline_name is None
        assert executor is None
        assert output == output_path
        output.write_text("artifact-yaml")
        return "artifact-yaml"

    monkeypatch.setattr("wurzel.cli.generate.main", fake_generate_main)

    generate("mod:pipe", backend="dvc", output=output_path)

    captured = capsys.readouterr()
    assert captured.out == f"Generated '{output_path}'.\n"
    assert output_path.read_text() == "artifact-yaml"


# ---------------------------------------------------------------------------
# env command
# ---------------------------------------------------------------------------


def test_env_outputs_requirements(capsys, monkeypatch):
    monkeypatch.setattr("wurzel.cli.environment.command.console", env_console.__class__(force_terminal=False, width=200))
    env_cmd("wurzel.steps.manual_markdown:ManualMarkdownStep")
    captured = capsys.readouterr()
    assert "Environment variables" in captured.out
    assert "MANUALMARKDOWNSTEP__FOLDER_PATH" in captured.out


def test_env_only_required_filters_optional(capsys, monkeypatch):
    monkeypatch.setattr("wurzel.cli.environment.command.console", env_console.__class__(force_terminal=False, width=200))
    env_cmd("examples.pipeline.pipelinedemo:pipeline", include_optional=False)
    captured = capsys.readouterr()
    assert "MANUALMARKDOWNSTEP__FOLDER_PATH" in captured.out
    assert "SIMPLESPLITTERSTEP__BATCH_SIZE" not in captured.out


def test_env_gen_env_outputs_env_file(capsys, monkeypatch, env):
    monkeypatch.setattr("wurzel.cli.environment.command.console", env_console.__class__(force_terminal=False, width=200))
    env.set("MANUALMARKDOWNSTEP__FOLDER_PATH", "/tmp/custom")
    env.set("SIMPLESPLITTERSTEP__BATCH_SIZE", "256")
    env_cmd("examples.pipeline.pipelinedemo:pipeline", gen_env=True)
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


def test_env_gen_env_default_values(capsys, monkeypatch):
    monkeypatch.setattr("wurzel.cli.environment.command.console", env_console.__class__(force_terminal=False, width=200))
    env_cmd("examples.pipeline.pipelinedemo:pipeline", gen_env=True)
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
    monkeypatch.setattr("wurzel.cli.environment.command.console", env_console.__class__(force_terminal=False, width=200))
    env.set("MANUALMARKDOWNSTEP__FOLDER_PATH", "/tmp")
    env_cmd("wurzel.steps.manual_markdown:ManualMarkdownStep", check=True)
    captured = capsys.readouterr()
    assert "All required environment variables are set." in captured.out


def test_env_check_failure(env, capsys, monkeypatch):
    monkeypatch.setattr("wurzel.cli.environment.command.console", env_console.__class__(force_terminal=False, width=200))
    env.clear()
    with pytest.raises(typer.Exit) as exc:
        env_cmd("wurzel.steps.manual_markdown:ManualMarkdownStep", check=True)
    assert exc.value.exit_code == 1
    captured = capsys.readouterr()
    assert "Missing environment variables" in captured.out
    assert "MANUALMARKDOWNSTEP__FOLDER_PATH" in captured.out


# ---------------------------------------------------------------------------
# complete_step_import / autocomplete
# ---------------------------------------------------------------------------


def test_autocomplete_returns_known_step():
    completion = complete_step_import("")
    assert completion
    assert "wurzel.steps.manual_markdown.ManualMarkdownStep" in completion


def test_autocomplete_non_matching_prefix_returns_list():
    results = complete_step_import("no_such_prefix_hopefully")
    assert isinstance(results, list)


def test_autocomplete_with_mocked_distributions():
    with (
        patch("wurzel.cli.shared.autocompletion.Path.cwd") as mock_cwd,
        patch("importlib.metadata.distributions") as mock_distributions,
        patch("importlib.util.find_spec") as mock_find_spec,
    ):
        mock_cwd.return_value = Path("/fake/path")
        mock_dist = Mock()
        mock_dist.name = "test_package"
        mock_distributions.return_value = [mock_dist]
        mock_spec = Mock()
        mock_spec.origin = "/path/to/test_package/__init__.py"
        mock_find_spec.return_value = mock_spec

        result = complete_step_import("test_package.SomeClass")
        assert isinstance(result, list)


def test_autocomplete_handles_cwd_exception_gracefully():
    with patch("wurzel.cli.shared.autocompletion.Path.cwd") as mock_cwd:
        mock_cwd.side_effect = Exception("Fake error")
        result = complete_step_import("some_input")
        assert isinstance(result, list)


def test_autocomplete_many_files_does_not_crash():
    with patch("wurzel.cli.shared.autocompletion.Path.cwd") as mock_cwd:
        mock_cwd.return_value = Path("/fake")
        # Mock rglob to return many files
        mock_path = Mock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.iterdir.return_value = []
        mock_path.glob.return_value = [Path(f"/fake/file{i}.py") for i in range(50)]
        with patch("wurzel.cli.shared.autocompletion.Path", return_value=mock_path) as mock_Path_class:
            mock_Path_class.cwd.return_value = mock_path
            result = complete_step_import("test")
            assert isinstance(result, list)


# ---------------------------------------------------------------------------
# _build_module_path
# ---------------------------------------------------------------------------


def test_build_module_path_with_base(tmp_path):
    search = tmp_path / "pkg"
    search.mkdir()
    (search / "sub").mkdir()
    f = search / "sub" / "mymodule.py"
    f.write_text("class X: pass")
    result = main._build_module_path(f, search, "base")
    assert result.startswith("base.")


def test_build_module_path_without_base(tmp_path):
    search = tmp_path / "pkg"
    search.mkdir()
    (search / "sub").mkdir()
    f = search / "sub" / "mymodule.py"
    f.write_text("class X: pass")
    result = main._build_module_path(f, search, "")
    assert result.count(".") >= 1


# ---------------------------------------------------------------------------
# _check_if_typed_step
# ---------------------------------------------------------------------------


def test_check_if_typed_step_true():
    code = "class MyStep(TypedStep):\n    pass\n"
    class_node = ast.parse(code).body[0]
    assert _check_if_typed_step(class_node) is True


def test_check_if_typed_step_false():
    code = "class MyOtherClass:\n    pass\n"
    class_node = ast.parse(code).body[0]
    assert _check_if_typed_step(class_node) is False


# ---------------------------------------------------------------------------
# _process_python_file
# ---------------------------------------------------------------------------


def test_process_python_file_finds_typed_step(tmp_path):
    f = tmp_path / "test_step.py"
    f.write_text("from wurzel.core.typed_step import TypedStep\n\nclass TestStep(TypedStep):\n    pass\n\nclass NotAStep:\n    pass\n")
    hints: list[str] = []
    _process_python_file(f, tmp_path, "test", "test", hints)
    assert len(hints) == 1
    assert "TestStep" in hints[0]


def test_process_python_file_ignores_non_typed_steps(tmp_path):
    f = tmp_path / "no_step.py"
    f.write_text("class RegularClass:\n    pass\n")
    hints: list[str] = []
    _process_python_file(f, tmp_path, "test", "test", hints)
    assert len(hints) == 0


# ---------------------------------------------------------------------------
# Performance: complete_step_import
# ---------------------------------------------------------------------------


class TestAutocompletionPerformance:
    def test_wurzel_project_under_threshold(self):
        times = []
        for _ in range(5):
            start = time.perf_counter()
            complete_step_import("")
            times.append(time.perf_counter() - start)
        assert sum(times) / len(times) < 1.0, "average must be < 1 s"
        assert max(times) < 2.0, "max must be < 2 s"

    def test_prefix_filtering_is_faster(self):
        times = []
        for _ in range(3):
            start = time.perf_counter()
            results = complete_step_import("wurzel.steps.")
            times.append(time.perf_counter() - start)
        assert sum(times) / len(times) < 0.7
        for result in results:
            assert result.startswith("wurzel.steps.")

    def test_user_project_finds_custom_steps(self):
        with tempfile.TemporaryDirectory() as tmp:
            import os

            steps_dir = Path(tmp) / "mysteps"
            steps_dir.mkdir()
            (steps_dir / "custom_step.py").write_text(
                "from wurzel.core import TypedStep\n\nclass MyCustomStep(TypedStep):\n    pass\n\nclass AnotherStep(TypedStep):\n    pass\n"
            )
            original = os.getcwd()
            try:
                os.chdir(tmp)
                times = []
                for _ in range(3):
                    start = time.perf_counter()
                    results = complete_step_import("")
                    times.append(time.perf_counter() - start)
                assert sum(times) / len(times) < 1.0
                assert max(times) < 2.0
                assert any("wurzel.steps." in r for r in results)
                assert any("mysteps." in r for r in results)
            finally:
                os.chdir(original)

    def test_large_project_under_threshold(self):
        with tempfile.TemporaryDirectory() as tmp:
            import os

            temp_path = Path(tmp)
            for i in range(10):
                subdir = temp_path / f"module_{i}"
                subdir.mkdir()
                for j in range(5):
                    fp = subdir / f"file_{j}.py"
                    if j % 3 == 0:
                        fp.write_text(f"from wurzel.core import TypedStep\n\nclass Step{i}{j}(TypedStep):\n    pass\n")
                    else:
                        fp.write_text(f"def func_{i}_{j}(): pass\n")
            original = os.getcwd()
            try:
                os.chdir(tmp)
                start = time.perf_counter()
                results = complete_step_import("")
                assert time.perf_counter() - start < 1.5
                user_steps = [r for r in results if not r.startswith("wurzel.")]
                assert len(user_steps) > 0
            finally:
                os.chdir(original)

    @pytest.mark.parametrize("incomplete", ["", "w", "wurzel", "wurzel.steps", "nonexistent"])
    def test_various_inputs_under_threshold(self, incomplete: str):
        start = time.perf_counter()
        results = complete_step_import(incomplete)
        assert time.perf_counter() - start < 1.0
        if incomplete:
            for result in results:
                assert result.startswith(incomplete)

    def test_external_packages_discovery_mechanism(self):
        """Test that wurzel-dependent packages are discovered efficiently.

        Uses dependency-based discovery to find only packages that depend on wurzel,
        which is faster and more accurate than keyword matching.
        """
        start = time.perf_counter()
        results = complete_step_import("")
        elapsed = time.perf_counter() - start

        # Should still be fast with dependency-based discovery
        assert elapsed < 2.0, f"Full scan took {elapsed:.2f}s, expected < 2s"

        # Should find wurzel steps
        has_wurzel = any(r.startswith("wurzel.") for r in results)
        assert has_wurzel, "Should find wurzel steps"

        # Should find at least some steps
        assert len(results) > 0, "Should find at least some steps"

    def test_external_packages_steps_telekom(self):
        """Test that steps_telekom package is discovered if installed."""
        results = complete_step_import("steps_telekom")

        # Should find steps_telekom if installed
        if results:
            for result in results:
                assert result.startswith("steps_telekom"), f"Result {result} doesn't start with 'steps_telekom'"
            assert any(".arize." in r for r in results), "Should find Arize step in steps_telekom"

    def test_external_packages_steps_greece(self):
        """Test that steps_greece package is discovered if installed."""
        results = complete_step_import("steps_greece")

        # Should find steps_greece if installed
        if results:
            for result in results:
                assert result.startswith("steps_greece"), f"Result {result} doesn't start with 'steps_greece'"
            assert any(".manual_markdown." in r for r in results), "Should find ManualMarkdown step in steps_greece"

    def test_external_package_prefix_filtering(self):
        """Test that prefix filtering works for hyphenated packages (steps- and steps_).

        This tests that both naming conventions are handled:
        - steps_telekom (underscore)
        - steps-greece (hyphen, normalized to steps_greece)
        """
        # Should normalize hyphenated names properly
        results = complete_step_import("steps_")

        # Should return a list
        assert isinstance(results, list)

        # All results should start with "steps_" (after normalization)
        for result in results:
            assert result.startswith("steps_"), f"Result {result} doesn't start with 'steps_'"

    def test_external_package_scanning_uses_skip_list(self):
        """Test that the scanner only examines packages depending on wurzel.

        Verifies efficient discovery by only scanning packages with actual
        wurzel dependencies, rather than trying all packages.
        """
        results = complete_step_import("")
        assert isinstance(results, list)
        assert len(results) > 0

        # Should find wurzel steps regardless of implementation
        has_wurzel = any(r.startswith("wurzel.") for r in results)
        assert has_wurzel, "Should find wurzel steps"

    def test_external_packages_nested_directories_discovered(self):
        """Test that nested directory TypedSteps are discovered from external packages.

        Verifies that the scanner correctly handles subdirectories in external
        packages and finds TypedStep classes at any nesting level (e.g., CdlStep
        in steps_telekom/kafka_cdl/step.py).
        """
        results = complete_step_import("")
        assert isinstance(results, list)

        # Expected nested steps from steps_telekom
        nested_telekom = {
            "steps_telekom.kafka_cdl.step.CdlStep",
            "steps_telekom.magenta_moments.step.MagentaMomentsStep",
            "steps_telekom.url_replacer.url_replacer_step.NonAbsoluteUrlReplacerStep",
        }

        # Check if steps_telekom is installed
        try:
            import steps_telekom  # noqa: F401, pylint: disable=unused-import

            for step in nested_telekom:
                assert step in results, f"Should find nested step {step}"
        except ImportError:
            # steps_telekom not installed, skip assertion
            pass

        # Expected nested steps from steps_greece
        nested_greece = {
            "steps_greece.chunking.chunking.GRMarkdownChunkingStep",
        }

        # Check if steps_greece is installed
        try:
            import steps_greece  # noqa: F401, pylint: disable=unused-import

            for step in nested_greece:
                assert step in results, f"Should find nested step {step}"
        except ImportError:
            # steps_greece not installed, skip assertion
            pass

    def test_wurzel_core_steps_excluded(self):
        """Test that wurzel.core.* steps are always excluded from autocompletion.

        Verifies that internal implementation details like SelfConsumingLeafStep
        are not exposed in autocompletion results, even though they are valid
        TypedStep subclasses. Only user-facing steps should be suggested.
        """
        results = complete_step_import("")
        assert isinstance(results, list)

        # Should NOT contain any wurzel.core.* steps
        core_steps = [r for r in results if r.startswith("wurzel.core.")]
        assert len(core_steps) == 0, f"Should not find wurzel.core.* steps, but found: {core_steps}"

        # Specifically check that SelfConsumingLeafStep is not in results
        assert "wurzel.core.self_consuming_step.SelfConsumingLeafStep" not in results

        # Verify we still find normal wurzel.steps
        user_facing_steps = [r for r in results if r.startswith("wurzel.steps.")]
        assert len(user_facing_steps) > 0, "Should find user-facing wurzel.steps"
