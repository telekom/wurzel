# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Pydantic models for the branch route."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from wurzel.manifest.models import PipelineManifest


class Branch(BaseModel):
    """A named branch within a project."""

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    is_protected: bool = False
    is_default: bool = False
    promotes_to_id: uuid.UUID | None = Field(None, description="Branch this one promotes into")
    promotes_to_name: str | None = Field(None, description="Name of the promotion target branch")
    created_at: datetime
    updated_at: datetime


class CreateBranchRequest(BaseModel):
    """Request body for ``POST /v1/projects/{id}/branches``."""

    name: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9\-/]*$")
    promotes_to_id: uuid.UUID | None = Field(None, description="Branch this one promotes into")


class UpdateBranchRequest(BaseModel):
    """Request body for ``PUT /v1/projects/{id}/branches/{name}``."""

    promotes_to_id: uuid.UUID | None = None


class ProtectBranchRequest(BaseModel):
    """Request body for ``POST /v1/projects/{id}/branches/{name}/protect``."""

    is_protected: bool


class BranchManifest(BaseModel):
    """The pipeline manifest stored on a branch."""

    branch_id: uuid.UUID
    branch_name: str
    definition: PipelineManifest | None = None
    updated_at: datetime | None = None


class FieldDiff(BaseModel):
    """Diff of a single field between two branches."""

    path: str = Field(description="Dot-separated field path, e.g. 'spec.steps[0].class'")
    source_value: Any = None
    target_value: Any = None
    status: str = Field(description="'added' | 'removed' | 'changed' | 'unchanged'")


class BranchDiff(BaseModel):
    """Field-level diff between two branch manifests for the side-by-side UI."""

    source_branch: str
    target_branch: str
    source_definition: PipelineManifest | None = None
    target_definition: PipelineManifest | None = None
    diffs: list[FieldDiff] = Field(default_factory=list)
    has_conflicts: bool = False


class MergeRequest(BaseModel):
    """Request body for ``POST /{branch_name}/merge/{target_branch}``.

    The caller supplies the fully-resolved manifest after reviewing the diff.
    """

    resolved_definition: PipelineManifest


class PromoteResponse(BaseModel):
    """Response after a successful promote operation."""

    source_branch: str
    target_branch: str
    manifest_id: uuid.UUID
    message: str = "Manifest promoted successfully"
