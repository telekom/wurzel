# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import abc
from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wurzel.step.typed_step import TypedStep  # noqa: F401

log = getLogger(__name__)


class StepMeta(abc.ABCMeta):
    """Metaclass that enables >> operator on classes themselves."""

    def __new__(mcs, name, bases, namespace):  # pylint: disable=unused-argument
        cls = super().__new__(mcs, name, bases, namespace)
        # Initialize class-level required steps
        cls._class_required_steps = set()  # pylint: disable=protected-access
        return cls

    def clear_class_dependencies(cls):
        """Clear class-level dependencies. Useful for testing."""
        if hasattr(cls, "_class_required_steps"):
            cls._class_required_steps.clear()  # pylint: disable=protected-access

    def __rshift__(cls, other):  # type: ignore
        """Allow Class >> Class syntax."""
        if isinstance(other, type):
            # Add this class as a dependency to the other class
            if not hasattr(other, "_class_required_steps"):
                other._class_required_steps = set()  # pylint: disable=protected-access
            other._class_required_steps.add(cls)  # pylint: disable=protected-access

            # Return the target class (other) with dependency relationship established
            return other
        raise TypeError("Cannot use class >> instance syntax")

    @property
    def traverse(cls):  # type: ignore
        """Class-level traverse property."""
        # Import TypedStep here to avoid circular imports
        from wurzel.step.typed_step import TypedStep  # pylint: disable=import-outside-toplevel

        # Check if this is a TypedStep class
        if issubclass(cls, TypedStep):
            # Implement class-level traverse logic
            def _class_traverse(current_cls, visited):  # type: ignore
                visited.add(current_cls)
                # Add dependencies from class-level required steps
                if hasattr(current_cls, "_class_required_steps"):
                    for dep_cls in current_cls._class_required_steps:  # pylint: disable=protected-access
                        if dep_cls not in visited:
                            _class_traverse(dep_cls, visited)
                return visited

            return lambda: _class_traverse(cls, set())

        # For regular Step classes, create instance and call traverse
        def regular_traverse():  # type: ignore
            # Create instance properly - this is safe because cls is a Step subclass
            instance = super(StepMeta, cls).__call__()
            return instance.traverse()

        return regular_traverse


class Step(abc.ABC, metaclass=StepMeta):
    """abstract class to define a WurzelStep."""

    required_steps: set["Step"]

    def __init__(self) -> None:  # pylint: disable=dangerous-default-value
        self.required_steps = set()

    def is_leaf(self) -> bool:
        """Returns if the node is a leaf in the pipeline tree.

        Returns:
        -------
        bool
            _description_

        """
        return not self.required_steps

    def output_path(self, folder: Path) -> Path:
        """Returns a generated output path."""
        return (folder / self.__class__.__name__).with_suffix(".file")

    def add_required_step(self, step: "Step"):
        """Adds a required step.

        Args:
            step (Step): will be added to required_steps

        """
        self.required_steps |= {step}

    def __rshift__(self, step):
        # Convert class to instance if needed
        if isinstance(step, type):
            step = step()

        # Maybe Todo:
        # Check if classname is already present
        # Disallow Cyclic graphs !
        step.add_required_step(self)
        return step

    def _traverse(self, set_of: set["Step"]):
        """Helper method for traverse."""
        set_of.add(self)
        for step in self.required_steps:
            step._traverse(set_of)  # pylint: disable=protected-access
        return set_of

    def traverse(self) -> set["Step"]:
        """Retrieve a set of all required steps including self."""
        return self._traverse(set())
