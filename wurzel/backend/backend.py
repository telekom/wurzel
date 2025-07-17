# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0


from wurzel.step.typed_step import TypedStep


class Backend:
    """Abstract base class that defines the interface for backend-specific implementations
    of pipeline step rendering.

    This class serves as a contract to standardize the generation of configuration
    artifacts (e.g., dictionaries or YAML) for various workflow orchestrators such as
    Argo Workflows, Apache Airflow, GitLab CI/CD, or DVC.

    Each backend implementation should subclass this and implement the abstract methods
    to convert a `TypedStep` into the appropriate format required by the target framework.
    """

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
