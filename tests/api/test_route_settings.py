# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for API route settings classes (search)."""

import pytest


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
