# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from wurzel.utils import HAS_HERA

from .backend import Backend
from .backend_dvc import DvcBackend

__all__ = ["Backend", "DvcBackend", "get_all_backends", "get_available_backends", "get_backend_by_name"]

if HAS_HERA:
    from .backend_argo import ArgoBackend  # noqa: F401

    __all__.append("ArgoBackend")


def get_all_backends() -> dict[str, type[Backend]]:
    """Get all registered backends (regardless of availability).

    Returns:
        dict[str, type[Backend]]: Mapping of backend name to backend class.

    """
    backends: dict[str, type[Backend]] = {"DvcBackend": DvcBackend}
    if HAS_HERA:
        backends["ArgoBackend"] = ArgoBackend
    return backends


def get_available_backends() -> dict[str, type[Backend]]:
    """Get all backends that have their dependencies installed.

    Returns:
        dict[str, type[Backend]]: Mapping of backend name to backend class for available backends.

    """
    return {name: cls for name, cls in get_all_backends().items() if cls.is_available()}


def get_backend_by_name(name: str) -> type[Backend] | None:
    """Get a backend class by name (case-insensitive).

    Args:
        name: Backend name (e.g., 'DvcBackend', 'ArgoBackend')

    Returns:
        Backend class if found and available, None otherwise.

    """
    available = get_available_backends()
    name_lower = name.lower()
    for backend_name, backend_cls in available.items():
        if backend_name.lower() == name_lower:
            return backend_cls
    return None
