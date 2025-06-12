# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

from hera.workflows import DAG, Artifact, Container, Task, Workflow
from wurzel.backend.backend import Backend
from wurzel.cli import generate_cli_call
from wurzel.step import TypedStep
from wurzel.step_executor import BaseStepExecutor, PrometheusStepExecutor


class ArgoBackend(Backend):
    """ArgoBackend is the wurzel backend using ArgoWorklow. The current implementation is an abstraction
    above 'hera' library.
    """

    image: str = "ghcr.io/telekom/wurzel"

    def __init__(
        self,
        data_dir: Path = Path("./data"),
        executer: BaseStepExecutor = PrometheusStepExecutor,
        encapsulate_env: bool = True,
        image: str = "ghcr.io/telekom/wurzel",
    ) -> None:
        if not isinstance(data_dir, Path):
            data_dir = Path(data_dir)
        self.executor: type[BaseStepExecutor] = executer
        self.encapsulate_env = encapsulate_env
        self.data_dir = data_dir

        self.image = image
        super().__init__()

    def generate_dict(self, step: TypedStep):
        return self._generate_workflow(step).to_dict()

    def generate_yaml(self, step: TypedStep):
        return self._generate_workflow(step).to_yaml()

    def _generate_workflow(self, step: type[TypedStep]) -> Workflow:
        with Workflow(
            generate_name="wurzel",
            entrypoint="wurzel-pipeline",
        ) as w:
            self.__generate_dag(step)
        return w

    w = Workflow()

    def _create_task(self, dag: DAG, step: type[TypedStep], argo_reqs: list[Task]) -> Task:
        if step.required_steps:
            inputs = [Artifact(name="wurzel-artifact", path=f"/tmp/{req.__class__.__name__}") for req in step.required_steps]
        else:
            inputs = []
        commands: list[str] = generate_cli_call(
            step.__class__, inputs=[inpt.from_ for inpt in inputs], output=self.data_dir / step.__class__.__name__
        ).split(" ")
        dag.__exit__()
        wurzel_call = Container(
            name=f"wurzel-run-template-{step.__class__.__name__.lower()}",
            image=self.image,
            command=commands,
            inputs=inputs,
            outputs=Artifact(name="wurzel-artifact", path=f"/tmp/{step.__class__.__name__}"),
        )
        dag.__enter__()  # pylint: disable=unnecessary-dunder-call
        input_refs = [argo_req.get_artifact("wurzel-artifact") for argo_req in argo_reqs] if argo_reqs else []
        return wurzel_call(
            name=step.__class__.__name__.lower(),
            arguments=input_refs,
            outputs=[Artifact(name=f"wurzel-artifact-{step.__class__.__name__.lower()}", path=f"/tmp/{step.__class__.__name__}")],
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
