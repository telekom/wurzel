-- SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
--
-- SPDX-License-Identifier: Apache-2.0

-- Migration: create branches table

CREATE TABLE IF NOT EXISTS branches (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      uuid        NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name            text        NOT NULL,
    is_protected    bool        NOT NULL DEFAULT false,
    is_default      bool        NOT NULL DEFAULT false,
    promotes_to_id  uuid        REFERENCES branches(id) ON DELETE SET NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),

    UNIQUE (project_id, name),

    -- The 'main' branch must always be protected
    CONSTRAINT main_always_protected CHECK (name <> 'main' OR is_protected = true)
);

CREATE INDEX IF NOT EXISTS branches_project_id_idx ON branches (project_id);

CREATE TRIGGER branches_updated_at
    BEFORE UPDATE ON branches
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
