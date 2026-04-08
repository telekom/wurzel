# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wurzel.core.typed_step import TypedStep


def _allowed_raw() -> str | None:
    return os.environ.get("WURZEL_TEMPORAL_ALLOWED_STEPS")


@lru_cache(maxsize=1)
def _by_step_key() -> dict[str, type[TypedStep]]:
    from wurzel.utils import find_typed_steps_in_package  # pylint: disable=import-outside-toplevel

    discovered = find_typed_steps_in_package("wurzel.steps")
    return {f"{c.__module__}.{c.__name__}": c for c in discovered.values()}


def resolve_step_class(step_key: str) -> type[TypedStep]:
    """Map catalog ``step_key`` (``module.ClassName``) to a loaded ``TypedStep`` subclass.

    Only classes discovered under ``wurzel.steps`` at worker startup are eligible.
    Optional env ``WURZEL_TEMPORAL_ALLOWED_STEPS`` (comma-separated keys, or ``*``) further restricts.
    """
    by_key = _by_step_key()
    if step_key not in by_key:
        raise KeyError(f"unknown step_key (not in wurzel.steps discovery): {step_key}")

    raw = _allowed_raw()
    if raw is None or raw.strip() == "" or raw.strip() == "*":
        return by_key[step_key]

    allowed = {s.strip() for s in raw.split(",") if s.strip()}
    if step_key not in allowed:
        raise PermissionError(f"step not in allowlist: {step_key}")
    return by_key[step_key]
