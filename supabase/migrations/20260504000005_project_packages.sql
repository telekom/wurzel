-- SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
--
-- SPDX-License-Identifier: Apache-2.0

-- Migration: per-project secrets, packages, and package lock tables


-- ── project_secrets ───────────────────────────────────────────────────────────
-- General-purpose per-project secret store. Initially used for private PyPI
-- index URLs; intentionally generic so other secrets can be stored here later.
-- Access is restricted to 'admin' and 'secret_editor' roles — values are
-- never returned by the list endpoint.

CREATE TABLE IF NOT EXISTS project_secrets (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  uuid        NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name        text        NOT NULL,     -- logical key, e.g. "my_private_index_url"
    value       text        NOT NULL,     -- plaintext secret value
    created_by  text        NOT NULL,     -- JWT sub of creator
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),

    UNIQUE (project_id, name)
);

CREATE INDEX IF NOT EXISTS project_secrets_project_id_idx ON project_secrets (project_id);

-- Auto-update updated_at on every write
CREATE OR REPLACE FUNCTION update_project_secrets_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END;
$$;

CREATE TRIGGER trg_project_secrets_updated_at
    BEFORE UPDATE ON project_secrets
    FOR EACH ROW EXECUTE FUNCTION update_project_secrets_updated_at();


-- ── project_packages ─────────────────────────────────────────────────────────
-- Tracks Python packages that a project admin has requested to install at
-- runtime. The background job picks up rows with status='pending', claims them
-- (optimistic distributed lock via status + installer_id), and runs
-- `uv pip install --target=<PACKAGES_DIR>/<project_id>/`.

CREATE TABLE IF NOT EXISTS project_packages (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          uuid        NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    package_spec        text        NOT NULL,   -- PEP 508 spec, e.g. "mypkg==1.0.0"
    index_secret_name   text,                   -- optional FK-by-name into project_secrets
    status              text        NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending', 'installing', 'installed', 'failed', 'deleted')),
    error               text,
    installer_id        text,                   -- replica UUID that claimed this install
    installed_at        timestamptz,
    created_at          timestamptz NOT NULL DEFAULT now(),
    created_by          text        NOT NULL    -- JWT sub of requester
);

CREATE INDEX IF NOT EXISTS project_packages_project_id_idx ON project_packages (project_id);
CREATE INDEX IF NOT EXISTS project_packages_status_idx     ON project_packages (status);


-- ── project_package_locks ────────────────────────────────────────────────────
-- DB-stored lock file: one row per resolved transitive dependency after a
-- successful install.  On startup, fresh replicas use these rows to re-install
-- with `uv pip install --require-hashes` for bit-for-bit reproducibility.

CREATE TABLE IF NOT EXISTS project_package_locks (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    package_id   uuid NOT NULL REFERENCES project_packages(id) ON DELETE CASCADE,
    requirement  text NOT NULL,   -- resolved name+version, e.g. "httpx==0.27.0"
    sha256       text NOT NULL    -- SHA-256 hash from .dist-info/RECORD
);

CREATE INDEX IF NOT EXISTS project_package_locks_package_id_idx ON project_package_locks (package_id);
