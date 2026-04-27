# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Middleware that resolves secret placeholders in env vars before step execution.

Secret placeholders use the format ``${secret:<provider>:<ref>}``. The middleware
scans all current env vars, resolves placeholders via the matching provider,
temporarily overrides those vars for the duration of step execution, then restores them.

```python
from wurzel.manifest.secrets.base import SecretProvider
from wurzel.executors.middlewares.secret_resolver.secret_resolver import (
    SecretResolverMiddleware,
)

class FakeProvider(SecretProvider, provider_name="fake"):
    def resolve(self, ref: str) -> str:
        return f"resolved-{ref}"

middleware = SecretResolverMiddleware(providers=[FakeProvider()])
print(middleware._providers[0].provider_name)
#> fake
```
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from wurzel.core.typed_step import TypedStep
from wurzel.executors.middlewares.base import BaseMiddleware, ExecuteStepCallable
from wurzel.manifest.secrets.base import SecretProvider
from wurzel.manifest.secrets.placeholder import find_placeholder_vars
from wurzel.path import PathToFolderWithBaseModels


def _build_default_providers() -> list[SecretProvider]:
    """Auto-detect and instantiate all registered providers that have their config present.

    Iterates the ``SecretProvider`` registry and calls ``build()`` on each class.
    Providers that return ``None`` from ``build()`` are silently skipped.
    """
    return [p for cls in SecretProvider.get_registry().values() if (p := cls.build()) is not None]


class SecretResolverMiddleware(BaseMiddleware):
    """Resolve ``${secret:<provider>:<ref>}`` placeholders in env vars before step execution.

    Scans all current environment variables for placeholders, dispatches to the
    matching SecretProvider, temporarily overrides the env vars with resolved values
    for the duration of the step execution, then restores the originals.

    If no explicit providers are passed, auto-detects configured providers from
    environment variables by calling ``build()`` on every registered ``SecretProvider``
    subclass. Add a new vault by subclassing ``SecretProvider`` with
    ``provider_name="myvault"`` and overriding ``build()``.
    """

    def __init__(self, providers: list[SecretProvider] | None = None) -> None:
        super().__init__()
        self._providers: list[SecretProvider] = providers if providers is not None else _build_default_providers()

    def _find_provider(self, provider_name: str) -> SecretProvider:
        """Return the provider matching provider_name, or raise ValueError."""
        for provider in self._providers:
            if provider.provider_name == provider_name:
                return provider
        available = [p.provider_name for p in self._providers]
        raise ValueError(f"No provider registered for '{provider_name}'. Available: {available}")

    def _resolve_secrets(self, refs: dict[str, Any]) -> dict[str, str]:
        """Resolve all SecretRefs to plaintext values using the matching provider."""
        return {env_var: self._find_provider(ref.provider).resolve(ref.ref) for env_var, ref in refs.items()}

    @staticmethod
    @contextmanager
    def _env_override(overrides: dict[str, str]) -> Iterator[None]:
        """Temporarily replace env vars with resolved values, restoring originals on exit."""
        original = {k: os.environ.get(k) for k in overrides}
        os.environ.update(overrides)
        try:
            yield
        finally:
            for key, old_value in original.items():
                if old_value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = old_value

    def __call__(
        self,
        call_next: ExecuteStepCallable,
        step_cls: type[TypedStep],
        inputs: set[PathToFolderWithBaseModels] | None,
        output_dir: PathToFolderWithBaseModels | None,
    ) -> list[tuple[Any, Any]]:
        placeholder_vars = find_placeholder_vars(dict(os.environ))
        resolved = self._resolve_secrets(placeholder_vars)
        with self._env_override(resolved):
            return call_next(step_cls, inputs, output_dir)
