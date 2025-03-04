# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import os
from pathlib import Path
import shutil
from typing import Tuple
from pydantic import ValidationError
import pydantic_core
import pytest
# Milvus-Lite; See: https://milvus.io/docs/milvus_lite.md
from milvus_lite.server import Server
import requests_mock
from wurzel.steps.milvus import MilvusSettings, MilvusConnectorStep
from wurzel.exceptions import StepFailed
from wurzel.step_executor import BaseStepExecutor
# Skip MILVUS tests if 'MILVUS_TESTS' is not set
@pytest.fixture(scope="function")
def milvus_lite(tmp_path: Path, env):
    pytest.skip("MILVUS_TESTS not set in environment")
#     MILV_OUT_DIR = tmp_path / "milvus"
#     env.update({
#         'COLLECTION': "dummy",
#         'PASSWORD': ""
#     })
#     test_name = tmp_path.name
#     milvus_mock.set_base_dir(MILV_OUT_DIR)
#     milvus_mock.start()
#     milvus_mock.wait_started()
#     yield 
#     milvus_mock.stop()
#     shutil.rmtree(f"./reports/logs/{test_name}", ignore_errors=True)
#     shutil.copytree(MILV_OUT_DIR / "logs", f"./reports/logs/{test_name}")




def test_milvus_connector_first(input_output_folder:Tuple[Path,Path], milvus_lite):
    input_path, output_path = input_output_folder
    input_file = input_path / 'milvus_at.csv'
    output_file = output_path/"MilvusConnectorStep"
    shutil.copy("./tests/data/embedded.csv", input_file)
    BaseStepExecutor().execute_step(MilvusConnectorStep, {input_file}, output_file)

def test_milvus_connector_has_previous(input_output_folder:Tuple[Path,Path], milvus_lite):
    input_path, output_path = input_output_folder

    input_file = input_path / 'milvus_at.csv'
    output_file = output_path/"MilvusConnectorStep"
    shutil.copy("./tests/data/embedded.csv", input_file)
    BaseStepExecutor().execute_step(MilvusConnectorStep, {input_file}, output_file)
    BaseStepExecutor().execute_step(MilvusConnectorStep, {input_file}, output_file)


def test_milvus_connector_no_csv(input_output_folder:Tuple[Path,Path], milvus_lite):
    input_path, output_path = input_output_folder
    output_file = output_path/"MilvusConnectorStep"
    with pytest.raises(StepFailed):
        BaseStepExecutor().execute_step(MilvusConnectorStep, {input_path}, output_file)


def test_milvus_connector_one_no_csv(input_output_folder:Tuple[Path,Path], milvus_lite):
    input_path, output_path = input_output_folder
    input_file = input_path / 'milvus_at.csv'
    output_file = output_path/"MilvusConnectorStep"
    shutil.copy("./tests/data/embedded.csv", input_file)
    with pytest.raises(StepFailed):
        BaseStepExecutor().execute_step(
            MilvusConnectorStep,
            [input_file, input_path.parent.parent /  "dummy_folder"/"brr.json"],
            output_file)


def test_milvus_collection_retirement(input_output_folder:Tuple[Path,Path], env, milvus_lite):
    input_path, output_path = input_output_folder
    env.set("MILVUS__COLLECTION_HISTORY_LEN", "3")
    input_file = input_path / 'milvus_at.csv'
    output_file = output_path/"MilvusConnectorStep"
    shutil.copy("./tests/data/embedded.csv", input_file)
    with BaseStepExecutor() as ex:
        ex(MilvusConnectorStep, {input_file}, output_file)
        ex(MilvusConnectorStep, {input_file}, output_file)
        ex(MilvusConnectorStep, {input_file}, output_file)
        # this will cover retire
        ex(MilvusConnectorStep, {input_file}, output_file)


    


def test_milvus_connector_csv_partially_not_same_shape(input_output_folder:Tuple[Path,Path], milvus_lite):
    input_path, output_path = input_output_folder
    output_file = output_path/"MilvusConnectorStep"
    input_file = input_path / 'milvus_at.csv'
    shutil.copy("./tests/data/embedded_broken.csv", input_file)
    with pytest.raises(StepFailed):
        BaseStepExecutor().execute_step(MilvusConnectorStep, {input_file}, output_file)


def test_milvus_connector_true_csv(input_output_folder:Tuple[Path,Path], milvus_lite):
    input_path, output_path = input_output_folder
    input_file = input_path / 'milvus_at.csv'
    output_file = output_path/MilvusConnectorStep.__name__
    shutil.copy("./tests/data/embedded.csv", input_file)
    BaseStepExecutor().execute_step(MilvusConnectorStep, {input_file}, output_file)
