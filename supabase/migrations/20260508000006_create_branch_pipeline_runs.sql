-- SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
--
-- SPDX-License-Identifier: Apache-2.0

-- Migration: create branch_pipeline_runs table
--
-- Stores full run history for branch manifest executions.

CREATE TABLE IF NOT EXISTS branch_pipeline_runs (
    id                uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    branch_id         uuid        NOT NULL REFERENCES branches(id) ON DELETE CASCADE,
    manifest_id       uuid        REFERENCES branch_manifests(id) ON DELETE SET NULL,
    manifest_snapshot jsonb       NOT NULL,
    backend_name      text        NOT NULL,
    backend_run_id    text,
    status            text        NOT NULL DEFAULT 'queued'
                                  CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
    logs_url          text,
    artifacts_url     text,
    error_message     text,
    created_by        text        NOT NULL,
    rerun_of_id       uuid        REFERENCES branch_pipeline_runs(id) ON DELETE SET NULL,
    started_at        timestamptz,
    finished_at       timestamptz,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS branch_pipeline_runs_branch_id_idx ON branch_pipeline_runs (branch_id);
CREATE INDEX IF NOT EXISTS branch_pipeline_runs_status_idx ON branch_pipeline_runs (status);
CREATE INDEX IF NOT EXISTS branch_pipeline_runs_created_at_idx ON branch_pipeline_runs (created_at DESC);

CREATE TRIGGER branch_pipeline_runs_updated_at
    BEFORE UPDATE ON branch_pipeline_runs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
