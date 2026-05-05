# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for wurzel.api.package_manager.db."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch


def _chain_query(data):
    query = MagicMock()
    query.select.return_value = query
    query.eq.return_value = query
    query.neq.return_value = query
    query.maybe_single.return_value = query
    query.upsert.return_value = query
    query.delete.return_value = query
    query.insert.return_value = query
    query.update.return_value = query
    query.in_.return_value = query
    query.execute = AsyncMock(return_value=SimpleNamespace(data=data))
    return query


class TestPackageManagerDB:
    def test_get_secret_value_none(self):
        from wurzel.api.package_manager.db import db_get_secret_value

        project_id = uuid.uuid4()
        db = MagicMock()
        db.table.return_value = _chain_query(None)

        with patch("wurzel.api.package_manager.db._get_client", new_callable=AsyncMock, return_value=db):
            value = asyncio.run(db_get_secret_value(project_id, "missing"))

        assert value is None

    def test_get_client_uses_supabase_async_client(self):
        from wurzel.api.package_manager.db import _get_client

        client = MagicMock()
        with patch("wurzel.api.backends.supabase.client._get_async_client", new_callable=AsyncMock, return_value=client):
            got = asyncio.run(_get_client())
        assert got is client

    def test_list_project_secrets(self):
        from wurzel.api.package_manager.db import db_list_project_secrets

        project_id = uuid.uuid4()
        rows = [{"id": str(uuid.uuid4()), "name": "index"}]
        db = MagicMock()
        db.table.return_value = _chain_query(rows)

        with patch("wurzel.api.package_manager.db._get_client", new_callable=AsyncMock, return_value=db):
            result = asyncio.run(db_list_project_secrets(project_id))

        assert result == rows

    def test_get_secret_value_found(self):
        from wurzel.api.package_manager.db import db_get_secret_value

        project_id = uuid.uuid4()
        db = MagicMock()
        db.table.return_value = _chain_query({"value": "https://secret-index/simple"})

        with patch("wurzel.api.package_manager.db._get_client", new_callable=AsyncMock, return_value=db):
            value = asyncio.run(db_get_secret_value(project_id, "index"))

        assert value == "https://secret-index/simple"

    def test_claim_pending_package_true_and_false(self):
        from wurzel.api.package_manager.db import db_claim_pending_package

        package_id = uuid.uuid4()

        db_true = MagicMock()
        db_true.table.return_value = _chain_query([{"id": str(package_id)}])
        with patch("wurzel.api.package_manager.db._get_client", new_callable=AsyncMock, return_value=db_true):
            assert asyncio.run(db_claim_pending_package(package_id, "replica-1")) is True

        db_false = MagicMock()
        db_false.table.return_value = _chain_query([])
        with patch("wurzel.api.package_manager.db._get_client", new_callable=AsyncMock, return_value=db_false):
            assert asyncio.run(db_claim_pending_package(package_id, "replica-1")) is False

    def test_add_list_delete_package_and_mark_failed(self):
        from wurzel.api.package_manager.db import (
            db_add_project_package,
            db_delete_project_package,
            db_list_project_packages,
            db_mark_failed,
        )

        project_id = uuid.uuid4()
        package_id = uuid.uuid4()
        inserted = {"id": str(package_id), "project_id": str(project_id), "package_spec": "mypkg==1.0.0"}

        insert_q = _chain_query([inserted])
        list_q = _chain_query([inserted])
        delete_q = _chain_query([])
        failed_q = _chain_query([])
        db = MagicMock()
        db.table.side_effect = [insert_q, list_q, delete_q, failed_q]

        with patch("wurzel.api.package_manager.db._get_client", new_callable=AsyncMock, return_value=db):
            add_row = asyncio.run(db_add_project_package(project_id, "mypkg==1.0.0", None, "u1"))
            listed = asyncio.run(db_list_project_packages(project_id))
            asyncio.run(db_delete_project_package(project_id, package_id))
            asyncio.run(db_mark_failed(package_id, "boom"))

        assert add_row == inserted
        assert listed == [inserted]
        delete_q.update.assert_called_once_with({"status": "deleted"})
        failed_q.update.assert_called_once_with({"status": "failed", "error": "boom"})

    def test_upsert_and_delete_secret(self):
        from wurzel.api.package_manager.db import db_delete_project_secret, db_upsert_project_secret

        project_id = uuid.uuid4()
        row = {"id": str(uuid.uuid4()), "name": "index", "created_by": "u1"}

        upsert_q = _chain_query([row])
        delete_q = _chain_query([])
        db = MagicMock()
        db.table.side_effect = [upsert_q, delete_q]

        with patch("wurzel.api.package_manager.db._get_client", new_callable=AsyncMock, return_value=db):
            got = asyncio.run(db_upsert_project_secret(project_id, "index", "https://secret", "u1"))
            asyncio.run(db_delete_project_secret(project_id, "index"))

        assert got == row
        upsert_q.upsert.assert_called_once()
        delete_q.delete.assert_called_once()

    def test_mark_installed_inserts_locks(self):
        from wurzel.api.package_manager.db import db_mark_installed

        package_id = uuid.uuid4()
        update_q = _chain_query([])
        insert_q = _chain_query([])
        db = MagicMock()
        db.table.side_effect = [update_q, insert_q]

        locks = [{"requirement": "mypkg==1.0.0", "sha256": "abc123"}]
        with patch("wurzel.api.package_manager.db._get_client", new_callable=AsyncMock, return_value=db):
            asyncio.run(db_mark_installed(package_id, locks))

        update_q.update.assert_called_once()
        insert_q.insert.assert_called_once_with([{"package_id": str(package_id), "requirement": "mypkg==1.0.0", "sha256": "abc123"}])

    def test_mark_installed_without_locks_skips_insert(self):
        from wurzel.api.package_manager.db import db_mark_installed

        package_id = uuid.uuid4()
        update_q = _chain_query([])
        db = MagicMock()
        db.table.return_value = update_q

        with patch("wurzel.api.package_manager.db._get_client", new_callable=AsyncMock, return_value=db):
            asyncio.run(db_mark_installed(package_id, []))

        assert db.table.call_count == 1

    def test_reset_stale_installing_resets_old_rows(self):
        from datetime import datetime, timedelta

        from wurzel.api.package_manager.db import db_reset_stale_installing

        old = (datetime.now(tz=UTC) - timedelta(seconds=601)).isoformat()
        fresh = (datetime.now(tz=UTC) - timedelta(seconds=10)).isoformat()

        select_q = _chain_query([{"id": "a", "created_at": old}, {"id": "b", "created_at": fresh}])
        update_q = _chain_query([])
        db = MagicMock()
        db.table.side_effect = [select_q, update_q]

        with patch("wurzel.api.package_manager.db._get_client", new_callable=AsyncMock, return_value=db):
            count = asyncio.run(db_reset_stale_installing("replica-1", 300))

        assert count == 1
        update_q.in_.assert_called_once_with("id", ["a"])

    def test_reset_stale_installing_unparseable_timestamp_is_reset(self):
        from wurzel.api.package_manager.db import db_reset_stale_installing

        select_q = _chain_query([{"id": "bad", "created_at": "not-a-date"}])
        update_q = _chain_query([])
        db = MagicMock()
        db.table.side_effect = [select_q, update_q]

        with patch("wurzel.api.package_manager.db._get_client", new_callable=AsyncMock, return_value=db):
            count = asyncio.run(db_reset_stale_installing("replica-1", 300))

        assert count == 1
        update_q.in_.assert_called_once_with("id", ["bad"])

    def test_reset_stale_installing_returns_zero_when_no_stale_rows(self):
        from datetime import datetime

        from wurzel.api.package_manager.db import db_reset_stale_installing

        fresh = datetime.now(tz=UTC).isoformat()
        select_q = _chain_query([{"id": "fresh", "created_at": fresh}])
        db = MagicMock()
        db.table.return_value = select_q

        with patch("wurzel.api.package_manager.db._get_client", new_callable=AsyncMock, return_value=db):
            count = asyncio.run(db_reset_stale_installing("replica-1", 300))

        assert count == 0

    def test_get_installed_packages_with_locks(self):
        from wurzel.api.package_manager.db import db_get_installed_packages_with_locks

        row = {
            "id": str(uuid.uuid4()),
            "project_id": str(uuid.uuid4()),
            "package_spec": "mypkg==1.0.0",
            "project_package_locks": [{"requirement": "mypkg==1.0.0", "sha256": "abc"}],
        }
        db = MagicMock()
        db.table.return_value = _chain_query([row])

        with patch("wurzel.api.package_manager.db._get_client", new_callable=AsyncMock, return_value=db):
            rows = asyncio.run(db_get_installed_packages_with_locks())

        assert rows == [row]

    def test_get_pending_packages(self):
        from wurzel.api.package_manager.db import db_get_pending_packages

        rows = [{"id": str(uuid.uuid4()), "status": "pending"}]
        db = MagicMock()
        db.table.return_value = _chain_query(rows)

        with patch("wurzel.api.package_manager.db._get_client", new_callable=AsyncMock, return_value=db):
            result = asyncio.run(db_get_pending_packages())

        assert result == rows
