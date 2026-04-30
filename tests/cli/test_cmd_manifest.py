# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for the 'manifest' CLI commands (validate and generate)."""

from typer.testing import CliRunner

from wurzel.cli.cmd_manifest import app

runner = CliRunner()

MINIMAL_MANIFEST_YAML = """\
apiVersion: wurzel.dev/v1alpha1
kind: Pipeline
metadata:
  name: test-pipeline
spec:
  backend: dvc
  steps:
    - name: source
      class: wurzel.steps.manual_markdown.ManualMarkdownStep
      settings:
        FOLDER_PATH: ./data
"""

INVALID_REFS_MANIFEST_YAML = """\
apiVersion: wurzel.dev/v1alpha1
kind: Pipeline
metadata:
  name: broken-pipeline
spec:
  backend: dvc
  steps:
    - name: splitter
      class: wurzel.steps.splitter.SimpleSplitterStep
      dependsOn:
        - nonexistent-step
"""


class TestValidateManifest:
    def test_validate_valid_manifest(self, tmp_path):
        f = tmp_path / "pipeline.yaml"
        f.write_text(MINIMAL_MANIFEST_YAML)
        result = runner.invoke(app, ["validate", str(f)])
        assert result.exit_code == 0
        assert "is valid" in result.stdout

    def test_validate_missing_file(self, tmp_path):
        result = runner.invoke(app, ["validate", str(tmp_path / "nonexistent.yaml")])
        assert result.exit_code != 0

    def test_validate_invalid_yaml(self, tmp_path):
        f = tmp_path / "bad.yaml"
        f.write_text("key: [unclosed bracket")
        result = runner.invoke(app, ["validate", str(f)])
        assert result.exit_code != 0

    def test_validate_invalid_refs(self, tmp_path):
        f = tmp_path / "pipeline.yaml"
        f.write_text(INVALID_REFS_MANIFEST_YAML)
        result = runner.invoke(app, ["validate", str(f)])
        assert result.exit_code != 0

    def test_validate_invalid_schema(self, tmp_path):
        f = tmp_path / "bad.yaml"
        f.write_text(
            "apiVersion: wurzel.dev/v1alpha1\nkind: Pipeline\nmetadata:\n  name: x\nspec:\n  backend: unknown_backend\n  steps: []\n"
        )
        result = runner.invoke(app, ["validate", str(f)])
        assert result.exit_code != 0

    def test_validate_shows_help(self):
        result = runner.invoke(app, ["validate", "--help"])
        assert result.exit_code == 0
        assert "manifest" in result.stdout.lower() or "validate" in result.stdout.lower()


class TestGenerateManifest:
    def test_generate_dvc_manifest(self, tmp_path):
        f = tmp_path / "pipeline.yaml"
        f.write_text(MINIMAL_MANIFEST_YAML)
        result = runner.invoke(app, ["generate", str(f)])
        assert result.exit_code == 0
        assert "Generated" in result.stdout
        assert (tmp_path / "dvc.yaml").exists()

    def test_generate_with_custom_output(self, tmp_path):
        f = tmp_path / "pipeline.yaml"
        f.write_text(MINIMAL_MANIFEST_YAML)
        out = tmp_path / "custom_output.yaml"
        result = runner.invoke(app, ["generate", str(f), "--output", str(out)])
        assert result.exit_code == 0
        assert out.exists()

    def test_generate_missing_file(self, tmp_path):
        result = runner.invoke(app, ["generate", str(tmp_path / "nonexistent.yaml")])
        assert result.exit_code != 0

    def test_generate_invalid_yaml(self, tmp_path):
        f = tmp_path / "bad.yaml"
        f.write_text("key: [unclosed")
        result = runner.invoke(app, ["generate", str(f)])
        assert result.exit_code != 0

    def test_generate_shows_help(self):
        result = runner.invoke(app, ["generate", "--help"])
        assert result.exit_code == 0

    def test_main_help(self):
        result = runner.invoke(app, [])
        assert result.exit_code == 0
