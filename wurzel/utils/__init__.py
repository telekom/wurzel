# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from . import semantic_splitter
from .meta_settings import WZ, create_model
from .meta_steps import find_typed_steps_in_package

__all__ = [
    "semantic_splitter",
    "WZ",
    "create_model",
    "try_get_length",
    "find_typed_steps_in_package",
]


def try_get_length(x) -> int:
    """Tries to get length, return 1 if fails

    Args:
        x (Any): get length of

    Returns:
        int: length or 1
    """
    try:
        return len(x)
    # pylint: disable=bare-except
    except:
        return 1
