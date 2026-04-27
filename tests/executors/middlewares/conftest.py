# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Shared fixtures for middleware tests."""

from types import SimpleNamespace
from typing import Any, Optional

import pytest


class DummyStep:
    """Minimal fake step class for Prometheus middleware tests."""


@pytest.fixture
def dummy_report():
    """Standard execution report used across prometheus tests."""
    return SimpleNamespace(
        results=1,
        inputs=2,
        time_to_save=0.1,
        time_to_load=0.2,
        time_to_execute=0.3,
    )


@pytest.fixture
def make_call_next():
    """Factory that returns a call_next function producing a given report."""

    def _factory(report):
        def call_next(step_cls: type, inputs: Optional[set], output_dir: Optional[Any]):
            return [(None, report)]

        return call_next

    return _factory
