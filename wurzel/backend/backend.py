# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

import yaml

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

    def generate_dict(self, step: TypedStep) -> dict:
        """Abstract method to generate a backend-specific dictionary representation of a pipeline step.

        Args:
            step (TypedStep): A step object representing an atomic unit of work in the pipeline.

        Returns:
            dict: A dictionary representing the step, tailored to the specific backend.

        Raises:
            NotImplementedError: This method must be implemented in a subclass.

        """
        raise NotImplementedError()

    def generate_yaml(self, step: TypedStep) -> str:
        """Abstract method to generate a backend-specific YAML string representation of a pipeline step.

        Args:
            step (TypedStep): A step object to be serialized.

        Returns:
            str: A YAML-formatted string suitable for the target backend.

        Raises:
            NotImplementedError: This method must be implemented in a subclass.

        """
        raise NotImplementedError()

    @classmethod
    def save_yaml(cls, yml: str, file: Path):
        """Writes the given YAML content to a file.

        This utility method is useful for persisting the rendered pipeline configuration
        (in YAML format) to disk, so that it can be used by the pipeline execution system.

        Args:
            yml (str): YAML string to be written.
            file (Path): Path object representing the destination file location.

        Note:
            This method uses UTF-8 encoding and dumps the string using PyYAML.

        """
        file.write_text(yaml.dump(yml), encoding="utf-8")
