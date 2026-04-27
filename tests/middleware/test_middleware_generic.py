# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Generic tests for middleware functionality that work with all available middlewares."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from wurzel.core.typed_step import TypedStep
from wurzel.datacontract import PydanticModel
from wurzel.executors.base_executor import BaseStepExecutor
from wurzel.executors.middlewares import get_registry


class DummyReport(SimpleNamespace):
    """Dummy report for testing."""

    time_to_load: float = 0.1
    time_to_execute: float = 0.2
    time_to_save: float = 0.3
    results: int = 1
    inputs: int = 1


class DummyOutput(PydanticModel):
    """Dummy output model."""

    result: str = "dummy"


class DummyStep(TypedStep[None, None, DummyOutput]):
    """Dummy step for testing."""

    def run(self, inpt):
        """Dummy run method."""
        return DummyOutput(result="dummy_result")


def test_all_middlewares_can_be_instantiated():
    """Test that all registered middlewares can be instantiated without errors."""
    registry = get_registry()
    available_middlewares = registry.list_available()

    assert len(available_middlewares) > 0, "No middlewares registered"

    for middleware_name in available_middlewares:
        middleware_class = registry.get(middleware_name)
        assert middleware_class is not None, f"Middleware {middleware_name} not found"

        # Try to instantiate the middleware
        try:
            middleware = middleware_class()
            assert middleware is not None
        except Exception as e:
            pytest.fail(f"Failed to instantiate middleware {middleware_name}: {e}")


def test_all_middlewares_can_execute_step(tmp_path: Path):
    """Test that all registered middlewares can execute a step without errors."""
    registry = get_registry()
    available_middlewares = registry.list_available()

    for middleware_name in available_middlewares:
        # Test each middleware individually
        with BaseStepExecutor(middlewares=[middleware_name], load_middlewares_from_env=False) as exc:
            result = exc(DummyStep, None, tmp_path / middleware_name)
            assert result is not None, f"Middleware {middleware_name} returned None"


def test_all_middlewares_support_context_manager():
    """Test that all registered middlewares support context manager protocol."""
    registry = get_registry()
    available_middlewares = registry.list_available()

    for middleware_name in available_middlewares:
        middleware_class = registry.get(middleware_name)
        middleware = middleware_class()

        # Test context manager protocol
        try:
            with middleware as m:
                assert m is not None
        except Exception as e:
            pytest.fail(f"Middleware {middleware_name} failed context manager test: {e}")


def test_all_middlewares_handle_exceptions_gracefully(tmp_path: Path):
    """Test that all middlewares handle exceptions in step execution gracefully."""
    from wurzel.exceptions import StepFailed

    registry = get_registry()
    available_middlewares = registry.list_available()

    class FailingStep(TypedStep[None, None, DummyOutput]):
        """Step that always fails."""

        def run(self, inpt):
            """Always raises an exception."""
            raise RuntimeError("Intentional failure for testing")

    for middleware_name in available_middlewares:
        # Each middleware should propagate the exception (wrapped in StepFailed)
        with BaseStepExecutor(middlewares=[middleware_name], load_middlewares_from_env=False) as exc:
            with pytest.raises(StepFailed, match="Intentional failure"):
                exc(FailingStep, None, tmp_path / middleware_name)


def test_middleware_chaining_all_combinations(tmp_path: Path):
    """Test chaining all available middlewares together."""
    registry = get_registry()
    available_middlewares = registry.list_available()

    if len(available_middlewares) < 2:
        pytest.skip("Need at least 2 middlewares for chaining test")

    # Test chaining all middlewares together
    with BaseStepExecutor(middlewares=available_middlewares, load_middlewares_from_env=False) as exc:
        result = exc(DummyStep, None, tmp_path / "all_chained")
        assert result is not None


def test_middleware_chaining_pairwise(tmp_path: Path):
    """Test chaining middlewares in pairs to ensure compatibility."""
    registry = get_registry()
    available_middlewares = registry.list_available()

    if len(available_middlewares) < 2:
        pytest.skip("Need at least 2 middlewares for pairwise chaining test")

    # Test all pairs of middlewares
    for i, middleware1 in enumerate(available_middlewares):
        for middleware2 in available_middlewares[i + 1 :]:
            with BaseStepExecutor(middlewares=[middleware1, middleware2], load_middlewares_from_env=False) as exc:
                result = exc(DummyStep, None, tmp_path / f"{middleware1}_{middleware2}")
                assert result is not None, f"Failed to chain {middleware1} and {middleware2}"


def test_middleware_order_independence(tmp_path: Path):
    """Test that middleware order doesn't break execution (though results may differ)."""
    registry = get_registry()
    available_middlewares = registry.list_available()

    if len(available_middlewares) < 2:
        pytest.skip("Need at least 2 middlewares for order test")

    # Test forward and reverse order
    with BaseStepExecutor(middlewares=available_middlewares, load_middlewares_from_env=False) as exc:
        result_forward = exc(DummyStep, None, tmp_path / "forward")
        assert result_forward is not None

    with BaseStepExecutor(middlewares=list(reversed(available_middlewares)), load_middlewares_from_env=False) as exc:
        result_reverse = exc(DummyStep, None, tmp_path / "reverse")
        assert result_reverse is not None


def test_middleware_can_be_loaded_by_name():
    """Test that all middlewares can be loaded by their registered name."""
    registry = get_registry()
    available_middlewares = registry.list_available()

    for middleware_name in available_middlewares:
        loaded_middlewares = registry.load_middlewares([middleware_name], from_env=False)
        assert len(loaded_middlewares) == 1
        assert loaded_middlewares[0] is not None


def test_middleware_registry_case_insensitive():
    """Test that middleware names are case-insensitive."""
    registry = get_registry()
    available_middlewares = registry.list_available()

    for middleware_name in available_middlewares:
        # Test different case variations
        variations = [
            middleware_name.lower(),
            middleware_name.upper(),
            middleware_name.capitalize(),
        ]

        for variation in variations:
            middleware_class = registry.get(variation)
            assert middleware_class is not None, f"Failed to get {middleware_name} with variation {variation}"


def test_middleware_with_multiple_steps(tmp_path: Path):
    """Test that middlewares work correctly with multiple step executions."""
    registry = get_registry()
    available_middlewares = registry.list_available()

    class Step1(TypedStep[None, None, DummyOutput]):
        def run(self, inpt):
            return DummyOutput(result="step1_result")

    class Step2(TypedStep[None, None, DummyOutput]):
        def run(self, inpt):
            return DummyOutput(result="step2_result")

    for middleware_name in available_middlewares:
        with BaseStepExecutor(middlewares=[middleware_name], load_middlewares_from_env=False) as exc:
            result1 = exc(Step1, None, tmp_path / f"{middleware_name}_step1")
            result2 = exc(Step2, None, tmp_path / f"{middleware_name}_step2")

            assert result1 is not None
            assert result2 is not None


def test_middleware_empty_list_works(tmp_path: Path):
    """Test that executor works with empty middleware list."""
    with BaseStepExecutor(middlewares=[], load_middlewares_from_env=False) as exc:
        result = exc(DummyStep, None, tmp_path / "no_middleware")
        assert result is not None


def test_middleware_duplicate_names_handled(tmp_path: Path):
    """Test that duplicate middleware names are handled correctly."""
    registry = get_registry()
    available_middlewares = registry.list_available()

    if len(available_middlewares) == 0:
        pytest.skip("No middlewares available")

    first_middleware = available_middlewares[0]

    # Try to load the same middleware multiple times
    with BaseStepExecutor(middlewares=[first_middleware, first_middleware], load_middlewares_from_env=False) as exc:
        result = exc(DummyStep, None, tmp_path / "duplicate")
        assert result is not None


def test_middleware_with_none_inputs(tmp_path: Path):
    """Test that all middlewares handle None inputs correctly."""
    registry = get_registry()
    available_middlewares = registry.list_available()

    for middleware_name in available_middlewares:
        with BaseStepExecutor(middlewares=[middleware_name], load_middlewares_from_env=False) as exc:
            result = exc(DummyStep, None, tmp_path / f"{middleware_name}_none_input")
            assert result is not None


def test_middleware_with_empty_set_inputs(tmp_path: Path):
    """Test that all middlewares handle empty set inputs correctly."""
    registry = get_registry()
    available_middlewares = registry.list_available()

    for middleware_name in available_middlewares:
        with BaseStepExecutor(middlewares=[middleware_name], load_middlewares_from_env=False) as exc:
            result = exc(DummyStep, set(), tmp_path / f"{middleware_name}_empty_set")
            assert result is not None


@pytest.mark.parametrize("middleware_count", [1, 2, 3])
def test_middleware_chain_different_lengths(tmp_path: Path, middleware_count: int):
    """Test middleware chains of different lengths."""
    registry = get_registry()
    available_middlewares = registry.list_available()

    if len(available_middlewares) < middleware_count:
        pytest.skip(f"Need at least {middleware_count} middlewares")

    middlewares_to_use = available_middlewares[:middleware_count]

    with BaseStepExecutor(middlewares=middlewares_to_use, load_middlewares_from_env=False) as exc:
        result = exc(DummyStep, None, tmp_path / f"chain_{middleware_count}")
        assert result is not None
