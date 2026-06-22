-- SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
--
-- SPDX-License-Identifier: Apache-2.0

-- Migration: create project_members table

CREATE TABLE IF NOT EXISTS project_members (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  uuid        NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id     text        NOT NULL,  -- Supabase Auth user UUID
    role        text        NOT NULL CHECK (role IN ('admin', 'member', 'secret_editor', 'viewer')),
    created_at  timestamptz NOT NULL DEFAULT now(),

    UNIQUE (project_id, user_id)  -- one role per user per project
);

CREATE INDEX IF NOT EXISTS project_members_project_id_idx ON project_members (project_id);
CREATE INDEX IF NOT EXISTS project_members_user_id_idx    ON project_members (user_id);
