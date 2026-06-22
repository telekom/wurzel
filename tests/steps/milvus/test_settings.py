# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for MilvusSettings JSON validator and progress display."""

import json

import pytest

pymilvus = pytest.importorskip("pymilvus")

from wurzel.steps.milvus.settings import MilvusSettings  # noqa: E402


class TestMilvusSettingsParseJson:
    def test_parse_json_string_for_search_params(self):
        params = json.dumps({"metric_type": "L2", "params": {"nprobe": 10}})
        s = MilvusSettings(COLLECTION="col", USER="u", PASSWORD="p", SEARCH_PARAMS=params)
        assert s.SEARCH_PARAMS == {"metric_type": "L2", "params": {"nprobe": 10}}

    def test_parse_json_string_for_index_params(self):
        params = json.dumps({"index_type": "IVF_FLAT", "field_name": "vec", "metric_type": "IP", "params": {}})
        s = MilvusSettings(COLLECTION="col", USER="u", PASSWORD="p", INDEX_PARAMS=params)
        assert s.INDEX_PARAMS["index_type"] == "IVF_FLAT"

    def test_parse_json_dict_passthrough(self):
        params = {"metric_type": "IP", "params": {}}
        s = MilvusSettings(COLLECTION="col", USER="u", PASSWORD="p", SEARCH_PARAMS=params)
        assert s.SEARCH_PARAMS == params

    def test_defaults_applied(self):
        s = MilvusSettings(COLLECTION="col", USER="u", PASSWORD="p")
        assert s.HOST == "localhost"
        assert s.PORT == 19530
        assert s.SECURED is False
