# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Supabase Vault secret provider."""

from __future__ import annotations

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from wurzel.manifest.secrets.base import SecretProvider, _SecretClient


class _SupabaseSettings(BaseSettings):
    """Supabase connection settings read from environment variables.

    Set these to enable Supabase Vault auto-detection:
        SECRET_RESOLVER__URL              - Project URL (e.g. http://127.0.0.1:54321)
        SECRET_RESOLVER__SERVICE_ROLE_KEY - Service-role JWT token
    """

    model_config = SettingsConfigDict(env_prefix="SECRET_RESOLVER__", extra="ignore", case_sensitive=True)

    URL: str = ""
    SERVICE_ROLE_KEY: SecretStr = SecretStr("")


class SupabaseVaultClient:
    """Fetches secrets from Supabase Vault using the ``vault.decrypted_secrets`` view.

    Looks up secrets by *name*. Requires the ``supabase`` Python package.

    Args:
        url: Supabase project URL (e.g. ``http://127.0.0.1:54321``).
        service_role_key: Service-role JWT — needed to bypass RLS and read vault.
    """

    def __init__(self, url: str, service_role_key: str) -> None:
        from supabase import create_client  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

        self._client = create_client(url, service_role_key)

    def fetch_secret(self, ref: str) -> str:
        """Return the decrypted secret value for *ref* (matched by name).

        Uses the ``public.get_vault_secret`` RPC function to bypass PostgREST's
        schema restriction (the ``vault`` schema is not exposed directly).

        Raises:
            KeyError: If no secret with that name exists in the vault.
        """
        response = self._client.rpc("get_vault_secret", {"secret_name": ref}).execute()
        if not response.data:
            raise KeyError(f"Supabase Vault secret '{ref}' not found")
        return response.data


class VaultSecretProvider(SecretProvider, provider_name="vault"):
    """Resolves secrets from Supabase Vault."""

    def __init__(self, client: _SecretClient) -> None:
        self._client = client

    @classmethod
    def build(cls) -> VaultSecretProvider | None:
        """Auto-instantiate if ``SECRET_RESOLVER__URL`` and ``SECRET_RESOLVER__SERVICE_ROLE_KEY`` are set."""
        settings = _SupabaseSettings()
        if settings.URL and settings.SERVICE_ROLE_KEY.get_secret_value():
            client = SupabaseVaultClient(
                url=settings.URL,
                service_role_key=settings.SERVICE_ROLE_KEY.get_secret_value(),
            )
            return cls(client=client)
        return None

    def resolve(self, ref: str) -> str:
        return self._client.fetch_secret(ref)
