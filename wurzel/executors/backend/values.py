# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Shared utilities for loading and merging YAML values files."""

from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from pathlib import Path
from typing import Any, TypeVar

import yaml
from pydantic import BaseModel

from wurzel.exceptions import ValuesFileError

T = TypeVar("T", bound=BaseModel)


def deep_merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge override into base."""

    def _merge(dst: dict[str, Any], src: dict[str, Any]) -> dict[str, Any]:
        merged = deepcopy(dst)
        for key, value in src.items():
            if key not in merged:
                merged[key] = value
                continue
            if isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = _merge(merged[key], value)
            else:
                merged[key] = value
        return merged

    return _merge(base, override)


def _load_values_file(path: Path) -> dict[str, Any]:
    """Load a single YAML values file."""
    if not path.exists():
        raise ValuesFileError(f"Values file '{path}' does not exist.")
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except yaml.YAMLError as exc:
        raise ValuesFileError(f"Failed to parse YAML in '{path}': {exc}") from exc
    if not isinstance(data, dict):
        raise ValuesFileError(f"Values file '{path}' must start with a mapping.")
    return data


def load_values(files: Iterable[Path], model: type[T]) -> T:
    """Load and merge YAML values files into a Pydantic model.

    Args:
        files: Iterable of paths to YAML values files.
        model: Pydantic model class to validate the merged data into.

    Returns:
        An instance of the model populated with merged values.

    """
    merged: dict[str, Any] = {}
    for file_path in files:
        file_data = _load_values_file(Path(file_path))
        merged = deep_merge_dicts(merged, file_data)
    return model.model_validate(merged or {})
