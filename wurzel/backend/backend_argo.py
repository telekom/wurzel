# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

from wurzel.backend.backend import Backend
from wurzel.step import TypedStep
from wurzel.step.typed_step import MODEL_TYPE
from wurzel.step_executor import BaseStepExecutor, PrometheusStepExecutor

from hera.workflows import DAG, Workflow, script,Artifact, Task




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
        return self.__generate_workflow(step).to_dict()
    def generate_yaml(self, step: TypedStep):
        return self.__generate_workflow(step).to_yaml()
    @staticmethod
    @script(image="ghcr.io/telekom/wurzel")
    def run_step(step_cls:type[TypedStep], input= None) ->MODEL_TYPE:
            with BaseStepExecutor() as ex:
                return ex.execute_step(step_cls=step_cls)


    def __generate_workflow(self, step: type[TypedStep])->Workflow:

        with Workflow(
            generate_name="wurzel",
            entrypoint="diamond",
        ) as w:

            self.__generate_dag(step)
        return w
    w = Workflow()
    def __generate_dag(self, step: type[TypedStep])-> DAG:
        def resolve_requirements(step: type[TypedStep])->Task:
            artifacts = []
            step_argo:Task  = self.run_step(step_cls=step,name=step.__class__.__name__)
            for req in step.required_steps:
                if req.required_steps:
                    req_argo = resolve_requirements(req)
                    artifacts.append(req_argo.result)
                else:

                    req_argo =self.run_step(step_cls=req,name=req.__class__.__name__)
                    req_argo >> step_argo
            return step_argo

        with DAG() as dag:
            resolve_requirements(step)
        return dag

