# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import pytest

from wurzel.manifest.loader import ManifestLoader
from wurzel.manifest.models import PipelineManifest


class TestManifestLoader:
    def test_loads_valid_file(self, tmp_path, minimal_manifest_yaml):
        f = tmp_path / "pipeline.yaml"
        f.write_text(minimal_manifest_yaml)
        manifest = ManifestLoader.load(f)
        assert isinstance(manifest, PipelineManifest)
        assert manifest.metadata.name == "test-pipeline"

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            ManifestLoader.load(tmp_path / "nonexistent.yaml")

    def test_invalid_yaml_raises(self, tmp_path):
        f = tmp_path / "bad.yaml"
        f.write_text("key: [unclosed")
        with pytest.raises(Exception):
            ManifestLoader.load(f)

    def test_invalid_schema_raises(self, tmp_path):
        f = tmp_path / "bad.yaml"
        f.write_text("apiVersion: wurzel.dev/v1alpha1\nkind: Pipeline\nmetadata:\n  name: x\nspec:\n  backend: unknown\n  steps: []\n")
        with pytest.raises(Exception):
            ManifestLoader.load(f)

    def test_loads_full_manifest(self, tmp_path, full_manifest_yaml):
        pytest.importorskip("hera")
        f = tmp_path / "full.yaml"
        f.write_text(full_manifest_yaml)
        manifest = ManifestLoader.load(f)
        assert manifest.spec.backend == "argo"
        assert len(manifest.spec.steps) == 3
