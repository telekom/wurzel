# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Pydantic models for the step-discovery route."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FieldSchema(BaseModel):
    """Schema description of a single settings field.

    Gives a UI everything it needs to render an editable form field —
    including whether the value is a secret (rendered as a password input).
    """

    name: str = Field(description="Python field name, e.g. 'TOKEN'")
    env_var: str = Field(description="Full environment variable name, e.g. 'SCRAPERAPI__TOKEN'")
    type_str: str = Field(description="Human-readable type annotation, e.g. 'SecretStr'")
    default: str | None = Field(None, description="Default value as string; None means required")
    description: str | None = Field(None, description="Field documentation string")
    required: bool = Field(description="True when no default is provided")
    secret: bool = Field(False, description="True when the field holds a SecretStr value")


class StepInfo(BaseModel):
    """Full introspection of a single TypedStep class."""

    class_path: str = Field(description="Fully-qualified class path, e.g. 'wurzel.steps.splitter.SimpleSplitterStep'")
    name: str = Field(description="Class name")
    module: str = Field(description="Module path")
    input_type: str | None = Field(None, description="Fully-qualified input contract type, or None for source steps")
    output_type: str | None = Field(None, description="Fully-qualified output contract type")
    settings_class: str | None = Field(None, description="Fully-qualified settings class path")
    env_prefix: str | None = Field(None, description="Environment variable prefix for this step's settings")
    settings_schema: list[FieldSchema] = Field(default_factory=list, description="Schema of all settings fields")


class StepSummary(BaseModel):
    """Lightweight step entry for the list endpoint."""

    class_path: str
    name: str
    module: str


class StepListResponse(BaseModel):
    """Response envelope for ``GET /v1/steps``."""

    steps: list[StepSummary]
    total: int
    package: str
