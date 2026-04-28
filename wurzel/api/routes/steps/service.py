# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Step-discovery service layer.

All application logic for browsing and introspecting TypedStep subclasses lives
here.  The HTTP route handlers in :mod:`router` are intentionally thin and only
delegate to the public functions :func:`discover_steps` and
:func:`fetch_step_info`.
"""

from __future__ import annotations

import functools
import importlib
import importlib.util
import inspect
import logging
import threading
import time
from pathlib import Path
from typing import Annotated, Any, get_args, get_type_hints

from fastapi import Depends
from fastapi import status as http_status
from pydantic import SecretStr
from pydantic_core import PydanticUndefined

from wurzel.api.errors import APIError
from wurzel.api.routes.steps.data import FieldSchema, StepInfo, StepListResponse, StepSummary
from wurzel.core.meta import (
    find_typed_steps_from_wurzel_dependents,
    scan_path_for_typed_steps,
)
from wurzel.core.typed_step import TypedStep

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------

_CACHE_TTL: float = 300.0  # seconds


class StepListCache:
    """In-process TTL cache for step discovery results.

    Injected into routes via :func:`get_step_list_cache`.  Override in tests
    via ``app.dependency_overrides[get_step_list_cache]``.
    """

    def __init__(self, ttl: float = _CACHE_TTL) -> None:
        self._ttl = ttl
        self._data: dict[str | None, tuple[float, list[str]]] = {}
        self._lock = threading.Lock()

    def get(self, package: str | None) -> list[str] | None:
        """Return cached class paths if within TTL, else ``None``."""
        entry = self._data.get(package)
        if entry is not None and time.monotonic() - entry[0] < self._ttl:
            return entry[1]
        return None

    def set(self, package: str | None, class_paths: list[str]) -> None:
        """Store *class_paths* for *package* with the current timestamp."""
        with self._lock:
            self._data[package] = (time.monotonic(), class_paths)

    def clear(self) -> None:
        """Evict all cached entries."""
        with self._lock:
            self._data.clear()

    def warm(self) -> None:
        """Pre-populate the all-venv cache entry. Call from app lifespan.

        Uses CLI's filtering approach: only scans packages that depend on wurzel.
        """
        class_paths = find_typed_steps_from_wurzel_dependents()
        self.set(None, class_paths)
        logger.info("Step cache warmed: %d steps discovered", len(class_paths))


# Module-level singleton — overridable via dependency_overrides in tests.
_step_list_cache = StepListCache()


def get_step_list_cache() -> StepListCache:
    """FastAPI dependency — returns the module-level :class:`StepListCache` singleton."""
    return _step_list_cache


CachedStepList = Annotated[StepListCache, Depends(get_step_list_cache)]


def warm_step_cache() -> None:
    """Warm the step list cache for the default all-venv scan.

    Intended to be called from the app lifespan, typically in a background
    thread to avoid blocking startup.
    """
    _step_list_cache.warm()


# ---------------------------------------------------------------------------
# Type introspection helpers
# ---------------------------------------------------------------------------


def _public_module(cls: type) -> str:
    """Return the shortest parent-package path that publicly re-exports *cls*.

    Walks up the module hierarchy (e.g. ``wurzel.datacontract.common`` →
    ``wurzel.datacontract`` → ``wurzel``) and stops at the first level where
    ``getattr(pkg, cls.__name__) is cls`` holds.  Falls back to the defining
    ``__module__`` when no shorter path is found.
    """
    module: str = cls.__module__
    parts = module.split(".")
    for i in range(len(parts) - 1, 0, -1):
        candidate = ".".join(parts[:i])
        try:
            mod = importlib.import_module(candidate)
            if getattr(mod, cls.__name__, None) is cls:
                return candidate
        except Exception:  # pylint: disable=broad-exception-caught
            pass
    return module


def _type_str(annotation: Any) -> str:
    """Return a fully-qualified string for an annotation."""
    if annotation is None:
        return "None"
    # Check generics BEFORE __name__: GenericAlias (list[X]) proxies __name__ to the origin
    origin = getattr(annotation, "__origin__", None)
    args = getattr(annotation, "__args__", None)
    if origin is not None and args is not None:
        return f"{_type_str(origin)}[{', '.join(_type_str(a) for a in args)}]"
    if hasattr(annotation, "__name__"):
        module = getattr(annotation, "__module__", None)
        if module and module != "builtins":
            return f"{_public_module(annotation)}.{annotation.__name__}"
        return annotation.__name__
    return str(annotation)


def _io_type_str(step_cls: type[TypedStep]) -> tuple[str | None, str | None]:
    """Extract input and output type strings from a TypedStep subclass."""
    hints = get_type_hints(step_cls)
    orig_bases = getattr(step_cls, "__orig_bases__", [])
    for base in orig_bases:
        args = get_args(base)
        if len(args) >= 3:  # TypedStep[Settings, In, Out]
            in_type = args[1]
            out_type = args[2]
            return (
                None if in_type is type(None) else _type_str(in_type),  # pylint: disable=unidiomatic-typecheck
                _type_str(out_type),
            )
    # Fallback: look for annotated run() method
    run = hints.get("return")
    return None, _type_str(run) if run else None


def _build_field_schema(settings_cls: type, env_prefix: str) -> list[FieldSchema]:
    """Build the list of :class:`FieldSchema` for a settings class."""
    fields = []
    for field_name, field_info in settings_cls.model_fields.items():
        annotation = field_info.annotation
        is_secret = annotation is SecretStr or (hasattr(annotation, "__args__") and SecretStr in (get_args(annotation) or []))
        default = field_info.default
        required = default is PydanticUndefined and field_info.default_factory is None
        default_str: str | None = None
        if not required and default is not PydanticUndefined:
            default_str = str(default)

        fields.append(
            FieldSchema(
                name=field_name,
                env_var=f"{env_prefix}{field_name}",
                type_str=_type_str(annotation),
                default=default_str,
                description=field_info.description,
                required=required,
                secret=is_secret,
            )
        )
    return fields


@functools.lru_cache(maxsize=1024)
def _build_step_info(step_cls: type[TypedStep]) -> StepInfo:
    """Introspect *step_cls* and return a fully populated :class:`StepInfo`."""
    module = step_cls.__module__
    class_path = f"{module}.{step_cls.__name__}"
    in_type, out_type = _io_type_str(step_cls)

    # Resolve Settings class — TypedStep stores it as the first type arg
    settings_cls = None
    settings_class_path = None
    env_prefix = ""
    schema: list[FieldSchema] = []

    try:
        orig_bases = getattr(step_cls, "__orig_bases__", [])
        for base in orig_bases:
            args = get_args(base)
            if args:
                candidate = args[0]
                if inspect.isclass(candidate) and hasattr(candidate, "model_fields"):
                    settings_cls = candidate
                    break
    except Exception:  # pylint: disable=broad-exception-caught
        pass

    if settings_cls is not None:
        settings_class_path = f"{settings_cls.__module__}.{settings_cls.__name__}"
        env_prefix = getattr(settings_cls, "model_config", {}).get("env_prefix", "") or f"{step_cls.__name__.upper()}__"
        try:
            schema = _build_field_schema(settings_cls, env_prefix)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.debug("Could not build field schema for %s: %s", step_cls, exc)

    return StepInfo(
        class_path=class_path,
        name=step_cls.__name__,
        module=module,
        input_type=in_type,
        output_type=out_type,
        settings_class=settings_class_path,
        env_prefix=env_prefix or None,
        settings_schema=schema,
    )


@functools.lru_cache(maxsize=1024)
def _safe_io_types(class_path: str) -> tuple[str | None, str | None]:
    """Return (input_type, output_type) strings for *class_path*, or (None, None) on failure."""
    try:
        module_path, class_name = class_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        cls = getattr(module, class_name, None)
        if cls is not None and inspect.isclass(cls) and issubclass(cls, TypedStep):
            return _io_type_str(cls)
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    return None, None


def _resolve_package_root(package: str) -> Path:
    """Return the filesystem root of an installed package or raise :class:`APIError`."""
    spec = importlib.util.find_spec(package)
    if spec is None:
        raise APIError(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            title="Package not found",
            detail=f"Could not locate installed package '{package}'.",
        )
    if spec.submodule_search_locations:
        return Path(list(spec.submodule_search_locations)[0])
    if spec.origin:
        return Path(spec.origin).parent
    raise APIError(
        status_code=http_status.HTTP_400_BAD_REQUEST,
        title="Package not found",
        detail=f"Could not determine root path for package '{package}'.",
    )


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


# Framework base classes that are never user-facing steps.
_EXCLUDED_CLASS_PATHS: frozenset[str] = frozenset(
    {
        "wurzel.core.self_consuming_step.SelfConsumingLeafStep",
    }
)


def discover_steps(cache: StepListCache, package: str | None) -> StepListResponse:
    """Discover all TypedStep subclasses from wurzel-dependent packages.

    Uses the CLI's filtering approach: only scans packages that actually depend
    on wurzel, not every installed package. This matches the behavior of the
    CLI autocompletion and ensures API results are consistent with CLI results.

    Args:
        cache: TTL cache instance (injected by FastAPI dependency).
        package: Restrict scan to this installed package, or ``None`` for all wurzel-dependent packages.

    Returns:
        A :class:`StepListResponse` with summaries of every discovered step.
    """
    pkg_label = "*" if package is None else package

    class_paths = cache.get(package)
    if class_paths is None:
        if package is None:
            # Use CLI's approach: only scan packages that depend on wurzel
            class_paths = find_typed_steps_from_wurzel_dependents()
        else:
            pkg_root = _resolve_package_root(package)
            class_paths = scan_path_for_typed_steps(pkg_root, package)
        cache.set(package, class_paths)
        logger.debug("Step list cache miss for package=%r — found %d steps", pkg_label, len(class_paths))
    else:
        logger.debug("Step list cache hit for package=%r", pkg_label)

    summaries = [
        StepSummary(
            class_path=cp,
            name=cp.rsplit(".", 1)[-1],
            module=cp.rsplit(".", 1)[0],
            input_type=_safe_io_types(cp)[0],
            output_type=_safe_io_types(cp)[1],
        )
        for cp in class_paths
        if cp not in _EXCLUDED_CLASS_PATHS
    ]
    return StepListResponse(steps=summaries, total=len(summaries), package=pkg_label)


def fetch_step_info(step_path: str) -> StepInfo:
    """Import and introspect the TypedStep at *step_path*.

    Args:
        step_path: Fully-qualified class path, e.g.
            ``wurzel.steps.splitter.SimpleSplitterStep``.

    Returns:
        A fully populated :class:`StepInfo`.

    Raises:
        :class:`~wurzel.api.errors.APIError`: 400 if *step_path* is not a
            valid dotted class path; 404 if the module or class cannot be found.
    """
    parts = step_path.rsplit(".", 1)
    if len(parts) != 2:
        raise APIError(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            title="Invalid step path",
            detail="step_path must be a fully-qualified class path, e.g. 'wurzel.steps.splitter.SimpleSplitterStep'",
        )
    module_path, class_name = parts

    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        raise APIError(
            status_code=http_status.HTTP_404_NOT_FOUND,
            title="Module not found",
            detail=f"Could not import module '{module_path}': {exc}",
        ) from exc

    step_cls = getattr(module, class_name, None)
    if step_cls is None or not (inspect.isclass(step_cls) and issubclass(step_cls, TypedStep)):
        raise APIError(
            status_code=http_status.HTTP_404_NOT_FOUND,
            title="Step not found",
            detail=f"'{class_name}' is not a TypedStep in module '{module_path}'",
        )

    return _build_step_info(step_cls)
