# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Argo backend that renders workflows from YAML values."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from functools import cache
from pathlib import Path
from typing import Any, Literal

import yaml
from hera.workflows import (
    DAG,
    ConfigMapEnvFrom,
    Container,
    CronWorkflow,
    Resources,
    S3Artifact,
    SecretEnvFrom,
    SecretVolume,
    Task,
    Workflow,
)
from hera.workflows.archive import NoneArchiveStrategy
from hera.workflows.models import (
    Capabilities,
    EnvVar,
    PodSecurityContext,
    SeccompProfile,
    SecurityContext,
    VolumeMount,
)
from pydantic import BaseModel, Field

from wurzel.backend.backend import Backend
from wurzel.backend.values import load_values
from wurzel.cli import generate_cli_call
from wurzel.step import TypedStep
from wurzel.step_executor import BaseStepExecutor, PrometheusStepExecutor

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Values schema
# ---------------------------------------------------------------------------


class SecretMapping(BaseModel):
    """Mapping entry for mounting a secret key to a target value."""

    key: str
    value: str


class SecretMount(BaseModel):
    """Description of how secrets should be mounted into a container."""

    source: str = Field(..., alias="from")
    destination: Path = Field(..., alias="to")
    mappings: list[SecretMapping]


class EnvFromConfig(BaseModel):
    """Configuration for inheriting environment variables from external sources."""

    kind: Literal["secret", "configMap"] = "secret"
    name: str
    prefix: str | None = None
    optional: bool = True


class SecurityContextConfig(BaseModel):
    """Security context configuration for pods and containers.

    This supports the Kubernetes security context fields needed to satisfy
    policies like require-run-as-nonroot.
    """

    runAsNonRoot: bool = True
    runAsUser: int | None = None
    runAsGroup: int | None = None
    fsGroup: int | None = None
    fsGroupChangePolicy: Literal["OnRootMismatch", "Always"] | None = None
    supplementalGroups: list[int] = Field(default_factory=list)
    allowPrivilegeEscalation: bool | None = False
    readOnlyRootFilesystem: bool | None = None
    dropCapabilities: list[str] = Field(default_factory=lambda: ["ALL"])
    seccompProfileType: Literal["RuntimeDefault", "Localhost"] = "RuntimeDefault"
    seccompLocalhostProfile: str | None = None


class ResourcesConfig(BaseModel):
    """Container resource requests/limits using Hera's Resources API."""

    cpu_request: str = "100m"
    cpu_limit: str = "500m"
    memory_request: str = "128Mi"
    memory_limit: str = "512Mi"


class ContainerConfig(BaseModel):
    """Runtime configuration applied to workflow containers."""

    image: str = "ghcr.io/telekom/wurzel"
    env: dict[str, str] = Field(default_factory=dict)
    envFrom: list[EnvFromConfig] = Field(default_factory=list)
    secretRef: list[str] = Field(default_factory=list)
    configMapRef: list[str] = Field(default_factory=list)
    mountSecrets: list[SecretMount] = Field(default_factory=list)
    annotations: dict[str, str] = Field(default_factory=lambda: {"sidecar.istio.io/inject": "false"})
    securityContext: SecurityContextConfig = Field(default_factory=SecurityContextConfig)
    resources: ResourcesConfig = Field(default_factory=ResourcesConfig)


class S3ArtifactConfig(BaseModel):
    """Storage destination for artifacts exchanged between steps."""

    bucket: str = "wurzel-bucket"
    endpoint: str = "s3.amazonaws.com"


class WorkflowConfig(BaseModel):
    """Workflow-level defaults rendered into the Argo manifest."""

    name: str = "wurzel"
    namespace: str = "argo-workflows"
    schedule: str | None = "0 4 * * *"
    entrypoint: str = "wurzel-pipeline"
    serviceAccountName: str = "wurzel-service-account"
    dataDir: Path = Path("/usr/app")
    annotations: dict[str, str] = Field(default_factory=lambda: {"sidecar.istio.io/inject": "false"})
    container: ContainerConfig = Field(default_factory=ContainerConfig)
    artifacts: S3ArtifactConfig = Field(default_factory=S3ArtifactConfig)
    podSecurityContext: SecurityContextConfig = Field(default_factory=SecurityContextConfig)
    podSpecPatch: str | None = None


class TemplateValues(BaseModel):
    """Helm-like values file parsed into strongly typed configuration."""

    workflows: dict[str, WorkflowConfig] = Field(default_factory=dict)


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


class ArgoBackend(Backend):
    """Render Argo workflows from typed steps based on declarative YAML values."""

    @classmethod
    def is_available(cls) -> bool:
        """Check if Hera is installed."""
        from wurzel.utils import HAS_HERA  # pylint: disable=import-outside-toplevel

        return HAS_HERA

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
    def from_values(cls, files: Iterable[Path], workflow_name: str | None = None) -> ArgoBackend:
        """Instantiate the backend from values files."""
        values = load_values(files, TemplateValues)
        return cls(values=values, workflow_name=workflow_name)

    # ------------------------------------------------------------------ helpers
    def _build_secret_mounts(self) -> tuple[list[SecretVolume], list[VolumeMount]]:
        volumes: list[SecretVolume] = []
        mounts: list[VolumeMount] = []

        for idx, secret_mount in enumerate(self.config.container.mountSecrets):
            volume_name = f"secret-mount-{idx}"
            volumes.append(
                SecretVolume(
                    name=volume_name,
                    secret_name=secret_mount.source,
                    mount_path=str(secret_mount.destination),
                )
            )
            for mapping in secret_mount.mappings:
                mount_path = secret_mount.destination / mapping.value
                mounts.append(
                    VolumeMount(
                        name=volume_name,
                        mount_path=mount_path.as_posix(),
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
        for secret_name in self.config.container.secretRef:
            env_from.append(SecretEnvFrom(name=secret_name, prefix="", optional=True))
        for configmap_name in self.config.container.configMapRef:
            env_from.append(ConfigMapEnvFrom(name=configmap_name, prefix="", optional=True))
        return env_from

    def _build_pod_security_context(self) -> PodSecurityContext:
        """Build pod-level security context from configuration."""
        ctx = self.config.podSecurityContext
        return PodSecurityContext(
            run_as_non_root=ctx.runAsNonRoot,
            run_as_user=ctx.runAsUser,
            run_as_group=ctx.runAsGroup,
            fs_group=ctx.fsGroup,
            fs_group_change_policy=ctx.fsGroupChangePolicy,
            supplemental_groups=ctx.supplementalGroups or None,
            seccomp_profile=SeccompProfile(
                type=ctx.seccompProfileType,
                localhost_profile=ctx.seccompLocalhostProfile,
            ),
        )

    def _build_container_security_context(self) -> SecurityContext:
        """Build container-level security context from configuration."""
        ctx = self.config.container.securityContext
        return SecurityContext(
            run_as_non_root=ctx.runAsNonRoot,
            run_as_user=ctx.runAsUser,
            run_as_group=ctx.runAsGroup,
            allow_privilege_escalation=ctx.allowPrivilegeEscalation,
            read_only_root_filesystem=ctx.readOnlyRootFilesystem,
            capabilities=Capabilities(drop=ctx.dropCapabilities),
            seccomp_profile=SeccompProfile(
                type=ctx.seccompProfileType,
                localhost_profile=ctx.seccompLocalhostProfile,
            ),
        )

    def _build_container_resources(self) -> Resources:
        """Build container resources using Hera's Resources class."""
        res = self.config.container.resources
        return Resources(
            cpu_request=res.cpu_request,
            cpu_limit=res.cpu_limit,
            memory_request=res.memory_request,
            memory_limit=res.memory_limit,
        )

    def _build_pod_spec_patch(self) -> str | None:
        if self.config.podSpecPatch is not None:
            return self.config.podSpecPatch

        ctx = self.config.container.securityContext
        resources = self.config.container.resources

        # Init containers need readOnlyRootFilesystem: false because Argo's
        # executor runs chmod on artifact files during download, which fails
        # on a read-only filesystem. See: https://github.com/argoproj/argo-workflows/issues/14114
        init_container_patch = {
            "securityContext": {
                "runAsNonRoot": ctx.runAsNonRoot,
                "runAsUser": ctx.runAsUser,
                "runAsGroup": ctx.runAsGroup,
                "allowPrivilegeEscalation": ctx.allowPrivilegeEscalation,
                "readOnlyRootFilesystem": False,
                "capabilities": {"drop": ctx.dropCapabilities},
                "seccompProfile": {
                    "type": ctx.seccompProfileType,
                    "localhostProfile": ctx.seccompLocalhostProfile,
                },
            },
            "resources": {
                "requests": {"cpu": resources.cpu_request, "memory": resources.memory_request},
                "limits": {"cpu": resources.cpu_limit, "memory": resources.memory_limit},
            },
        }

        patch = {
            "initContainers": [
                {"name": "init", **init_container_patch},
                {"name": "wait", **init_container_patch},
            ],
        }

        return yaml.safe_dump(patch, sort_keys=False)

    def generate_artifact(self, step: TypedStep[Any, Any, Any]):
        """Return YAML manifest(s) for workflow + optional dependent resources."""
        workflow_manifest = self._generate_workflow(step).to_dict()

        return yaml.safe_dump(workflow_manifest, sort_keys=False).strip()

    def _generate_workflow(self, step: TypedStep[Any, Any, Any]) -> Workflow:
        """Creates a CronWorkflow with the full pipeline DAG constructed from the root step.

        Args:
            step (TypedStep): The root step to generate the workflow from.

        Returns:
            Workflow: A Hera `Workflow` object representing the pipeline.

        """
        workflow_kwargs = {
            "name": self.config.name,
            "namespace": self.config.namespace,
            "entrypoint": self.config.entrypoint,
            "annotations": self.config.annotations,
            "service_account_name": self.config.serviceAccountName,
            "volumes": self._volumes or None,
            "security_context": self._build_pod_security_context(),
            "pod_spec_patch": self._build_pod_spec_patch(),
        }

        if self.config.schedule:
            context = CronWorkflow(schedule=self.config.schedule, **workflow_kwargs)
        else:
            context = Workflow(**workflow_kwargs)

        with context as workflow:
            self.__generate_dag(step)
        return workflow

    @cache  # pylint: disable=method-cache-max-size-none
    def _create_artifact_from_step(self, step: TypedStep[Any, Any, Any]) -> S3Artifact:
        """Generates an S3Artifact reference for the step output.

        Args:
            step (TypedStep): The step to generate the output artifact for.

        Returns:
            S3Artifact: Hera object for artifact input/output.

        """
        # Use {{workflow.name}} to create unique artifact paths per workflow run.
        # For CronWorkflows, workflow.name includes a unique timestamp suffix (e.g., "my-workflow-1702656000").
        # This prevents data from different runs or pipelines from mixing in the same S3 location.
        return S3Artifact(
            name=f"wurzel-artifact-{step.__class__.__name__.lower()}",
            recurse_mode=True,
            archive=NoneArchiveStrategy(),
            key="{{workflow.name}}/" + step.__class__.__name__.lower(),
            path=str((self.config.dataDir / step.__class__.__name__).absolute()),
            bucket=self.config.artifacts.bucket,
            endpoint=self.config.artifacts.endpoint,
        )

    def _create_task(self, dag: DAG, step: TypedStep[Any, Any, Any]) -> Task:
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

        cli_call = generate_cli_call(
            step.__class__,
            inputs=[Path(inpt.path) for inpt in inputs if inpt.path],
            output=self.config.dataDir / step.__class__.__name__,
        )
        commands: list[str] = [entry for entry in cli_call.split(" ") if entry.strip()]

        dag.__exit__()
        env_vars = [EnvVar(name=name, value=str(value)) for name, value in self.config.container.env.items()]
        wurzel_call = Container(
            name=f"wurzel-run-template-{step.__class__.__name__.lower()}",
            image=self.config.container.image,
            security_context=self._build_container_security_context(),
            resources=self._build_container_resources(),
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

    def __generate_dag(self, step: TypedStep[Any, Any, Any]) -> DAG:
        """Recursively builds a DAG from a step and its dependencies using Hera's DAG API.

        Args:
            step (TypedStep): The root step to construct the graph from.

        Returns:
            DAG: A complete DAG with all tasks and their dependency edges.

        """

        def resolve_requirements(step: TypedStep[Any, Any, Any]) -> Task:
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
