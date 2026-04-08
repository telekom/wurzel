# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Optional wrapper for ``supabase test db`` (pgTAP).

Set ``RUN_SUPABASE_DB_TESTS=1`` and ensure the Supabase CLI is on ``PATH`` and local
Postgres has migrations applied (``supabase db reset`` / ``supabase start``).

See: https://supabase.com/docs/guides/local-development/testing/overview
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.supabase_db
def test_supabase_pgtap_via_cli():
    if os.environ.get("RUN_SUPABASE_DB_TESTS") != "1":
        pytest.skip("Set RUN_SUPABASE_DB_TESTS=1 to run pgTAP tests via Supabase CLI.")

    if not shutil.which("supabase"):
        pytest.skip("Supabase CLI not found on PATH.")

    proc = subprocess.run(
        ["supabase", "test", "db"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    if proc.returncode != 0:
        pytest.fail(
            f"supabase test db failed:\n--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}",
        )
