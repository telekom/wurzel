# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0


import pytest
import yaml

from wurzel.backend import ArgoBackend, DvcBackend
from wurzel.backend.backend import Backend
from wurzel.backend.backend_argo import ArgoBackendSettings
from wurzel.datacontract import MarkdownDataContract
from wurzel.step.typed_step import TypedStep
from wurzel.steps.docling.docling_step import DoclingStep
from wurzel.steps.duplication import DropDuplicationStep
from wurzel.steps.splitter import SimpleSplitterStep
from wurzel.utils.meta_settings import WZ


class A(TypedStep[None, None, MarkdownDataContract]):
    def run(self, inpt: None) -> MarkdownDataContract:
        return super().run(inpt)


class B(TypedStep[None, MarkdownDataContract, MarkdownDataContract]):
    def run(self, inpt: MarkdownDataContract) -> MarkdownDataContract:
        return super().run(inpt)


class C(TypedStep[None, MarkdownDataContract, MarkdownDataContract]):
    def run(self, inpt: MarkdownDataContract) -> MarkdownDataContract:
        return super().run(inpt)


class D(TypedStep[None, MarkdownDataContract, MarkdownDataContract]):
    def run(self, inpt: MarkdownDataContract) -> MarkdownDataContract:
        return super().run(inpt)


@pytest.mark.parametrize(
    "backend",
    [
        pytest.param(DvcBackend, id="DVC Backend"),
        pytest.param(ArgoBackend, id="ArGo Backend"),
    ],
)
def test_dict(backend):
    a = WZ(A)
    b = WZ(B)
    a >> b
    dic = backend()._generate_dict(b)
    assert dic


def safeget(dct, *keys):
    for key in keys:
        try:
            dct = dct[key]
        except KeyError:
            return None
    return dct


@pytest.mark.parametrize(
    "backend,keys",
    [
        pytest.param(DvcBackend, ["stages"], id="DVC Backend"),
        pytest.param(ArgoBackend, ["spec", "workflowSpec", "templates", 0, "dag", "tasks"], id="ArGo Backend"),
    ],
)
def test_yaml(backend: type[Backend], keys):
    a = WZ(A)
    b = WZ(B)
    c = WZ(C)
    d = WZ(D)
    a >> b >> c
    d >> c
    y = backend().generate_artifact(b)
    y_dict = yaml.safe_load(y)
    assert len(safeget(y_dict, *keys)) == 2
    y = backend().generate_artifact(c)
    y_dict = yaml.safe_load(y)
    assert len(safeget(y_dict, *keys)) == 4
    y = backend().generate_artifact(d)
    y_dict = yaml.safe_load(y)
    assert len(safeget(y_dict, *keys)) == 1
    y = backend().generate_artifact(a)
    y_dict = yaml.safe_load(y)
    assert len(safeget(y_dict, *keys)) == 1


@pytest.mark.parametrize(
    "backend,keys,params",
    [
        pytest.param(DvcBackend, ["stages"], {}, id="DVC Backend"),
        pytest.param(
            ArgoBackend, ["spec", "workflowSpec", "templates", 0, "dag", "tasks"], {"settings": ArgoBackendSettings()}, id="ArGo Backend"
        ),
    ],
)
def test_minimal_pipeline(backend: type[Backend], keys, params):
    agb = WZ(DoclingStep)
    splitter = WZ(SimpleSplitterStep)
    duplication = WZ(DropDuplicationStep)
    agb >> splitter >> duplication

    y = backend(**params).generate_artifact(duplication)
    y_dict = yaml.safe_load(y)
    assert len(safeget(y_dict, *keys)) == 3
