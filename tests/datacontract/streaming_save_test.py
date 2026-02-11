# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for PydanticModel.save_to_path streaming JSON serialization.

The streaming implementation writes JSON arrays item-by-item to avoid
building the entire serialised string in memory.
"""

import json
from typing import Any

import pytest

from wurzel.datacontract.datacontract import PydanticModel


class SimpleItem(PydanticModel):
    value: int
    name: str


class ItemWithSpecialChars(PydanticModel):
    text: str


class ItemWithNested(PydanticModel):
    value: int
    tags: list[str]
    meta: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Round-trip: save list -> load list
# ---------------------------------------------------------------------------


def test_save_list_roundtrip(tmp_path):
    """Save a list of PydanticModel instances, load it back, assert equality."""
    items = [SimpleItem(value=i, name=f"item_{i}") for i in range(5)]
    path = tmp_path / "output"

    SimpleItem.save_to_path(path, items)

    loaded = SimpleItem.load_from_path(tmp_path / "output.json", list[SimpleItem])
    assert len(loaded) == 5
    for i, item in enumerate(loaded):
        assert item.value == i
        assert item.name == f"item_{i}"


def test_save_list_produces_valid_json(tmp_path):
    """Save a list and verify the raw file is a valid JSON array."""
    items = [SimpleItem(value=i, name=f"n{i}") for i in range(3)]
    SimpleItem.save_to_path(tmp_path / "out", items)

    with (tmp_path / "out.json").open() as f:
        raw = json.load(f)

    assert isinstance(raw, list)
    assert len(raw) == 3
    assert raw[0] == {"value": 0, "name": "n0"}
    assert raw[2] == {"value": 2, "name": "n2"}


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_save_empty_list(tmp_path):
    """Empty list should produce '[]' on disk."""
    SimpleItem.save_to_path(tmp_path / "empty", [])

    with (tmp_path / "empty.json").open() as f:
        raw = json.load(f)
    assert raw == []


def test_save_single_item_list(tmp_path):
    """List with one element — no array-separator comma should appear."""
    items = [SimpleItem(value=42, name="only")]
    SimpleItem.save_to_path(tmp_path / "single", items)

    text = (tmp_path / "single.json").read_text(encoding="UTF-8")
    parsed = json.loads(text)
    assert len(parsed) == 1
    assert parsed[0]["value"] == 42
    # The text starts with '[{' and ends with '}]' — no comma separating
    # array elements (commas *within* the single object are fine).
    assert text.startswith("[{")
    assert text.endswith("}]")


# ---------------------------------------------------------------------------
# Large list (exercises streaming without being slow in CI)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("count", [100, 1_000, 10_000])
def test_save_large_list_roundtrip(tmp_path, count):
    """Save a large list and verify all items survive the round-trip."""
    items = [SimpleItem(value=i, name=f"item_{i}") for i in range(count)]
    SimpleItem.save_to_path(tmp_path / "big", items)

    loaded = SimpleItem.load_from_path(tmp_path / "big.json", list[SimpleItem])
    assert len(loaded) == count
    assert loaded[0].value == 0
    assert loaded[-1].value == count - 1


# ---------------------------------------------------------------------------
# Special characters / unicode
# ---------------------------------------------------------------------------


def test_save_list_special_chars(tmp_path):
    """Items with unicode, quotes, newlines — ensure JSON escaping is correct."""
    items = [
        ItemWithSpecialChars(text='hello "world"'),
        ItemWithSpecialChars(text="line1\nline2\ttab"),
        ItemWithSpecialChars(text="emoji: \U0001f680"),
        ItemWithSpecialChars(text="backslash: \\path\\to\\file"),
        ItemWithSpecialChars(text="umlaut: \u00e4\u00f6\u00fc\u00df"),
    ]
    ItemWithSpecialChars.save_to_path(tmp_path / "special", items)

    loaded = ItemWithSpecialChars.load_from_path(tmp_path / "special.json", list[ItemWithSpecialChars])
    assert len(loaded) == len(items)
    for orig, got in zip(items, loaded):
        assert orig.text == got.text


# ---------------------------------------------------------------------------
# Nested / complex fields
# ---------------------------------------------------------------------------


def test_save_list_nested_fields(tmp_path):
    """Items with list and dict fields are serialized correctly."""
    items = [
        ItemWithNested(value=1, tags=["a", "b"], meta={"key": "val"}),
        ItemWithNested(value=2, tags=[], meta=None),
        ItemWithNested(value=3, tags=["x"], meta={"nested": {"deep": True}}),
    ]
    ItemWithNested.save_to_path(tmp_path / "nested", items)

    loaded = ItemWithNested.load_from_path(tmp_path / "nested.json", list[ItemWithNested])
    assert len(loaded) == 3
    assert loaded[0].tags == ["a", "b"]
    assert loaded[0].meta == {"key": "val"}
    assert loaded[1].meta is None
    assert loaded[2].meta == {"nested": {"deep": True}}


# ---------------------------------------------------------------------------
# Consistency with single-object save
# ---------------------------------------------------------------------------


def test_save_single_object_unchanged(tmp_path):
    """Saving a single PydanticModel (not a list) still works as before."""
    item = SimpleItem(value=99, name="solo")
    SimpleItem.save_to_path(tmp_path / "solo", item)

    loaded = SimpleItem.load_from_path(tmp_path / "solo.json", SimpleItem)
    assert loaded.value == 99
    assert loaded.name == "solo"


def test_save_unsupported_type_raises(tmp_path):
    """Saving an unsupported type still raises NotImplementedError."""
    with pytest.raises(NotImplementedError):
        SimpleItem.save_to_path(tmp_path / "bad", "not a model")
