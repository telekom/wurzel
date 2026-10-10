# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for wurzel.cli.shared.ast_helpers — cached AST utility wrappers."""

import ast

from wurzel.cli.shared.ast_helpers import build_module_path, check_if_typed_step


def make_class_def(name: str, bases: list[str | tuple[str, str]]) -> ast.ClassDef:
    """Build a synthetic ClassDef node for testing."""
    ast_bases = []
    for base in bases:
        if isinstance(base, str):
            ast_bases.append(ast.Name(id=base))
        elif isinstance(base, tuple):
            # (module, attr) → ast.Attribute
            value_node = ast.Name(id=base[0])
            ast_bases.append(ast.Attribute(value=value_node, attr=base[1]))
    return ast.ClassDef(name=name, bases=ast_bases, keywords=[], body=[], decorator_list=[])


def make_subscript_class_def(name: str, base_name: str) -> ast.ClassDef:
    """Build a ClassDef where base is TypedStep[A, B, C]."""
    subscript = ast.Subscript(value=ast.Name(id=base_name), slice=ast.Constant(value=None))
    return ast.ClassDef(name=name, bases=[subscript], keywords=[], body=[], decorator_list=[])


def make_attr_subscript_class_def(name: str, module: str, attr: str) -> ast.ClassDef:
    """Build ClassDef where base is module.TypedStep[...]."""
    value_node = ast.Attribute(value=ast.Name(id=module), attr=attr)
    subscript = ast.Subscript(value=value_node, slice=ast.Constant(value=None))
    return ast.ClassDef(name=name, bases=[subscript], keywords=[], body=[], decorator_list=[])


class TestCheckIfTypedStep:
    def test_direct_name_base(self):
        node = make_class_def("MyStep", ["TypedStep"])
        assert check_if_typed_step(node) is True

    def test_subscript_base(self):
        node = make_subscript_class_def("MyStep", "TypedStep")
        assert check_if_typed_step(node) is True

    def test_attribute_base(self):
        node = make_class_def("MyStep", [("wurzel", "TypedStep")])
        assert check_if_typed_step(node) is True

    def test_attribute_subscript_base(self):
        node = make_attr_subscript_class_def("MyStep", "wurzel", "TypedStep")
        assert check_if_typed_step(node) is True

    def test_non_typed_step_base(self):
        node = make_class_def("MyClass", ["SomethingElse"])
        assert check_if_typed_step(node) is False

    def test_no_bases(self):
        node = make_class_def("MyClass", [])
        assert check_if_typed_step(node) is False

    def test_caches_function(self):
        """Calling twice should use the cached function."""
        from wurzel.cli.shared import ast_helpers

        ast_helpers._ast_helpers_cache.clear()
        node = make_class_def("MyStep", ["TypedStep"])
        check_if_typed_step(node)
        assert "check_if_typed_step" in ast_helpers._ast_helpers_cache
        # Call again — should use cache
        check_if_typed_step(node)


class TestBuildModulePath:
    def test_builds_module_path(self, tmp_path):
        # Create a simple Python file in a package structure
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        py_file = pkg / "mystep.py"
        py_file.write_text("# empty\n")

        result = build_module_path(py_file, tmp_path, "mypkg")
        assert "mystep" in result

    def test_caches_function(self, tmp_path):
        from wurzel.cli.shared import ast_helpers

        ast_helpers._ast_helpers_cache.clear()
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        py_file = pkg / "step.py"
        py_file.write_text("# empty\n")

        build_module_path(py_file, tmp_path, "mypkg")
        assert "build_module_path" in ast_helpers._ast_helpers_cache
