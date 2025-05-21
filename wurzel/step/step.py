# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import abc
from logging import getLogger
from pathlib import Path

log = getLogger(__name__)


class Step(abc.ABC):
    """abstract class to define a WurzelStep."""

    required_steps: set["Step"]

    def __init__(self) -> None:  # pylint: disable=dangerous-default-value
        self.required_steps = set()

    def is_leaf(self) -> bool:
        """Returns if the node is a leaf in the pipeline tree.

        Returns
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

    def __rshift__(self, step: "Step"):
        # Maybe Todo:
        # Check if classname is already present
        # Disallow Cyclic graphs !
        step.add_required_step(self)
        return step
