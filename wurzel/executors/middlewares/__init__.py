# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Middleware system for step executors.

This module provides a flexible middleware system for adding cross-cutting
concerns to step execution. Middlewares can be chained together to add
features like metrics, logging, tracing, etc.

Example:
    >>> from wurzel.step_executor.middlewares import MiddlewareRegistry
    >>> from wurzel.step_executor.middlewares.prometheus import PrometheusMiddleware
    >>>
    >>> # Register and load middlewares
    >>> registry = MiddlewareRegistry()
    >>> middlewares = registry.load_middlewares(["prometheus"])
"""

import logging
import os
from typing import Optional

from .base import BaseMiddleware, MiddlewareChain  # noqa: F401

log = logging.getLogger(__name__)


class MiddlewareRegistry:
    """Registry for discovering and loading middlewares.

    The registry manages available middlewares and can load them based on
    configuration (environment variables or explicit names).
    """

    def __init__(self):
        """Initialize the middleware registry."""
        self._middlewares: dict[str, type[BaseMiddleware]] = {}
        self._register_builtin_middlewares()

    def _register_builtin_middlewares(self):
        """Register built-in middlewares."""
        try:
            # pylint: disable=import-outside-toplevel
            from .prometheus import PrometheusMiddleware

            self.register("prometheus", PrometheusMiddleware)
            log.debug("Registered prometheus middleware")
        except ImportError as e:
            log.debug(f"Could not load prometheus middleware: {e}")

    def register(self, name: str, middleware_class: type[BaseMiddleware]):
        """Register a middleware with a name.

        Args:
            name: The name to register the middleware under
            middleware_class: The middleware class to register
        """
        self._middlewares[name.lower()] = middleware_class
        log.debug(f"Registered middleware: {name}")

    def get(self, name: str) -> Optional[type[BaseMiddleware]]:
        """Get a middleware class by name.

        Args:
            name: The name of the middleware

        Returns:
            The middleware class or None if not found
        """
        return self._middlewares.get(name.lower())

    def list_available(self) -> list[str]:
        """List all available middleware names.

        Returns:
            List of registered middleware names
        """
        return list(self._middlewares.keys())

    def load_middlewares(self, names: Optional[list[str]] = None, from_env: bool = True) -> list[BaseMiddleware]:
        """Load middlewares by name or from environment configuration.

        Args:
            names: List of middleware names to load. If None, loads from environment
            from_env: Whether to also check MIDDLEWARES environment variable

        Returns:
            List of instantiated middleware objects
        """
        middleware_names = names or []

        # Load from environment if requested
        if from_env:
            env_middlewares = os.environ.get("MIDDLEWARES", "").strip()
            if env_middlewares:
                env_names = [name.strip().lower() for name in env_middlewares.split(",")]
                middleware_names.extend(env_names)

        # Remove duplicates while preserving order
        middleware_names = list(dict.fromkeys(middleware_names))

        # Instantiate middlewares
        loaded_middlewares = []
        for name in middleware_names:
            name = name.lower()
            middleware_class = self.get(name)
            if middleware_class:
                try:
                    middleware = middleware_class()
                    loaded_middlewares.append(middleware)
                    log.info(f"Loaded middleware: {name}")
                except Exception as e:  # pylint: disable=broad-exception-caught
                    log.error(f"Failed to instantiate middleware '{name}': {e}", exc_info=True)
            else:
                log.warning(f"Middleware '{name}' not found in registry. Available: {self.list_available()}")

        return loaded_middlewares

    def create_chain(self, names: Optional[list[str]] = None, from_env: bool = True) -> MiddlewareChain:
        """Create a middleware chain from names or environment configuration.

        Args:
            names: List of middleware names to load. If None, loads from environment
            from_env: Whether to also check MIDDLEWARES environment variable

        Returns:
            A configured MiddlewareChain
        """
        middlewares = self.load_middlewares(names, from_env)
        return MiddlewareChain(middlewares)


# Global registry instance
_default_registry = MiddlewareRegistry()


def get_registry() -> MiddlewareRegistry:
    """Get the default global middleware registry.

    Returns:
        The global MiddlewareRegistry instance
    """
    return _default_registry


def load_middlewares(names: Optional[list[str]] = None, from_env: bool = True) -> list[BaseMiddleware]:
    """Load middlewares using the global registry.

    Convenience function that uses the default registry.

    Args:
        names: List of middleware names to load. If None, loads from environment
        from_env: Whether to also check MIDDLEWARES environment variable

    Returns:
        List of instantiated middleware objects
    """
    return _default_registry.load_middlewares(names, from_env)


def create_middleware_chain(names: Optional[list[str]] = None, from_env: bool = True) -> MiddlewareChain:
    """Create a middleware chain using the global registry.

    Convenience function that uses the default registry.

    Args:
        names: List of middleware names to load. If None, loads from environment
        from_env: Whether to also check MIDDLEWARES environment variable

    Returns:
        A configured MiddlewareChain
    """
    return _default_registry.create_chain(names, from_env)


__all__ = [
    "BaseMiddleware",
    "MiddlewareChain",
    "MiddlewareRegistry",
    "get_registry",
    "load_middlewares",
    "create_middleware_chain",
]
