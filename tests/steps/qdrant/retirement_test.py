# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import shutil
import unittest.mock
from pathlib import Path

import pytest

from wurzel.utils import HAS_QDRANT

if not HAS_QDRANT:
    pytest.skip("Qdrant is not available", allow_module_level=True)

from qdrant_client import QdrantClient, models
from qdrant_client.models import AliasDescription, CollectionsAliasesResponse

from wurzel.executors import BaseStepExecutor
from wurzel.steps.qdrant import QdrantConnectorStep


@pytest.mark.parametrize(
    "hist_len, step_run, aliased_collections, count_remaining_collection, remaining_collections,"
    "untracked_collection, dry_run, enable_collection_retirement",
    [
        # Case 1: v1 is aliased, keep v3-v5 by version
        pytest.param(
            3,
            5,
            ["dummy_v1"],
            4,
            ["dummy_v1", "dummy_v3", "dummy_v4", "dummy_v5"],
            [],
            False,
            True,
            id="aliased_and_latest_versions",
        ),
        # Case 2: Keep only latest v4; v2 is aliased. Unused v1 is deleted.
        pytest.param(1, 4, ["dummy_v2"], 2, ["dummy_v2", "dummy_v4"], [], False, True, id="latest_plus_alias"),
        # Case 3: Keep top 2 by version only
        pytest.param(2, 5, [], 2, ["dummy_v4", "dummy_v5"], [], False, True, id="top_versions_only"),
        # Case 4: v2 aliased; keep v4,v5
        pytest.param(2, 5, ["dummy_v2"], 3, ["dummy_v2", "dummy_v4", "dummy_v5"], [], False, True, id="aliased_plus_top_versions"),
        # Case 5: Only latest v4; v1,v2 aliased
        pytest.param(
            1, 4, ["dummy_v1", "dummy_v2"], 3, ["dummy_v1", "dummy_v2", "dummy_v4"], [], False, True, id="multiple_aliased_and_latest"
        ),
        # Case 6: Untracked collection (abc_dummy) should not be deleted, latest v4,v5
        pytest.param(2, 5, [], 3, ["abc_dummy", "dummy_v4", "dummy_v5"], ["abc_dummy"], False, True, id="untracked_collection_retained"),
        # Case 7: Dry run mode (no deletions)
        pytest.param(
            2,
            5,
            [],
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

    mock_aliases = CollectionsAliasesResponse(
        aliases=[AliasDescription(alias_name=col, collection_name=col) for col in aliased_collections]
    )

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
