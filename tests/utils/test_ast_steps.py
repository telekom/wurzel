# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for wurzel.core.meta.ast_steps."""

import ast

import pytest

from wurzel.core.meta.ast_steps import (
    build_module_path,
    check_if_typed_step,
    find_typed_steps_in_venv,
    scan_path_for_typed_steps,
)

# ---------------------------------------------------------------------------
# check_if_typed_step
# ---------------------------------------------------------------------------


def _class_node(src: str) -> ast.ClassDef:
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            return node
    raise AssertionError("No ClassDef found")


@pytest.mark.parametrize(
    "src",
    [
        "class Foo(TypedStep): pass",
        "class Foo(TypedStep[S, I, O]): pass",
        "class Foo(wurzel.TypedStep): pass",
        "class Foo(core.typed_step.TypedStep[S, I, O]): pass",
    ],
    ids=["plain", "generic", "attribute", "nested_attribute_generic"],
)
def test_check_if_typed_step_matches(src):
    assert check_if_typed_step(_class_node(src)) is True


@pytest.mark.parametrize(
    "src",
    [
        "class Foo(BaseModel): pass",
        "class Foo(Step): pass",
        "class Foo: pass",
        "class Foo(SomeTypedStepWrapper): pass",
    ],
    ids=["base_model", "plain_step", "no_base", "similar_name"],
)
def test_check_if_typed_step_no_match(src):
    assert check_if_typed_step(_class_node(src)) is False


# ---------------------------------------------------------------------------
# build_module_path
# ---------------------------------------------------------------------------


def test_build_module_path_with_base(tmp_path):
    py_file = tmp_path / "foo" / "bar.py"
    py_file.parent.mkdir()
    py_file.touch()
    assert build_module_path(py_file, tmp_path, "mypkg") == "mypkg.foo.bar"


def test_build_module_path_without_base(tmp_path):
    py_file = tmp_path / "baz.py"
    py_file.touch()
    assert build_module_path(py_file, tmp_path, "") == "baz"


def test_build_module_path_raises_for_unrelated_file(tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    py_file = other / "x.py"
    py_file.touch()
    with pytest.raises(ValueError):
        build_module_path(py_file, tmp_path / "unrelated", "pkg")


# ---------------------------------------------------------------------------
# scan_path_for_typed_steps
# ---------------------------------------------------------------------------


def test_scan_path_finds_typed_step(tmp_path):
    (tmp_path / "mystep.py").write_text(
        "from wurzel import TypedStep\n\nclass MyStep(TypedStep[None, None, None]):\n    pass\n",
        encoding="utf-8",
    )
    results = scan_path_for_typed_steps(tmp_path, "mypkg")
    assert "mypkg.mystep.MyStep" in results


def test_scan_path_skips_init(tmp_path):
    (tmp_path / "__init__.py").write_text("class InitStep(TypedStep): pass\n", encoding="utf-8")
    results = scan_path_for_typed_steps(tmp_path, "mypkg")
    assert results == []


def test_scan_path_skips_non_typed_step(tmp_path):
    (tmp_path / "plain.py").write_text("class Plain:\n    pass\n", encoding="utf-8")
    results = scan_path_for_typed_steps(tmp_path, "mypkg")
    assert results == []


def test_scan_path_skips_excluded_dirs(tmp_path):
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    (cache / "cached.py").write_text("class CachedStep(TypedStep): pass\n", encoding="utf-8")
    results = scan_path_for_typed_steps(tmp_path, "mypkg")
    assert results == []


def test_scan_path_handles_syntax_error(tmp_path):
    (tmp_path / "broken.py").write_text("class Foo(TypedStep\n", encoding="utf-8")
    results = scan_path_for_typed_steps(tmp_path, "mypkg")
    assert results == []


# ---------------------------------------------------------------------------
# find_typed_steps_in_venv
# ---------------------------------------------------------------------------


def test_find_typed_steps_in_venv_contains_known_step():
    results = find_typed_steps_in_venv()
    assert "wurzel.steps.manual_markdown.ManualMarkdownStep" in results


def test_find_typed_steps_in_venv_returns_list():
    results = find_typed_steps_in_venv()
    assert isinstance(results, list)
    assert len(results) > 0


def test_find_typed_steps_in_venv_no_duplicates():
    results = find_typed_steps_in_venv()
    assert len(results) == len(set(results))
