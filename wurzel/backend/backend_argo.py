# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

from wurzel.backend.backend import Backend
from wurzel.cli import generate_cli_call
from wurzel.step import TypedStep
from wurzel.step.typed_step import MODEL_TYPE
from wurzel.step_executor import BaseStepExecutor, PrometheusStepExecutor

from hera.workflows import DAG, Workflow, script,Artifact, Task, Script, Container, Parameter




class ArgoBackend(Backend):
    image:str = "ghcr.io/telekom/wurzel"
    def __init__(
        self,
        data_dir: Path = Path("./data"),
        executer: BaseStepExecutor = PrometheusStepExecutor,
        encapsulate_env: bool = True,
        image:str = "ghcr.io/telekom/wurzel"
    ) -> None:
        if not isinstance(data_dir, Path):
            data_dir = Path(data_dir)
        self.executor: type[BaseStepExecutor] = executer
        self.data_dir = data_dir
        self.encapsulate_env = encapsulate_env
        self.image= image
        super().__init__()

    def generate_dict(self, step: TypedStep):
        return self._generate_workflow(step).to_dict()
    def generate_yaml(self, step: TypedStep):
        return self._generate_workflow(step).to_yaml()

    def _generate_workflow(self, step: type[TypedStep])->Workflow:

        with Workflow(
            generate_name="wurzel",
            entrypoint="wurzel-pipeline",
        ) as w:

            self.__generate_dag(step)
        return w
    w = Workflow()
    def _create_task(self,dag:DAG, step:type[TypedStep], reqs:list[Task]=None)->Task:
        if reqs:
            inputs = [reqs[0].get_artifact("wurzel-artifact").from_]
        else:
            inputs = []
        commands:list[str] = generate_cli_call(step.__class__, inputs=inputs, output=self.data_dir/step.__class__.__name__).split(" ")
        dag.__exit__()
        wurzel_call = Container(
            name=f"wurzel-run-{step.__class__.__name__}",
            image=self.image,
            command=commands,
            inputs=[Parameter(name="inputs")],
            outputs=Artifact(name=f"wurzel-artifact", path=f"/tmp/{step.__class__.__name__}")
        )
        dag.__enter__()
        return wurzel_call(

            name=step.__class__.__name__,
            arguments={"inputs": inputs},

        )
    def __generate_dag(self, step: type[TypedStep])-> DAG:
        def resolve_requirements(step: type[TypedStep])->Task:
            artifacts = []
            argo_reqs:list[Task] = []

            for req in step.required_steps:
                if req.required_steps:
                    req_argo = resolve_requirements(req)

                else: # Leaf
                    req_argo =self._create_task(dag, req)
                artifacts.append(req_argo.result)
                argo_reqs.append(req_argo)
            step_argo:Task = self._create_task(dag,step,[argo_req for argo_req in argo_reqs] )
            for argo_req in argo_reqs:
                argo_req >> step_argo
            return step_argo
        with DAG(name="wurzel-pipeline") as dag:
            resolve_requirements(step)
        return dag

