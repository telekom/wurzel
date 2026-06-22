-- SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
--
-- SPDX-License-Identifier: Apache-2.0

-- Migration: create projects table

CREATE TABLE IF NOT EXISTS projects (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    name        text        NOT NULL,
    description text,
    created_by  text        NOT NULL,  -- Supabase Auth user UUID (JWT 'sub')
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

-- Index for listing projects by creator
CREATE INDEX IF NOT EXISTS projects_created_by_idx ON projects (created_by);

-- Auto-update updated_at on every row change
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER projects_updated_at
    BEFORE UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
