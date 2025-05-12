# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import importlib
import inspect
import pkgutil
from typing import TypeVar

from wurzel.step.typed_step import TypedStep

T = TypeVar("T", bound=object)


def find_sub_classes(parent: T, package: str = __package__) -> dict[str, T]:
    """Searches for all DVC step definitions and returns them based on their name."""

    def is_non_abs_child(member: object) -> bool:
        return (
            True
            and inspect.isclass(member)
            and issubclass(member, parent)
            and not inspect.isabstract(member)
            and not bool(getattr(member, "__abstractmethods__", False))
        )

    result = {}
    visited = set([f"{__package__}.main", f"{__package__}.utils"])  # noqa: C405
    module_iterator = pkgutil.iter_modules(importlib.import_module(package).__path__)
    for _, module_name, is_package in module_iterator:
        full_module_name = f"{package}.{module_name}"
        if full_module_name in visited:
            continue
        visited.add(full_module_name)
        # Recurse through any sub-packages
        try:
            if is_package:
                classes_in_subpackage = find_sub_classes(parent, package=full_module_name)
                result.update(classes_in_subpackage)
            # Load the module for inspection

            module = importlib.import_module(full_module_name)
        except:  # pylint: disable=bare-except  # noqa: E722
            continue
        # Iterate through all the objects in the module and
        # using the lambda, filter for class objects and only objects that exist within the module
        for _name, obj in inspect.getmembers(module, is_non_abs_child):
            result[obj.__name__] = obj
    return result


def find_typed_steps_in_package(package: str) -> dict[str, type[TypedStep]]:
    """Recursively find all subclasses of TypedStep."""
    return find_sub_classes(TypedStep, package)
