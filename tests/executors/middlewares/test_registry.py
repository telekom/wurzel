# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Generic tests for middleware functionality that work with all available middlewares."""

import itertools
from pathlib import Path

import pytest

from wurzel.core.typed_step import TypedStep
from wurzel.datacontract import PydanticModel
from wurzel.executors.base_executor import BaseStepExecutor
from wurzel.executors.middlewares import get_registry


class DummyOutput(PydanticModel):
    """Dummy output model."""

    result: str = "dummy"


class DummyStep(TypedStep[None, None, DummyOutput]):
    """Dummy step for testing."""

    def run(self, inpt):
        """Dummy run method."""
        return DummyOutput(result="dummy_result")


# ── helpers evaluated once at collection time ──────────────────────────────


def _available_middlewares() -> list[str]:
    return get_registry().list_available()


def _middleware_pairs() -> list[tuple[str, str]]:
    return list(itertools.combinations(_available_middlewares(), 2))


# ── per-middleware fixtures / parametrize ───────────────────────────────────


@pytest.fixture(params=_available_middlewares())
def middleware_name(request: pytest.FixtureRequest) -> str:
    return request.param  # type: ignore[return-value]


# ── tests ────────────────────────────────────────────────────────────────────


def test_at_least_one_middleware_is_registered():
    """Sanity check: the registry must not be empty."""
    assert len(_available_middlewares()) > 0, "No middlewares registered"


def test_middleware_can_be_instantiated(middleware_name: str):
    """Each registered middleware can be instantiated without errors."""
    middleware_class = get_registry().get(middleware_name)
    assert middleware_class is not None
    assert middleware_class() is not None


def test_middleware_can_execute_step(middleware_name: str, tmp_path: Path):
    """Each middleware can run a step to completion."""
    with BaseStepExecutor(middlewares=[middleware_name], load_middlewares_from_env=False) as exc:
        result = exc(DummyStep, None, tmp_path / middleware_name)
        assert result is not None


def test_middleware_supports_context_manager(middleware_name: str):
    """Each middleware implements the context-manager protocol."""
    middleware = get_registry().get(middleware_name)()
    with middleware as m:
        assert m is not None


def test_middleware_handles_step_failure_gracefully(middleware_name: str, tmp_path: Path):
    """Each middleware propagates step failures wrapped in StepFailed."""
    from wurzel.exceptions import StepFailed  # noqa: PLC0415

    class FailingStep(TypedStep[None, None, DummyOutput]):
        def run(self, inpt):
            raise RuntimeError("Intentional failure for testing")

    with BaseStepExecutor(middlewares=[middleware_name], load_middlewares_from_env=False) as exc:
        with pytest.raises(StepFailed, match="Intentional failure"):
            exc(FailingStep, None, tmp_path / middleware_name)


def test_middleware_can_be_loaded_by_name(middleware_name: str):
    """Each middleware can be loaded from the registry by name."""
    loaded = get_registry().load_middlewares([middleware_name], from_env=False)
    assert len(loaded) == 1
    assert loaded[0] is not None


@pytest.mark.parametrize("variation_fn", [str.lower, str.upper, str.capitalize], ids=["lower", "upper", "capitalize"])
def test_middleware_registry_case_insensitive(middleware_name: str, variation_fn):
    """Registry lookup is case-insensitive for all registered middlewares."""
    assert get_registry().get(variation_fn(middleware_name)) is not None


def test_middleware_handles_none_inputs(middleware_name: str, tmp_path: Path):
    """Each middleware handles None as the inputs argument."""
    with BaseStepExecutor(middlewares=[middleware_name], load_middlewares_from_env=False) as exc:
        assert exc(DummyStep, None, tmp_path / f"{middleware_name}_none") is not None


def test_middleware_handles_empty_set_inputs(middleware_name: str, tmp_path: Path):
    """Each middleware handles an empty set as the inputs argument."""
    with BaseStepExecutor(middlewares=[middleware_name], load_middlewares_from_env=False) as exc:
        assert exc(DummyStep, set(), tmp_path / f"{middleware_name}_empty") is not None


def test_middleware_works_with_multiple_sequential_steps(middleware_name: str, tmp_path: Path):
    """Each middleware correctly handles multiple step executions in sequence."""

    class Step1(TypedStep[None, None, DummyOutput]):
        def run(self, inpt):
            return DummyOutput(result="step1_result")

    class Step2(TypedStep[None, None, DummyOutput]):
        def run(self, inpt):
            return DummyOutput(result="step2_result")

    with BaseStepExecutor(middlewares=[middleware_name], load_middlewares_from_env=False) as exc:
        assert exc(Step1, None, tmp_path / f"{middleware_name}_step1") is not None
        assert exc(Step2, None, tmp_path / f"{middleware_name}_step2") is not None


# ── multi-middleware chain tests ─────────────────────────────────────────────


def test_middleware_chaining_all_together(tmp_path: Path):
    """All available middlewares can be chained together in a single executor."""
    available = _available_middlewares()
    if len(available) < 2:
        pytest.skip("Need at least 2 middlewares for chaining test")

    with BaseStepExecutor(middlewares=available, load_middlewares_from_env=False) as exc:
        assert exc(DummyStep, None, tmp_path / "all_chained") is not None


@pytest.mark.parametrize("mw1,mw2", _middleware_pairs())
def test_middleware_chaining_pairwise(tmp_path: Path, mw1: str, mw2: str):
    """Every pair of middlewares can be chained without errors."""
    with BaseStepExecutor(middlewares=[mw1, mw2], load_middlewares_from_env=False) as exc:
        assert exc(DummyStep, None, tmp_path / f"{mw1}__{mw2}") is not None


def test_middleware_order_independence(tmp_path: Path):
    """Forward and reverse middleware ordering both complete without errors."""
    available = _available_middlewares()
    if len(available) < 2:
        pytest.skip("Need at least 2 middlewares for order test")

    with BaseStepExecutor(middlewares=available, load_middlewares_from_env=False) as exc:
        assert exc(DummyStep, None, tmp_path / "forward") is not None

    with BaseStepExecutor(middlewares=list(reversed(available)), load_middlewares_from_env=False) as exc:
        assert exc(DummyStep, None, tmp_path / "reverse") is not None


def test_middleware_empty_list_works(tmp_path: Path):
    """An executor with an empty middleware list still runs steps."""
    with BaseStepExecutor(middlewares=[], load_middlewares_from_env=False) as exc:
        assert exc(DummyStep, None, tmp_path / "no_middleware") is not None


def test_middleware_duplicate_names_handled(tmp_path: Path):
    """Duplicate middleware names in the list don't cause errors."""
    available = _available_middlewares()
    if not available:
        pytest.skip("No middlewares available")

    first = available[0]
    with BaseStepExecutor(middlewares=[first, first], load_middlewares_from_env=False) as exc:
        assert exc(DummyStep, None, tmp_path / "duplicate") is not None


@pytest.mark.parametrize("middleware_count", [1, 2, 3])
def test_middleware_chain_different_lengths(tmp_path: Path, middleware_count: int):
    """Middleware chains of length 1, 2, and 3 all work correctly."""
    available = _available_middlewares()
    if len(available) < middleware_count:
        pytest.skip(f"Need at least {middleware_count} middlewares")

    with BaseStepExecutor(middlewares=available[:middleware_count], load_middlewares_from_env=False) as exc:
        assert exc(DummyStep, None, tmp_path / f"chain_{middleware_count}") is not None


def test_module_level_load_middlewares_returns_list():
    """Module-level load_middlewares() function delegates to the global registry."""
    from wurzel.executors.middlewares import load_middlewares  # noqa: PLC0415

    result = load_middlewares(names=[], from_env=False)
    assert isinstance(result, list)
