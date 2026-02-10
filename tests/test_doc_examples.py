# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG
#
# SPDX-License-Identifier: Apache-2.0

"""Test code examples in README and documentation using pytest-examples.

Verifies that Python snippets in markdown and docstrings lint and run correctly.
"""

from pathlib import Path

import pytest
from pytest_examples import CodeExample, EvalExample, find_examples

# Repo root (parent of tests/)
_REPO_ROOT = Path(__file__).resolve().parent.parent

DOC_PATHS = [
    _REPO_ROOT / "README.md",
    _REPO_ROOT / "docs",
]


def _collect_examples():
    """Collect all code examples from documentation paths."""
    examples = []
    for p in DOC_PATHS:
        if not p.exists():
            continue
        for ex in find_examples(p):
            examples.append(ex)
    return examples


@pytest.mark.parametrize("example", _collect_examples(), ids=str)
def test_doc_examples_lint_and_run(example: CodeExample, eval_example: EvalExample) -> None:
    """Lint and run each Python example in README and docs.

    Run with `pytest --update-examples` to format examples in place (black/ruff)
    and update print output checks.
    """
    if eval_example.update_examples:
        eval_example.format(example)
        eval_example.run_print_update(example)
    else:
        eval_example.lint(example)
        eval_example.run(example)
