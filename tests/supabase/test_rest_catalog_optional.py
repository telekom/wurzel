# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Application-style check against PostgREST (Supabase REST).

Mirrors the “application-level testing” section of the Supabase testing guide:
https://supabase.com/docs/guides/local-development/testing/overview

Requires:
  - ``SUPABASE_URL`` (e.g. http://127.0.0.1:54321)
  - ``SUPABASE_ANON_KEY`` (publishable/anon key)

Set ``RUN_SUPABASE_REST_TESTS=1`` to enable.
"""

from __future__ import annotations

import os

import httpx
import pytest


@pytest.mark.supabase_rest
def test_step_type_catalog_readable_with_anon_key():
    if os.environ.get("RUN_SUPABASE_REST_TESTS") != "1":
        pytest.skip("Set RUN_SUPABASE_REST_TESTS=1 plus SUPABASE_URL and SUPABASE_ANON_KEY.")

    base = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_ANON_KEY", "")
    if not base or not key:
        pytest.skip("SUPABASE_URL and SUPABASE_ANON_KEY must be set.")

    url = f"{base}/rest/v1/step_type_catalog"
    params = {"select": "step_key", "limit": "1"}
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}

    response = httpx.get(url, params=params, headers=headers, timeout=30.0)
    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data, list)
