# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Backend-neutral runtime context for Wurzel executions."""

import os
from collections.abc import Mapping
from dataclasses import dataclass

WURZEL_RUN_ID_ENV = "WURZEL_RUN_ID"
WURZEL_WORKFLOW_NAME_ENV = "WURZEL_WORKFLOW_NAME"
UNKNOWN_CONTEXT_VALUE = "unknown"


@dataclass(frozen=True)
class WurzelRuntimeContext:
    """Runtime context supplied by a Wurzel backend."""

    run_id: str = UNKNOWN_CONTEXT_VALUE
    workflow_name: str = UNKNOWN_CONTEXT_VALUE

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "WurzelRuntimeContext":
        """Build runtime context from Wurzel-owned environment variables."""
        env = environ if environ is not None else os.environ
        return cls(
            run_id=env.get(WURZEL_RUN_ID_ENV) or UNKNOWN_CONTEXT_VALUE,
            workflow_name=env.get(WURZEL_WORKFLOW_NAME_ENV) or UNKNOWN_CONTEXT_VALUE,
        )

    def metric_labels(self) -> dict[str, str]:
        """Return labels common to Wurzel runtime metrics."""
        return {
            "run_id": self.run_id,
            "workflow_name": self.workflow_name,
        }
