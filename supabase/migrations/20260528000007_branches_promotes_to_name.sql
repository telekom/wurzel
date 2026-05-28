-- SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
--
-- SPDX-License-Identifier: Apache-2.0

-- Migration: replace promotes_to_id (UUID FK) with promotes_to_name (text)
--
-- The application now resolves the promotion target by branch name within the
-- same project, so a plain text column is sufficient and avoids the need for a
-- self-referential FK join on every branch read.

ALTER TABLE branches
    DROP COLUMN IF EXISTS promotes_to_id,
    ADD COLUMN IF NOT EXISTS promotes_to_name text;
