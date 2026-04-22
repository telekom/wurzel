# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0


import os
from typing import TYPE_CHECKING, Any, ClassVar

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

    Each backend implementation should subclass this and implement the ``generate_artifact``
    method to convert a `TypedStep` into the appropriate format required by the target
    framework, while also inheriting all step execution functionality from BaseStepExecutor.

    The backend implementations must set the ``WURZEL_RUN_ID`` environment variable in their
    generated artifacts. This provides a unique identifier for each pipeline run that can
    be used for Prometheus job names, logging, and other runtime identification needs.
    For Argo Workflows, this should be set to ``{{workflow.uid}}``.

    Subclasses register themselves automatically by passing ``backend_name`` as a class
    keyword argument. Once registered, ``Backend.create("name", raw_config)`` will
    instantiate the matching backend.

    ```python
    from wurzel.executors.backend.backend import Backend

    registry = Backend.get_registry()
    print("dvc" in registry)
    #> True
    ```

    Subclasses register like this (no explicit registry call needed):

    ```python
    from pathlib import Path
    from wurzel.core import TypedStep
    from wurzel.executors.backend.backend import Backend

    class MyBackend(Backend, backend_name="mybackend"):
        def generate_artifact(self, step: type[TypedStep], output: Path) -> None:
            pass  # write YAML / Makefile / … here

        @classmethod
        def from_manifest_config(cls, raw_config: dict) -> "MyBackend":
            return cls()

    print("mybackend" in Backend.get_registry())
    #> True
    ```
    """

    _registry: ClassVar[dict[str, type["Backend"]]] = {}
    backend_name: ClassVar[str] = ""

    def __init_subclass__(cls, backend_name: str = "", **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if backend_name:
            cls.backend_name = backend_name
            Backend._registry[backend_name] = cls

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

    @classmethod
    def get_registry(cls) -> dict[str, type["Backend"]]:
        """Return the mapping of registered backend names to their classes.

        Returns:
            dict[str, type[Backend]]: A copy of the registry at call time.

        """
        return dict(cls._registry)

    @classmethod
    def from_manifest_config(cls, raw_config: dict[str, Any]) -> "Backend":
        """Instantiate this backend from a raw config dict sourced from the manifest.

        Each subclass must override this to parse ``raw_config`` into its own
        typed config model and return a ready-to-use backend instance.

        Args:
            raw_config: Arbitrary key/value config from the manifest's ``backendConfig``
                block for this backend, plus any top-level manifest fields injected by
                the generator (e.g. ``schedule``).

        Raises:
            NotImplementedError: Must be implemented by subclasses.

        """
        raise NotImplementedError(f"{cls.__name__} must implement from_manifest_config()")

    @classmethod
    def create(cls, name: str, raw_config: dict[str, Any]) -> "Backend":
        """Look up ``name`` in the registry and instantiate the backend.

        Args:
            name: The registered backend name (e.g. ``"dvc"``, ``"argo"``).
            raw_config: Config dict forwarded to ``from_manifest_config``.

        Raises:
            ValueError: If ``name`` is not in the registry.

        """
        if name not in cls._registry:
            known = ", ".join(f"'{k}'" for k in sorted(cls._registry))
            raise ValueError(f"Unknown backend '{name}'. Registered backends: {known}.")
        return cls._registry[name].from_manifest_config(raw_config)

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

    def generate_artifact(self, step: TypedStep, *, env_vars: dict[str, str] | None = None) -> str:
        """Abstract method to generate a backend-specific YAML string representation of a pipeline step.

        Args:
            step (TypedStep): A step object to be serialized.
            env_vars: Optional mapping of environment variables to inject.

        Returns:
            str: A YAML-formatted string suitable for the target backend.

        Raises:
            NotImplementedError: This method must be implemented in a subclass.

        """
        raise NotImplementedError()
