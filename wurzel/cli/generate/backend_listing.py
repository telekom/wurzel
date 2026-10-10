# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Backend listing utilities for the 'generate' command."""

from __future__ import annotations


def get_available_backends() -> list[str]:
    """Get list of available backend names.

    Returns:
        list[str]: List of available backend names (e.g., ['dvc', 'argo'])
    """
    from wurzel.executors.backend import get_available_backends as _get_backends  # pylint: disable=import-outside-toplevel

    return list(_get_backends().keys())
