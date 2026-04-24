# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Pydantic models for the ingest route."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class IngestItemInput(BaseModel):
    """A single document to ingest."""

    title: str
    content: str
    source: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class IngestRequest(BaseModel):
    """Request body for ``POST /v1/ingest``."""

    items: list[IngestItemInput] = Field(min_length=1)


class IngestJobStatus(str, Enum):
    """Lifecycle states of a bulk-ingest job."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class IngestResponse(BaseModel):
    """Immediate response returned when a bulk-ingest job is accepted."""

    job_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    status: IngestJobStatus = IngestJobStatus.PENDING
    item_count: int
    created_at: datetime = Field(default_factory=datetime.utcnow)


class IngestJobResponse(BaseModel):
    """Detailed status of a bulk-ingest job."""

    job_id: uuid.UUID
    status: IngestJobStatus
    item_count: int
    processed: int = 0
    failed: int = 0
    created_at: datetime
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    error: str | None = None
