# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import json
from pathlib import Path
import re
import pytest
from wurzel import BaseStepExecutor, TypedStep, NoSettings, MarkdownDataContract

class MyStep(TypedStep[NoSettings, MarkdownDataContract, list[MarkdownDataContract]]):
    def run(self, inputs: MarkdownDataContract) -> list[MarkdownDataContract]:
        return [inputs, inputs]
DEFAULT_OBJ = MarkdownDataContract(md="md", keywords="ib", url="ur")
def test_memory_in_file_out(tmp_path):
    out = tmp_path / "out"
    with BaseStepExecutor() as ex:
        ex(MyStep, (DEFAULT_OBJ,), out)
    files = list(out.glob("*"))
    expected = (out / "[Memory]-My.json")
    assert len(files) == 1
    assert expected in files

def test_file_in_memory_out(tmp_path):
    inpt_folder = tmp_path / "input"
    inpt_folder.mkdir()
    (inpt_folder / "First.json").write_text(DEFAULT_OBJ.model_dump_json())
    with BaseStepExecutor() as ex:
        res = ex.execute_step(MyStep, (inpt_folder,), None)
    assert res[0][0] == [DEFAULT_OBJ, DEFAULT_OBJ]
    assert res[0][1].time_to_save == 0

class TestAStep(TypedStep[NoSettings, None, MarkdownDataContract]):
    def run(self, inputs: None) -> MarkdownDataContract:
        return MarkdownDataContract(md="A", keywords="A", url="A")
class TestA2Step(TypedStep[NoSettings, None, MarkdownDataContract]):
    def run(self, inputs: None) -> MarkdownDataContract:
        return MarkdownDataContract(md="A2", keywords="A2", url="A2")
class TestBStep(TypedStep[NoSettings, MarkdownDataContract, list[MarkdownDataContract]]):
    def run(self, inputs: MarkdownDataContract) -> list[MarkdownDataContract]:
        return [inputs, inputs]
class TestCStep(TypedStep[NoSettings, list[MarkdownDataContract], MarkdownDataContract]):
    def run(self, inputs: list[MarkdownDataContract]) -> MarkdownDataContract:
            return inputs[0]
def test_chain(tmp_path):
    out_a = tmp_path / "out_a"
    out_b = tmp_path / "out_b"
    out_c = tmp_path / "out_c"
    with BaseStepExecutor() as ex:
        a = ex.execute_step(TestAStep, None, out_a)
        b = ex.execute_step(TestBStep, (out_a,), out_b)
        c = ex.execute_step(TestCStep, (out_b,), out_c)
    for i in [a,b,c]:
        assert len(i) == 1
    for (res, _rep) in [a[0],c[0]]:
        res: MarkdownDataContract
        assert res.md == "A"
    assert len(b[0][0])== 2
    assert all((md.md == "A" for md in b[0][0]))
    pass


def test_2_to_1(tmp_path):
    # A   \
    #     > B
    # A2  /
    out_as = [
        tmp_path / "out_a1",
        tmp_path / "out_a2"
    ]
    out_b = tmp_path / "out_b"
    with BaseStepExecutor() as ex:
        ex.execute_step(TestAStep, None, output_dir=out_as[0])
        ex.execute_step(TestA2Step, None, output_dir=out_as[1])
        b = ex.execute_step(TestBStep, out_as, out_b)
    assert len(b) == 2
    assert len(list(out_b.glob("*"))) == 2
    for p in  out_b.glob("*"):
        assert p.name in ["TestA-TestB.json", "TestA2-TestB.json"]

def test_2_to_2_to_1(tmp_path):
    # A  > B  \
    #          > C
    # A2 > B  /

    out_as = [
        tmp_path / "out_a1",
        tmp_path / "out_a2"
    ]

    out_b1 = tmp_path / "out_b1"
    final = tmp_path / "final"
    with BaseStepExecutor() as ex:
        ex.execute_step(TestAStep, None, output_dir=out_as[0])
        ex.execute_step(TestA2Step, None, output_dir=out_as[1])
        for out in out_as:
            ex.execute_step(TestBStep, (out,), out_b1)
        c = ex.execute_step(TestCStep, (out_b1,), final)
    assert len(c) == 2
    assert len(list(final.glob("*"))) == 2

    assert list(out_as[0].glob("*"))[0].name == "TestA.json"
    assert list(out_as[1].glob("*"))[0].name == "TestA2.json"
    for p in out_b1.glob("*"):
        assert p.name in ["TestA-TestB.json", "TestA2-TestB.json"]

    for p in final.glob("*"):
        assert p.name in ["TestA-TestB-TestC.json", "TestA2-TestB-TestC.json"]

def test_2_to_1_to_1(tmp_path):
    # A   \
    #      > B  > C
    # A2  /

    out_as = [
        tmp_path / "out_a1",
        tmp_path / "out_a2"
    ]

    out_b1 = tmp_path / "out_b1"
    final = tmp_path / "final"
    with BaseStepExecutor() as ex:
        ex.execute_step(TestAStep, None, output_dir=out_as[0])
        ex.execute_step(TestA2Step, None, output_dir=out_as[1])
        b = ex.execute_step(TestBStep, out_as, out_b1)
        c = ex.execute_step(TestCStep, (out_b1,), final)
    assert len(c) == 2
    assert len(list(final.glob("*"))) == 2
    for p in  final.glob("*"):
        assert p.name in ["TestA-TestB-TestC.json", "TestA2-TestB-TestC.json"]
