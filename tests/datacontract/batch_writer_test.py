# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for BatchWriter and DataModel.batch_writer().

Covers:
- Buffer accumulation and automatic flush at threshold
- Manual flush of partial buffers
- Context manager (directory creation, auto-flush on exit)
- Read-only stat properties (total_items, file_count, store_time)
- Edge cases: empty extend, no output path, custom flush size
- File naming convention (_batch0000, _batch0001, …)
- Data integrity round-trip through batch files
- Best-effort sorting (sortable and unsortable items)
- DataModel.batch_writer() classmethod / inheritance
"""

import json
from typing import Any

import pytest

from wurzel.datacontract.datacontract import BatchWriter, DataModel, PanderaDataFrameModel, PydanticModel

# ---------------------------------------------------------------------------
# Test models
# ---------------------------------------------------------------------------


class SimpleItem(PydanticModel):
    value: int
    name: str = ""


class UnsortableItem(PydanticModel):
    """A model that deliberately breaks comparison to test _try_sort fallback."""

    data: dict[str, Any]

    def __lt__(self, other: object) -> bool:  # noqa: ARG002
        raise TypeError("unsortable on purpose")

    def __hash__(self) -> int:
        return id(self)


# ---------------------------------------------------------------------------
# BatchWriter: basic accumulation
# ---------------------------------------------------------------------------


class TestBatchWriterAccumulation:
    def test_extend_below_threshold_does_not_flush(self, tmp_path):
        """Items below flush_size stay in the buffer; no files are written."""
        writer = BatchWriter(SimpleItem, tmp_path, "test", flush_size=10)
        with writer:
            writer.extend([SimpleItem(value=i) for i in range(5)])
            # Before exiting, nothing has been flushed yet
            assert writer.file_count == 0
            assert writer.total_items == 0
        # After __exit__, the remaining 5 items are flushed
        assert writer.total_items == 5
        assert writer.file_count == 1

    def test_extend_triggers_auto_flush(self, tmp_path):
        """When the buffer reaches flush_size, items are flushed automatically."""
        with BatchWriter(SimpleItem, tmp_path, "test", flush_size=5) as writer:
            writer.extend([SimpleItem(value=i) for i in range(12)])
        # 12 items with flush_size=5: 2 full flushes (5+5) + 1 partial (2)
        assert writer.total_items == 12
        assert writer.file_count == 3

    def test_extend_exact_flush_size(self, tmp_path):
        """Extending with exactly flush_size items triggers one flush, no remainder."""
        with BatchWriter(SimpleItem, tmp_path, "test", flush_size=5) as writer:
            writer.extend([SimpleItem(value=i) for i in range(5)])
        assert writer.total_items == 5
        assert writer.file_count == 1

    def test_multiple_extend_calls(self, tmp_path):
        """Several small extend calls accumulate in the buffer until threshold."""
        with BatchWriter(SimpleItem, tmp_path, "test", flush_size=6) as writer:
            writer.extend([SimpleItem(value=1)])
            writer.extend([SimpleItem(value=2)])
            writer.extend([SimpleItem(value=3)])
            assert writer.file_count == 0  # still below threshold
            writer.extend([SimpleItem(value=i) for i in range(4, 8)])  # total = 7
        # 7 items / flush_size 6 → 1 full flush + 1 partial (1 item)
        assert writer.total_items == 7
        assert writer.file_count == 2

    def test_extend_with_generator(self, tmp_path):
        """extend() accepts non-list iterables (e.g. generators)."""
        with BatchWriter(SimpleItem, tmp_path, "test", flush_size=100) as writer:
            writer.extend(SimpleItem(value=i) for i in range(10))
        assert writer.total_items == 10
        assert writer.file_count == 1


# ---------------------------------------------------------------------------
# BatchWriter: manual flush
# ---------------------------------------------------------------------------


class TestBatchWriterManualFlush:
    def test_flush_writes_partial_buffer(self, tmp_path):
        writer = BatchWriter(SimpleItem, tmp_path, "test", flush_size=100)
        with writer:
            writer.extend([SimpleItem(value=1), SimpleItem(value=2)])
            writer.flush()
            assert writer.total_items == 2
            assert writer.file_count == 1
            # Buffer is now empty; another flush is a no-op
            writer.flush()
            assert writer.file_count == 1

    def test_flush_on_empty_buffer_is_noop(self, tmp_path):
        writer = BatchWriter(SimpleItem, tmp_path, "test", flush_size=100)
        with writer:
            writer.flush()
        assert writer.total_items == 0
        assert writer.file_count == 0


# ---------------------------------------------------------------------------
# BatchWriter: context manager
# ---------------------------------------------------------------------------


class TestBatchWriterContextManager:
    def test_creates_output_directory(self, tmp_path):
        out = tmp_path / "nested" / "deep" / "output"
        with BatchWriter(SimpleItem, out, "test") as writer:
            writer.extend([SimpleItem(value=1)])
        assert out.is_dir()

    def test_exit_flushes_remaining(self, tmp_path):
        writer = BatchWriter(SimpleItem, tmp_path, "test", flush_size=100)
        with writer:
            writer.extend([SimpleItem(value=i) for i in range(3)])
        # __exit__ should have flushed the 3 buffered items
        assert writer.total_items == 3
        assert writer.file_count == 1
        assert (tmp_path / "test_batch0000.json").exists()

    def test_exit_does_not_suppress_exceptions(self, tmp_path):
        """__exit__ returns False, so exceptions propagate normally."""
        with pytest.raises(RuntimeError, match="boom"):
            with BatchWriter(SimpleItem, tmp_path, "test") as writer:
                writer.extend([SimpleItem(value=1)])
                raise RuntimeError("boom")
        # Items should still be flushed before the exception propagates
        assert writer.total_items == 1

    def test_no_output_path(self):
        """When output_path is None, items are counted but nothing is saved."""
        with BatchWriter(SimpleItem, None, "test", flush_size=5) as writer:
            writer.extend([SimpleItem(value=i) for i in range(8)])
        assert writer.total_items == 8
        assert writer.file_count == 2
        assert writer.store_time == 0.0


# ---------------------------------------------------------------------------
# BatchWriter: stat properties
# ---------------------------------------------------------------------------


class TestBatchWriterStats:
    def test_store_time_is_non_negative_when_writing(self, tmp_path):
        with BatchWriter(SimpleItem, tmp_path, "test", flush_size=100) as writer:
            writer.extend([SimpleItem(value=i) for i in range(50)])
        # On Windows, time.time() resolution can be coarse enough that small
        # writes complete within a single tick, yielding 0.0.
        assert writer.store_time >= 0.0

    def test_store_time_accumulates_across_flushes(self, tmp_path):
        with BatchWriter(SimpleItem, tmp_path, "test", flush_size=3) as writer:
            writer.extend([SimpleItem(value=i) for i in range(10)])
        # Multiple flushes → store_time should be the cumulative total
        assert writer.store_time > 0.0
        assert writer.file_count >= 3  # 10 / 3 = 3 full + 1 partial

    def test_initial_stats_are_zero(self, tmp_path):
        writer = BatchWriter(SimpleItem, tmp_path, "test")
        assert writer.total_items == 0
        assert writer.file_count == 0
        assert writer.store_time == 0.0


# ---------------------------------------------------------------------------
# BatchWriter: file naming
# ---------------------------------------------------------------------------


class TestBatchWriterFileNaming:
    def test_zero_padded_numbering(self, tmp_path):
        with BatchWriter(SimpleItem, tmp_path, "MyStep", flush_size=2) as writer:
            writer.extend([SimpleItem(value=i) for i in range(7)])
        # 7 / 2 = 3 full + 1 partial = 4 files
        files = sorted(tmp_path.glob("*.json"))
        assert len(files) == 4
        expected_names = [
            "MyStep_batch0000.json",
            "MyStep_batch0001.json",
            "MyStep_batch0002.json",
            "MyStep_batch0003.json",
        ]
        assert [f.name for f in files] == expected_names

    def test_prefix_is_used(self, tmp_path):
        with BatchWriter(SimpleItem, tmp_path, "CustomPrefix", flush_size=100) as writer:
            writer.extend([SimpleItem(value=1)])
        assert (tmp_path / "CustomPrefix_batch0000.json").exists()


# ---------------------------------------------------------------------------
# BatchWriter: data integrity round-trip
# ---------------------------------------------------------------------------


class TestBatchWriterDataIntegrity:
    def test_all_items_are_persisted(self, tmp_path):
        """All items across multiple flushes can be loaded back."""
        items = [SimpleItem(value=i, name=f"n{i}") for i in range(25)]
        with BatchWriter(SimpleItem, tmp_path, "rt", flush_size=10) as writer:
            writer.extend(items)
        # 25 / 10 = 2 full + 1 partial = 3 files
        assert writer.file_count == 3

        all_loaded = []
        for f in sorted(tmp_path.glob("*.json")):
            with f.open() as fp:
                all_loaded.extend(json.load(fp))

        assert len(all_loaded) == 25
        loaded_values = sorted(d["value"] for d in all_loaded)
        assert loaded_values == list(range(25))

    def test_single_item_batches(self, tmp_path):
        """Extending one item at a time still works correctly."""
        with BatchWriter(SimpleItem, tmp_path, "one", flush_size=3) as writer:
            for i in range(7):
                writer.extend([SimpleItem(value=i)])

        all_loaded = []
        for f in sorted(tmp_path.glob("*.json")):
            with f.open() as fp:
                all_loaded.extend(json.load(fp))

        assert len(all_loaded) == 7
        assert sorted(d["value"] for d in all_loaded) == list(range(7))

    def test_empty_extends_produce_no_files(self, tmp_path):
        """extend([]) should not produce any output."""
        with BatchWriter(SimpleItem, tmp_path, "empty", flush_size=10) as writer:
            writer.extend([])
            writer.extend([])
        assert writer.total_items == 0
        assert writer.file_count == 0
        assert list(tmp_path.glob("*.json")) == []


# ---------------------------------------------------------------------------
# BatchWriter: sorting
# ---------------------------------------------------------------------------


class TestBatchWriterSorting:
    def test_items_are_sorted_in_each_batch_file(self, tmp_path):
        """PydanticModel.__lt__ is based on hash, so items should be sorted."""
        items = [SimpleItem(value=i) for i in reversed(range(5))]
        with BatchWriter(SimpleItem, tmp_path, "sort", flush_size=100) as writer:
            writer.extend(items)

        with (tmp_path / "sort_batch0000.json").open() as fp:
            data = json.load(fp)
        values = [d["value"] for d in data]
        # Values should be in the same order as sorted() would produce
        assert values == [d["value"] for d in sorted(data, key=lambda d: SimpleItem(**d))]

    def test_unsortable_items_still_persisted(self, tmp_path):
        """When items can't be sorted, they're saved in insertion order."""
        items = [
            UnsortableItem(data={"a": 1}),
            UnsortableItem(data={"b": 2}),
            UnsortableItem(data={"c": 3}),
        ]
        with BatchWriter(UnsortableItem, tmp_path, "unsort", flush_size=100) as writer:
            writer.extend(items)

        with (tmp_path / "unsort_batch0000.json").open() as fp:
            data = json.load(fp)
        assert len(data) == 3
        assert data[0]["data"] == {"a": 1}
        assert data[1]["data"] == {"b": 2}
        assert data[2]["data"] == {"c": 3}


# ---------------------------------------------------------------------------
# BatchWriter._try_sort (static method, unit test)
# ---------------------------------------------------------------------------


class TestTrySort:
    def test_sortable_list(self):
        assert BatchWriter._try_sort([3, 1, 2]) == [1, 2, 3]

    def test_unsortable_returns_original(self):
        mixed = [object(), object()]
        result = BatchWriter._try_sort(mixed)
        assert result is mixed

    def test_empty_list(self):
        assert BatchWriter._try_sort([]) == []


# ---------------------------------------------------------------------------
# DataModel.batch_writer() classmethod
# ---------------------------------------------------------------------------


class TestDataModelBatchWriterFactory:
    def test_returns_batch_writer_instance(self, tmp_path):
        writer = SimpleItem.batch_writer(tmp_path, "test")
        assert isinstance(writer, BatchWriter)

    def test_uses_model_class_for_saving(self, tmp_path):
        """The writer uses the model class's save_to_path for persistence."""
        with SimpleItem.batch_writer(tmp_path, "cls", flush_size=10) as writer:
            writer.extend([SimpleItem(value=42, name="hi")])

        data = json.loads((tmp_path / "cls_batch0000.json").read_text())
        assert len(data) == 1
        assert data[0]["value"] == 42
        assert data[0]["name"] == "hi"

    def test_custom_flush_size(self, tmp_path):
        with SimpleItem.batch_writer(tmp_path, "sz", flush_size=3) as writer:
            writer.extend([SimpleItem(value=i) for i in range(10)])
        # 10 / 3 = 3 full (3+3+3) + 1 partial (1) = 4 files
        assert writer.file_count == 4

    def test_inherited_by_subclass(self, tmp_path):
        """batch_writer() is available on any DataModel subclass."""

        class ChildModel(PydanticModel):
            x: int

        with ChildModel.batch_writer(tmp_path, "child") as writer:
            writer.extend([ChildModel(x=1), ChildModel(x=2)])

        data = json.loads((tmp_path / "child_batch0000.json").read_text())
        assert len(data) == 2
        assert data[0]["x"] == 1

    def test_batch_writer_on_base_datamodel(self):
        """DataModel itself exposes batch_writer() (not just PydanticModel)."""
        writer = DataModel.batch_writer(None, "base")
        assert isinstance(writer, BatchWriter)

    def test_none_output_path(self):
        """batch_writer(None, ...) counts items without writing."""
        with SimpleItem.batch_writer(None, "noop") as writer:
            writer.extend([SimpleItem(value=i) for i in range(5)])
        assert writer.total_items == 5
        assert writer.file_count == 1
        assert writer.store_time == 0.0

    def test_default_flush_size(self, tmp_path):
        """Without explicit flush_size, the default (500) is used."""
        writer = SimpleItem.batch_writer(tmp_path, "default")
        assert writer._flush_size == BatchWriter.DEFAULT_FLUSH_SIZE == 500

    def test_pandera_model_raises_type_error(self, tmp_path):
        """PanderaDataFrameModel.batch_writer() raises because save_to_path expects a DataFrame."""
        with pytest.raises(TypeError, match="does not support batch_writer"):
            PanderaDataFrameModel.batch_writer(tmp_path, "pandera")

    def test_pandera_subclass_raises_type_error(self, tmp_path):
        """Subclasses of PanderaDataFrameModel also inherit the guard."""
        import pandera as pa

        class MySchema(PanderaDataFrameModel):
            col_a: pa.typing.Series[str]

        with pytest.raises(TypeError, match="does not support batch_writer"):
            MySchema.batch_writer(tmp_path, "sub")
