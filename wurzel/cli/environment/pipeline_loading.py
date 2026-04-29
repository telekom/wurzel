# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Pipeline loading utilities for the 'env' command."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wurzel.core import TypedStep


def _ensure_pipeline_obj(pipeline: TypedStep | str):
    """Resolve pipeline argument to a WZ pipeline instance."""
    from wurzel.cli.environment.callbacks import pipeline_callback  # pylint: disable=import-outside-toplevel

    if isinstance(pipeline, str):
        return pipeline_callback(None, None, pipeline)
    return pipeline


def _load_requirements(pipeline: TypedStep | str, include_optional: bool) -> tuple[TypedStep, list, list]:
    """Load and filter environment variable requirements.

    Args:
        pipeline: Pipeline step or import path string
        include_optional: Whether to include optional environment variables

    Returns:
        Tuple of (pipeline_obj, all_requirements, filtered_requirements)
    """
    from wurzel.cli.environment import collect_env_requirements  # pylint: disable=import-outside-toplevel

    pipeline_obj = _ensure_pipeline_obj(pipeline)
    requirements = collect_env_requirements(pipeline_obj)
    filtered = requirements if include_optional else [req for req in requirements if req.required]
    return pipeline_obj, requirements, filtered
