# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import logging
from functools import cache
from pathlib import Path
from typing import Any

from hera.workflows import DAG, ConfigMapEnvFrom, Container, CronWorkflow, S3Artifact, SecretEnvFrom, Task, Workflow
from hera.workflows.archive import NoneArchiveStrategy
from hera.workflows.models import EnvVar, SecurityContext
from pydantic import Field, SecretStr
from pydantic_settings import SettingsConfigDict

from wurzel.backend.backend import Backend
from wurzel.cli import generate_cli_call
from wurzel.step import TypedStep
from wurzel.step.settings import SettingsBase, SettingsLeaf
from wurzel.step_executor import BaseStepExecutor, PrometheusStepExecutor

log = logging.getLogger(__name__)


class S3ArtifactTemplate(SettingsLeaf):
    """Leaf settings used to define the S3 artifact configuration for input/output persistence in Argo.

    Attributes:
        bucket (str): Name of the S3 bucket used to store pipeline artifacts.
        endpoint (str): Endpoint URL of the S3-compatible storage service.

    """

    bucket: str = "wurzel-bucket"
    endpoint: str = "s3.amazonaws.com"


DNS_LABEL_REGEX = r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$"


class ArgoBackendSettings(SettingsBase):
    """Settings object for the Argo Workflows backend, configurable via environment variables.

    Environment Variables:
        Prefix: ARGOWORKFLOWBACKEND__

    Attributes:
        IMAGE (str): Docker image used to run pipeline steps.
        INLINE_STEP_SETTINGS (bool): if STEP environment variables have to get loaded based on settings and passed directly to it's step.
        SCHEDULE (str): Cron expression for scheduling the workflow.
        DATA_DIR (Path): Base directory inside the container where step data is written.
        ENCAPSULATE_ENV (bool): Whether to encapsulate step execution with environment variables.
        S3_ARTIFACT_TEMPLATE (S3ArtifactTemplate): S3 configuration used for input/output mapping.
        SERVICE_ACCOUNT_NAME (str): Kubernetes service account used for Argo workflow execution.
        SECRET_NAME (str): Name of the Kubernetes Secret passed into the workflow container.
        CONFIG_MAP (str): Name of the ConfigMap passed into the container environment.
        ANNOTATIONS (dict): Custom annotations to be applied to workflow tasks.
        NAMESPACE (str): Kubernetes namespace to run the workflow in.
        PIPELINE_NAME (str): Name of the Argo workflow pipeline (must comply with DNS label rules).

    """

    model_config = SettingsConfigDict(env_prefix="ARGOWORKFLOWBACKEND__")
    INLINE_STEP_SETTINGS: bool = False
    IMAGE: str = "ghcr.io/telekom/wurzel"
    SCHEDULE: str = "0 4 * * *"
    DATA_DIR: Path = Path("/usr/app")
    ENCAPSULATE_ENV: bool = True
    S3_ARTIFACT_TEMPLATE: S3ArtifactTemplate = S3ArtifactTemplate()
    SERVICE_ACCOUNT_NAME: str = "wurzel-service-account"
    SECRET_NAME: str = "wurzel-secret"
    CONFIG_MAP: str = "wurzel-config"
    ANNOTATIONS: dict[str, str] = {"sidecar.istio.io/inject": "false"}
    NAMESPACE: str = "argo-workflows"
    PIPELINE_NAME: str = Field(
        default="wurzel",
        max_length=63,
        description="Kubernetes-compliant name: lowercase alphanumeric, '-' allowed, must start and end with alphanumeric.",
        pattern=DNS_LABEL_REGEX,
    )


class ArgoBackend(Backend):
    """Backend implementation for generating Argo Workflow YAML using the Hera Python SDK.

    This backend converts a graph of `TypedStep` instances into a CronWorkflow definition
    with DAG-structured task execution and artifact-based I/O between steps.
    """

    def __init__(self, settings: ArgoBackendSettings | None = None, executer: type[BaseStepExecutor] = PrometheusStepExecutor) -> None:
        self.executor: type[BaseStepExecutor] = executer
        self.settings = settings if settings else ArgoBackendSettings()
        super().__init__()

    def _create_envs_from_step_settings(self, step: "TypedStep[Any, Any, Any]") -> list[EnvVar]:
        if not self.settings.INLINE_STEP_SETTINGS:
            return []

        env_vars = []

        for field_name, field_value in step.settings_class().model_dump().items():
            # Skip fields with sensitive keywords in their names
            if isinstance(field_value, SecretStr):
                log.info(f"skipped config {field_name} due to secret detection")
                continue
            # Add as Env object with uppercase name and stringified value
            if self.settings.ENCAPSULATE_ENV:
                env_vars.append(EnvVar(name=f"{step.__class__.__name__.upper()}__{field_name.upper()}", value=str(field_value)))
            else:
                env_vars.append(EnvVar(name=field_name.upper(), value=str(field_value)))

        return env_vars

    def _generate_dict(self, step: "TypedStep[Any, Any, Any]"):
        """Returns the workflow as a Python dictionary representation.

        Args:
            step (TypedStep): Root step of the pipeline.

        Returns:
            dict: Dictionary representing the Argo workflow.

        """
        return self._generate_workflow(step).to_dict()

    def generate_artifact(self, step: "TypedStep[Any, Any, Any]"):
        """Returns the workflow serialized to a valid Argo YAML definition.

        Args:
            step (TypedStep): Root step of the pipeline.

        Returns:
            str: YAML string suitable for Argo submission.

        """
        return self._generate_workflow(step).to_yaml()

    def _generate_workflow(self, step: "TypedStep[Any, Any, Any]") -> Workflow:
        """Creates a CronWorkflow with the full pipeline DAG constructed from the root step.

        Args:
            step (TypedStep): The root step to generate the workflow from.

        Returns:
            Workflow: A Hera `Workflow` object representing the pipeline.

        """
        with CronWorkflow(
            schedule=self.settings.SCHEDULE,
            name=self.settings.PIPELINE_NAME,
            entrypoint="wurzel-pipeline",
            annotations=self.settings.ANNOTATIONS,
            namespace=self.settings.NAMESPACE,
            service_account_name=self.settings.SERVICE_ACCOUNT_NAME,
        ) as w:
            self.__generate_dag(step)
        return w

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
            path=str((self.settings.DATA_DIR / step.__class__.__name__).absolute()),
            bucket=self.settings.S3_ARTIFACT_TEMPLATE.bucket,
            endpoint=self.settings.S3_ARTIFACT_TEMPLATE.endpoint,
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
                output=self.settings.DATA_DIR / step.__class__.__name__,
            ).split(" ")
            if entry.strip()
        ]

        dag.__exit__()
        env_vars = self._create_envs_from_step_settings(step)
        wurzel_call = Container(
            name=f"wurzel-run-template-{step.__class__.__name__.lower()}",
            image=self.settings.IMAGE,
            security_context=SecurityContext(run_as_non_root=True),
            command=commands,
            annotations=self.settings.ANNOTATIONS,
            inputs=inputs,
            env=env_vars,
            env_from=[
                SecretEnvFrom(prefix="", name=self.settings.SECRET_NAME, optional=True),
                ConfigMapEnvFrom(prefix="", name=self.settings.CONFIG_MAP, optional=True),
            ],
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
