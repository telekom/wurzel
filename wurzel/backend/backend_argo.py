# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path
from hera.shared import global_config
from hera.workflows import DAG, Container, Task, Workflow, CronWorkflow, S3Artifact,ConfigMapEnvFrom, Container, SecretEnvFrom
from hera.workflows.models import S3Artifact as S3ArtifactTemplate
from hera.workflows.archive import NoneArchiveStrategy
from pydantic import BaseModel
from wurzel.backend.backend import Backend
from wurzel.cli import generate_cli_call
from wurzel.step import TypedStep
from wurzel.step_executor import BaseStepExecutor, PrometheusStepExecutor





class ArtifactsSettings(BaseModel):
    pass



class ArgoBackend(Backend):
    """ArgoBackend is the wurzel backend using ArgoWorklow. The current implementation is an abstraction
    above 'hera' library.
    """

    image: str = "ghcr.io/telekom/wurzel"

    def __init__(
        self,
        schedule:str = "0 4 * * *",
        data_dir: Path = Path("."),
        executer: BaseStepExecutor = PrometheusStepExecutor,
        encapsulate_env: bool = True,
        image: str = "ghcr.io/telekom/wurzel",
        s3_artifact_template:S3ArtifactTemplate = S3ArtifactTemplate(bucket="oneai-nonprod-pipelines",endpoint="s3.amazonaws.com"),
        service_account_name:str = "argo-workflow"
    ) -> None:
        if not isinstance(data_dir, Path):
            data_dir = Path(data_dir)
        self.executor: type[BaseStepExecutor] = executer
        self.encapsulate_env = encapsulate_env
        self.data_dir = data_dir
        self.schedule = schedule
        self.image = image
        self.s3_artifact_template = s3_artifact_template
        global_config.service_account_name = service_account_name
        super().__init__()

    def generate_dict(self, step: TypedStep):
        return self._generate_workflow(step).to_dict()

    def generate_yaml(self, step: TypedStep):
        return self._generate_workflow(step).to_yaml()

    def _generate_workflow(self, step: type[TypedStep]) -> Workflow:
        with CronWorkflow(
            schedule=self.schedule,
            name="wurzel",
            entrypoint="wurzel-pipeline",
            namespace="knowledge-pipeline-dev"
        ) as w:
            self.__generate_dag(step)
        return w


    def _create_task(self, dag: DAG, step: type[TypedStep], argo_reqs: list[Task]) -> Task:
        def _create_artifact_from_step(step: type[TypedStep])->S3Artifact:
            return S3Artifact(key=step.__class__.__name__.lower(), name="wurzel-artifact", path=(self.data_dir/step.__class__.__name__).as_posix(),archive=NoneArchiveStrategy(),endpoint=self.s3_artifact_template.endpoint,bucket=self.s3_artifact_template.bucket)
        if step.required_steps:
            inputs = [_create_artifact_from_step(req) for req in step.required_steps]
        else:
            inputs = []
        commands: list[str] = [entry for entry in generate_cli_call(
            step.__class__, inputs=[inpt.path for inpt in inputs], output=self.data_dir / step.__class__.__name__
        ).split(" ") if entry.strip()]
        dag.__exit__()
        wurzel_call = Container(
            name=f"wurzel-run-template-{step.__class__.__name__.lower()}",
            image=self.image,
            command=commands,
            inputs=inputs,
            env_from=[SecretEnvFrom(prefix="", name="knowledge-pipeline-de", optional=True),ConfigMapEnvFrom(prefix="", name="knowledge-pipeline-de", optional=True)],
            outputs=_create_artifact_from_step(step)
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
