-- SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
--
-- SPDX-License-Identifier: Apache-2.0

-- Migration: create branch_manifests table
--
-- Each branch holds at most ONE active manifest definition (1:1 via UNIQUE branch_id).
-- The definition column stores the full PipelineManifest as JSONB.

CREATE TABLE IF NOT EXISTS branch_manifests (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    branch_id   uuid        NOT NULL REFERENCES branches(id) ON DELETE CASCADE,
    definition  jsonb       NOT NULL,
    run_status  text        NOT NULL DEFAULT 'pending'
                            CHECK (run_status IN ('pending', 'running', 'succeeded', 'failed', 'cancelled')),
    run_id      text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),

    UNIQUE (branch_id)  -- one manifest per branch
);

CREATE INDEX IF NOT EXISTS branch_manifests_branch_id_idx ON branch_manifests (branch_id);

CREATE TRIGGER branch_manifests_updated_at
    BEFORE UPDATE ON branch_manifests
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
