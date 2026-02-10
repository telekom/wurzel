# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for middleware system."""

from pathlib import Path

from wurzel.core.typed_step import TypedStep
from wurzel.datacontract.common import MarkdownDataContract
from wurzel.executors import BaseStepExecutor
from wurzel.executors.middlewares import (
    BaseMiddleware,
    MiddlewareChain,
    get_registry,
)


class DummyStep(TypedStep[None, None, MarkdownDataContract]):
    """Dummy step for testing."""

    def run(self, inpt: None) -> MarkdownDataContract:
        return MarkdownDataContract(md="test", keywords="test", url="test")


class TrackerMiddleware(BaseMiddleware):
    """Middleware that tracks execution for testing."""

    def __init__(self):
        super().__init__()
        self.calls = []
        self.entered = False
        self.exited = False

    def __call__(self, call_next, step_cls, inputs, output_dir):
        """Track execution."""
        self.calls.append(("before", step_cls.__name__))
        result = call_next(step_cls, inputs, output_dir)
        self.calls.append(("after", step_cls.__name__))
        return result

    def __enter__(self):
        """Track enter."""
        self.entered = True
        return self

    def __exit__(self, *exc_details):
        """Track exit."""
        self.exited = True


def test_middleware_chain_empty():
    """Test executor with no middlewares."""
    with BaseStepExecutor(middlewares=[], load_middlewares_from_env=False) as exc:
        result = exc(DummyStep, None, None)
        assert result


def test_middleware_chain_single(tmp_path: Path):
    """Test executor with single middleware."""
    tracker = TrackerMiddleware()

    with BaseStepExecutor(middlewares=[tracker], load_middlewares_from_env=False) as exc:
        assert tracker.entered
        result = exc(DummyStep, None, tmp_path)
        assert result
        assert len(tracker.calls) == 2
        assert tracker.calls[0] == ("before", "DummyStep")
        assert tracker.calls[1] == ("after", "DummyStep")

    assert tracker.exited


def test_middleware_chain_multiple(tmp_path: Path):
    """Test executor with multiple middlewares."""
    tracker1 = TrackerMiddleware()
    tracker2 = TrackerMiddleware()

    with BaseStepExecutor(middlewares=[tracker1, tracker2], load_middlewares_from_env=False) as exc:
        result = exc(DummyStep, None, tmp_path)
        assert result

        # tracker1 wraps tracker2, so it executes first
        assert tracker1.calls[0] == ("before", "DummyStep")
        assert tracker2.calls[0] == ("before", "DummyStep")
        assert tracker2.calls[1] == ("after", "DummyStep")
        assert tracker1.calls[1] == ("after", "DummyStep")


def test_middleware_by_name(tmp_path: Path, env):
    """Test loading middleware by name."""
    # Register tracker middleware
    registry = get_registry()
    registry.register("tracker", TrackerMiddleware)

    with BaseStepExecutor(middlewares=["tracker"], load_middlewares_from_env=False) as exc:
        result = exc(DummyStep, None, tmp_path)
        assert result


def test_middleware_from_env(tmp_path: Path, env):
    """Test loading middleware from environment."""
    env.set("MIDDLEWARES", "prometheus")

    with BaseStepExecutor(load_middlewares_from_env=True) as exc:
        # Should work even if prometheus middleware is available
        result = exc(DummyStep, None, tmp_path)
        assert result


def test_middleware_env_not_loaded_by_default(tmp_path: Path, env):
    """Ensure env middlewares are not loaded unless explicitly requested."""
    registry = get_registry()

    class EnvTrackerMiddleware(BaseMiddleware):
        created_instances = 0

        def __init__(self):
            super().__init__()
            EnvTrackerMiddleware.created_instances += 1

        def __call__(self, call_next, step_cls, inputs, output_dir):
            return call_next(step_cls, inputs, output_dir)

    middleware_name = "envtrackerdefault"
    registry.register(middleware_name, EnvTrackerMiddleware)
    env.set("MIDDLEWARES", middleware_name)

    try:
        with BaseStepExecutor() as exc:
            result = exc(DummyStep, None, tmp_path)
            assert result
        assert EnvTrackerMiddleware.created_instances == 0
    finally:
        registry._middlewares.pop(middleware_name, None)


def test_middleware_env_load_flag_preserves_old_behavior(tmp_path: Path, env):
    """Ensure enabling env loading recreates the previous default behavior."""
    registry = get_registry()

    class EnvTrackerMiddleware(BaseMiddleware):
        created_instances = 0

        def __init__(self):
            super().__init__()
            EnvTrackerMiddleware.created_instances += 1

        def __call__(self, call_next, step_cls, inputs, output_dir):
            return call_next(step_cls, inputs, output_dir)

    middleware_name = "envtrackerlegacy"
    registry.register(middleware_name, EnvTrackerMiddleware)
    env.set("MIDDLEWARES", middleware_name)

    try:
        with BaseStepExecutor(load_middlewares_from_env=True) as exc:
            result = exc(DummyStep, None, tmp_path)
            assert result
        assert EnvTrackerMiddleware.created_instances == 1
    finally:
        registry._middlewares.pop(middleware_name, None)


def test_prometheus_middleware_integration(tmp_path: Path):
    """Test that prometheus middleware works via new pattern."""
    with BaseStepExecutor(middlewares=["prometheus"], load_middlewares_from_env=False) as exc:
        result = exc(DummyStep, None, tmp_path)
        assert result


def test_middleware_chain_builder():
    """Test middleware chain builder."""
    tracker1 = TrackerMiddleware()
    tracker2 = TrackerMiddleware()

    chain = MiddlewareChain()
    chain.add(tracker1)
    chain.add(tracker2)

    assert len(chain.middlewares) == 2
    assert chain.middlewares[0] is tracker1
    assert chain.middlewares[1] is tracker2


def test_registry_list_available():
    """Test listing available middlewares."""
    registry = get_registry()
    available = registry.list_available()

    # At least prometheus should be available
    assert "prometheus" in available


def test_prometheus_middleware_with_settings(tmp_path: Path, env):
    """Test prometheus middleware respects settings."""
    # Set prometheus settings with correct PROMETHEUS__ prefix
    env.set("PROMETHEUS__GATEWAY", "http://localhost:9091")
    env.set("PROMETHEUS__JOB", "test-job")
    env.set("PROMETHEUS__DISABLE_CREATED_METRIC", "True")

    # Verify settings are loaded correctly
    from wurzel.executors.middlewares.prometheus.settings import PrometheusMiddlewareSettings

    settings = PrometheusMiddlewareSettings()
    assert settings.GATEWAY == "http://localhost:9091", f"Expected 'http://localhost:9091', got '{settings.GATEWAY}'"
    assert settings.JOB == "test-job", f"Expected 'test-job', got '{settings.JOB}'"
    assert settings.DISABLE_CREATED_METRIC is True, f"Expected True, got {settings.DISABLE_CREATED_METRIC}"

    with BaseStepExecutor(middlewares=["prometheus"], load_middlewares_from_env=False) as exc:
        result = exc(DummyStep, None, tmp_path)
        assert result


def test_prometheus_middleware_execution_tracking(tmp_path: Path):
    """Test that prometheus middleware tracks execution using name string."""
    # Use prometheus via name to avoid duplicate registry issues
    with BaseStepExecutor(middlewares=["prometheus"], load_middlewares_from_env=False) as exc:
        # Execute the step
        result = exc(DummyStep, None, tmp_path)
        assert result
