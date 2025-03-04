# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import os
from pathlib import Path
import shutil
from typing import Tuple
from unittest import mock
import unittest
import unittest.mock
import pytest
# qdrant-Lite; See: https://qdrant.io/docs/qdrant_lite.md
from qdrant_client import QdrantClient
import requests_mock
from wurzel.steps.qdrant import QdrantConnectorStep, QdrantConnectorMultiVectorStep
from wurzel.exceptions import StepFailed
from wurzel.step_executor import BaseStepExecutor




def test_qdrant_connector_first(input_output_folder:Tuple[Path,Path], dummy_collection):
    input_path, output_path = input_output_folder
    input_file = input_path / 'qdrant_at.csv'
    output_file = output_path/"QdrantConnectorStep"
    shutil.copy("./tests/data/embedded.csv", input_file)
    BaseStepExecutor().execute_step(QdrantConnectorStep, {input_path}, output_file)

def test_qdrant_connector_has_previous(input_output_folder:Tuple[Path,Path], dummy_collection):
    input_path, output_path = input_output_folder

    input_file = input_path / 'qdrant_at.csv'
    output_file = output_path/"QdrantConnectorStep"
    shutil.copy("./tests/data/embedded.csv", input_file)
    BaseStepExecutor().execute_step(QdrantConnectorStep, {input_path}, output_file)
    BaseStepExecutor().execute_step(QdrantConnectorStep, {input_path}, output_file)


def test_qdrant_connector_no_csv(input_output_folder:Tuple[Path,Path]):
    input_path, output_path = input_output_folder
    output_file = output_path/"QdrantConnectorStep"
    with pytest.raises(StepFailed):
        BaseStepExecutor().execute_step(QdrantConnectorStep, {input_path}, output_file)


def test_qdrant_connector_one_no_csv(input_output_folder:Tuple[Path,Path]):
    input_path, output_path = input_output_folder
    input_file = input_path / 'qdrant_at.csv'
    output_file = output_path/"QdrantConnectorStep"
    shutil.copy("./tests/data/embedded.csv", input_file)
    with pytest.raises(StepFailed):
        BaseStepExecutor().execute_step(
            QdrantConnectorStep,
            [input_path, input_path.parent.parent /  "dummy_folder"/"brr.json"],
            output_file)

def test_qdrant_collection_retirement(input_output_folder:Tuple[Path,Path], env, dummy_collection):
    input_path, output_path = input_output_folder
    HIST_LEN = 3
    env.set("COLLECTION_HISTORY_LEN", str(HIST_LEN))
    input_file = input_path / 'qdrant_at.csv'
    output_file = output_path/"QdrantConnectorStep"
    shutil.copy("./tests/data/embedded.csv", input_file)
    client = QdrantClient(location=":memory:")
    old_close = client.close
    client.close = print
    with unittest.mock.patch("wurzel.steps.qdrant.step.QdrantClient") as mock:
        mock.return_value = client
        with BaseStepExecutor() as ex:
            ex(QdrantConnectorStep, {input_path}, output_file)
            ex(QdrantConnectorStep, {input_path}, output_file)
            ex(QdrantConnectorStep, {input_path}, output_file)
            # this will cover retire
            ex(QdrantConnectorStep, {input_path}, output_file)
        client.close = old_close
        assert len(client.get_collections().collections) == 3
        assert len([col.name for col in client.get_collections().collections if "austria" in col.name]) <= HIST_LEN


def test_qdrant_connector_csv_partially_not_same_shape(input_output_folder:Tuple[Path,Path]):
    input_path, output_path = input_output_folder
    output_file = output_path/"QdrantConnectorStep"
    input_file = input_path / 'qdrant_at.csv'
    shutil.copy("./tests/data/embedded_broken.csv", input_file)
    with pytest.raises(StepFailed):
        BaseStepExecutor().execute_step(QdrantConnectorStep, {input_path}, output_file)


def test_qdrant_connector_true_csv(input_output_folder:Tuple[Path,Path], dummy_collection):
    input_path, output_path = input_output_folder
    input_file = input_path / 'qdrant_at.csv'
    output_file = output_path/QdrantConnectorStep.__name__
    shutil.copy("./tests/data/embedded.csv", input_file)
    BaseStepExecutor().execute_step(QdrantConnectorStep, {input_path}, output_file)


def test_qdrant_connector_true_csv_multi(input_output_folder:Tuple[Path,Path], dummy_collection):
    input_path, output_path = input_output_folder
    input_file = input_path / 'qdrant_at.csv'
    output_file = output_path/QdrantConnectorMultiVectorStep.__name__
    shutil.copy("./tests/data/embedding_multi.csv", input_file)
    BaseStepExecutor().execute_step(QdrantConnectorMultiVectorStep, {input_path}, output_file)
