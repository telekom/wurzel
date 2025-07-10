# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

from hera.workflows import DAG, ConfigMapEnvFrom, Container, CronWorkflow, S3Artifact, SecretEnvFrom, Task, Workflow
from hera.workflows.archive import NoneArchiveStrategy
from hera.workflows.models import S3Artifact as S3ArtifactTemplate
from hera.workflows.models import SecurityContext
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from wurzel.backend.backend import Backend
from wurzel.cli import generate_cli_call
from wurzel.step import TypedStep
from wurzel.step_executor import BaseStepExecutor, PrometheusStepExecutor


class ArgoBackendSettings(BaseSettings):
    """Settings object which is infusable through ENV variables like ARGOWORKFLOWBACKEND__ENCAPSULATE_ENV."""

    model_config = SettingsConfigDict(env_prefix="ARGOWORKFLOWBACKEND__")
    IMAGE: str = "ghcr.io/telekom/wurzel"
    SCHEDULE: str = "0 4 * * *"
    DATA_DIR: Path = Path("/usr/app")
    ENCAPSULATE_ENV: bool = True
    S3_ARTIFACT_TEMPLATE: S3ArtifactTemplate = Field(
        S3ArtifactTemplate(
            bucket="wurzel-bucket",  # "oneai-nonprod-pipelines",
            endpoint="s3.amazonaws.com",
        )
    )
    SERVICE_ACCOUNT_NAME: str = "wurzel-service-account"
    SECRET_NAME: str = "wurzel-secret"
    CONFIG_MAP: str = "wurzel-config"
    ANNOTATIONS: dict = {"sidecar.istio.io/inject": "false"}
    NAMESPACE: str = "argo-workflows"
    PIPELINE_SUFFIX: str = ""

    @field_validator("S3_ARTIFACT_TEMPLATE", mode="plain")
    @classmethod
    def validate_s3_artifact_template(cls, value) -> S3ArtifactTemplate:
        """Spetial validator  is needed because hera is based on pytantic v1."""
        if isinstance(value, S3ArtifactTemplate):
            return value
        if isinstance(value, dict):
            return S3ArtifactTemplate(**value)
        raise TypeError("S3_ARTIFACT_TEMPLATE must be a dict or S3ArtifactTemplate instance")


class ArgoBackend(Backend):
    """ArgoBackend is the wurzel backend using ArgoWorklow. The current implementation is an abstraction
    above 'hera' library.
    """

    def __init__(self, settings: ArgoBackendSettings | None = None, executer: BaseStepExecutor = PrometheusStepExecutor) -> None:
        self.executor: type[BaseStepExecutor] = executer
        self.settings = settings if settings else ArgoBackendSettings()

        super().__init__()

    def generate_dict(self, step: TypedStep):
        return self._generate_workflow(step).to_dict()

    def generate_yaml(self, step: TypedStep):
        return self._generate_workflow(step).to_yaml()

    def _generate_workflow(self, step: type[TypedStep]) -> Workflow:
        with CronWorkflow(
            schedule=self.settings.SCHEDULE,
            name=f"wurzel_{self.settings.PIPELINE_SUFFIX}"[:200].strip(" ,-_+"),  # kubernetes name cleanup
            entrypoint="wurzel-pipeline",
            annotations=self.settings.ANNOTATIONS,
            namespace=self.settings.NAMESPACE,
        ) as w:
            self.__generate_dag(step)
        return w

    def _create_artifact_from_step(self, step: type[TypedStep]) -> S3Artifact:
        return S3Artifact(
            name="wurzel-artifact",
            mode=775,
            recurse_mode=True,
            archive=NoneArchiveStrategy(),
            key=step.__class__.__name__.lower(),
            path=(self.settings.DATA_DIR / step.__class__.__name__).as_posix(),
            bucket=self.settings.S3_ARTIFACT_TEMPLATE.bucket,  # pylint: disable=no-member
            endpoint=self.settings.S3_ARTIFACT_TEMPLATE.endpoint,  # pylint: disable=no-member
        )

    def _create_task(self, dag: DAG, step: type[TypedStep], argo_reqs: list[Task]) -> Task:
        if step.required_steps:
            inputs = [self._create_artifact_from_step(req) for req in step.required_steps]
        else:
            inputs = []
        commands: list[str] = [
            entry
            for entry in generate_cli_call(
                step.__class__, inputs=[inpt.path for inpt in inputs], output=self.settings.DATA_DIR / step.__class__.__name__
            ).split(" ")
            if entry.strip()
        ]
        dag.__exit__()  # restriction from hera, can not create Container in context of active dag
        wurzel_call = Container(
            name=f"wurzel-run-template-{step.__class__.__name__.lower()}",
            image=self.settings.IMAGE,
            security_context=SecurityContext(run_as_non_root=True),
            command=commands,
            annotations=self.settings.ANNOTATIONS,
            inputs=inputs,
            env_from=[
                SecretEnvFrom(prefix="", name=self.settings.SECRET_NAME, optional=True),
                ConfigMapEnvFrom(prefix="", name=self.settings.CONFIG_MAP, optional=True),
            ],
            outputs=self._create_artifact_from_step(step),
        )
        dag.__enter__()  # pylint: disable=unnecessary-dunder-call
        input_refs = [argo_req.get_artifact("wurzel-artifact") for argo_req in argo_reqs] if argo_reqs else []
        return wurzel_call(
            name=step.__class__.__name__.lower(),
            arguments=input_refs,
        )

    def __generate_dag(self, step: type[TypedStep]) -> DAG:
        def resolve_requirements(step: type[TypedStep]) -> Task:
            artifacts = []
            argo_reqs: list[Task] = []

            for req in step.required_steps:
                if req.required_steps:
                    req_argo = resolve_requirements(req)

                else:  # Leaf
                    req_argo = self._create_task(dag, req, argo_reqs=[])
                artifacts.append(req_argo.result)
                argo_reqs.append(req_argo)
            step_argo: Task = self._create_task(dag, step, argo_reqs=argo_reqs)
            for argo_req in argo_reqs:
                argo_req >> step_argo  # pylint: disable=pointless-statement
            return step_argo

        with DAG(name="wurzel-pipeline") as dag:
            resolve_requirements(step)
        return dag
