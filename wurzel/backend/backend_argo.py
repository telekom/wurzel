# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Argo backend that renders workflows, secrets and config maps from YAML values."""

from __future__ import annotations

import logging
from copy import deepcopy
from functools import cache
from pathlib import Path
from typing import Any, Iterable, Literal

import yaml
from hera.workflows import (
    ConfigMapEnvFrom,
    Container,
    CronWorkflow,
    DAG,
    S3Artifact,
    SecretEnvFrom,
    Task,
    Volume,
    Workflow,
)
from hera.workflows.archive import NoneArchiveStrategy
from hera.workflows.models import EnvVar, SecretVolumeSource, SecurityContext, VolumeMount
from pydantic import BaseModel, Field

from wurzel.backend.backend import Backend
from wurzel.cli import generate_cli_call
from wurzel.step import TypedStep
from wurzel.step_executor import BaseStepExecutor, PrometheusStepExecutor

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Values schema
# ---------------------------------------------------------------------------


class SecretMapping(BaseModel):
    key: str
    value: str


class SecretMount(BaseModel):
    source: str = Field(..., alias="from")
    destination: Path = Field(..., alias="to")
    mappings: list[SecretMapping]


class EnvFromConfig(BaseModel):
    kind: Literal["secret", "configMap"] = "secret"
    name: str
    prefix: str | None = None
    optional: bool = True


class ContainerConfig(BaseModel):
    image: str = "ghcr.io/telekom/wurzel"
    env: dict[str, str] = Field(default_factory=dict)
    envFrom: list[EnvFromConfig] = Field(default_factory=list)
    mountSecrets: list[SecretMount] = Field(default_factory=list)
    annotations: dict[str, str] = Field(default_factory=lambda: {"sidecar.istio.io/inject": "false"})


class S3ArtifactConfig(BaseModel):
    bucket: str = "wurzel-bucket"
    endpoint: str = "s3.amazonaws.com"


class WorkflowConfig(BaseModel):
    name: str = "wurzel"
    namespace: str = "argo-workflows"
    schedule: str | None = "0 4 * * *"
    entrypoint: str = "wurzel-pipeline"
    serviceAccountName: str = "wurzel-service-account"
    dataDir: Path = Path("/usr/app")
    annotations: dict[str, str] = Field(default_factory=lambda: {"sidecar.istio.io/inject": "false"})
    container: ContainerConfig = Field(default_factory=ContainerConfig)
    artifacts: S3ArtifactConfig = Field(default_factory=S3ArtifactConfig)


class ConfigMapConfig(BaseModel):
    data: dict[str, str]


class SecretConfig(BaseModel):
    type: str = "Opaque"
    data: dict[str, str] | None = None
    stringData: dict[str, str] | None = None


class TemplateValues(BaseModel):
    workflows: dict[str, WorkflowConfig] = Field(default_factory=dict)
    configMaps: dict[str, ConfigMapConfig] = Field(default_factory=dict)
    secrets: dict[str, SecretConfig] = Field(default_factory=dict)


def deep_merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge override into base."""

    def _merge(dst: dict[str, Any], src: dict[str, Any]) -> dict[str, Any]:
        merged = deepcopy(dst)
        for key, value in src.items():
            if key not in merged:
                merged[key] = value
                continue
            if isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = _merge(merged[key], value)
            else:
                merged[key] = value
        return merged

    return _merge(base, override)


def _load_values_file(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
        if not isinstance(data, dict):
            raise ValueError(f"Values file '{path}' must start with a mapping.")
        return data


def load_values(files: Iterable[Path]) -> TemplateValues:
    """Load and merge Helm-like values files."""
    merged: dict[str, Any] = {}
    for file_path in files:
        file_data = _load_values_file(Path(file_path))
        merged = deep_merge_dicts(merged, file_data)
    return TemplateValues.model_validate(merged or {})


def select_workflow(values: TemplateValues, workflow_name: str | None) -> WorkflowConfig:
    """Select a workflow configuration either by name or falling back to the first entry."""
    if workflow_name:
        try:
            return values.workflows[workflow_name]
        except KeyError as exc:  # pragma: no cover - validated via tests
            raise ValueError(f"workflow '{workflow_name}' not found in values") from exc
    if values.workflows:
        first_key = next(iter(values.workflows))
        return values.workflows[first_key]
    return WorkflowConfig()


def build_configmap_manifest(name: str, config: ConfigMapConfig) -> dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {"name": name},
        "data": config.data,
    }


def build_secret_manifest(name: str, config: SecretConfig) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {"name": name},
        "type": config.type,
    }
    if config.data:
        manifest["data"] = config.data
    if config.stringData:
        manifest["stringData"] = config.stringData
    return manifest


class ArgoBackend(Backend):
    """Render Argo workflows from typed steps based on declarative YAML values."""

    def __init__(
        self,
        config: WorkflowConfig | None = None,
        *,
        values: TemplateValues | None = None,
        workflow_name: str | None = None,
        executor: type[BaseStepExecutor] = PrometheusStepExecutor,
    ) -> None:
        super().__init__()
        self.executor: type[BaseStepExecutor] = executor
        self.values = values or TemplateValues()
        self.config = config or select_workflow(self.values, workflow_name)
        self._volumes, self._volume_mounts = self._build_secret_mounts()

    @classmethod
    def from_values(cls, files: Iterable[Path], workflow_name: str | None = None) -> "ArgoBackend":
        """Instantiate the backend from values files."""
        values = load_values(files)
        return cls(values=values, workflow_name=workflow_name)

    # ------------------------------------------------------------------ helpers
    def _build_secret_mounts(self) -> tuple[list[Volume], list[VolumeMount]]:
        volumes: list[Volume] = []
        mounts: list[VolumeMount] = []

        for idx, secret_mount in enumerate(self.config.container.mountSecrets):
            volume_name = f"secret-mount-{idx}"
            volumes.append(
                Volume(
                    name=volume_name,
                    secret=SecretVolumeSource(secret_name=secret_mount.source),
                )
            )
            for mapping in secret_mount.mappings:
                mount_path = secret_mount.destination / mapping.value
                mounts.append(
                    VolumeMount(
                        name=volume_name,
                        mount_path=str(mount_path),
                        sub_path=mapping.key,
                    )
                )

        return volumes, mounts

    def _build_env_from(self) -> list[ConfigMapEnvFrom | SecretEnvFrom]:
        env_from: list[ConfigMapEnvFrom | SecretEnvFrom] = []
        for value in self.config.container.envFrom:
            prefix = value.prefix or ""
            if value.kind == "configMap":
                env_from.append(ConfigMapEnvFrom(name=value.name, prefix=prefix, optional=value.optional))
            else:
                env_from.append(SecretEnvFrom(name=value.name, prefix=prefix, optional=value.optional))
        return env_from

    def generate_artifact(self, step: "TypedStep[Any, Any, Any]"):
        """Return YAML manifest(s) for workflow + optional dependent resources."""
        workflow_manifest = self._generate_workflow(step).to_dict()

        manifests: list[dict[str, Any]] = []
        if self.values.configMaps:
            manifests.extend(build_configmap_manifest(name, cfg) for name, cfg in self.values.configMaps.items())
        if self.values.secrets:
            manifests.extend(build_secret_manifest(name, cfg) for name, cfg in self.values.secrets.items())

        manifests.append(workflow_manifest)
        return yaml.safe_dump_all(manifests, sort_keys=False).strip()

    def _generate_workflow(self, step: "TypedStep[Any, Any, Any]") -> Workflow:
        """Creates a CronWorkflow with the full pipeline DAG constructed from the root step.

        Args:
            step (TypedStep): The root step to generate the workflow from.

        Returns:
            Workflow: A Hera `Workflow` object representing the pipeline.

        """
        workflow_kwargs = dict(
            name=self.config.name,
            namespace=self.config.namespace,
            entrypoint=self.config.entrypoint,
            annotations=self.config.annotations,
            service_account_name=self.config.serviceAccountName,
            volumes=self._volumes or None,
        )

        if self.config.schedule:
            context = CronWorkflow(schedule=self.config.schedule, **workflow_kwargs)
        else:
            context = Workflow(**workflow_kwargs)

        with context as workflow:
            self.__generate_dag(step)
        return workflow

    @cache  # pylint: disable=method-cache-max-size-none
    def _create_artifact_from_step(self, step: "TypedStep[Any, Any, Any]") -> S3Artifact:
        """Generates an S3Artifact reference for the step output.

        Args:
            step (TypedStep): The step to generate the output artifact for.

        Returns:
            S3Artifact: Hera object for artifact input/output.

        """
        return S3Artifact(
            name=f"wurzel-artifact-{step.__class__.__name__.lower()}",
            mode=775,
            recurse_mode=True,
            archive=NoneArchiveStrategy(),
            key=step.__class__.__name__.lower(),
            path=str((self.config.dataDir / step.__class__.__name__).absolute()),
            bucket=self.config.artifacts.bucket,
            endpoint=self.config.artifacts.endpoint,
        )

    def _create_task(self, dag: DAG, step: "TypedStep[Any, Any, Any]") -> Task:
        """Creates an Argo task for a Wurzel step, linking input/output artifacts and environment.

        Args:
            dag (DAG): The DAG object to add the task to.
            step (TypedStep): The step to convert to an Argo Task.

        Returns:
            Task: The configured Hera Task instance.

        """
        if step.required_steps:
            inputs = [self._create_artifact_from_step(req) for req in step.required_steps]
        else:
            inputs = []

        commands: list[str] = [
            entry
            for entry in generate_cli_call(
                step.__class__,
                inputs=[Path(inpt.path) for inpt in inputs if inpt.path],
                output=self.config.dataDir / step.__class__.__name__,
            ).split(" ")
            if entry.strip()
        ]

        dag.__exit__()
        env_vars = [EnvVar(name=name, value=str(value)) for name, value in self.config.container.env.items()]
        wurzel_call = Container(
            name=f"wurzel-run-template-{step.__class__.__name__.lower()}",
            image=self.config.container.image,
            security_context=SecurityContext(run_as_non_root=True),
            command=commands,
            annotations=self.config.container.annotations,
            inputs=inputs,
            env=env_vars,
            env_from=self._build_env_from(),
            volume_mounts=self._volume_mounts or None,
            outputs=self._create_artifact_from_step(step),
        )

        dag.__enter__()  # pylint: disable=unnecessary-dunder-call

        input_refs = [self._create_artifact_from_step(req) for req in step.required_steps]
        task = wurzel_call(
            name=step.__class__.__name__.lower(),
            arguments=input_refs,
        )

        if not isinstance(task, Task):
            raise RuntimeError(f"Expected Task from Container call, got {type(task)}")

        return task

    def __generate_dag(self, step: "TypedStep[Any, Any, Any]") -> DAG:
        """Recursively builds a DAG from a step and its dependencies using Hera's DAG API.

        Args:
            step (TypedStep): The root step to construct the graph from.

        Returns:
            DAG: A complete DAG with all tasks and their dependency edges.

        """

        def resolve_requirements(step: "TypedStep[Any, Any, Any]") -> Task:
            artifacts = []
            argo_reqs: list[Task] = []

            for req in step.required_steps:
                if req.required_steps:
                    req_argo = resolve_requirements(req)  # type: ignore[arg-type]
                else:
                    req_argo = self._create_task(dag, req)  # type: ignore[arg-type]
                artifacts.append(req_argo.result)
                argo_reqs.append(req_argo)

            step_argo: Task = self._create_task(dag, step)

            for argo_req in argo_reqs:
                argo_req >> step_argo  # pylint: disable=pointless-statement

            return step_argo

        with DAG(name="wurzel-pipeline") as dag:
            resolve_requirements(step)

        return dag
