# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Abstract storage backend Protocol.

All concrete backends (Supabase, Postgres, in-memory, …) must implement this
interface so that route handlers can be written against a single stable API.
"""
# pylint: disable=unnecessary-ellipsis

from __future__ import annotations

from typing import Protocol, runtime_checkable

from wurzel.api.routes.search.data import SearchRequest, SearchResult


@runtime_checkable
class SearchBackend(Protocol):
    """Storage backend interface for the Wurzel Search API.

    Implementations must be safe for concurrent async access.
    """

    # ── Search ────────────────────────────────────────────────────────────────

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        """Execute a semantic / full-text search and return ranked results."""
        ...
