# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0


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
