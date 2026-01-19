# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0


import pytest
import yaml

from wurzel.utils import HAS_DOCLING, HAS_HERA

if not HAS_DOCLING:
    pytest.skip("Docling is not available", allow_module_level=True)

from wurzel.core.typed_step import TypedStep
from wurzel.datacontract import MarkdownDataContract
from wurzel.executors import DvcBackend
from wurzel.executors.backend.backend import Backend
from wurzel.steps.docling.docling_step import DoclingStep
from wurzel.steps.duplication import DropDuplicationStep
from wurzel.steps.splitter import SimpleSplitterStep
from wurzel.utils.meta_settings import WZ

if HAS_HERA:
    from wurzel.executors import ArgoBackend


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


def _get_yaml_test_params():
    params = [pytest.param(DvcBackend, ["stages"], id="DVC Backend")]
    if HAS_HERA:
        params.append(pytest.param(ArgoBackend, ["spec", "workflowSpec", "templates", 0, "dag", "tasks"], id="Argo Backend"))
    return params


@pytest.mark.parametrize("backend,keys", _get_yaml_test_params())
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


def _get_minimal_pipeline_test_params():
    params = [pytest.param(DvcBackend, ["stages"], {}, id="DVC Backend")]
    if HAS_HERA:
        params.append(pytest.param(ArgoBackend, ["spec", "workflowSpec", "templates", 0, "dag", "tasks"], {}, id="Argo Backend"))
    return params


@pytest.mark.parametrize("backend,keys,params", _get_minimal_pipeline_test_params())
def test_minimal_pipeline(backend: type[Backend], keys, params):
    agb = WZ(DoclingStep)
    splitter = WZ(SimpleSplitterStep)
    duplication = WZ(DropDuplicationStep)
    agb >> splitter >> duplication

    y = backend(**params).generate_artifact(duplication)
    y_dict = yaml.safe_load(y)
    assert len(safeget(y_dict, *keys)) == 3
