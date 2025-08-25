# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0


import shutil
import unittest
import unittest.mock
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Union

import pytest

# qdrant-Lite; See: https://qdrant.io/docs/qdrant_lite.md
from qdrant_client import QdrantClient, models
from qdrant_client.http.models.models import (
    CollectionsTelemetry,
    CollectionTelemetry,
    InlineResponse2002,
    LocalShardTelemetry,
    OperationDurationStatistics,
    OptimizerTelemetry,
    ReplicaSetTelemetry,
    TelemetryData,
)
from qdrant_client.models import AliasDescription, CollectionsAliasesResponse

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
    mock_telemetry = InlineResponse2002(result=TelemetryData.model_construct(collections=CollectionsTelemetry.model_construct()))

    with unittest.mock.patch("wurzel.steps.qdrant.step.QdrantConnectorStep._get_telemetry", return_value=mock_telemetry):
        BaseStepExecutor().execute_step(QdrantConnectorStep, {input_path}, output_file)


def test_qdrant_connector_has_previous(input_output_folder: tuple[Path, Path], dummy_collection):
    input_path, output_path = input_output_folder

    input_file = input_path / "qdrant_at.csv"
    output_file = output_path / "QdrantConnectorStep"
    shutil.copy("./tests/data/embedded.csv", input_file)
    mock_telemetry = InlineResponse2002(result=TelemetryData.model_construct(collections=CollectionsTelemetry.model_construct()))

    with unittest.mock.patch("wurzel.steps.qdrant.step.QdrantConnectorStep._get_telemetry", return_value=mock_telemetry):
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


@pytest.mark.parametrize(
    "hist_len, step_run, aliased_collections,recently_used ,count_remaining_collection, remaining_collections,untracked_collection,dry_run",
    [
        # Case 1: v1 is aliased + recent, keep v3-v5 by version
        (3, 5, ["dummy_v1"], ["dummy_v1"], 4, ["dummy_v1", "dummy_v3", "dummy_v4", "dummy_v5"], [], False),
        # Case 2: Keep only latest v4, v1 is recent, v2 is aliased
        (1, 4, ["dummy_v2"], ["dummy_v1"], 3, ["dummy_v1", "dummy_v2", "dummy_v4"], [], False),
        # Case 3: Keep top 2 by version: v4, v5; v1 is recent
        (2, 5, [], ["dummy_v1"], 3, ["dummy_v1", "dummy_v4", "dummy_v5"], [], False),
        # Case 4: v2 aliased, v4 recent; keep v4,v5
        (2, 5, ["dummy_v2"], [], 3, ["dummy_v2", "dummy_v4", "dummy_v5"], [], False),
        # Case 5: Only latest v4; v1,v2 aliased
        (1, 4, ["dummy_v1", "dummy_v2"], [], 3, ["dummy_v1", "dummy_v2", "dummy_v4"], [], False),
        # Case 6: Untracked collection (abc_dummy) should not be deleted,latest v4,v5
        (2, 5, [], [], 3, ["abc_dummy", "dummy_v4", "dummy_v5"], ["abc_dummy"], False),
        # Case 7: Same as Case 3 but in dry run mode (no deletions)
        (2, 5, [], ["dummy_v1"], 5, ["dummy_v1", "dummy_v2", "dummy_v3", "dummy_v4", "dummy_v5"], [], True),
        # Case 8: Collections: dummy_v1 to v5, plus malformed ones: dummy_v, dummy_v_abc, dummy_v23_abc, dummy_vabc
        (
            2,
            5,
            [],
            [],
            6,
            ["dummy_v", "dummy_v_abc", "dummy_v23_abc", "dummy_vabc", "dummy_v4", "dummy_v5"],
            ["dummy_v", "dummy_v_abc", "dummy_v23_abc", "dummy_vabc"],
            False,
        ),
    ],
)
def test_qdrant_collection_retirement_with_missing_versions(
    input_output_folder: tuple[Path, Path],
    env,
    dummy_collection,
    hist_len,
    step_run,
    aliased_collections,
    recently_used,
    count_remaining_collection,
    remaining_collections,
    untracked_collection,
    dry_run,
):
    input_path, output_path = input_output_folder
    env.set("COLLECTION_HISTORY_LEN", str(hist_len))
    env.set("COLLECTION_RETIRE_DRY_RUN", str(dry_run).lower())

    input_file = input_path / "qdrant_at.csv"
    output_file = output_path / "QdrantConnectorStep"
    shutil.copy("./tests/data/embedded.csv", input_file)

    client = QdrantClient(location=":memory:")
    old_close = client.close
    client.close = print

    old_time = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    recent_time = (datetime.now(timezone.utc) - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    collection_data = [(col_id, recent_time if col_id in recently_used else old_time) for col_id in remaining_collections]

    mock_telemetry = InlineResponse2002(
        result=TelemetryData.model_construct(
            collections=CollectionsTelemetry.model_construct(
                collections=[
                    CollectionTelemetry.model_construct(
                        id=col_id,
                        shards=[
                            ReplicaSetTelemetry.model_construct(
                                local=LocalShardTelemetry.model_construct(
                                    optimizations=OptimizerTelemetry.model_construct(
                                        optimizations=OperationDurationStatistics.model_construct(last_responded=last_used)
                                    )
                                ),
                                remote=[],
                            )
                        ],
                    )
                    for col_id, last_used in collection_data
                ]
            )
        )
    )

    mock_aliases = CollectionsAliasesResponse(
        aliases=[AliasDescription(alias_name=col, collection_name=col) for col in aliased_collections]
    )

    with unittest.mock.patch("wurzel.steps.qdrant.step.QdrantConnectorStep._get_telemetry", return_value=mock_telemetry):
        with unittest.mock.patch("wurzel.steps.qdrant.step.QdrantClient.get_aliases", return_value=mock_aliases):
            with unittest.mock.patch("wurzel.steps.qdrant.step.QdrantClient") as mock:
                mock.return_value = client
                if untracked_collection:
                    for untracked in untracked_collection:
                        client.create_collection(untracked, vectors_config={"size": 1, "distance": "Cosine"})

                with BaseStepExecutor() as ex:
                    for _ in range(step_run):
                        ex(QdrantConnectorStep, {input_path}, output_file)

                client.close = old_close
                remaining = [col.name for col in client.get_collections().collections]
                assert len(remaining) == count_remaining_collection
                assert remaining == remaining_collections
                for aliased in aliased_collections:
                    assert aliased in remaining
                for recent_used in recently_used:
                    assert recent_used in remaining
                for untracked in untracked_collection:
                    assert untracked in remaining


def test_qdrant_get_collections_with_ephemerals(input_output_folder: tuple[Path, Path], env, dummy_collection):
    input_path, output_path = input_output_folder
    HIST_LEN = 3
    env.set("COLLECTION_HISTORY_LEN", str(HIST_LEN))
    env.set("COLLECTION", "tenant1-dev")
    input_file = input_path / "qdrant_at.csv"
    shutil.copy("./tests/data/embedded.csv", input_file)
    client = QdrantClient(location=":memory:")
    {
        client.create_collection(
            coll,
            vectors_config=models.VectorParams(size=100, distance=models.Distance.COSINE),
        )
        for coll in [
            "tenant1-dev_v1",
            "tenant1-dev_v2",
            "tenant1-dev_v3",
            "tenant1-dev-feature-abc_v1",
        ]
    }

    client.close = print
    with unittest.mock.patch("wurzel.steps.qdrant.step.QdrantClient") as mock:
        mock.return_value = client
        step = QdrantConnectorStep()
        result = step._get_collection_versions()
        assert len(result) == 3
        assert set(result.keys()) == {1, 2, 3}

        env.set("COLLECTION", "tenant1-dev-feature-abc")
        step = QdrantConnectorStep()
        result = step._get_collection_versions()
        assert len(result) == 1
        assert set(result.keys()) == {1}


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
    mock_telemetry = InlineResponse2002(result=TelemetryData.model_construct(collections=CollectionsTelemetry.model_construct()))

    with unittest.mock.patch("wurzel.steps.qdrant.step.QdrantConnectorStep._get_telemetry", return_value=mock_telemetry):
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
