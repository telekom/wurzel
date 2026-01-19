# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for wurzel.backend.values module (no optional dependencies required)."""

from pathlib import Path

import pytest
from pydantic import BaseModel

from wurzel.executors.backend.values import ValuesFileError, deep_merge_dicts, load_values


class SimpleModel(BaseModel):
    """Simple model for testing load_values."""

    key: str = "default"


class TestValuesFileError:
    def test_malformed_yaml_raises_values_file_error(self, tmp_path: Path):
        malformed_file = tmp_path / "malformed.yaml"
        malformed_file.write_text("key: value\n  bad_indent: oops")
        with pytest.raises(ValuesFileError, match="Failed to parse YAML"):
            load_values([malformed_file], SimpleModel)

    def test_non_dict_yaml_raises_values_file_error(self, tmp_path: Path):
        invalid_file = tmp_path / "invalid.yaml"
        invalid_file.write_text("- item1\n- item2")
        with pytest.raises(ValuesFileError, match="must start with a mapping"):
            load_values([invalid_file], SimpleModel)

    def test_error_message_includes_file_path(self, tmp_path: Path):
        malformed_file = tmp_path / "bad.yaml"
        malformed_file.write_text("key: value\n  bad: indent")
        with pytest.raises(ValuesFileError) as exc_info:
            load_values([malformed_file], SimpleModel)
        assert str(malformed_file) in str(exc_info.value)


class TestLoadValuesBasic:
    def test_empty_file(self, tmp_path: Path):
        empty_file = tmp_path / "empty.yaml"
        empty_file.write_text("")
        values = load_values([empty_file], SimpleModel)
        assert values.key == "default"

    def test_single_file(self, tmp_path: Path):
        file = tmp_path / "values.yaml"
        file.write_text("key: test-value")
        values = load_values([file], SimpleModel)
        assert values.key == "test-value"

    def test_no_files(self):
        values = load_values([], SimpleModel)
        assert values.key == "default"


class TestDeepMergeDictsBasic:
    def test_empty_dicts(self):
        assert deep_merge_dicts({}, {}) == {}

    def test_simple_merge(self):
        result = deep_merge_dicts({"a": 1}, {"b": 2})
        assert result == {"a": 1, "b": 2}

    def test_override(self):
        result = deep_merge_dicts({"a": 1}, {"a": 2})
        assert result == {"a": 2}

    def test_nested_merge(self):
        result = deep_merge_dicts({"a": {"b": 1}}, {"a": {"c": 2}})
        assert result == {"a": {"b": 1, "c": 2}}
