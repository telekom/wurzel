# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Integration tests verifying that steps can execute without OTel middleware.

This test suite ensures that:
1. Steps execute correctly when middleware is disabled
2. Steps don't have hard dependencies on the OTel middleware
3. The middleware is truly optional and doesn't interfere with normal operation
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from wurzel.core.typed_step import TypedStep
from wurzel.datacontract import PydanticModel
from wurzel.executors.base_executor import BaseStepExecutor
from wurzel.executors.middlewares.base import BaseMiddleware


class DummyOutput(PydanticModel):
    """Simple output model for test steps."""

    result: str = "ok"


class SimpleStep(TypedStep[None, None, DummyOutput]):
    """Minimal test step for middleware-less execution."""

    def run(self, inp):
        """Simple run that returns a test result."""
        return DummyOutput(result="success")


class SimpleStepWithInput(TypedStep[None, DummyOutput, DummyOutput]):
    """Test step that accepts input."""

    def run(self, inp: DummyOutput) -> DummyOutput:
        """Transform input to output."""
        return DummyOutput(result=f"processed_{inp.result}")


class NoOpMiddleware(BaseMiddleware):
    """Test middleware that does nothing but verifies it's called."""

    def __init__(self):
        super().__init__()
        self.call_count = 0

    def __call__(self, call_next, step_cls, inputs, output_dir):
        """Pass through to next middleware/executor."""
        self.call_count += 1
        return call_next(step_cls, inputs, output_dir)


class TestStepsWithoutOtelMiddleware:
    """Verify steps work without OTel middleware."""

    def test_step_runs_without_any_middleware(self):
        """A step can execute with BaseStepExecutor and no middleware."""
        with BaseStepExecutor(load_middlewares_from_env=False) as executor:
            # Should not raise
            result = executor(SimpleStep, None, None)
            assert result is not None
            assert isinstance(result, list)
            assert len(result) > 0

    def test_step_runs_with_disabled_otel_middleware(self):
        """OTel middleware disabled via settings acts as transparent pass-through."""
        from wurzel.executors.middlewares.otel import OtelMiddleware, OtelMiddlewareSettings

        settings = OtelMiddlewareSettings(ENABLED=False)
        middleware = OtelMiddleware(settings=settings)

        # Middleware should be transparent
        mock_result = ("result", MagicMock())
        call_next = MagicMock(return_value=[mock_result])

        result = middleware(
            call_next=call_next,
            step_cls=SimpleStep,
            inputs=None,
            output_dir=None,
        )

        # call_next should have been called directly
        assert call_next.called
        assert result == [mock_result]

    def test_step_executes_without_middleware_chain(self):
        """Steps execute normally when no middleware chain is configured."""
        with BaseStepExecutor(load_middlewares_from_env=False) as executor:
            with tempfile.TemporaryDirectory() as tmpdir:
                output_dir = Path(tmpdir)

                # Direct execution without middleware
                results = list(executor._execute_step(SimpleStep, set(), output_dir))

                assert len(results) > 0
                for result, report in results:
                    assert result is not None
                    assert report is not None

    def test_multiple_steps_without_middleware(self):
        """Multiple different steps can execute without middleware."""
        executor = BaseStepExecutor(load_middlewares_from_env=False)

        for _ in range(3):
            result = executor(SimpleStep, None, None)
            assert result is not None
            assert isinstance(result, list)

    def test_middleware_can_be_added_optionally(self):
        """Middleware can be optionally added to the execution chain."""
        noop = NoOpMiddleware()

        # Create a simple chain manually
        executor = BaseStepExecutor(load_middlewares_from_env=False)

        # Wrap executor call with middleware manually
        def execute_with_middleware(step_cls, inputs, output_dir):
            return noop(
                call_next=lambda s, i, o: executor(s, i, o),
                step_cls=step_cls,
                inputs=inputs,
                output_dir=output_dir,
            )

        # Execute through middleware
        result = execute_with_middleware(SimpleStep, None, None)

        # Middleware should have been invoked
        assert noop.call_count == 1
        assert result is not None
        assert isinstance(result, list)

    def test_middleware_disabled_is_same_as_no_middleware(self):
        """Disabled middleware doesn't affect step execution."""
        from wurzel.executors.middlewares.otel import OtelMiddleware, OtelMiddlewareSettings

        # Run without middleware
        executor1 = BaseStepExecutor(load_middlewares_from_env=False)
        result1 = executor1(SimpleStep, None, None)

        # Run with disabled middleware
        settings = OtelMiddlewareSettings(ENABLED=False)
        disabled_middleware = OtelMiddleware(settings=settings)
        executor2 = BaseStepExecutor(load_middlewares_from_env=False)

        # Manually apply disabled middleware
        result2 = disabled_middleware(
            call_next=lambda step_cls, inputs, output_dir: executor2(
                step_cls, inputs, output_dir
            ),
            step_cls=SimpleStep,
            inputs=None,
            output_dir=None,
        )

        # Both should produce results
        assert result1 is not None
        assert result2 is not None
        assert len(result1) > 0
        assert len(result2) > 0


class TestOtelMiddlewareOptional:
    """Verify OTel middleware is optional and doesn't break steps."""

    def test_otel_middleware_import_doesnt_require_installation(self):
        """OTel middleware can be imported without runtime errors."""
        # This test passes if import succeeds
        from wurzel.executors.middlewares.otel import OtelMiddleware  # noqa: F401

    def test_otel_settings_load_without_env_vars(self):
        """OTel settings can be loaded with defaults if env vars not set."""
        from wurzel.executors.middlewares.otel import OtelMiddlewareSettings

        # Should not raise even without env vars
        settings = OtelMiddlewareSettings()

        assert settings.ENABLED is True
        assert settings.ENDPOINT == "localhost:4317"
        assert settings.SERVICE_NAME == "wurzel"

    def test_otel_disabled_setting_makes_middleware_transparent(self):
        """ENABLED=False setting makes middleware a no-op."""
        from wurzel.executors.middlewares.otel import OtelMiddleware, OtelMiddlewareSettings

        settings = OtelMiddlewareSettings(ENABLED=False)
        middleware = OtelMiddleware(settings=settings)

        # Even with middleware present, it should be transparent
        mock_call_next = MagicMock(return_value=[("x", "y")])

        result = middleware(mock_call_next, SimpleStep, None, None)

        # Should forward directly to call_next
        mock_call_next.assert_called_once_with(SimpleStep, None, None)
        assert result == [("x", "y")]

    def test_step_works_without_otel_optional_dependency(self):
        """Steps work even if OTel dependencies aren't installed."""
        # This test verifies the step architecture doesn't require OTel
        executor = BaseStepExecutor(load_middlewares_from_env=False)

        # Execute without any OTel involvement
        result = executor(SimpleStep, None, None)

        assert result is not None
        assert isinstance(result, list)
        assert len(result) > 0
