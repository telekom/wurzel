# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for batched / generator output handling in BaseStepExecutor.

Covers:
- ``yields_batches`` flag on a step
- Generator return from ``run()`` -> numbered batch files on disk
- StepReport accuracy for batched output
- Empty-batch skipping
- Round-trip data integrity across batch files
"""

import json

from wurzel.step import NoSettings, PydanticModel, TypedStep
from wurzel.step_executor import BaseStepExecutor

# ---------------------------------------------------------------------------
# Test models
# ---------------------------------------------------------------------------


class SimpleItem(PydanticModel):
    value: int


# ---------------------------------------------------------------------------
# Steps that yield batches
# ---------------------------------------------------------------------------


class BatchedLeafStep(TypedStep[NoSettings, None, list[SimpleItem]]):
    """A leaf step (no input) that yields 3 batches of items."""

    def run(self, inpt: None) -> list[SimpleItem]:
        for batch_num in range(3):
            yield [SimpleItem(value=batch_num * 100 + i) for i in range(100)]


class SingleBatchStep(TypedStep[NoSettings, None, list[SimpleItem]]):
    """Yields exactly one batch."""

    def run(self, inpt: None) -> list[SimpleItem]:
        yield [SimpleItem(value=i) for i in range(10)]


class EmptyBatchStep(TypedStep[NoSettings, None, list[SimpleItem]]):
    """Yields some empty batches mixed with non-empty ones."""

    def run(self, inpt: None) -> list[SimpleItem]:
        yield []  # should be skipped
        yield [SimpleItem(value=1)]
        yield []  # should be skipped
        yield [SimpleItem(value=2), SimpleItem(value=3)]
        yield []  # should be skipped


class LargeBatchStep(TypedStep[NoSettings, None, list[SimpleItem]]):
    """Yields many batches to exercise the numbering format."""

    def run(self, inpt: None) -> list[SimpleItem]:
        for batch_num in range(5):
            yield [SimpleItem(value=batch_num * 1000 + i) for i in range(500)]


# ---------------------------------------------------------------------------
# Test: batched step saves numbered files
# ---------------------------------------------------------------------------


def test_batched_step_saves_numbered_files(tmp_path):
    out = tmp_path / "out"
    with BaseStepExecutor() as ex:
        results = ex(BatchedLeafStep, None, out)

    assert len(results) == 1
    _, report = results[0]
    batch_files = sorted(out.glob("*.json"))
    # 300 items total (3 yields * 100) < _BATCH_FLUSH_SIZE (500) → 1 file
    assert len(batch_files) == 1
    assert "_batch" in batch_files[0].stem


def test_batched_step_result_is_none(tmp_path):
    """The executor yields (None, report) for batched steps — data is on disk."""
    out = tmp_path / "out"
    with BaseStepExecutor() as ex:
        results = ex(BatchedLeafStep, None, out)

    res, _report = results[0]
    assert res is None


def test_batched_step_report_totals(tmp_path):
    """StepReport.results equals the sum of items across all batches."""
    out = tmp_path / "out"
    with BaseStepExecutor() as ex:
        results = ex(BatchedLeafStep, None, out)

    _, report = results[0]
    assert report.results == 300  # 3 batches * 100 items
    assert report.step_name == "BatchedLeafStep"
    assert report.time_to_save > 0
    assert report.time_to_execute >= 0


def test_batched_step_empty_batches_skipped(tmp_path):
    """Empty batches should not produce files."""
    out = tmp_path / "out"
    with BaseStepExecutor() as ex:
        results = ex(EmptyBatchStep, None, out)

    _, report = results[0]
    # 3 items total (1 + 2) < _BATCH_FLUSH_SIZE → accumulated into 1 file
    batch_files = sorted(out.glob("*.json"))
    assert len(batch_files) == 1
    # Total items: 1 + 2 = 3
    assert report.results == 3


# ---------------------------------------------------------------------------
# Test: data integrity (round-trip)
# ---------------------------------------------------------------------------


def test_batched_step_data_integrity(tmp_path):
    """Load all batch files back and verify the combined data matches."""
    out = tmp_path / "out"
    with BaseStepExecutor() as ex:
        ex(BatchedLeafStep, None, out)

    all_items = []
    for f in sorted(out.glob("*.json")):
        with f.open() as fp:
            data = json.load(fp)
        all_items.extend(data)

    assert len(all_items) == 300
    values = sorted(item["value"] for item in all_items)
    expected = sorted(list(range(0, 100)) + list(range(100, 200)) + list(range(200, 300)))
    assert values == expected


# ---------------------------------------------------------------------------
# Test: single batch
# ---------------------------------------------------------------------------


def test_single_batch_step(tmp_path):
    out = tmp_path / "out"
    with BaseStepExecutor() as ex:
        results = ex(SingleBatchStep, None, out)

    _, report = results[0]
    assert report.results == 10
    batch_files = sorted(out.glob("*.json"))
    assert len(batch_files) == 1
    assert "_batch0000" in batch_files[0].stem


# ---------------------------------------------------------------------------
# Test: large batched step (file numbering)
# ---------------------------------------------------------------------------


def test_large_batch_numbering(tmp_path):
    out = tmp_path / "out"
    with BaseStepExecutor() as ex:
        results = ex(LargeBatchStep, None, out)

    _, report = results[0]
    assert report.results == 2500  # 5 * 500
    batch_files = sorted(out.glob("*.json"))
    assert len(batch_files) == 5
    # Verify 4-digit zero-padded numbering
    for i, f in enumerate(batch_files):
        assert f"_batch{i:04d}" in f.stem


# ---------------------------------------------------------------------------
# Test: batched step without output path (memory-only)
# ---------------------------------------------------------------------------


class BatchedNoOutputStep(TypedStep[NoSettings, None, list[SimpleItem]]):
    def run(self, inpt: None) -> list[SimpleItem]:
        yield [SimpleItem(value=1)]
        yield [SimpleItem(value=2)]


def test_batched_step_no_output_path(tmp_path):
    """When output_path=None, batched output works but nothing is saved."""
    with BaseStepExecutor() as ex:
        results = ex(BatchedNoOutputStep, None, None)

    res, report = results[0]
    assert res is None
    assert report.results == 2  # 2 batches of 1 item each
    assert report.time_to_save == 0.0


# ---------------------------------------------------------------------------
# Test: generator functions are auto-detected (no flag needed)
# ---------------------------------------------------------------------------


class AutoDetectedGeneratorStep(TypedStep[NoSettings, None, list[SimpleItem]]):
    """A generator function — no flag needed, the executor detects yield automatically."""

    def run(self, inpt: None) -> list[SimpleItem]:
        yield [SimpleItem(value=1)]
        yield [SimpleItem(value=2)]


def test_generator_auto_detected(tmp_path):
    """Generator run() methods are automatically routed to the batched path."""
    out = tmp_path / "out"
    with BaseStepExecutor() as ex:
        results = ex(AutoDetectedGeneratorStep, None, out)

    res, report = results[0]
    assert res is None  # batched path yields None
    assert report.results == 2
    # 2 items < _BATCH_FLUSH_SIZE → accumulated into 1 file
    batch_files = sorted(out.glob("*.json"))
    assert len(batch_files) == 1


def test_non_generator_uses_standard_path(tmp_path):
    """A regular (non-generator) run() is handled via the standard path."""

    class StandardStep(TypedStep[NoSettings, None, list[SimpleItem]]):
        def run(self, inpt: None) -> list[SimpleItem]:
            return [SimpleItem(value=1), SimpleItem(value=2)]

    out = tmp_path / "out"
    with BaseStepExecutor() as ex:
        results = ex(StandardStep, None, out)

    res, report = results[0]
    assert res is not None  # standard path returns the actual result
    assert len(res) == 2
    assert report.results == 2


# ---------------------------------------------------------------------------
# Test: batched step with input data
# ---------------------------------------------------------------------------


class BatchedTransformStep(TypedStep[NoSettings, list[SimpleItem], list[SimpleItem]]):
    """Takes a list of items and yields them back in batches of 2."""

    def run(self, inpt: list[SimpleItem]) -> list[SimpleItem]:
        batch_size = 2
        for i in range(0, len(inpt), batch_size):
            yield inpt[i : i + batch_size]


def test_batched_step_with_input(tmp_path):
    """A batched step that receives input data from a previous step."""
    input_items = [SimpleItem(value=i) for i in range(7)]
    out = tmp_path / "out"

    with BaseStepExecutor() as ex:
        results = ex(BatchedTransformStep, (input_items,), out)

    _, report = results[0]
    assert report.results == 7  # all 7 items saved across batches
    # 7 items < _BATCH_FLUSH_SIZE → accumulated into 1 file
    batch_files = sorted(out.glob("*.json"))
    assert len(batch_files) == 1
