# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""AST helper utilities with caching and optimization."""

from __future__ import annotations

import ast
from typing import Any

# Lazy-loaded cache for AST helper functions
_ast_helpers_cache: dict[str, Any] = {}


def check_if_typed_step(node: ast.ClassDef) -> bool:
    """Check if an AST ClassDef node is a TypedStep subclass."""
    if "check_if_typed_step" not in _ast_helpers_cache:
        from wurzel.core.meta.ast_steps import check_if_typed_step as _check  # pylint: disable=import-outside-toplevel

        _ast_helpers_cache["check_if_typed_step"] = _check
    return _ast_helpers_cache["check_if_typed_step"](node)


def build_module_path(py_file: Any, search_path: Any, base_module: str) -> str:
    """Build module path from file location."""
    if "build_module_path" not in _ast_helpers_cache:
        from wurzel.core.meta.ast_steps import build_module_path as _build  # pylint: disable=import-outside-toplevel

        _ast_helpers_cache["build_module_path"] = _build
    return _ast_helpers_cache["build_module_path"](py_file, search_path, base_module)
