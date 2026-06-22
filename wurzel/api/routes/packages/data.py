# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Pydantic models for the packages and secrets routes."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AddPackageRequest(BaseModel):
    """Request body for ``POST /v1/projects/{project_id}/packages``."""

    package_spec: str = Field(
        ...,
        description=("PEP 508 dependency specifier, e.g. 'mypkg==1.0.0'. Must not contain shell metacharacters."),
    )
    index_secret_name: str | None = Field(
        None,
        description=(
            "Name of a project secret whose value is the private PyPI index URL "
            "(including credentials).  The secret must already exist in the project "
            "before the package can be installed."
        ),
    )


class PackageResponse(BaseModel):
    """A single project package row."""

    id: uuid.UUID
    project_id: uuid.UUID
    package_spec: str
    index_secret_name: str | None = None
    status: str
    error: str | None = None
    installed_at: datetime | None = None
    created_at: datetime
    created_by: str


class SecretRequest(BaseModel):
    """Request body for ``PUT /v1/projects/{project_id}/secrets/{secret_name}``."""

    value: str = Field(..., description="Plaintext secret value (e.g. a private PyPI index URL).")


class SecretMetaResponse(BaseModel):
    """Secret metadata — the ``value`` field is intentionally omitted."""

    id: uuid.UUID
    name: str
    created_at: datetime
    updated_at: datetime
