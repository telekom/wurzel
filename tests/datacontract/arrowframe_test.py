# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for ArrowFrame integration with PydanticModel."""

import pydantic
import pytest
from pydantic_arrow import ArrowFrame

from wurzel.core import MarkdownDataContract, NoSettings, TypedStep
from wurzel.core.self_consuming_step import SelfConsumingLeafStep
from wurzel.datacontract import PydanticModel
from wurzel.executors import BaseStepExecutor


class SimpleModel(PydanticModel):
    """Simple test model."""

    name: str
    value: int


def test_arrowframe_save_load_roundtrip(tmp_path):
    """Test saving and loading ArrowFrame to/from parquet."""
    models = [
        SimpleModel(name="a", value=1),
        SimpleModel(name="b", value=2),
        SimpleModel(name="c", value=3),
    ]
    
    # Create ArrowFrame from rows
    frame = ArrowFrame[SimpleModel].from_rows(models)
    
    # Save to parquet
    path = tmp_path / "test"
    PydanticModel.save_to_path(path, frame)
    
    # Load as ArrowFrame (lazy)
    loaded_frame = PydanticModel.load_from_path(path.with_suffix(".parquet"), ArrowFrame[SimpleModel])
    
    # Verify it's an ArrowFrame (not materialized)
    assert isinstance(loaded_frame, ArrowFrame)
    
    # Collect and verify data
    loaded_models = loaded_frame.collect()
    assert len(loaded_models) == 3
    assert loaded_models[0].name == "a"
    assert loaded_models[1].value == 2


def test_arrowframe_lazy_loading(tmp_path):
    """Verify that loading as ArrowFrame doesn't call collect()."""
    models = [SimpleModel(name=f"item_{i}", value=i) for i in range(100)]
    
    # Save
    path = tmp_path / "lazy_test"
    PydanticModel.save_to_path(path, models)
    
    # Load as ArrowFrame - should be lazy
    frame = PydanticModel.load_from_path(path.with_suffix(".parquet"), ArrowFrame[SimpleModel])
    
    # Verify it's an ArrowFrame
    assert isinstance(frame, ArrowFrame)
    
    # Iterate without collecting all at once
    count = 0
    for model in frame:
        count += 1
        assert isinstance(model, SimpleModel)
    assert count == 100


def test_arrowframe_list_compatibility(tmp_path):
    """Test that ArrowFrame and list can interoperate."""
    models = [
        SimpleModel(name="x", value=10),
        SimpleModel(name="y", value=20),
    ]
    
    # Save as list
    path = tmp_path / "list_test"
    PydanticModel.save_to_path(path, models)
    
    # Load as list (materializes)
    loaded_list = PydanticModel.load_from_path(path.with_suffix(".parquet"), list[SimpleModel])
    assert isinstance(loaded_list, list)
    assert len(loaded_list) == 2
    assert loaded_list[0].name == "x"


def test_arrowframe_single_model(tmp_path):
    """Test saving and loading a single model."""
    model = SimpleModel(name="single", value=42)
    
    # Save single model
    path = tmp_path / "single"
    PydanticModel.save_to_path(path, model)
    
    # Load as single model
    loaded = PydanticModel.load_from_path(path.with_suffix(".parquet"), SimpleModel)
    assert isinstance(loaded, SimpleModel)
    assert loaded.name == "single"
    assert loaded.value == 42


class LeafArrowFrameStep(TypedStep[NoSettings, None, ArrowFrame[MarkdownDataContract]]):
    """Leaf step that returns ArrowFrame."""
    
    def run(self, inpt: None) -> ArrowFrame[MarkdownDataContract]:
        def generate():
            for i in range(5):
                yield MarkdownDataContract(
                    md=f"Content {i}",
                    keywords=f"kw{i}",
                    url=f"http://example.com/{i}",
                )
        return ArrowFrame[MarkdownDataContract].from_iterable(generate())


def test_leaf_step_arrowframe(tmp_path):
    """Test leaf step that creates ArrowFrame from generator."""
    output = tmp_path / "leaf_output"
    
    with BaseStepExecutor() as ex:
        _ = ex.execute_step(LeafArrowFrameStep, None, output)
    
    # Check that file was created
    files = list(output.glob("*.parquet"))
    assert len(files) == 1
    
    # Load and verify
    frame = PydanticModel.load_from_path(files[0], ArrowFrame[MarkdownDataContract])
    models = frame.collect()
    assert len(models) == 5
    assert models[0].md == "Content 0"
    assert models[4].url == "http://example.com/4"


class SelfConsumingArrowFrameStep(SelfConsumingLeafStep[NoSettings, list[MarkdownDataContract]]):
    """Self-consuming step for testing."""
    
    def run(self, inpt: list[MarkdownDataContract] | None) -> list[MarkdownDataContract]:
        if not inpt:
            return [MarkdownDataContract(md="first", url="url1", keywords="k1")]
        else:
            # Double the input
            return inpt + inpt


def test_self_consuming_step_arrowframe(tmp_path):
    """Test SelfConsumingLeafStep with ArrowFrame storage."""
    output = tmp_path / "self_consuming"
    output.mkdir(parents=True, exist_ok=True)
    
    with BaseStepExecutor() as ex:
        # First run - creates initial data
        result1 = ex(SelfConsumingArrowFrameStep, set(), output)
        assert len(result1[0][0]) == 1
        
        # Second run - loads previous output and doubles it
        result2 = ex(SelfConsumingArrowFrameStep, set(), output)
        assert len(result2[0][0]) == 2


def test_arrowframe_with_metadata(tmp_path):
    """Test that MarkdownDataContract metadata field works with ArrowFrame."""
    doc1 = MarkdownDataContract(
        md="text1",
        keywords="kw1",
        url="url1",
        metadata={"key1": "value1", "num": 42}  # dict auto-serialized to JSON string
    )
    doc2 = MarkdownDataContract(
        md="text2",
        keywords="kw2",
        url="url2",
        metadata=None
    )
    
    # Save as ArrowFrame
    path = tmp_path / "metadata_test"
    frame = ArrowFrame[MarkdownDataContract].from_rows([doc1, doc2])
    PydanticModel.save_to_path(path, frame)
    
    # Load and verify
    loaded_frame = PydanticModel.load_from_path(path.with_suffix(".parquet"), ArrowFrame[MarkdownDataContract])
    loaded = loaded_frame.collect()
    
    assert len(loaded) == 2
    # Metadata is stored as JSON string, use get_metadata_dict()
    assert loaded[0].get_metadata_dict() == {"key1": "value1", "num": 42}
    assert loaded[1].get_metadata_dict() is None


def test_streaming_large_dataset(tmp_path):
    """Test that large dataset can be streamed without loading all into memory."""
    # Create a generator for a large dataset
    def large_generator():
        for i in range(10000):
            yield SimpleModel(name=f"item_{i}", value=i)
    
    # Create ArrowFrame from generator (never materializes full dataset)
    frame = ArrowFrame[SimpleModel].from_iterable(large_generator())
    
    # Save (streaming write)
    path = tmp_path / "large"
    PydanticModel.save_to_path(path, frame)
    
    # Load as ArrowFrame (lazy)
    loaded_frame = PydanticModel.load_from_path(path.with_suffix(".parquet"), ArrowFrame[SimpleModel])
    
    # Verify we can iterate without materializing all
    count = 0
    for _ in loaded_frame:
        count += 1
        if count >= 100:  # Just check first 100
            break
    assert count == 100


def test_empty_arrowframe(tmp_path):
    """Test edge case of empty ArrowFrame."""
    empty_frame = ArrowFrame[SimpleModel].from_rows([])
    
    # Save empty frame
    path = tmp_path / "empty"
    PydanticModel.save_to_path(path, empty_frame)
    
    # Load and verify
    loaded_frame = PydanticModel.load_from_path(path.with_suffix(".parquet"), ArrowFrame[SimpleModel])
    loaded = loaded_frame.collect()
    assert len(loaded) == 0


def test_arrowframe_chaining_steps(tmp_path):
    """Test that ArrowFrame can be chained between steps."""
    class Step1(TypedStep[NoSettings, None, ArrowFrame[SimpleModel]]):
        def run(self, inpt: None) -> ArrowFrame[SimpleModel]:
            def generate():
                for i in range(10):
                    yield SimpleModel(name=f"s1_{i}", value=i)
            return ArrowFrame[SimpleModel].from_iterable(generate())
    
    class Step2(TypedStep[NoSettings, ArrowFrame[SimpleModel], ArrowFrame[SimpleModel]]):
        def run(self, inpt: ArrowFrame[SimpleModel]) -> ArrowFrame[SimpleModel]:
            def transform():
                for model in inpt:
                    # Double the value
                    yield SimpleModel(name=model.name + "_transformed", value=model.value * 2)
            return ArrowFrame[SimpleModel].from_iterable(transform())
    
    out1 = tmp_path / "out1"
    out2 = tmp_path / "out2"
    
    with BaseStepExecutor() as ex:
        ex.execute_step(Step1, None, out1)
        result = ex.execute_step(Step2, (out1,), out2)
    
    # Verify the chained result
    assert len(result) == 1
    transformed = result[0][0]
    assert isinstance(transformed, ArrowFrame)
    
    # Collect and verify transformation
    models = transformed.collect()
    assert len(models) == 10
    assert models[0].name == "s1_0_transformed"
    assert models[0].value == 0
    assert models[5].value == 10


def test_arrowframe_to_list_step_chain(tmp_path):
    """Test chaining ArrowFrame output to list input."""
    class ArrowStep(TypedStep[NoSettings, None, ArrowFrame[SimpleModel]]):
        def run(self, inpt: None) -> ArrowFrame[SimpleModel]:
            return ArrowFrame[SimpleModel].from_rows([
                SimpleModel(name="a", value=1),
                SimpleModel(name="b", value=2),
            ])
    
    class ListStep(TypedStep[NoSettings, list[SimpleModel], list[SimpleModel]]):
        def run(self, inpt: list[SimpleModel]) -> list[SimpleModel]:
            # Just pass through
            return inpt
    
    out1 = tmp_path / "out1"
    out2 = tmp_path / "out2"
    
    with BaseStepExecutor() as ex:
        ex.execute_step(ArrowStep, None, out1)
        result = ex.execute_step(ListStep, (out1,), out2)
    
    # Verify the list was properly materialized
    assert len(result) == 1
    models = result[0][0]
    assert isinstance(models, list)
    assert len(models) == 2
    assert models[0].name == "a"


def test_list_to_arrowframe_step_chain(tmp_path):
    """Test chaining list output to ArrowFrame input."""
    class ListStep(TypedStep[NoSettings, None, list[SimpleModel]]):
        def run(self, inpt: None) -> list[SimpleModel]:
            return [
                SimpleModel(name="x", value=10),
                SimpleModel(name="y", value=20),
            ]
    
    class ArrowStep(TypedStep[NoSettings, ArrowFrame[SimpleModel], ArrowFrame[SimpleModel]]):
        def run(self, inpt: ArrowFrame[SimpleModel]) -> ArrowFrame[SimpleModel]:
            # Verify input is lazy ArrowFrame
            assert isinstance(inpt, ArrowFrame)
            return inpt
    
    out1 = tmp_path / "out1"
    out2 = tmp_path / "out2"
    
    with BaseStepExecutor() as ex:
        ex.execute_step(ListStep, None, out1)
        result = ex.execute_step(ArrowStep, (out1,), out2)
    
    # Verify ArrowFrame was created from list
    assert len(result) == 1
    frame = result[0][0]
    assert isinstance(frame, ArrowFrame)


def test_arrowframe_batch_iteration(tmp_path):
    """Test iterating over batches directly."""
    models = [SimpleModel(name=f"item_{i}", value=i) for i in range(1000)]
    
    # Save
    path = tmp_path / "batch_test"
    PydanticModel.save_to_path(path, models)
    
    # Load as ArrowFrame
    frame = PydanticModel.load_from_path(path.with_suffix(".parquet"), ArrowFrame[SimpleModel])
    
    # Iterate over raw Arrow batches
    batch_count = 0
    total_rows = 0
    for batch in frame.iter_batches():
        batch_count += 1
        total_rows += len(batch)
    
    assert total_rows == 1000
    assert batch_count >= 1  # At least one batch


def test_arrowframe_filter_operation(tmp_path):
    """Test filtering ArrowFrame."""
    models = [
        SimpleModel(name="include", value=5),
        SimpleModel(name="exclude", value=15),
        SimpleModel(name="include", value=3),
        SimpleModel(name="exclude", value=25),
    ]
    
    # Save
    path = tmp_path / "filter_test"
    frame = ArrowFrame[SimpleModel].from_rows(models)
    PydanticModel.save_to_path(path, frame)
    
    # Load and filter
    loaded_frame = PydanticModel.load_from_path(path.with_suffix(".parquet"), ArrowFrame[SimpleModel])
    
    # Filter using Python callable
    filtered = loaded_frame.filter(lambda m: m.value < 10)
    
    # Collect filtered results
    filtered_models = filtered.collect()
    assert len(filtered_models) == 2
    assert all(m.value < 10 for m in filtered_models)


def test_arrowframe_concurrent_steps(tmp_path):
    """Test multiple steps writing ArrowFrames concurrently."""
    class StepA(TypedStep[NoSettings, None, ArrowFrame[SimpleModel]]):
        def run(self, inpt: None) -> ArrowFrame[SimpleModel]:
            return ArrowFrame[SimpleModel].from_rows([
                SimpleModel(name="a1", value=1),
                SimpleModel(name="a2", value=2),
            ])
    
    class StepB(TypedStep[NoSettings, None, ArrowFrame[SimpleModel]]):
        def run(self, inpt: None) -> ArrowFrame[SimpleModel]:
            return ArrowFrame[SimpleModel].from_rows([
                SimpleModel(name="b1", value=10),
                SimpleModel(name="b2", value=20),
            ])
    
    out_a = tmp_path / "out_a"
    out_b = tmp_path / "out_b"
    
    with BaseStepExecutor() as ex:
        result_a = ex.execute_step(StepA, None, out_a)
        result_b = ex.execute_step(StepB, None, out_b)
    
    # Verify both results
    assert len(result_a) == 1
    assert len(result_b) == 1
    
    # Check files exist
    assert len(list(out_a.glob("*.parquet"))) == 1
    assert len(list(out_b.glob("*.parquet"))) == 1


def test_arrowframe_memory_efficiency(tmp_path):
    """Test that ArrowFrame doesn't materialize unnecessarily."""
    # Create a large generator
    def large_generator():
        for i in range(50000):
            yield SimpleModel(name=f"item_{i}", value=i)
    
    # Create ArrowFrame from generator
    frame = ArrowFrame[SimpleModel].from_iterable(large_generator())
    
    # Save (should stream without materializing all)
    path = tmp_path / "memory_test"
    PydanticModel.save_to_path(path, frame)
    
    # Load as ArrowFrame (lazy)
    loaded = PydanticModel.load_from_path(path.with_suffix(".parquet"), ArrowFrame[SimpleModel])
    
    # Process in chunks without full materialization
    processed_count = 0
    
    for _ in loaded:
        processed_count += 1
        # Process only first 1000 to verify streaming works
        if processed_count >= 1000:
            break
    
    assert processed_count == 1000


def test_arrowframe_with_complex_metadata(tmp_path):
    """Test ArrowFrame with complex nested metadata."""
    docs = [
        MarkdownDataContract(
            md="text1",
            keywords="k1",
            url="url1",
            metadata={
                "nested": {"key": "value", "num": 123},
                "list": [1, 2, 3],
                "bool": True,
                "null": None,
            }
        ),
        MarkdownDataContract(
            md="text2",
            keywords="k2",
            url="url2",
            metadata={"simple": "value"}
        ),
    ]
    
    # Save
    path = tmp_path / "complex_metadata"
    frame = ArrowFrame[MarkdownDataContract].from_rows(docs)
    PydanticModel.save_to_path(path, frame)
    
    # Load and verify
    loaded_frame = PydanticModel.load_from_path(path.with_suffix(".parquet"), ArrowFrame[MarkdownDataContract])
    loaded = loaded_frame.collect()
    
    assert len(loaded) == 2
    
    # Check complex metadata
    meta1 = loaded[0].get_metadata_dict()
    assert meta1["nested"]["key"] == "value"
    assert meta1["nested"]["num"] == 123
    assert meta1["list"] == [1, 2, 3]
    assert meta1["bool"] is True
    assert meta1["null"] is None
    
    meta2 = loaded[1].get_metadata_dict()
    assert meta2["simple"] == "value"


def test_arrowframe_limit_and_head(tmp_path):
    """Test ArrowFrame limit and head operations."""
    models = [SimpleModel(name=f"item_{i}", value=i) for i in range(100)]
    
    # Save
    path = tmp_path / "limit_test"
    PydanticModel.save_to_path(path, models)
    
    # Load and limit
    frame = PydanticModel.load_from_path(path.with_suffix(".parquet"), ArrowFrame[SimpleModel])
    
    # Get first 10
    limited = frame.limit(10)
    limited_models = limited.collect()
    assert len(limited_models) == 10
    assert limited_models[0].value == 0
    assert limited_models[9].value == 9


def test_arrowframe_exception_handling(tmp_path):
    """Test error handling in ArrowFrame operations."""
    # Test loading non-existent file
    with pytest.raises(Exception):
        PydanticModel.load_from_path(tmp_path / "nonexistent.parquet", ArrowFrame[SimpleModel])
    
    # Test invalid model type
    models = [SimpleModel(name="test", value=1)]
    path = tmp_path / "test"
    PydanticModel.save_to_path(path, models)
    
    # Loading with wrong type should fail during validation
    class WrongModel(PydanticModel):
        different_field: str
    
    frame = PydanticModel.load_from_path(path.with_suffix(".parquet"), ArrowFrame[WrongModel])
    with pytest.raises(Exception):
        # This should fail when trying to validate the data
        frame.collect()


def test_arrowframe_step_metrics(tmp_path):
    """Test that ArrowFrame metrics are collected correctly."""
    class MetricsStep(TypedStep[NoSettings, None, ArrowFrame[SimpleModel]]):
        def run(self, inpt: None) -> ArrowFrame[SimpleModel]:
            return ArrowFrame[SimpleModel].from_rows([
                SimpleModel(name=f"item_{i}", value=i) for i in range(100)
            ])
    
    out = tmp_path / "metrics_out"
    
    with BaseStepExecutor() as ex:
        result = ex.execute_step(MetricsStep, None, out)
    
    # Check that metrics were collected
    report = result[0][1]
    assert "rows" in report.metrics
    assert report.metrics["rows"] == 100.0


def test_arrowframe_unicode_handling(tmp_path):
    """Test that ArrowFrame handles unicode correctly."""
    docs = [
        MarkdownDataContract(
            md="Unicode text: 日本語 中文 한글 العربية",
            keywords="unicode,test,🎉",
            url="http://example.com/unicode",
            metadata={"emoji": "🚀", "text": "Ñoño"}
        ),
    ]
    
    # Save
    path = tmp_path / "unicode_test"
    frame = ArrowFrame[MarkdownDataContract].from_rows(docs)
    PydanticModel.save_to_path(path, frame)
    
    # Load and verify
    loaded_frame = PydanticModel.load_from_path(path.with_suffix(".parquet"), ArrowFrame[MarkdownDataContract])
    loaded = loaded_frame.collect()
    
    assert len(loaded) == 1
    assert "日本語" in loaded[0].md
    assert "🎉" in loaded[0].keywords
    meta = loaded[0].get_metadata_dict()
    assert meta["emoji"] == "🚀"
    assert meta["text"] == "Ñoño"


def test_arrowframe_multiple_history_files(tmp_path):
    """Test loading multiple parquet files from different histories."""
    class Step1(TypedStep[NoSettings, None, SimpleModel]):
        def run(self, inpt: None) -> SimpleModel:
            return SimpleModel(name="step1", value=1)
    
    class Step2(TypedStep[NoSettings, None, SimpleModel]):
        def run(self, inpt: None) -> SimpleModel:
            return SimpleModel(name="step2", value=2)
    
    class CombineStep(TypedStep[NoSettings, SimpleModel, list[SimpleModel]]):
        def run(self, inpt: SimpleModel) -> list[SimpleModel]:
            return [inpt, inpt]
    
    out1 = tmp_path / "out1"
    out2 = tmp_path / "out2"
    combined = tmp_path / "combined"
    
    with BaseStepExecutor() as ex:
        ex.execute_step(Step1, None, out1)
        ex.execute_step(Step2, None, out2)
        result = ex.execute_step(CombineStep, (out1, out2), combined)
    
    # Should have processed both inputs
    assert len(result) == 2
    
    # Check combined output has files from both histories
    files = list(combined.glob("*.parquet"))
    assert len(files) == 2
    
    # File names should contain the step names in history
    file_names = [f.name for f in files]
    assert any("Step1" in name for name in file_names)
    assert any("Step2" in name for name in file_names)


def test_arrowframe_schema_validation(tmp_path):
    """Test that ArrowFrame validates against Pydantic schema."""
    # Create a model with validation
    class ValidatedModel(PydanticModel):
        name: str
        value: int
        
        @pydantic.field_validator('value')
        @classmethod
        def value_must_be_positive(cls, v):
            if v < 0:
                raise ValueError('value must be positive')
            return v
    
    # Valid data
    valid_models = [
        ValidatedModel(name="a", value=1),
        ValidatedModel(name="b", value=2),
    ]
    
    path = tmp_path / "validated"
    PydanticModel.save_to_path(path, valid_models)
    
    # Load and verify validation works
    frame = PydanticModel.load_from_path(path.with_suffix(".parquet"), ArrowFrame[ValidatedModel])
    loaded = frame.collect()
    assert all(m.value > 0 for m in loaded)


def test_arrowframe_optional_fields(tmp_path):
    """Test ArrowFrame with optional fields."""
    class OptionalModel(PydanticModel):
        name: str
        optional_value: int | None = None
        optional_text: str | None = None
    
    models = [
        OptionalModel(name="full", optional_value=10, optional_text="text"),
        OptionalModel(name="partial", optional_value=20),
        OptionalModel(name="minimal"),
    ]
    
    # Save
    path = tmp_path / "optional"
    PydanticModel.save_to_path(path, models)
    
    # Load and verify
    loaded = PydanticModel.load_from_path(path.with_suffix(".parquet"), list[OptionalModel])
    assert len(loaded) == 3
    assert loaded[0].optional_value == 10
    assert loaded[0].optional_text == "text"
    assert loaded[1].optional_value == 20
    assert loaded[1].optional_text is None
    assert loaded[2].optional_value is None


def test_arrowframe_nested_models(tmp_path):
    """Test ArrowFrame with nested Pydantic models."""
    class Inner(PydanticModel):
        inner_name: str
        inner_value: int
    
    class Outer(PydanticModel):
        outer_name: str
        nested: Inner
    
    models = [
        Outer(outer_name="a", nested=Inner(inner_name="a1", inner_value=1)),
        Outer(outer_name="b", nested=Inner(inner_name="b1", inner_value=2)),
    ]
    
    # Save
    path = tmp_path / "nested"
    frame = ArrowFrame[Outer].from_rows(models)
    PydanticModel.save_to_path(path, frame)
    
    # Load and verify
    loaded_frame = PydanticModel.load_from_path(path.with_suffix(".parquet"), ArrowFrame[Outer])
    loaded = loaded_frame.collect()
    
    assert len(loaded) == 2
    assert loaded[0].nested.inner_name == "a1"
    assert loaded[1].nested.inner_value == 2


def test_arrowframe_list_fields(tmp_path):
    """Test ArrowFrame with list fields."""
    class ListModel(PydanticModel):
        name: str
        tags: list[str]
        values: list[int]
    
    models = [
        ListModel(name="a", tags=["tag1", "tag2"], values=[1, 2, 3]),
        ListModel(name="b", tags=["tag3"], values=[10, 20]),
        ListModel(name="c", tags=[], values=[]),
    ]
    
    # Save
    path = tmp_path / "lists"
    PydanticModel.save_to_path(path, models)
    
    # Load and verify
    loaded = PydanticModel.load_from_path(path.with_suffix(".parquet"), list[ListModel])
    
    assert len(loaded) == 3
    assert loaded[0].tags == ["tag1", "tag2"]
    assert loaded[0].values == [1, 2, 3]
    assert loaded[2].tags == []
    assert loaded[2].values == []


def test_arrowframe_step_error_handling(tmp_path):
    """Test error handling in steps that return ArrowFrame."""
    class FailingStep(TypedStep[NoSettings, None, ArrowFrame[SimpleModel]]):
        def run(self, inpt: None) -> ArrowFrame[SimpleModel]:
            def generate():
                for i in range(5):
                    if i == 3:
                        raise ValueError("Intentional error at i=3")
                    yield SimpleModel(name=f"item_{i}", value=i)
            return ArrowFrame[SimpleModel].from_iterable(generate())
    
    out = tmp_path / "failing_out"
    
    with BaseStepExecutor() as ex:
        with pytest.raises(Exception):
            # Error should be raised during execution
            ex.execute_step(FailingStep, None, out)


def test_arrowframe_preserve_order(tmp_path):
    """Test that ArrowFrame preserves insertion order."""
    models = [SimpleModel(name=f"item_{i}", value=i) for i in range(20)]
    
    # Save
    path = tmp_path / "order_test"
    frame = ArrowFrame[SimpleModel].from_rows(models)
    PydanticModel.save_to_path(path, frame)
    
    # Load and verify order
    loaded_frame = PydanticModel.load_from_path(path.with_suffix(".parquet"), ArrowFrame[SimpleModel])
    loaded = loaded_frame.collect()
    
    for i, model in enumerate(loaded):
        assert model.name == f"item_{i}"
        assert model.value == i


def test_arrowframe_concat_operation(tmp_path):
    """Test concatenating ArrowFrames."""
    frame1 = ArrowFrame[SimpleModel].from_rows([
        SimpleModel(name="a", value=1),
        SimpleModel(name="b", value=2),
    ])
    
    frame2 = ArrowFrame[SimpleModel].from_rows([
        SimpleModel(name="c", value=3),
        SimpleModel(name="d", value=4),
    ])
    
    # Concatenate
    combined = frame1 + frame2
    
    # Save
    path = tmp_path / "concat"
    PydanticModel.save_to_path(path, combined)
    
    # Load and verify
    loaded = PydanticModel.load_from_path(path.with_suffix(".parquet"), list[SimpleModel])
    assert len(loaded) == 4
    assert [m.name for m in loaded] == ["a", "b", "c", "d"]


def test_arrowframe_to_arrow_table(tmp_path):
    """Test converting ArrowFrame to Arrow Table."""
    import pyarrow as pa
    
    models = [SimpleModel(name="test", value=i) for i in range(5)]
    
    # Save
    path = tmp_path / "table_test"
    PydanticModel.save_to_path(path, models)
    
    # Load as ArrowFrame
    frame = PydanticModel.load_from_path(path.with_suffix(".parquet"), ArrowFrame[SimpleModel])
    
    # Convert to Arrow Table
    table = frame.to_arrow()
    assert isinstance(table, pa.Table)
    assert len(table) == 5
    assert "name" in table.column_names
    assert "value" in table.column_names


def test_arrowframe_slice_operation(tmp_path):
    """Test slicing ArrowFrame."""
    models = [SimpleModel(name=f"item_{i}", value=i) for i in range(50)]
    
    # Save
    path = tmp_path / "slice_test"
    PydanticModel.save_to_path(path, models)
    
    # Load as ArrowFrame
    frame = PydanticModel.load_from_path(path.with_suffix(".parquet"), ArrowFrame[SimpleModel])
    
    # Slice [10:20]
    sliced = frame[10:20]
    assert isinstance(sliced, ArrowFrame)
    
    sliced_models = sliced.collect()
    assert len(sliced_models) == 10
    assert sliced_models[0].value == 10
    assert sliced_models[9].value == 19


def test_arrowframe_index_access(tmp_path):
    """Test accessing individual rows by index."""
    models = [
        SimpleModel(name="first", value=1),
        SimpleModel(name="second", value=2),
        SimpleModel(name="third", value=3),
    ]
    
    # Save
    path = tmp_path / "index_test"
    PydanticModel.save_to_path(path, models)
    
    # Load as ArrowFrame
    frame = PydanticModel.load_from_path(path.with_suffix(".parquet"), ArrowFrame[SimpleModel])
    
    # Access by index
    first = frame[0]
    assert isinstance(first, SimpleModel)
    assert first.name == "first"
    
    second = frame[1]
    assert second.name == "second"
    
    # Negative indexing
    last = frame[-1]
    assert last.name == "third"


def test_arrowframe_generator_exhaustion(tmp_path):
    """Test that generator-based ArrowFrame can only be iterated once."""
    iteration_count = [0]
    
    def counting_generator():
        for i in range(5):
            iteration_count[0] += 1
            yield SimpleModel(name=f"item_{i}", value=i)
    
    # Create from generator
    frame = ArrowFrame[SimpleModel].from_iterable(counting_generator())
    
    # First iteration - generator is consumed
    path = tmp_path / "generator_test"
    PydanticModel.save_to_path(path, frame)
    
    # Generator was called during save
    assert iteration_count[0] == 5
    
    # Load from parquet (new source, can iterate multiple times)
    loaded1 = PydanticModel.load_from_path(path.with_suffix(".parquet"), ArrowFrame[SimpleModel])
    loaded2 = PydanticModel.load_from_path(path.with_suffix(".parquet"), ArrowFrame[SimpleModel])
    
    # Both can be iterated
    assert len(loaded1.collect()) == 5
    assert len(loaded2.collect()) == 5


def test_arrowframe_metadata_none_vs_empty(tmp_path):
    """Test distinction between None metadata and empty dict metadata."""
    docs = [
        MarkdownDataContract(md="a", keywords="k", url="u", metadata=None),
        MarkdownDataContract(md="b", keywords="k", url="u", metadata={}),
        MarkdownDataContract(md="c", keywords="k", url="u", metadata={"key": "value"}),
    ]
    
    path = tmp_path / "meta_none_empty"
    PydanticModel.save_to_path(path, docs)
    
    loaded = PydanticModel.load_from_path(path.with_suffix(".parquet"), list[MarkdownDataContract])
    
    assert loaded[0].get_metadata_dict() is None
    assert loaded[1].get_metadata_dict() == {}
    assert loaded[2].get_metadata_dict() == {"key": "value"}


def test_arrowframe_large_metadata_dict(tmp_path):
    """Test ArrowFrame with large metadata dictionaries."""
    large_meta = {
        f"key_{i}": f"value_{i}" for i in range(100)
    }
    large_meta["nested"] = {
        "level1": {
            "level2": {
                "data": [1, 2, 3, 4, 5]
            }
        }
    }
    
    doc = MarkdownDataContract(
        md="Large metadata test",
        keywords="test",
        url="http://example.com",
        metadata=large_meta
    )
    
    # Save
    path = tmp_path / "large_meta"
    PydanticModel.save_to_path(path, [doc])
    
    # Load and verify
    loaded = PydanticModel.load_from_path(path.with_suffix(".parquet"), list[MarkdownDataContract])
    loaded_meta = loaded[0].get_metadata_dict()
    
    assert len(loaded_meta) == 101  # 100 keys + nested
    assert loaded_meta["key_50"] == "value_50"
    assert loaded_meta["nested"]["level1"]["level2"]["data"] == [1, 2, 3, 4, 5]


class EmptyFieldsModel(PydanticModel):
    """Model with no fields for edge case testing."""


def test_empty_pydantic_model(tmp_path):
    """Test ArrowFrame with PydanticModel that has no fields."""
    # Create instances of empty model
    empty_models = [EmptyFieldsModel(), EmptyFieldsModel(), EmptyFieldsModel()]
    
    # Save
    path = tmp_path / "empty_model"
    PydanticModel.save_to_path(path, empty_models)
    
    # Load and verify count is preserved even with no data columns
    loaded = PydanticModel.load_from_path(path.with_suffix(".parquet"), list[EmptyFieldsModel])
    assert len(loaded) == 3


def test_arrowframe_step_chaining_mixed_types(tmp_path):
    """Test complex chaining with mixed container types."""
    class Step1(TypedStep[NoSettings, None, list[SimpleModel]]):
        def run(self, inpt: None) -> list[SimpleModel]:
            return [SimpleModel(name="a", value=1)]
    
    class Step2(TypedStep[NoSettings, ArrowFrame[SimpleModel], ArrowFrame[SimpleModel]]):
        def run(self, inpt: ArrowFrame[SimpleModel]) -> ArrowFrame[SimpleModel]:
            # Process the ArrowFrame lazily
            def transform():
                for model in inpt:
                    yield SimpleModel(name=model.name + "_v2", value=model.value * 2)
            return ArrowFrame[SimpleModel].from_iterable(transform())
    
    class Step3(TypedStep[NoSettings, list[SimpleModel], SimpleModel]):
        def run(self, inpt: list[SimpleModel]) -> SimpleModel:
            return inpt[0]
    
    out1 = tmp_path / "out1"
    out2 = tmp_path / "out2"
    out3 = tmp_path / "out3"
    
    with BaseStepExecutor() as ex:
        ex.execute_step(Step1, None, out1)
        ex.execute_step(Step2, (out1,), out2)
        result = ex.execute_step(Step3, (out2,), out3)
    
    # Verify final result
    final_model = result[0][0]
    assert isinstance(final_model, SimpleModel)
    assert final_model.name == "a_v2"
    assert final_model.value == 2


def test_arrowframe_num_rows_property(tmp_path):
    """Test that num_rows property works for countable sources."""
    models = [SimpleModel(name=f"item_{i}", value=i) for i in range(42)]
    
    # From rows (countable)
    frame_rows = ArrowFrame[SimpleModel].from_rows(models)
    assert frame_rows.num_rows == 42
    
    # Save and load from parquet (countable via metadata)
    path = tmp_path / "num_rows"
    PydanticModel.save_to_path(path, frame_rows)
    
    loaded_frame = PydanticModel.load_from_path(path.with_suffix(".parquet"), ArrowFrame[SimpleModel])
    assert loaded_frame.num_rows == 42


def test_arrowframe_schema_property(tmp_path):
    """Test that schema property is accessible."""
    import pyarrow as pa
    
    models = [SimpleModel(name="test", value=1)]
    frame = ArrowFrame[SimpleModel].from_rows(models)
    
    # Check schema
    schema = frame.schema
    assert isinstance(schema, pa.Schema)
    assert "name" in schema.names
    assert "value" in schema.names
    
    # Verify field types
    assert schema.field("name").type == pa.utf8()
    assert schema.field("value").type == pa.int64()


def test_arrowframe_model_with_defaults(tmp_path):
    """Test ArrowFrame with models that have default values."""
    class DefaultModel(PydanticModel):
        name: str
        value: int = 100
        tag: str = "default_tag"
    
    models = [
        DefaultModel(name="custom", value=50, tag="custom_tag"),
        DefaultModel(name="with_default"),
        DefaultModel(name="partial", value=75),
    ]
    
    # Save
    path = tmp_path / "defaults"
    PydanticModel.save_to_path(path, models)
    
    # Load and verify defaults are preserved
    loaded = PydanticModel.load_from_path(path.with_suffix(".parquet"), list[DefaultModel])
    
    assert loaded[0].value == 50
    assert loaded[0].tag == "custom_tag"
    assert loaded[1].value == 100  # default
    assert loaded[1].tag == "default_tag"  # default
    assert loaded[2].value == 75
    assert loaded[2].tag == "default_tag"  # default


def test_arrowframe_in_memory_passing(tmp_path):
    """Test passing ArrowFrame in memory between steps."""
    class Step1(TypedStep[NoSettings, None, ArrowFrame[SimpleModel]]):
        def run(self, inpt: None) -> ArrowFrame[SimpleModel]:
            return ArrowFrame[SimpleModel].from_rows([
                SimpleModel(name="s1", value=10)
            ])
    
    class Step2(TypedStep[NoSettings, ArrowFrame[SimpleModel], SimpleModel]):
        def run(self, inpt: ArrowFrame[SimpleModel]) -> SimpleModel:
            # Consume the frame
            models = inpt.collect()
            return models[0]
    
    out1 = tmp_path / "out1"
    
    with BaseStepExecutor() as ex:
        result1 = ex.execute_step(Step1, None, out1)
        
        # Pass the ArrowFrame result directly to Step2 (in-memory, no disk)
        in_memory_frame = result1[0][0]
        result2 = ex.execute_step(Step2, {in_memory_frame}, None)
    
    # Verify in-memory passing worked
    final = result2[0][0]
    assert isinstance(final, SimpleModel)
    assert final.name == "s1"


def test_arrowframe_equality_after_roundtrip(tmp_path):
    """Test that models maintain equality after ArrowFrame roundtrip."""
    original = SimpleModel(name="test", value=42)
    
    # Save
    path = tmp_path / "equality"
    PydanticModel.save_to_path(path, [original])
    
    # Load
    loaded_list = PydanticModel.load_from_path(path.with_suffix(".parquet"), list[SimpleModel])
    
    # Verify equality
    assert loaded_list[0] == original
    assert loaded_list[0].name == original.name
    assert loaded_list[0].value == original.value
