# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Step-discovery routes.

Exposes all installed TypedStep subclasses so that a future UI can browse,
inspect, and configure any step without prior knowledge of the codebase.

Routes
------
``GET /v1/steps``                 — list all discoverable steps
``GET /v1/steps/{step_path:path}`` — full schema for a single step (settings, secrets, IO types)
"""

from __future__ import annotations

import importlib
import inspect
import logging
from typing import Any, get_args, get_type_hints

from fastapi import APIRouter, Query
from fastapi import status as http_status
from pydantic import SecretStr
from pydantic_core import PydanticUndefined

from wurzel.api.dependencies import RequireAPIKey
from wurzel.api.errors import APIError
from wurzel.api.routes.steps.data import FieldSchema, StepInfo, StepListResponse, StepSummary
from wurzel.core.meta import find_typed_steps_in_package
from wurzel.core.typed_step import TypedStep

logger = logging.getLogger(__name__)
router = APIRouter()


def _type_str(annotation: Any) -> str:
    """Return a human-readable string for an annotation."""
    if annotation is None:
        return "None"
    if hasattr(annotation, "__name__"):
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

        description = field_info.description if hasattr(field_info, "description") else None

        fields.append(
            FieldSchema(
                name=field_name,
                env_var=f"{env_prefix}{field_name}",
                type_str=_type_str(annotation),
                default=default_str,
                description=description,
                required=required,
                secret=is_secret,
            )
        )
    return fields


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


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("", response_model=StepListResponse)
async def list_steps(
    _auth: RequireAPIKey,
    package: str = Query(
        "wurzel.steps",
        description="Python package to scan for TypedStep subclasses",
    ),
) -> StepListResponse:
    """Return all TypedStep subclasses discoverable in *package*.

    Pass ``?package=my_custom_package`` to discover steps in other installed
    packages — useful for UIs that need to present user-defined steps.
    """
    try:
        found = find_typed_steps_in_package(package)
    except Exception as exc:
        raise APIError(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            title="Package not found",
            detail=f"Could not scan package '{package}': {exc}",
        ) from exc

    summaries = [
        StepSummary(
            class_path=f"{cls.__module__}.{cls.__name__}",
            name=cls.__name__,
            module=cls.__module__,
        )
        for cls in found.values()
    ]
    return StepListResponse(steps=summaries, total=len(summaries), package=package)


@router.get("/{step_path:path}", response_model=StepInfo)
async def get_step(
    step_path: str,
    _auth: RequireAPIKey,
) -> StepInfo:
    """Return the full introspection schema for a single step.

    ``step_path`` is the fully-qualified class path, e.g.
    ``wurzel.steps.splitter.SimpleSplitterStep``.
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
