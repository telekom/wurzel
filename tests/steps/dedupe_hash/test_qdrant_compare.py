# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG

# Standard library imports


import os
import sys

import pandas as pd
import pytest

# Pfad zur wurzel-Bibliothek hinzufügen
sys.path.append(os.path.abspath("/Users/A1167082/Desktop/wurzel"))

from wurzel.steps.dedupe_hash.settings import QdrantCompareSettings
from wurzel.steps.dedupe_hash.step import QdrantCompareStep


# --------- make_step als Pytest-Fixture ---------
@pytest.fixture
def make_step():
    settings = QdrantCompareSettings()
    settings.QDRANT_URL = "http://localhost:6333"
    settings.QDRANT_API_KEY = "dummy"
    settings.OPAI_API_KEY = "dummy"
    settings.AZURE_ENDPOINT = "https://dummy-endpoint"
    settings.GPT_MODEL = "dummy"
    settings.QDRANT_COLLECTION_PREFIX = "test_v"
    settings.FUZZY_THRESHOLD = 85
    settings.TLSH_MAX_DIFF = 10

    step = QdrantCompareStep()
    step.settings = settings
    return step


# --------- Testfunktionen ---------


def test_identical_tlsh_analysis(make_step):
    step = make_step
    df1 = pd.DataFrame([{"tlsh": "A" * 70}, {"tlsh": "B" * 70}])
    df2 = pd.DataFrame([{"tlsh": "A" * 70}, {"tlsh": "C" * 70}])
    identical, count = step._identical_tlsh_analysis(df1, df2, "tlsh")
    assert count == 1
    assert "A" * 70 in identical


def test_fuzzy_tlsh_matches(make_step):
    step = make_step
    df = pd.DataFrame([{"tlsh": "A" * 70}, {"tlsh": "A" * 70}, {"tlsh": "B" * 70}])
    matches = step._fuzzy_tlsh_matches(df, "tlsh", 100)
    assert any(isinstance(m, tuple) and len(m) == 3 for m in matches)


def test_diff_snippet(make_step):
    step = make_step
    diff = step._diff_snippet("Hallo Welt", "Hallo Erde")
    assert "Hallo" in diff


def test_suspicious_cases_analysis(make_step):
    step = make_step
    df = pd.DataFrame([{"text": "Hallo Welten", "tlsh": "A" * 70}, {"text": "Hallo Erde", "tlsh": "B" * 70}])
    matches = [(0, 1, 5)]
    suspicious = step._suspicious_cases_analysis(df, matches, "text")
    assert isinstance(suspicious, list)
    assert suspicious[0]["fuzz_ratio"] < 100


def test_analyze_extra_docs_detail(make_step):
    step = make_step
    df_base = pd.DataFrame([{"text": "Hallo Welt"}])
    df_extra = pd.DataFrame([{"text": "Hallo Mars"}])
    result = step._analyze_extra_docs_detail(df_base, df_extra, "text", 80)
    assert isinstance(result, list)
    assert "is_truly_new" in result[0]


def test_extract_gpt_shortform(make_step):
    step = make_step
    assert step._extract_gpt_shortform({"gpt_analysis": "Contradiction found."}) == "contradiction"
    assert step._extract_gpt_shortform({"gpt_analysis": "Keep both"}) == "both"
    assert step._extract_gpt_shortform({"gpt_analysis": "Remove document 1"}) == "a remove"
    assert step._extract_gpt_shortform({"gpt_analysis": "Remove document 2"}) == "b remove"


def test_previous_version_exists(make_step, monkeypatch):
    step = make_step

    dummy_collections_response = {
        "result": {
            "collections": [
                {"name": "test_v1"},
                {"name": "test_v2"},
                {"name": "irrelevant_collection"},
            ]
        }
    }

    def mock_get(url, headers=None, *args, **kwargs):
        class DummyResponse:
            def raise_for_status(self):
                pass

            def json(self):
                return dummy_collections_response

        return DummyResponse()

    # monkeypatch requests.get auf deinen mock_get
    monkeypatch.setattr("requests.get", mock_get)

    collections = step.list_top_collections(
        qdrant_url=step.settings.QDRANT_URL,
        headers=step.headers,
        prefix=step.settings.QDRANT_COLLECTION_PREFIX,
        top_n=2,
    )

    assert isinstance(collections, list)
    assert len(collections) == 2
    assert collections == ["test_v2", "test_v1"]
