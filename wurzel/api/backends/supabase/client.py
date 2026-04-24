# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Supabase client factory and FastAPI dependency.

Install the optional dependency with::

    pip install wurzel[supabase]

Usage in a route::

    from fastapi import Depends
    from wurzel.api.backends.supabase.client import get_backend

    @router.get("/example")
    async def example(backend = Depends(get_backend)):
        ...
"""

from __future__ import annotations

import logging
from functools import lru_cache

from wurzel.api.backends.supabase.settings import SupabaseSettings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_settings() -> SupabaseSettings:
    return SupabaseSettings()


def create_supabase_client(settings: SupabaseSettings | None = None):  # type: ignore[return]
    """Create and return a Supabase client instance.

    Args:
        settings: Override :class:`SupabaseSettings`.
                  Defaults to reading from environment variables.

    Returns:
        A ``supabase.Client`` instance.

    Raises:
        ImportError: If ``supabase`` is not installed (``wurzel[supabase]``).
    """
    try:
        from supabase import create_client  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError("supabase is not installed. Run: pip install wurzel[supabase]") from exc

    _settings = settings or _get_settings()
    client = create_client(_settings.URL, _settings.SERVICE_KEY.get_secret_value())
    logger.info("Supabase client created for project: %s", _settings.URL)
    return client


def get_backend():  # type: ignore[return]
    """FastAPI dependency that returns the configured :class:`~wurzel.api.backends.base.KnowledgeBackend`.

    Swap this dependency in ``app.py`` (or per-router ``dependencies=[...]``)
    once the ``SupabaseKnowledgeBackend`` implementation is complete.
    """
    raise NotImplementedError(
        "SupabaseKnowledgeBackend is not yet implemented. Implement wurzel/api/backends/supabase/backend.py and wire it here."
    )
