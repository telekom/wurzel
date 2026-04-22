# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0


import shutil
import unittest.mock
from pathlib import Path
from typing import Union

import pytest

from wurzel.utils import HAS_QDRANT

if not HAS_QDRANT:
    pytest.skip("Qdrant is not available", allow_module_level=True)

from wurzel.exceptions import StepFailed
from wurzel.step_executor import BaseStepExecutor
from wurzel.steps.qdrant import QdrantConnectorMultiVectorStep, QdrantConnectorStep
from wurzel.steps.qdrant.data import QdrantMultiVectorResult, QdrantResult
from wurzel.utils import HAS_TLSH


def test_qdrant_connector_first(input_output_folder: tuple[Path, Path], dummy_collection):
    input_path, output_path = input_output_folder
    input_file = input_path / "qdrant_at.csv"
    output_file = output_path / "QdrantConnectorStep"
    shutil.copy("./tests/data/embedded.csv", input_file)
    with unittest.mock.patch("wurzel.steps.qdrant.retirement.CollectionRetirer._get_telemetry", return_value=[]):
        with BaseStepExecutor() as ex:
            step_res = ex(QdrantConnectorStep, {input_path}, output_file)

            step_output, step_report = step_res[0]

            assert step_report.results == 2, "Invalid step results"
            assert step_output["collection"][1] == "dummy_v1", "Invalid step output in collection name"
            assert step_output["metadata"][0]["foo"] == "bar", "Invalid step output in metadata"


def test_qdrant_connector_has_previous(input_output_folder: tuple[Path, Path], dummy_collection):
    input_path, output_path = input_output_folder

    input_file = input_path / "qdrant_at.csv"
    output_file = output_path / "QdrantConnectorStep"
    shutil.copy("./tests/data/embedded.csv", input_file)
    with unittest.mock.patch("wurzel.steps.qdrant.retirement.CollectionRetirer._get_telemetry", return_value=[]):
        all_outputs = []
        for _ in range(3):
            result = BaseStepExecutor().execute_step(QdrantConnectorStep, {input_path}, output_file)
            outputs, _ = zip(*result)
            all_outputs.extend(outputs)
        assert len(all_outputs) == 3


def test_qdrant_connector_no_csv(input_output_folder: tuple[Path, Path]):
    input_path, output_path = input_output_folder
    output_file = output_path / "QdrantConnectorStep"
    with pytest.raises(StepFailed):
        BaseStepExecutor().execute_step(QdrantConnectorStep, {input_path}, output_file)


def test_qdrant_connector_one_no_csv(input_output_folder: tuple[Path, Path]):
    input_path, output_path = input_output_folder
    input_file = input_path / "qdrant_at.csv"
    output_file = output_path / "QdrantConnectorStep"
    shutil.copy("./tests/data/embedded.csv", input_file)
    with pytest.raises(StepFailed):
        BaseStepExecutor().execute_step(
            QdrantConnectorStep,
            [input_path, input_path.parent.parent / "dummy_folder" / "brr.json"],
            output_file,
        )


def test_qdrant_connector_csv_partially_not_same_shape(
    input_output_folder: tuple[Path, Path],
):
    input_path, output_path = input_output_folder
    output_file = output_path / "QdrantConnectorStep"
    input_file = input_path / "qdrant_at.csv"
    shutil.copy("./tests/data/embedded_broken.csv", input_file)
    with pytest.raises(StepFailed):
        BaseStepExecutor().execute_step(QdrantConnectorStep, {input_path}, output_file)


@pytest.mark.parametrize(
    ["step", "result_type", "inpt_file"],
    [
        pytest.param(
            QdrantConnectorMultiVectorStep,
            QdrantMultiVectorResult,
            "./tests/data/embedding_multi.csv",
            id="MultiVector",
        ),
        pytest.param(
            QdrantConnectorStep,
            QdrantResult,
            "./tests/data/embedded.csv",
            id="SingleVector",
        ),
    ],
)
@pytest.mark.parametrize("tlsh", [True, False])
def test_qdrant_connector_true_csv(
    input_output_folder: tuple[Path, Path],
    dummy_collection,
    step: type[Union[QdrantConnectorStep, QdrantConnectorMultiVectorStep]],
    result_type: Union[QdrantResult, QdrantMultiVectorResult],
    inpt_file: str,
    tlsh: bool,
):
    input_path, output_path = input_output_folder
    input_file = input_path / "qdrant_at.csv"
    output_file = output_path / step.__name__
    shutil.copy(inpt_file, input_file)

    with unittest.mock.patch("wurzel.steps.qdrant.retirement.CollectionRetirer._get_telemetry", return_value=[]):
        res = BaseStepExecutor().execute_step(step, {input_path}, output_file)
        expected_cols = list(result_type.to_schema().columns)
        if tlsh and not HAS_TLSH:
            pytest.skip("TLSH dep is not installed")
        if not tlsh:
            expected_cols.remove("text_tlsh_hash")
        data, rep = res[0]
        assert res
        for col in expected_cols:
            assert col in data
