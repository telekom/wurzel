# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""OpenTelemetry middleware for Wurzel step execution.

This middleware provides distributed tracing and automatic HTTP instrumentation
for every step in a Wurzel pipeline.  It:

* Creates a ``TracerProvider`` backed by an OTLP/gRPC exporter.
* Auto-instruments the ``requests``, ``urllib3``, ``threading``, and ``logging``
  libraries so that all outbound HTTP calls made by steps are captured as child
  spans and log records carry ``trace_id`` / ``span_id`` context automatically.
* Wraps each step execution in a root span annotated with ``wurzel.step.name``
  and ``wurzel.run.id``.
* Records any exception that escapes the step on the span and marks it as
  ``StatusCode.ERROR`` before re-raising.
* Cleans up (uninstruments + shuts down the provider) when used as a context
  manager, which prevents test-isolation leakage.

Example::

    from wurzel.executors.middlewares.otel import OtelMiddleware

    with OtelMiddleware() as otel:
        chain = MiddlewareChain([otel])
        chain.execute(step_cls, inputs, output_dir)
"""

import time
from logging import getLogger
from typing import Any

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.threading import ThreadingInstrumentor
from opentelemetry.instrumentation.urllib3 import URLLib3Instrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import SpanKind, StatusCode

from wurzel.core.typed_step import TypedStep
from wurzel.executors.runtime_context import WurzelRuntimeContext
from wurzel.path import PathToFolderWithBaseModels

from ..base import BaseMiddleware, ExecuteStepCallable
from .settings import OtelMiddlewareSettings

_RESOURCE_PROJECT_NAME = "project.name"
_RESOURCE_TENANT = "tenant"

log = getLogger(__name__)

_INSTRUMENTATION_SCOPE = "wurzel"


class OtelMiddleware(BaseMiddleware):
    """Middleware that adds OpenTelemetry distributed tracing to step execution.

    Auto-instruments:

    * ``requests`` — ``RequestsInstrumentor``
    * ``urllib3`` — ``URLLib3Instrumentor`` (the transport layer beneath ``requests``)
    * ``threading`` — ``ThreadingInstrumentor`` (propagates trace context across threads,
      used by steps that employ ``ThreadPoolExecutor``)
    * ``logging`` — ``LoggingInstrumentor`` (injects ``trace_id``/``span_id`` into every
      log record so traces and logs can be correlated)

    Each step execution is wrapped in a span named
    ``wurzel.step.<StepClassName>`` with the following attributes:

    * ``wurzel.step.name`` — the step class name
    * ``wurzel.run.id`` — pipeline run identifier from :class:`WurzelRuntimeContext`
    """

    def __init__(
        self,
        settings: OtelMiddlewareSettings | None = None,
        *,
        tracer_provider: TracerProvider | None = None,
    ):
        """Initialise the middleware.

        Args:
            settings: OTel configuration.  Loaded from environment if omitted.
            tracer_provider: Optional pre-built :class:`~opentelemetry.sdk.trace.TracerProvider`
                to use instead of constructing one from *settings*.  Intended for
                testing — pass a provider backed by an ``InMemorySpanExporter``.
        """
        super().__init__()
        self.settings = settings or OtelMiddlewareSettings()
        self._instrumentors: list[Any] = []
        self._provider: TracerProvider | None = None

        if not self.settings.ENABLED:
            log.debug("OtelMiddleware is disabled — no instrumentation applied")
            return

        if tracer_provider is not None:
            self._provider = tracer_provider
            # Provider was externally created (e.g. by phoenix.otel.register()).
            # Do NOT override the global — the caller already configured it.
        else:
            resource_attrs: dict[str, str] = {SERVICE_NAME: self.settings.SERVICE_NAME}
            if self.settings.PROJECT_NAME:
                resource_attrs[_RESOURCE_PROJECT_NAME] = self.settings.PROJECT_NAME
            if self.settings.TENANT:
                resource_attrs[_RESOURCE_TENANT] = self.settings.TENANT
            resource = Resource.create(resource_attrs)
            exporter = OTLPSpanExporter(
                endpoint=self.settings.ENDPOINT,
                insecure=self.settings.INSECURE,
            )
            provider = TracerProvider(resource=resource)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            self._provider = provider
            trace.set_tracer_provider(self._provider)

        self._instrument_libraries()

    # ------------------------------------------------------------------

    def __call__(
        self,
        call_next: ExecuteStepCallable,
        step_cls: type[TypedStep],
        inputs: set[PathToFolderWithBaseModels] | None,
        output_dir: PathToFolderWithBaseModels | None,
    ) -> list[tuple[Any, Any]]:
        """Execute *step_cls* wrapped in an OTel trace span.

        If ``ENABLED`` is ``False`` the middleware is a transparent pass-through.
        """
        if not self.settings.ENABLED:
            return call_next(step_cls, inputs, output_dir)

        tracer = self._provider.get_tracer(_INSTRUMENTATION_SCOPE)
        span_name = f"wurzel.step.{step_cls.__name__}"
        context = WurzelRuntimeContext.from_env()

        with tracer.start_as_current_span(span_name, kind=SpanKind.INTERNAL) as span:
            span.set_attribute("wurzel.step.name", step_cls.__name__)
            span.set_attribute("wurzel.run.id", context.run_id)
            if self.settings.PROJECT_NAME:
                span.set_attribute(_RESOURCE_PROJECT_NAME, self.settings.PROJECT_NAME)
            if self.settings.TENANT:
                span.set_attribute(_RESOURCE_TENANT, self.settings.TENANT)

            # Record input/output metadata
            if output_dir:
                span.set_attribute("wurzel.output.dir", str(output_dir))
            if inputs:
                span.set_attribute("wurzel.input.count", len(inputs))
                input_paths = [str(p) for p in list(inputs)[:10]]  # Limit to first 10 for brevity
                span.set_attribute("wurzel.input.paths", ",".join(input_paths))

            start_time = time.time()
            try:
                result = call_next(step_cls, inputs, output_dir)
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(StatusCode.ERROR, str(exc))
                raise
            else:
                # Record execution results
                duration_ms = (time.time() - start_time) * 1000
                result_count = len(result) if result else 0
                span.set_attribute("wurzel.execution.duration_ms", duration_ms)
                span.set_attribute("wurzel.execution.result_count", result_count)

                # Add completion event with structured metadata
                event_attrs: dict[str, Any] = {
                    "result_count": result_count,
                    "duration_ms": duration_ms,
                }
                if inputs:
                    event_attrs["input_count"] = len(inputs)
                if output_dir:
                    event_attrs["output_dir"] = str(output_dir)

                span.add_event(
                    "step_completed",
                    attributes=event_attrs,
                    timestamp=int(time.time() * 1e9),  # OTel expects nanoseconds
                )

                span.set_status(StatusCode.OK)
                return result

    def __exit__(self, *exc_details: Any) -> bool:
        """Uninstrument all libraries and flush/shutdown the tracer provider."""
        self._uninstrument_libraries()
        if self._provider is not None:
            self._provider.force_flush()
            self._provider.shutdown()
            self._provider = None
        return False

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _instrument_libraries(self) -> None:
        """Activate auto-instrumentation for all supported request libraries."""
        self._instrumentors = [
            RequestsInstrumentor(),
            URLLib3Instrumentor(),
            ThreadingInstrumentor(),
            LoggingInstrumentor(),
        ]
        for instrumentor in self._instrumentors:
            instrumentor.instrument()
        log.debug(
            "OtelMiddleware instrumented: %s",
            [type(i).__name__ for i in self._instrumentors],
        )

    def _uninstrument_libraries(self) -> None:
        """Remove auto-instrumentation from all supported request libraries."""
        for instrumentor in self._instrumentors:
            try:
                instrumentor.uninstrument()
            except Exception:  # noqa: BLE001 — best-effort cleanup
                log.debug("Failed to uninstrument %s", type(instrumentor).__name__, exc_info=True)
        self._instrumentors = []
