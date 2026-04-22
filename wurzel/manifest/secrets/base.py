# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Abstract secret provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar, Protocol, runtime_checkable


class SecretProvider(ABC):
    """Abstract base for secret resolution backends.

    Subclasses register themselves automatically by passing ``provider_name`` as
    a class keyword argument::

        class MyProvider(SecretProvider, provider_name="myvault"): ...

    Once registered, the provider is discoverable via ``SecretProvider.get_registry()``
    and can be auto-instantiated by overriding ``build()``.
    """

    _registry: ClassVar[dict[str, type[SecretProvider]]] = {}
    provider_name: ClassVar[str] = ""

    def __init_subclass__(cls, provider_name: str = "", **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if provider_name:
            cls.provider_name = provider_name
            SecretProvider._registry[provider_name] = cls

    @classmethod
    def get_registry(cls) -> dict[str, type[SecretProvider]]:
        """Return a copy of the registered provider name → class mapping."""
        return dict(cls._registry)

    @classmethod
    def build(cls) -> SecretProvider | None:
        """Try to auto-instantiate this provider from environment variables.

        Subclasses should override this to inspect their own env vars and return
        a ready-to-use instance, or ``None`` if the required configuration is absent.

        Returns:
            A configured provider instance, or ``None`` if unconfigured.
        """
        return None

    @abstractmethod
    def resolve(self, ref: str) -> str:
        """Resolve a provider-specific ref to a plaintext secret value.

        Args:
            ref: Provider-specific reference string
                 (e.g. ``"my-secret"`` for Vault or ``"my-secret/key"`` for K8s).

        Returns:
            The resolved plaintext secret value.

        Raises:
            Any exception raised by the underlying client.
        """


@runtime_checkable
class _SecretClient(Protocol):
    """Protocol for injectable secret clients (used in tests and production)."""

    def fetch_secret(self, ref: str) -> str:
        """Fetch and return the secret value for *ref*."""
