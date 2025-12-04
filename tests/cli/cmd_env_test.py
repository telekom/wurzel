# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for wurzel.cli.cmd_env helpers."""

from examples.pipeline import pipelinedemo
from wurzel.cli import cmd_env


def test_collect_env_requirements_preserves_step_and_field_order():
    reqs = cmd_env.collect_env_requirements(pipelinedemo.pipeline)

    manual = [req for req in reqs if req.step_name == "ManualMarkdownStep"]
    simple = [req for req in reqs if req.step_name == "SimpleSplitterStep"]

    assert manual and manual[0].env_var == "MANUALMARKDOWNSTEP__FOLDER_PATH"
    assert [req.env_var for req in simple] == [
        "SIMPLESPLITTERSTEP__BATCH_SIZE",
        "SIMPLESPLITTERSTEP__NUM_THREADS",
        "SIMPLESPLITTERSTEP__TOKEN_COUNT_MIN",
        "SIMPLESPLITTERSTEP__TOKEN_COUNT_MAX",
        "SIMPLESPLITTERSTEP__TOKEN_COUNT_BUFFER",
        "SIMPLESPLITTERSTEP__TOKENIZER_MODEL",
        "SIMPLESPLITTERSTEP__SENTENCE_SPLITTER_MODEL",
    ]


def test_format_env_snippet_matches_expected_layout():
    reqs = cmd_env.collect_env_requirements(pipelinedemo.pipeline)
    snippet = cmd_env.format_env_snippet(reqs)

    assert snippet == (
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
        "SIMPLESPLITTERSTEP__SENTENCE_SPLITTER_MODEL=de_core_news_sm\n\n"
    )


def test_format_env_snippet_prefers_current_env_values():
    reqs = cmd_env.collect_env_requirements(pipelinedemo.pipeline)

    snippet = cmd_env.format_env_snippet(
        reqs,
        current_env={
            "MANUALMARKDOWNSTEP__FOLDER_PATH": "/tmp/data",
            "SIMPLESPLITTERSTEP__BATCH_SIZE": "256",
        },
    )

    assert "MANUALMARKDOWNSTEP__FOLDER_PATH=/tmp/data" in snippet
    assert "SIMPLESPLITTERSTEP__BATCH_SIZE=256" in snippet


def test_validate_env_vars_reports_missing(env):
    env.clear()
    issues = cmd_env.validate_env_vars(pipelinedemo.pipeline, allow_extra_fields=False)
    missing = {issue.env_var for issue in issues}
    assert "MANUALMARKDOWNSTEP__FOLDER_PATH" in missing


def test_validate_env_vars_passes_when_required_present(env, tmp_path):
    env.set("MANUALMARKDOWNSTEP__FOLDER_PATH", str(tmp_path))
    issues = cmd_env.validate_env_vars(pipelinedemo.pipeline, allow_extra_fields=False)
    assert issues == []
