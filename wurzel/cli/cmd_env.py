# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0
"""Helpers for CLI environment commands."""

from __future__ import annotations

from json import dumps
from types import NoneType
from typing import TYPE_CHECKING

from pydantic import BaseModel, SecretStr, ValidationError
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined

if TYPE_CHECKING:  # pragma: no cover - typing imports only
    from wurzel.step import TypedStep


class EnvVarRequirement(BaseModel):
    """Represents a single environment variable requirement for a step."""

    env_var: str
    step_name: str
    field_name: str
    required: bool
    default: str
    description: str | None
    step_index: int
    field_index: int


class EnvValidationIssue(BaseModel):
    """Represents a validation issue for an environment variable."""

    env_var: str
    message: str


def _format_default_value(field: FieldInfo) -> str:
    default = field.get_default(call_default_factory=True)
    if default is PydanticUndefined or default is None:
        return ""
    if isinstance(default, SecretStr):
        return "***"
    if isinstance(default, (list, dict, set, tuple)):
        return dumps(default)
    return str(default)


def collect_env_requirements(pipeline: TypedStep) -> list[EnvVarRequirement]:
    """Collect environment requirements for all steps in a pipeline."""
    requirements: list[EnvVarRequirement] = []
    ordered_steps = sorted(pipeline.traverse(), key=lambda stp: stp.__class__.__name__)
    for step_index, step in enumerate(ordered_steps):
        settings_cls = step.settings_class
        if settings_cls in (None, NoneType):
            continue
        prefix = step.__class__.__name__.upper()
        for field_index, (field_name, field) in enumerate(settings_cls.model_fields.items()):
            env_var = f"{prefix}__{field_name}"
            requirements.append(
                EnvVarRequirement(
                    env_var=env_var,
                    step_name=step.__class__.__name__,
                    field_name=field_name,
                    required=field.is_required(),
                    default=_format_default_value(field),
                    description=field.description,
                    step_index=step_index,
                    field_index=field_index,
                )
            )
    return sorted(requirements, key=lambda req: (req.step_index, req.field_index))


def format_env_snippet(requirements: list[EnvVarRequirement]) -> str:
    """Return .env-style representation of requirements grouped by step."""
    lines: list[str] = ["# Generated env vars"]
    current_step = None
    for req in requirements:
        if req.step_name != current_step:
            lines.append("")
            lines.append(f"# {req.step_name}")
            current_step = req.step_name
        default = req.default
        if not default:
            default = ""
        lines.append(f"{req.env_var}={default}")
    lines.append("")
    return "\n".join(lines) + "\n"


def validate_env_vars(pipeline: TypedStep, allow_extra_fields: bool) -> list[EnvValidationIssue]:
    """Validate that all required env vars are present for the pipeline."""
    from wurzel.executors.base_executor import BaseStepExecutor  # pylint: disable=import-outside-toplevel
    from wurzel.utils import create_model  # pylint: disable=import-outside-toplevel

    # BaseStepExecutor.is_allow_extra_settings already checks env var, so reuse when None supplied
    allow_extra = allow_extra_fields or BaseStepExecutor.is_allow_extra_settings()
    settings_model = create_model(list(pipeline.traverse()), allow_extra_fields=allow_extra)

    try:
        settings_model()
        return []
    except ValidationError as err:  # pragma: no cover - exercised via CLI tests
        issues: list[EnvValidationIssue] = []
        for error in err.errors():
            loc = error.get("loc", ())
            env_var = "__".join(str(part) for part in loc if part)
            if not env_var:
                env_var = error.get("type", "validation_error")
            issues.append(EnvValidationIssue(env_var=env_var, message=error.get("msg", error["type"])))
        return issues
