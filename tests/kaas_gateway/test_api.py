# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("fastapi")

from wurzel.kaas_gateway import deps


@pytest.fixture
def patched_temporal():
    mock_inst = MagicMock()
    mock_inst.start_workflow = AsyncMock(
        return_value=SimpleNamespace(id="wurzel-pipeline-mocked-wid"),
    )
    connect_mock = AsyncMock(return_value=mock_inst)
    with patch("wurzel.kaas_gateway.app.Client.connect", connect_mock):
        from wurzel.kaas_gateway.app import create_app

        yield create_app(), mock_inst


@pytest.fixture
def mock_supabase_clients(monkeypatch):
    rev_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())

    user = MagicMock()
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.single.return_value = chain
    chain.execute.return_value = MagicMock(data={"id": rev_id, "dag_json": {"nodes": [], "edges": []}})
    user.from_.return_value = chain

    reg = MagicMock()
    reg.execute.return_value = MagicMock(data=run_id)
    user.rpc.return_value = reg

    svc = MagicMock()
    upd = MagicMock()
    upd.execute.return_value = MagicMock()
    svc.rpc.return_value = upd

    def _create_client(url, key, options=None):
        from wurzel.kaas_gateway.settings import get_settings

        s = get_settings()
        if key == s.SUPABASE_ANON_KEY:
            return user
        if key == s.SUPABASE_SERVICE_ROLE_KEY:
            return svc
        return user

    monkeypatch.setattr(deps, "create_client", _create_client)
    return rev_id, run_id, user, svc


def test_is_alive(patched_temporal):
    app, _ = patched_temporal
    with TestClient(app) as client:
        r = client.get("/api/v1/isAlive")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_search_not_implemented(patched_temporal):
    app, _ = patched_temporal
    with TestClient(app) as client:
        r = client.post("/api/v1/search", json={"query": "hello", "limit": 5})
    assert r.status_code == 501


def test_pipeline_start_success(patched_temporal, mock_supabase_clients):
    app, mock_temporal_inst = patched_temporal
    rev_id, run_id, _, _ = mock_supabase_clients
    with TestClient(app) as client:
        r = client.post(
            "/api/v1/pipeline-runs/start",
            json={"config_revision_id": rev_id},
            headers={"Authorization": "Bearer fake-jwt"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["pipeline_run_id"] == run_id
    assert body["temporal_workflow_id"] == "wurzel-pipeline-mocked-wid"
    mock_temporal_inst.start_workflow.assert_awaited_once()


def test_pipeline_missing_authorization(patched_temporal):
    app, _ = patched_temporal
    with TestClient(app) as client:
        r = client.post(
            "/api/v1/pipeline-runs/start",
            json={"config_revision_id": str(uuid.uuid4())},
        )
    assert r.status_code == 401


def test_workflow_status_success(patched_temporal, monkeypatch):
    from temporalio.client import WorkflowExecutionStatus

    app, mock_temporal_inst = patched_temporal
    wid = "wurzel-pipeline-test-run"
    pr_id = str(uuid.uuid4())

    pr_chain = MagicMock()
    pr_chain.select.return_value = pr_chain
    pr_chain.eq.return_value = pr_chain
    pr_chain.single.return_value = pr_chain
    pr_chain.execute.return_value = MagicMock(data={"id": pr_id, "status": "running"})
    user = MagicMock()
    user.from_.return_value = pr_chain

    mock_handle = MagicMock()
    mock_desc = MagicMock()
    mock_desc.status = WorkflowExecutionStatus.COMPLETED
    mock_handle.describe = AsyncMock(return_value=mock_desc)
    mock_temporal_inst.get_workflow_handle = MagicMock(return_value=mock_handle)

    def _create_client(url, key, options=None):
        from wurzel.kaas_gateway.settings import get_settings

        s = get_settings()
        if key == s.SUPABASE_ANON_KEY:
            return user
        return MagicMock()

    monkeypatch.setattr(deps, "create_client", _create_client)

    with TestClient(app) as client:
        r = client.get(
            f"/api/v1/workflow-status?workflow_id={wid}",
            headers={"Authorization": "Bearer fake-jwt"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["workflow_id"] == wid
    assert body["pipeline_run_id"] == pr_id
    assert body["temporal_status"] == "COMPLETED"
    assert body["db_status"] == "running"
    mock_temporal_inst.get_workflow_handle.assert_called_once_with(wid)
