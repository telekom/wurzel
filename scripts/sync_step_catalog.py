#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0
"""Export TypedStep metadata to JSON and/or SQL for ``public.step_type_catalog``.

Examples:
  uv run python scripts/sync_step_catalog.py --out-json apps/web/public/step_catalog.json
  uv run python scripts/sync_step_catalog.py --out-sql supabase/migrations/20260407120100_step_catalog_seed.sql
"""

from __future__ import annotations

import argparse
from pathlib import Path

from wurzel.kaas.catalog_export import (
    catalog_to_json,
    catalog_to_sql_upserts,
    iter_step_catalog_entries,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--package",
        default="wurzel.steps",
        help="Root package to scan for TypedStep subclasses (default: wurzel.steps).",
    )
    parser.add_argument("--out-json", type=Path, help="Write catalog JSON for the web UI.")
    parser.add_argument(
        "--out-sql",
        type=Path,
        help="Write SQL upserts for Supabase (run via migration or psql).",
    )
    args = parser.parse_args()

    entries = iter_step_catalog_entries(args.package)
    if not entries:
        raise SystemExit("No steps discovered; check --package.")

    if args.out_json:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(catalog_to_json(entries), encoding="utf-8")
        print(f"Wrote {len(entries)} entries to {args.out_json}")

    if args.out_sql:
        args.out_sql.parent.mkdir(parents=True, exist_ok=True)
        header = "-- Step type catalog seed (generated)\n\n"
        args.out_sql.write_text(header + catalog_to_sql_upserts(entries), encoding="utf-8")
        print(f"Wrote SQL upserts to {args.out_sql}")

    if not args.out_json and not args.out_sql:
        print(catalog_to_json(entries))


if __name__ == "__main__":
    main()
