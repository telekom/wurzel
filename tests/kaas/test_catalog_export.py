# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from wurzel.kaas.catalog_export import build_entry, catalog_to_sql_upserts
from wurzel.steps.duplication import DropDuplicationStep
from wurzel.steps.manual_markdown import ManualMarkdownStep


def test_build_entry_manual_markdown():
    entry = build_entry(ManualMarkdownStep)
    assert entry["step_key"] == "wurzel.steps.manual_markdown.ManualMarkdownStep"
    assert entry["settings_json_schema"] is not None
    assert entry["input_json_schema"] == {"type": "null", "title": "input"}


def test_build_entry_drop_duplication():
    entry = build_entry(DropDuplicationStep)
    assert "MarkdownDataContract" in (entry.get("input_type_fqn") or "")


def test_catalog_sql_contains_step_key():
    entries = [build_entry(ManualMarkdownStep)]
    sql = catalog_to_sql_upserts(entries)
    assert "ManualMarkdownStep" in sql
    assert "on conflict (step_key)" in sql
