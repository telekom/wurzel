# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from typing import Any

from . import semantic_splitter
from .meta_settings import WZ, create_model
from .meta_steps import find_typed_steps_in_package
from .to_markdown.html2md import to_markdown

__all__ = [
    "semantic_splitter",
    "WZ",
    "create_model",
    "try_get_length",
    "find_typed_steps_in_package",
    "to_markdown",
]


def try_get_length(x: Any) -> int:
    """Tries to get length, return 1 if fails

    Args:
        x (Any): get length of

    Returns:
        int: length or 1
    """
    try:
        return len(x)
    # pylint: disable=bare-except
    except:  # noqa: E722
        return 1
