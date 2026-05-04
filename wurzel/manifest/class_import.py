# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Shared TypedStep class import helpers for manifest handling."""

from __future__ import annotations

import importlib
import inspect

from wurzel.core import TypedStep


def import_step_class(class_path: str) -> type[TypedStep]:
    """Import a TypedStep subclass by dotted class path."""
    module_path, _, class_name = class_path.rpartition(".")
    if not module_path:
        raise ImportError(f"Invalid class path '{class_path}': no module component.")
    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        raise ImportError(f"Cannot import module '{module_path}': {exc}") from exc
    if not hasattr(module, class_name):
        raise ImportError(f"Class '{class_name}' not found in module '{module_path}'.")
    obj = getattr(module, class_name)
    if not inspect.isclass(obj):
        raise ImportError(f"'{class_name}' in '{module_path}' is not a class.")
    if not issubclass(obj, TypedStep):
        raise ImportError(f"'{class_name}' in '{module_path}' is not a TypedStep subclass.")
    return obj
