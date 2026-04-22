# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import shutil
import unittest.mock
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from wurzel.utils import HAS_QDRANT

if not HAS_QDRANT:
    pytest.skip("Qdrant is not available", allow_module_level=True)

from dateutil.parser import isoparse
from pydantic import ValidationError
from qdrant_client import QdrantClient, models
from qdrant_client.models import AliasDescription, CollectionsAliasesResponse

from wurzel.step_executor import BaseStepExecutor
from wurzel.steps.qdrant import QdrantConnectorStep
from wurzel.steps.qdrant.retirement import CollectionRetirer
from wurzel.steps.qdrant.telemetry import (
    CollectionTelemetry,
    LocalShardTelemetry,
    OperationStats,
    OptimizerTelemetry,
    ReplicaSetTelemetry,
)


@pytest.mark.parametrize(
    "hist_len, step_run, aliased_collections,recently_used ,count_remaining_collection, remaining_collections,"
    "untracked_collection,dry_run,enable_collection_retirement",
    [
        # Case 1: v1 is aliased + recent, keep v3-v5 by version
        pytest.param(
            3,
            5,
            ["dummy_v1"],
            ["dummy_v1"],
            4,
            ["dummy_v1", "dummy_v3", "dummy_v4", "dummy_v5"],
            [],
            False,
            True,
            id="aliased_recent_and_latest_versions",
        ),
        # Case 2: Keep only latest v4, v1 is recent, v2 is aliased
        pytest.param(
            1, 4, ["dummy_v2"], ["dummy_v1"], 3, ["dummy_v1", "dummy_v2", "dummy_v4"], [], False, True, id="latest_plus_alias_recent"
        ),
        # Case 3: Keep top 2 by version: v4, v5; v1 is recent
        pytest.param(2, 5, [], ["dummy_v1"], 3, ["dummy_v1", "dummy_v4", "dummy_v5"], [], False, True, id="recent_plus_top_versions"),
        # Case 4: v2 aliased, v4 recent; keep v4,v5
        pytest.param(2, 5, ["dummy_v2"], [], 3, ["dummy_v2", "dummy_v4", "dummy_v5"], [], False, True, id="aliased_plus_top_versions"),
        # Case 5: Only latest v4; v1,v2 aliased
        pytest.param(
            1, 4, ["dummy_v1", "dummy_v2"], [], 3, ["dummy_v1", "dummy_v2", "dummy_v4"], [], False, True, id="multiple_aliased_and_latest"
        ),
        # Case 6: Untracked collection (abc_dummy) should not be deleted, latest v4,v5
        pytest.param(
            2, 5, [], [], 3, ["abc_dummy", "dummy_v4", "dummy_v5"], ["abc_dummy"], False, True, id="untracked_collection_retained"
        ),
        # Case 7: Same as Case 3 but in dry run mode (no deletions)
        pytest.param(
            2,
            5,
            [],
            ["dummy_v1"],
            5,
            ["dummy_v1", "dummy_v2", "dummy_v3", "dummy_v4", "dummy_v5"],
            [],
            True,
            True,
            id="dry_run_retains_all",
        ),
        # Case 8: Collections: dummy_v1 to v5, plus malformed ones: dummy_v, dummy_v_abc, dummy_v23_abc, dummy_vabc
        pytest.param(
            2,
            5,
            [],
            [],
            6,
            ["dummy_v", "dummy_v_abc", "dummy_v23_abc", "dummy_vabc", "dummy_v4", "dummy_v5"],
            ["dummy_v", "dummy_v_abc", "dummy_v23_abc", "dummy_vabc"],
            False,
            True,
            id="malformed_versions_ignored",
        ),
        # Case 9: if ENABLE_COLLECTION_RETIREMENT is false, all versions are retained
        pytest.param(
            1,
            4,
            [],
            [],
            5,
            ["abc_dummy", "dummy_v1", "dummy_v2", "dummy_v3", "dummy_v4"],
            ["abc_dummy"],
            False,
            False,
            id="enable_collection_retirement",
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
    enable_collection_retirement,
):
    input_path, output_path = input_output_folder
    env.set("COLLECTION_HISTORY_LEN", str(hist_len))
    env.set("COLLECTION_RETIRE_DRY_RUN", str(dry_run).lower())
    env.set("ENABLE_COLLECTION_RETIREMENT", str(enable_collection_retirement).lower())

    input_file = input_path / "qdrant_at.csv"
    output_file = output_path / "QdrantConnectorStep"
    shutil.copy("./tests/data/embedded.csv", input_file)

    client = QdrantClient(location=":memory:")
    old_close = client.close
    client.close = print

    old_time = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    recent_time = (datetime.now(timezone.utc) - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    collection_data = [(col_id, recent_time if col_id in recently_used else old_time) for col_id in remaining_collections]

    mock_telemetry = [
        CollectionTelemetry(
            id=col_id,
            shards=[
                ReplicaSetTelemetry(
                    local=LocalShardTelemetry(
                        optimizations=OptimizerTelemetry(optimizations=OperationStats(last_responded=isoparse(last_used)))
                    ),
                    remote=[],
                )
            ],
        )
        for col_id, last_used in collection_data
    ]

    mock_aliases = CollectionsAliasesResponse(
        aliases=[AliasDescription(alias_name=col, collection_name=col) for col in aliased_collections]
    )

    with unittest.mock.patch("wurzel.steps.qdrant.retirement.CollectionRetirer._get_telemetry", return_value=mock_telemetry):
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


def test_get_telemetry_success(env, dummy_collection):
    """Test successful telemetry fetch from Qdrant."""
    env.set("COLLECTION", "dummy")

    client = QdrantClient(location=":memory:")
    client.close = print

    mock_response_data = {
        "result": {
            "collections": {
                "collections": [
                    {
                        "id": "test_collection",
                        "shards": [
                            {
                                "local": {"optimizations": {"optimizations": {"last_responded": "2025-01-15T10:30:00.000Z"}}},
                                "remote": [],
                            }
                        ],
                    }
                ]
            }
        }
    }
    mock_response = MagicMock()
    mock_response.json.return_value = mock_response_data
    mock_response.raise_for_status.return_value = None

    with patch("wurzel.steps.qdrant.step.QdrantClient") as mock_client:
        mock_client.return_value = client
        with patch("wurzel.steps.qdrant.retirement.requests.get", return_value=mock_response) as mock_get:
            step = QdrantConnectorStep()
            retirer = CollectionRetirer(step.client, step.settings)
            result = retirer._get_telemetry(details_level=3)
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert call_args[0][0] == "http://localhost:6333/telemetry?details_level=3"
            assert "api-key" in call_args[1]["headers"]
            assert "timeout" in call_args[1]
            assert call_args[1]["timeout"] > 0
            assert isinstance(result, list)
            assert len(result) == 1
            assert isinstance(result[0], CollectionTelemetry)
            assert result[0].id == "test_collection"
            shard = (result[0].shards or [])[0]
            assert shard.local is not None
            assert shard.local.optimizations is not None
            assert shard.local.optimizations.optimizations is not None
            assert shard.local.optimizations.optimizations.last_responded is not None


@pytest.mark.parametrize(
    "response_body, expected_exception, expected_result",
    [
        # --- Responses that must raise ValidationError ---
        pytest.param(
            {},
            ValidationError,
            None,
            id="empty_response_missing_result",
        ),
        pytest.param(
            {"result": None},
            ValidationError,
            None,
            id="result_is_null",
        ),
        pytest.param(
            {"result": {}},
            ValidationError,
            None,
            id="result_missing_collections_key",
        ),
        pytest.param(
            {"result": {"collections": {"collections": "not-a-list"}}},
            ValidationError,
            None,
            id="collections_is_wrong_type",
        ),
        pytest.param(
            {"result": {"collections": {"collections": [{"shards": []}]}}},
            ValidationError,
            None,
            id="collection_item_missing_required_id",
        ),
        # --- Valid but sparse responses that return an empty list ---
        pytest.param(
            {"result": {"collections": {}}},
            None,
            [],
            id="collections_key_absent_returns_empty",
        ),
        pytest.param(
            {"result": {"collections": {"collections": None}}},
            None,
            [],
            id="collections_null_returns_empty",
        ),
        pytest.param(
            {"result": {"collections": {"collections": []}}},
            None,
            [],
            id="empty_collections_list_returns_empty",
        ),
    ],
)
def test_get_telemetry_unexpected_response(env, dummy_collection, response_body, expected_exception, expected_result):
    """_get_telemetry must raise ValidationError for structurally invalid responses
    and gracefully return [] for valid-but-empty ones.
    """
    env.set("COLLECTION", "dummy")

    client = QdrantClient(location=":memory:")
    client.close = print

    mock_response = MagicMock()
    mock_response.json.return_value = response_body
    mock_response.raise_for_status.return_value = None

    with patch("wurzel.steps.qdrant.step.QdrantClient") as mock_client:
        mock_client.return_value = client
        with patch("wurzel.steps.qdrant.retirement.requests.get", return_value=mock_response):
            step = QdrantConnectorStep()
            retirer = CollectionRetirer(step.client, step.settings)
            if expected_exception is not None:
                with pytest.raises(expected_exception):
                    retirer._get_telemetry(details_level=3)
            else:
                result = retirer._get_telemetry(details_level=3)
                assert result == expected_result
