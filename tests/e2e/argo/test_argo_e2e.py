# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""End-to-end test: manifest → Argo Workflow generation and execution on k3d.

Run locally (requires the wurzel-argo-e2e k3d cluster to be up):

    ARGO_E2E=1 uv run pytest tests/e2e/argo/ -v

In CI this file is invoked by .github/workflows/test-argo-e2e.yaml which
sets ARGO_E2E=1 after setting up the cluster and loading the Docker image.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import pytest
import yaml

# Skip the whole module unless ARGO_E2E is explicitly set.
if not os.getenv("ARGO_E2E"):
    pytest.skip("Set ARGO_E2E=1 to run Argo end-to-end tests", allow_module_level=True)

# Hera must be available for the Argo backend.
pytest.importorskip("hera", reason="hera package required for Argo e2e tests")

from wurzel.manifest.generator import ManifestGenerator  # noqa: E402
from wurzel.manifest.loader import ManifestLoader  # noqa: E402

FIXTURES_DIR = Path(__file__).parent / "fixtures"
MANIFEST_PATH = FIXTURES_DIR / "pipeline.yaml"

# k3d context used for all kubectl / argo CLI calls.
K3D_CONTEXT = os.getenv("ARGO_E2E_CONTEXT", "k3d-wurzel-argo-e2e")
ARGO_NAMESPACE = os.getenv("ARGO_E2E_NAMESPACE", "argo")

# How long (seconds) to wait for the workflow to reach a terminal state.
WORKFLOW_TIMEOUT = int(os.getenv("ARGO_E2E_TIMEOUT", "180"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _kubectl(*args: str) -> subprocess.CompletedProcess:
    cmd = ["kubectl", "--context", K3D_CONTEXT, "-n", ARGO_NAMESPACE, *args]
    return subprocess.run(cmd, capture_output=True, text=True, check=True)


def _workflow_phase(name: str) -> str:
    """Return the current phase of an Argo Workflow (e.g. Running, Succeeded, Failed)."""
    result = _kubectl(
        "get",
        "workflow",
        name,
        "-o",
        "jsonpath={.status.phase}",
    )
    return result.stdout.strip()


def _wait_for_workflow(name: str, timeout: int = WORKFLOW_TIMEOUT) -> str:
    """Poll until the workflow reaches a terminal phase or the timeout expires."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        phase = _workflow_phase(name)
        if phase in ("Succeeded", "Failed", "Error"):
            return phase
        time.sleep(5)
    raise TimeoutError(f"Workflow '{name}' did not finish within {timeout}s. Last phase: {_workflow_phase(name)}")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestArgoManifestGeneration:
    """Tests that ManifestGenerator produces valid Argo Workflow YAML."""

    def test_generates_valid_yaml(self, tmp_path: Path) -> None:
        """ManifestGenerator must produce parseable YAML for the e2e manifest."""
        manifest = ManifestLoader.load(MANIFEST_PATH)
        output = tmp_path / "workflow.yaml"
        ManifestGenerator(manifest).generate(output)
        assert output.exists(), "generate() must write the output file"
        doc = yaml.safe_load(output.read_text())
        assert doc is not None
        assert doc.get("apiVersion") == "argoproj.io/v1alpha1"

    def test_generates_plain_workflow_not_cron(self, tmp_path: Path) -> None:
        """schedule: null in the manifest must produce a Workflow, not a CronWorkflow."""
        manifest = ManifestLoader.load(MANIFEST_PATH)
        output = tmp_path / "workflow.yaml"
        ManifestGenerator(manifest).generate(output)
        doc = yaml.safe_load(output.read_text())
        assert doc.get("kind") == "Workflow", "schedule: null must produce kind: Workflow, not CronWorkflow"

    def test_dag_contains_manualmarkdownstep(self, tmp_path: Path) -> None:
        """The generated DAG must contain a task for ManualMarkdownStep."""
        manifest = ManifestLoader.load(MANIFEST_PATH)
        output = tmp_path / "workflow.yaml"
        ManifestGenerator(manifest).generate(output)
        raw = output.read_text()
        assert "manualmarkdownstep" in raw.lower(), "Generated workflow must reference the ManualMarkdownStep container"

    def test_workflow_name_and_namespace(self, tmp_path: Path) -> None:
        """Name and namespace from backendConfig must appear in the generated workflow."""
        manifest = ManifestLoader.load(MANIFEST_PATH)
        output = tmp_path / "workflow.yaml"
        ManifestGenerator(manifest).generate(output)
        doc = yaml.safe_load(output.read_text())
        meta = doc.get("metadata", {})
        assert meta.get("name") == "wurzel-e2e-test"
        assert meta.get("namespace") == "argo"

    def test_env_var_from_settings_in_generated_workflow(self, tmp_path: Path) -> None:
        """Step settings must be expanded to env vars in the generated container spec."""
        manifest = ManifestLoader.load(MANIFEST_PATH)
        output = tmp_path / "workflow.yaml"
        ManifestGenerator(manifest).generate(output)
        raw = output.read_text()
        # The step setting FOLDER_PATH should appear as an env var
        assert "MANUALMARKDOWNSTEP__FOLDER_PATH" in raw


class TestArgoWorkflowExecution:
    """Tests that a generated workflow can be submitted and runs successfully on the cluster."""

    @pytest.fixture(autouse=True)
    def _generated_workflow(self, tmp_path: Path) -> Path:
        """Generate the workflow YAML once for the execution tests."""
        manifest = ManifestLoader.load(MANIFEST_PATH)
        out = tmp_path / "workflow.yaml"
        ManifestGenerator(manifest).generate(out)
        self._workflow_yaml_path = out
        return out

    def test_workflow_applies_to_cluster(self) -> None:
        """Kubectl apply must succeed for the generated workflow YAML."""
        result = _kubectl("apply", "-f", str(self._workflow_yaml_path))
        assert result.returncode == 0, f"kubectl apply failed:\n{result.stderr}"

    def test_workflow_runs_to_success(self) -> None:
        """The submitted workflow must reach Succeeded within the timeout."""
        # Apply (idempotent if already applied by the previous test)
        _kubectl("apply", "-f", str(self._workflow_yaml_path))

        # Discover the actual workflow name (may have had a generateName suffix in the past
        # but our fixture uses a fixed name "wurzel-e2e-test").
        workflow_name = "wurzel-e2e-test"

        phase = _wait_for_workflow(workflow_name, timeout=WORKFLOW_TIMEOUT)
        assert phase == "Succeeded", (
            f"Workflow reached phase '{phase}' instead of 'Succeeded'. Check `argo logs -n argo wurzel-e2e-test` for details."
        )
