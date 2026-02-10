# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0


import os
from typing import TYPE_CHECKING

from wurzel.core.typed_step import TypedStep
from wurzel.executors.base_executor import BaseStepExecutor

if TYPE_CHECKING:  # pragma: no cover - only used for type checking
    from wurzel.executors.middlewares.base import BaseMiddleware


class Backend(BaseStepExecutor):
    """Abstract base class that defines the interface for backend-specific implementations
    of pipeline step rendering.

    This class inherits from BaseStepExecutor, combining step execution capabilities with
    the ability to generate deployment artifacts (e.g., YAML configurations) for various
    workflow orchestrators such as Argo Workflows, Apache Airflow, GitLab CI/CD, or DVC.

    Each backend implementation should subclass this and implement the generate_artifact method
    to convert a `TypedStep` into the appropriate format required by the target framework,
    while also inheriting all step execution functionality from BaseStepExecutor.

    The backend implementations must set the WURZEL_RUN_ID environment variable in their
    generated artifacts. This provides a unique identifier for each pipeline run that can
    be used for Prometheus job names, logging, and other runtime identification needs.
    For Argo Workflows, this should be set to {{workflow.uid}}.
    """

    def __init__(
        self,
        executer: type[BaseStepExecutor] | None = None,
        *,
        dont_encapsulate: bool = False,
        middlewares: list[str] | list["BaseMiddleware"] | None = None,
        load_middlewares_from_env: bool = False,
    ) -> None:
        super().__init__(
            dont_encapsulate=dont_encapsulate,
            middlewares=middlewares,
            load_middlewares_from_env=load_middlewares_from_env,
        )
        self.executor: type[BaseStepExecutor] | None = executer

    @property
    def run_id(self) -> str:
        """Get the unique run ID for the current pipeline execution.

        This ID is set by the workflow orchestrator via the WURZEL_RUN_ID environment variable.
        For Argo Workflows, this is typically the workflow.uid.
        For DVC, this is generated at pipeline execution time.

        Returns:
            str: The unique run ID, or empty string if not set.

        """
        return os.environ.get("WURZEL_RUN_ID", "")

    @classmethod
    def is_available(cls) -> bool:
        """Check if this backend's dependencies are installed.

        Returns:
            bool: True if the backend is available, False otherwise.

        """
        return True

    def generate_artifact(self, step: TypedStep) -> str:
        """Abstract method to generate a backend-specific YAML string representation of a pipeline step.

        Args:
            step (TypedStep): A step object to be serialized.

        Returns:
            str: A YAML-formatted string suitable for the target backend.

        Raises:
            NotImplementedError: This method must be implemented in a subclass.

        """
        raise NotImplementedError()
