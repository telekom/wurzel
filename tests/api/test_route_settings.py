# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for API route settings classes (ingest, knowledge, search)."""

import pytest


class TestIngestSettings:
    def test_defaults(self):
        from wurzel.api.routes.ingest.settings import IngestSettings

        s = IngestSettings()
        assert s.MAX_BATCH_SIZE == 1000
        assert s.CONCURRENCY == 4

    def test_override_via_constructor(self):
        from wurzel.api.routes.ingest.settings import IngestSettings

        s = IngestSettings(MAX_BATCH_SIZE=500, CONCURRENCY=2)
        assert s.MAX_BATCH_SIZE == 500
        assert s.CONCURRENCY == 2

    def test_override_via_env(self, env):
        from wurzel.api.routes.ingest.settings import IngestSettings

        env.set("INGEST__MAX_BATCH_SIZE", "250")
        env.set("INGEST__CONCURRENCY", "8")
        s = IngestSettings()
        assert s.MAX_BATCH_SIZE == 250
        assert s.CONCURRENCY == 8

    def test_invalid_batch_size_raises(self):
        from wurzel.api.routes.ingest.settings import IngestSettings

        with pytest.raises(Exception):
            IngestSettings(MAX_BATCH_SIZE=0)


class TestKnowledgeSettings:
    def test_defaults(self):
        from wurzel.api.routes.knowledge.settings import KnowledgeSettings

        s = KnowledgeSettings()
        assert s.MAX_CONTENT_LENGTH == 1_000_000

    def test_override_via_constructor(self):
        from wurzel.api.routes.knowledge.settings import KnowledgeSettings

        s = KnowledgeSettings(MAX_CONTENT_LENGTH=512)
        assert s.MAX_CONTENT_LENGTH == 512

    def test_override_via_env(self, env):
        from wurzel.api.routes.knowledge.settings import KnowledgeSettings

        env.set("KNOWLEDGE__MAX_CONTENT_LENGTH", "65536")
        s = KnowledgeSettings()
        assert s.MAX_CONTENT_LENGTH == 65536

    def test_invalid_content_length_raises(self):
        from wurzel.api.routes.knowledge.settings import KnowledgeSettings

        with pytest.raises(Exception):
            KnowledgeSettings(MAX_CONTENT_LENGTH=0)


class TestSearchSettings:
    def test_defaults(self):
        from wurzel.api.routes.search.settings import SearchSettings

        s = SearchSettings()
        assert s.DEFAULT_LIMIT == 10
        assert s.SCORE_THRESHOLD == 0.0

    def test_override_via_constructor(self):
        from wurzel.api.routes.search.settings import SearchSettings

        s = SearchSettings(DEFAULT_LIMIT=25, SCORE_THRESHOLD=0.5)
        assert s.DEFAULT_LIMIT == 25
        assert s.SCORE_THRESHOLD == 0.5

    def test_override_via_env(self, env):
        from wurzel.api.routes.search.settings import SearchSettings

        env.set("SEARCH__DEFAULT_LIMIT", "20")
        env.set("SEARCH__SCORE_THRESHOLD", "0.7")
        s = SearchSettings()
        assert s.DEFAULT_LIMIT == 20
        assert s.SCORE_THRESHOLD == 0.7

    def test_invalid_limit_raises(self):
        from wurzel.api.routes.search.settings import SearchSettings

        with pytest.raises(Exception):
            SearchSettings(DEFAULT_LIMIT=0)

    def test_score_threshold_bounds(self):
        from wurzel.api.routes.search.settings import SearchSettings

        with pytest.raises(Exception):
            SearchSettings(SCORE_THRESHOLD=1.5)

        with pytest.raises(Exception):
            SearchSettings(SCORE_THRESHOLD=-0.1)
