# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Load a pipeline manifest from a YAML file."""

from pathlib import Path

import yaml

from wurzel.manifest.models import PipelineManifest


class ManifestLoader:
    """Loads and deserializes pipeline manifests from YAML files."""

    @staticmethod
    def load(path: Path) -> PipelineManifest:
        """Deserialize a YAML file into a validated PipelineManifest.

        Raises:
            FileNotFoundError: If the file does not exist.
            yaml.YAMLError: If the file is not valid YAML.
            pydantic.ValidationError: If the data does not match the schema.
        """
        if not path.exists():
            raise FileNotFoundError(f"Manifest file not found: {path}")

        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        return PipelineManifest.model_validate(raw)
