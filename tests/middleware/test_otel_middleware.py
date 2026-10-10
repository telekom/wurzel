# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for OtelMiddleware."""

from typing import Any
from unittest.mock import MagicMock

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from wurzel.executors.middlewares.otel import OtelMiddleware, OtelMiddlewareSettings

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _disabled_settings() -> OtelMiddlewareSettings:
    return OtelMiddlewareSettings(ENABLED=False)


def _make_provider() -> tuple[TracerProvider, InMemorySpanExporter]:
    """Return a TracerProvider backed by an in-memory exporter."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


class _DummyStep:
    __name__ = "DummyStep"


def _call_next_ok(results: list[Any] | None = None):
    results = results or [MagicMock()]

    def _inner(step_cls, inputs, output_dir):
        return [(None, r) for r in results]

    return _inner


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------


def test_otel_middleware_instantiation_disabled():
    """Middleware can be instantiated when ENABLED=False without any OTel backend."""
    middleware = OtelMiddleware(settings=_disabled_settings())
    assert middleware is not None


def test_otel_middleware_instantiation_with_injected_provider():
    """Middleware can be instantiated with an injected TracerProvider."""
    provider, _ = _make_provider()
    settings = OtelMiddlewareSettings(ENABLED=True, ENDPOINT="localhost:4317")
    middleware = OtelMiddleware(settings=settings, tracer_provider=provider)
    assert middleware is not None
    # Cleanup
    middleware.__exit__(None, None, None)


# ---------------------------------------------------------------------------
# call_next forwarding
# ---------------------------------------------------------------------------


def test_call_next_invoked_once_when_enabled():
    """call_next is invoked exactly once per middleware call when ENABLED=True."""
    provider, _ = _make_provider()
    settings = OtelMiddlewareSettings(ENABLED=True)
    middleware = OtelMiddleware(settings=settings, tracer_provider=provider)

    call_next = MagicMock(return_value=[(None, MagicMock())])
    middleware(call_next, _DummyStep, set(), None)

    call_next.assert_called_once_with(_DummyStep, set(), None)
    middleware.__exit__(None, None, None)


def test_call_next_invoked_once_when_disabled():
    """call_next is invoked even when ENABLED=False (transparent pass-through)."""
    middleware = OtelMiddleware(settings=_disabled_settings())
    call_next = MagicMock(return_value=[(None, MagicMock())])
    middleware(call_next, _DummyStep, set(), None)
    call_next.assert_called_once_with(_DummyStep, set(), None)


# ---------------------------------------------------------------------------
# Span creation
# ---------------------------------------------------------------------------


def test_span_created_with_correct_name(monkeypatch):
    """A span named 'wurzel.step.DummyStep' is created for each step execution."""
    monkeypatch.setenv("WURZEL_RUN_ID", "test-run-001")
    provider, exporter = _make_provider()
    settings = OtelMiddlewareSettings(ENABLED=True)
    middleware = OtelMiddleware(settings=settings, tracer_provider=provider)

    middleware(_call_next_ok(), _DummyStep, set(), None)
    middleware.__exit__(None, None, None)

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "wurzel.step._DummyStep"


def test_span_attributes_set(monkeypatch):
    """The span carries wurzel.step.name and wurzel.run.id attributes."""
    monkeypatch.setenv("WURZEL_RUN_ID", "my-run-42")
    provider, exporter = _make_provider()
    settings = OtelMiddlewareSettings(ENABLED=True)
    middleware = OtelMiddleware(settings=settings, tracer_provider=provider)

    middleware(_call_next_ok(), _DummyStep, set(), None)
    middleware.__exit__(None, None, None)

    span = exporter.get_finished_spans()[0]
    assert span.attributes["wurzel.step.name"] == "_DummyStep"
    assert span.attributes["wurzel.run.id"] == "my-run-42"


def test_project_name_attribute_set_on_span():
    """project.name is added to the span when PROJECT_NAME is set."""
    provider, exporter = _make_provider()
    settings = OtelMiddlewareSettings(ENABLED=True, PROJECT_NAME="my-project")
    middleware = OtelMiddleware(settings=settings, tracer_provider=provider)

    middleware(_call_next_ok(), _DummyStep, set(), None)
    middleware.__exit__(None, None, None)

    span = exporter.get_finished_spans()[0]
    assert span.attributes["project.name"] == "my-project"


def test_tenant_attribute_set_on_span():
    """Tenant is added to the span when TENANT is set."""
    provider, exporter = _make_provider()
    settings = OtelMiddlewareSettings(ENABLED=True, TENANT="acme-corp")
    middleware = OtelMiddleware(settings=settings, tracer_provider=provider)

    middleware(_call_next_ok(), _DummyStep, set(), None)
    middleware.__exit__(None, None, None)

    span = exporter.get_finished_spans()[0]
    assert span.attributes["tenant"] == "acme-corp"


def test_empty_project_name_not_set_on_span():
    """project.name is NOT added to the span when PROJECT_NAME is empty."""
    provider, exporter = _make_provider()
    settings = OtelMiddlewareSettings(ENABLED=True, PROJECT_NAME="")
    middleware = OtelMiddleware(settings=settings, tracer_provider=provider)

    middleware(_call_next_ok(), _DummyStep, set(), None)
    middleware.__exit__(None, None, None)

    span = exporter.get_finished_spans()[0]
    assert "project.name" not in span.attributes


def test_empty_tenant_not_set_on_span():
    """Tenant is NOT added to the span when TENANT is empty."""
    provider, exporter = _make_provider()
    settings = OtelMiddlewareSettings(ENABLED=True, TENANT="")
    middleware = OtelMiddleware(settings=settings, tracer_provider=provider)

    middleware(_call_next_ok(), _DummyStep, set(), None)
    middleware.__exit__(None, None, None)

    span = exporter.get_finished_spans()[0]
    assert "tenant" not in span.attributes


def test_span_status_ok_on_success():
    """Span status is OK when the step completes successfully."""
    provider, exporter = _make_provider()
    settings = OtelMiddlewareSettings(ENABLED=True)
    middleware = OtelMiddleware(settings=settings, tracer_provider=provider)

    middleware(_call_next_ok(), _DummyStep, set(), None)
    middleware.__exit__(None, None, None)

    span = exporter.get_finished_spans()[0]
    assert span.status.status_code == StatusCode.OK


def test_no_span_when_disabled():
    """No spans are emitted when ENABLED=False."""
    provider, exporter = _make_provider()
    settings = OtelMiddlewareSettings(ENABLED=False)
    # Even if a provider is set globally, the disabled middleware does nothing OTel-specific
    middleware = OtelMiddleware(settings=settings)

    middleware(_call_next_ok(), _DummyStep, set(), None)

    assert exporter.get_finished_spans() == ()


# ---------------------------------------------------------------------------
# Exception handling
# ---------------------------------------------------------------------------


def test_exception_recorded_on_span():
    """An exception from call_next is recorded on the span."""
    provider, exporter = _make_provider()
    settings = OtelMiddlewareSettings(ENABLED=True)
    middleware = OtelMiddleware(settings=settings, tracer_provider=provider)

    boom = RuntimeError("step exploded")

    def failing_call_next(step_cls, inputs, output_dir):
        raise boom

    with pytest.raises(RuntimeError, match="step exploded"):
        middleware(failing_call_next, _DummyStep, set(), None)

    middleware.__exit__(None, None, None)

    span = exporter.get_finished_spans()[0]
    assert span.status.status_code == StatusCode.ERROR
    # OTel records the exception as an event
    event_names = [e.name for e in span.events]
    assert "exception" in event_names


def test_exception_is_reraised():
    """Exceptions always propagate out of the middleware."""
    provider, _ = _make_provider()
    settings = OtelMiddlewareSettings(ENABLED=True)
    middleware = OtelMiddleware(settings=settings, tracer_provider=provider)

    def failing_call_next(step_cls, inputs, output_dir):
        raise ValueError("oops")

    with pytest.raises(ValueError, match="oops"):
        middleware(failing_call_next, _DummyStep, set(), None)

    middleware.__exit__(None, None, None)


# ---------------------------------------------------------------------------
# Context manager cleanup
# ---------------------------------------------------------------------------


def test_context_manager_cleans_up():
    """Using OtelMiddleware as a context manager calls __exit__ automatically."""
    provider, _ = _make_provider()
    settings = OtelMiddlewareSettings(ENABLED=True)

    with OtelMiddleware(settings=settings, tracer_provider=provider) as middleware:
        assert middleware is not None

    # After the with-block the provider reference should be cleared
    assert middleware._provider is None


def test_exit_uninstruments_all():
    """After __exit__, the _instrumentors list is empty (all uninstrumented)."""
    provider, _ = _make_provider()
    settings = OtelMiddlewareSettings(ENABLED=True)
    middleware = OtelMiddleware(settings=settings, tracer_provider=provider)

    assert len(middleware._instrumentors) == 4  # requests, urllib3, threading, logging

    middleware.__exit__(None, None, None)
    assert middleware._instrumentors == []


# ─────────────────────────────────────────────────────────────────────────────
# Input/Output & Execution Metadata
# ─────────────────────────────────────────────────────────────────────────────


def test_output_dir_recorded_on_span():
    """output_dir path is recorded as a span attribute."""
    from pathlib import Path

    provider, exporter = _make_provider()
    settings = OtelMiddlewareSettings(ENABLED=True)
    middleware = OtelMiddleware(settings=settings, tracer_provider=provider)
    output_dir = Path("/tmp/output")

    middleware(_call_next_ok(), _DummyStep, set(), output_dir)
    middleware.__exit__(None, None, None)

    span = exporter.get_finished_spans()[0]
    assert span.attributes["wurzel.output.dir"] == str(output_dir)


def test_input_count_and_paths_recorded():
    """Input count and paths are recorded as span attributes."""
    from pathlib import Path

    provider, exporter = _make_provider()
    settings = OtelMiddlewareSettings(ENABLED=True)
    middleware = OtelMiddleware(settings=settings, tracer_provider=provider)

    input_paths = {Path(f"/tmp/input{i}") for i in range(3)}
    middleware(_call_next_ok(), _DummyStep, input_paths, None)
    middleware.__exit__(None, None, None)

    span = exporter.get_finished_spans()[0]
    assert span.attributes["wurzel.input.count"] == 3
    assert "wurzel.input.paths" in span.attributes


def test_execution_duration_recorded():
    """Execution duration is recorded as a span attribute (in milliseconds)."""
    provider, exporter = _make_provider()
    settings = OtelMiddlewareSettings(ENABLED=True)
    middleware = OtelMiddleware(settings=settings, tracer_provider=provider)

    middleware(_call_next_ok(), _DummyStep, set(), None)
    middleware.__exit__(None, None, None)

    span = exporter.get_finished_spans()[0]
    assert "wurzel.execution.duration_ms" in span.attributes
    assert span.attributes["wurzel.execution.duration_ms"] >= 0


def test_result_count_recorded():
    """Result count is recorded as a span attribute."""
    provider, exporter = _make_provider()
    settings = OtelMiddlewareSettings(ENABLED=True)
    middleware = OtelMiddleware(settings=settings, tracer_provider=provider)

    results = [MagicMock() for _ in range(5)]
    middleware(_call_next_ok(results), _DummyStep, set(), None)
    middleware.__exit__(None, None, None)

    span = exporter.get_finished_spans()[0]
    assert span.attributes["wurzel.execution.result_count"] == 5


def test_step_completed_event_added():
    """A 'step_completed' event is added with metadata."""
    provider, exporter = _make_provider()
    settings = OtelMiddlewareSettings(ENABLED=True)
    middleware = OtelMiddleware(settings=settings, tracer_provider=provider)

    middleware(_call_next_ok(), _DummyStep, set(), None)
    middleware.__exit__(None, None, None)

    span = exporter.get_finished_spans()[0]
    event_names = [e.name for e in span.events]
    assert "step_completed" in event_names

    event = [e for e in span.events if e.name == "step_completed"][0]
    assert "result_count" in event.attributes
    assert "duration_ms" in event.attributes
