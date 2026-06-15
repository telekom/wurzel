# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for wurzel.executors.backend.values module."""

from pathlib import Path

import pytest
from pydantic import BaseModel

from wurzel.executors.backend.values import ValuesFileError, deep_merge_dicts, load_values


class SimpleModel(BaseModel):
    """Simple model for testing load_values."""

    key: str = "default"


class TestValuesFileError:
    def test_malformed_yaml_raises_values_file_error(self, tmp_path: Path):
        """Test that malformed YAML raises ValuesFileError."""
        malformed_file = tmp_path / "malformed.yaml"
        malformed_file.write_text("key: value\n  bad_indent: oops")
        with pytest.raises(ValuesFileError, match="Failed to parse YAML"):
            load_values([malformed_file], SimpleModel)

    def test_non_dict_yaml_raises_values_file_error(self, tmp_path: Path):
        """Test that non-dict YAML raises ValuesFileError."""
        invalid_file = tmp_path / "invalid.yaml"
        invalid_file.write_text("- item1\n- item2")
        with pytest.raises(ValuesFileError, match="must start with a mapping"):
            load_values([invalid_file], SimpleModel)

    def test_missing_file_raises_values_file_error(self, tmp_path: Path):
        """Test that missing file raises ValuesFileError."""
        missing_file = tmp_path / "nonexistent.yaml"
        with pytest.raises(ValuesFileError, match="does not exist"):
            load_values([missing_file], SimpleModel)


class TestDeepMergeDicts:
    def test_merge_simple_dicts(self):
        """Test merging two simple dictionaries."""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = deep_merge_dicts(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_merge_nested_dicts(self):
        """Test merging nested dictionaries."""
        base = {"outer": {"inner": 1, "keep": "me"}}
        override = {"outer": {"inner": 2, "new": "value"}}
        result = deep_merge_dicts(base, override)
        assert result == {"outer": {"inner": 2, "keep": "me", "new": "value"}}

    def test_merge_with_lists(self):
        """Test that lists are replaced, not merged."""
        base = {"items": [1, 2, 3]}
        override = {"items": [4, 5]}
        result = deep_merge_dicts(base, override)
        assert result == {"items": [4, 5]}

    def test_merge_empty_dicts(self):
        """Test merging with empty dictionaries."""
        base = {"a": 1}
        result = deep_merge_dicts(base, {})
        assert result == {"a": 1}

        result = deep_merge_dicts({}, {"b": 2})
        assert result == {"b": 2}


class TestLoadValues:
    def test_load_single_file(self, tmp_path: Path):
        """Test loading values from a single file."""
        values_file = tmp_path / "values.yaml"
        values_file.write_text("key: custom")

        result = load_values([values_file], SimpleModel)
        assert result.key == "custom"

    def test_load_multiple_files_with_override(self, tmp_path: Path):
        """Test loading and merging multiple values files."""
        base_file = tmp_path / "base.yaml"
        base_file.write_text("key: base")

        override_file = tmp_path / "override.yaml"
        override_file.write_text("key: override")

        result = load_values([base_file, override_file], SimpleModel)
        assert result.key == "override"

    def test_load_with_default_values(self, tmp_path: Path):
        """Test that default values are used when not in file."""
        values_file = tmp_path / "empty.yaml"
        values_file.write_text("{}")

        result = load_values([values_file], SimpleModel)
        assert result.key == "default"
