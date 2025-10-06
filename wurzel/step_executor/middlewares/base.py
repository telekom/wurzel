# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Base middleware interface for step executor middlewares."""

from abc import ABC, abstractmethod
from logging import getLogger
from typing import Any, Callable, Optional

from wurzel.path import PathToFolderWithBaseModels
from wurzel.step.typed_step import TypedStep

log = getLogger(__name__)


ExecuteStepCallable = Callable[
    [type[TypedStep], Optional[set[PathToFolderWithBaseModels]], Optional[PathToFolderWithBaseModels]],
    list[tuple[Any, Any]],
]


class BaseMiddleware(ABC):
    """Base class for all step executor middlewares.

    Middlewares wrap the step execution to add cross-cutting concerns like
    metrics, logging, tracing, etc. Each middleware can execute code before
    and after the step execution.

    Middlewares follow the Chain of Responsibility pattern, where each
    middleware calls the next one in the chain.
    """

    def __init__(self):
        """Initialize the middleware."""
        self.next_middleware: Optional[BaseMiddleware] = None

    def set_next(self, middleware: "BaseMiddleware") -> "BaseMiddleware":
        """Set the next middleware in the chain.

        Args:
            middleware: The next middleware to call

        Returns:
            The middleware that was set (for chaining)
        """
        self.next_middleware = middleware
        return middleware

    @abstractmethod
    def execute(
        self,
        next_call: ExecuteStepCallable,
        step_cls: type[TypedStep],
        inputs: Optional[set[PathToFolderWithBaseModels]],
        output_dir: Optional[PathToFolderWithBaseModels],
    ) -> list[tuple[Any, Any]]:
        """Execute the middleware logic and call the next middleware or executor.

        This method should:
        1. Execute any pre-processing logic
        2. Call next_call() to continue the chain
        3. Execute any post-processing logic
        4. Return the result

        Args:
            next_call: The next function in the chain (next middleware or base executor)
            step_cls: The step class to execute
            inputs: Input paths or objects for the step
            output_dir: Output directory for results

        Returns:
            List of tuples containing step results and reports
        """

    @abstractmethod
    def __enter__(self):
        """Context manager entry. Called when executor is used with 'with' statement."""

    @abstractmethod
    def __exit__(self, *exc_details):
        """Context manager exit. Called when leaving the 'with' block."""


class MiddlewareChain:
    """Manages a chain of middlewares and executes them in order."""

    def __init__(self, middlewares: Optional[list[BaseMiddleware]] = None):
        """Initialize the middleware chain.

        Args:
            middlewares: List of middlewares to chain together
        """
        self.middlewares = middlewares or []

    def add(self, middleware: BaseMiddleware) -> "MiddlewareChain":
        """Add a middleware to the chain.

        Args:
            middleware: The middleware to add

        Returns:
            Self for method chaining
        """
        self.middlewares.append(middleware)
        return self

    def build_chain(self, base_call: ExecuteStepCallable) -> ExecuteStepCallable:
        """Build the middleware chain and return the final callable.

        This creates a nested chain where each middleware wraps the next one,
        ultimately wrapping the base executor call.

        Args:
            base_call: The base executor function to wrap

        Returns:
            A callable that executes the entire middleware chain
        """
        # Build chain from bottom up (reverse order)
        current_call = base_call

        for middleware in reversed(self.middlewares):
            # Capture current_call in closure
            current_call = self._wrap_middleware(middleware, current_call)

        return current_call

    @staticmethod
    def _wrap_middleware(middleware: BaseMiddleware, next_call: ExecuteStepCallable) -> ExecuteStepCallable:
        """Wrap a middleware around a callable.

        Args:
            middleware: The middleware to wrap
            next_call: The next callable in the chain

        Returns:
            A new callable that executes the middleware
        """

        def wrapped(
            step_cls: type[TypedStep],
            inputs: Optional[set[PathToFolderWithBaseModels]],
            output_dir: Optional[PathToFolderWithBaseModels],
        ) -> list[tuple[Any, Any]]:
            return middleware.execute(next_call, step_cls, inputs, output_dir)

        return wrapped

    def __enter__(self):
        """Enter context manager for all middlewares."""
        for middleware in self.middlewares:
            middleware.__enter__()
        return self

    def __exit__(self, *exc_details):
        """Exit context manager for all middlewares (in reverse order)."""
        for middleware in reversed(self.middlewares):
            middleware.__exit__(*exc_details)
