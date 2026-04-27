# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import os

import pytest

from wurzel.executors.middlewares.secret_resolver import SecretResolverMiddleware
from wurzel.manifest.secrets.base import SecretProvider


class _MockProvider(SecretProvider):
    provider_name = "mock"

    def __init__(self, secrets: dict[str, str]):
        self._secrets = secrets

    def resolve(self, ref: str) -> str:
        return self._secrets[ref]


class TestSecretResolverMiddleware:
    def test_no_placeholders_calls_next_unchanged(self, env, mocker):
        env.set("PLAIN_VAR", "plain-value")
        call_next = mocker.MagicMock(return_value=[])
        middleware = SecretResolverMiddleware(providers=[])
        middleware(call_next, mocker.MagicMock(), None, None)
        call_next.assert_called_once()

    def test_placeholder_resolved_before_call_next(self, env, mocker):
        env.set("MY_SECRET", "${secret:mock:my-key}")
        provider = _MockProvider({"my-key": "resolved-value"})
        resolved_env = {}

        def capture_call_next(step_cls, inputs, output_dir):
            resolved_env["MY_SECRET"] = os.environ.get("MY_SECRET")
            return []

        middleware = SecretResolverMiddleware(providers=[provider])
        middleware(capture_call_next, mocker.MagicMock(), None, None)
        assert resolved_env["MY_SECRET"] == "resolved-value"  # pragma: allowlist secret

    def test_env_var_restored_after_call(self, env, mocker):
        env.set("MY_SECRET", "${secret:mock:my-key}")
        provider = _MockProvider({"my-key": "resolved-value"})
        call_next = mocker.MagicMock(return_value=[])
        middleware = SecretResolverMiddleware(providers=[provider])
        middleware(call_next, mocker.MagicMock(), None, None)
        assert os.environ["MY_SECRET"] == "${secret:mock:my-key}"

    def test_unknown_provider_raises(self, env, mocker):
        env.set("SECRET", "${secret:unknown:ref}")
        call_next = mocker.MagicMock(return_value=[])
        middleware = SecretResolverMiddleware(providers=[])
        with pytest.raises(ValueError, match="unknown"):
            middleware(call_next, mocker.MagicMock(), None, None)

    def test_multiple_placeholders_all_resolved(self, env, mocker):
        env.set("S1", "${secret:mock:key1}")
        env.set("S2", "${secret:mock:key2}")
        provider = _MockProvider({"key1": "val1", "key2": "val2"})
        captured = {}

        def capture_call_next(step_cls, inputs, output_dir):
            captured["S1"] = os.environ.get("S1")
            captured["S2"] = os.environ.get("S2")
            return []

        middleware = SecretResolverMiddleware(providers=[provider])
        middleware(capture_call_next, mocker.MagicMock(), None, None)
        assert captured["S1"] == "val1"
        assert captured["S2"] == "val2"

    def test_env_restored_even_when_call_next_raises(self, env, mocker):
        env.set("MY_SECRET", "${secret:mock:key}")
        provider = _MockProvider({"key": "val"})

        def failing_next(step_cls, inputs, output_dir):
            raise RuntimeError("step failed")

        middleware = SecretResolverMiddleware(providers=[provider])
        with pytest.raises(RuntimeError):
            middleware(failing_next, mocker.MagicMock(), None, None)
        assert os.environ["MY_SECRET"] == "${secret:mock:key}"

    # --- gaps ---

    def test_default_providers_none_does_not_raise(self, env, mocker):
        """SecretResolverMiddleware() with no args must not crash on a plain env."""
        env.set("PLAIN", "value")
        call_next = mocker.MagicMock(return_value=[])
        middleware = SecretResolverMiddleware()
        middleware(call_next, mocker.MagicMock(), None, None)
        call_next.assert_called_once()

    def test_multiple_providers_dispatched_correctly(self, env, mocker):
        """Each placeholder is resolved by its own matching provider."""
        env.set("SEC_A", "${secret:provA:ref-a}")
        env.set("SEC_B", "${secret:provB:ref-b}")

        class _ProvA(_MockProvider):
            provider_name = "provA"

        class _ProvB(_MockProvider):
            provider_name = "provB"

        captured = {}

        def capture_call_next(step_cls, inputs, output_dir):
            captured["SEC_A"] = os.environ.get("SEC_A")
            captured["SEC_B"] = os.environ.get("SEC_B")
            return []

        middleware = SecretResolverMiddleware(providers=[_ProvA({"ref-a": "secret-a"}), _ProvB({"ref-b": "secret-b"})])
        middleware(capture_call_next, mocker.MagicMock(), None, None)
        assert captured["SEC_A"] == "secret-a"
        assert captured["SEC_B"] == "secret-b"

    def test_call_next_return_value_is_forwarded(self, mocker):
        """The return value produced by call_next must be returned from __call__."""
        expected = [("a", "b"), ("c", "d")]
        call_next = mocker.MagicMock(return_value=expected)
        middleware = SecretResolverMiddleware(providers=[])
        result = middleware(call_next, mocker.MagicMock(), None, None)
        assert result is expected

    def test_provider_resolve_raises_propagates_and_env_unchanged(self, env, mocker):
        """If a provider raises during resolve, the exception propagates and env is unchanged."""
        env.set("BAD_SECRET", "${secret:mock:missing-key}")
        provider = _MockProvider({})  # empty dict → KeyError on any resolve

        call_next = mocker.MagicMock()
        middleware = SecretResolverMiddleware(providers=[provider])
        with pytest.raises(KeyError):
            middleware(call_next, mocker.MagicMock(), None, None)
        # env_override was never entered, so original value must still be present
        assert os.environ["BAD_SECRET"] == "${secret:mock:missing-key}"
        call_next.assert_not_called()

    def test_unknown_provider_error_lists_available_providers(self, env, mocker):
        """ValueError for unknown provider must name the available providers."""
        env.set("SEC", "${secret:ghost:ref}")
        middleware = SecretResolverMiddleware(
            providers=[_MockProvider({})]  # only "mock" is available
        )
        with pytest.raises(ValueError, match="Available:.*mock"):
            middleware(mocker.MagicMock(), mocker.MagicMock(), None, None)

    def test_env_override_removes_key_that_did_not_exist_before(self):
        """_env_override must pop a key that was not present before the override."""
        key = "_WURZEL_TEST_EPHEMERAL_KEY_"
        os.environ.pop(key, None)  # ensure absent
        with SecretResolverMiddleware._env_override({key: "temp"}):
            assert os.environ[key] == "temp"
        assert key not in os.environ


class TestBuildDefaultProviders:
    def test_providers_registered_after_package_import(self):
        """Importing SecretResolverMiddleware must trigger provider registration.
        The providers package must be imported in the secret_resolver __init__.py.
        """
        from wurzel.executors.middlewares.secret_resolver import SecretResolverMiddleware  # noqa: F401, PLC0415
        from wurzel.manifest.secrets.base import SecretProvider  # noqa: PLC0415

        registry = SecretProvider.get_registry()
        assert "k8s" in registry, "K8sSecretProvider must be registered via package import"
        assert "vault" in registry, "VaultSecretProvider must be registered via package import"

    def test_no_env_vars_returns_empty_providers(self, monkeypatch):
        monkeypatch.delenv("SECRET_RESOLVER__URL", raising=False)
        monkeypatch.delenv("SECRET_RESOLVER__SERVICE_ROLE_KEY", raising=False)
        from wurzel.executors.middlewares.secret_resolver.secret_resolver import _build_default_providers

        providers = _build_default_providers()
        assert providers == []

    def test_url_without_key_returns_empty(self, monkeypatch):
        monkeypatch.setenv("SECRET_RESOLVER__URL", "http://localhost:54321")
        monkeypatch.delenv("SECRET_RESOLVER__SERVICE_ROLE_KEY", raising=False)
        from wurzel.executors.middlewares.secret_resolver.secret_resolver import _build_default_providers

        providers = _build_default_providers()
        assert providers == []

    def test_both_env_vars_set_returns_vault_provider(self, monkeypatch):
        pytest.importorskip("supabase")
        monkeypatch.setenv("SECRET_RESOLVER__URL", "http://localhost:54321")
        monkeypatch.setenv("SECRET_RESOLVER__SERVICE_ROLE_KEY", "fake-jwt")
        mock_client = object()

        def fake_create_client(url, key):
            return mock_client

        import unittest.mock as mock

        with mock.patch("supabase.create_client", fake_create_client):
            import importlib

            from wurzel.executors.middlewares.secret_resolver import secret_resolver as sr_mod

            importlib.reload(sr_mod)
            from wurzel.executors.middlewares.secret_resolver.providers.vault import VaultSecretProvider
            from wurzel.executors.middlewares.secret_resolver.secret_resolver import _build_default_providers

            providers = _build_default_providers()
        assert len(providers) == 1
        assert isinstance(providers[0], VaultSecretProvider)


class TestVaultSecretProvider:
    def test_fetch_secret_returns_data(self, mocker):
        from wurzel.executors.middlewares.secret_resolver.providers.vault import SupabaseVaultClient, VaultSecretProvider

        mock_supabase = mocker.MagicMock()
        mock_supabase.rpc.return_value.execute.return_value.data = "my-secret-value"

        client = SupabaseVaultClient.__new__(SupabaseVaultClient)
        client._client = mock_supabase

        provider = VaultSecretProvider(client=client)
        assert provider.resolve("my-key") == "my-secret-value"
        mock_supabase.rpc.assert_called_once_with("get_vault_secret", {"secret_name": "my-key"})  # pragma: allowlist secret

    def test_fetch_secret_raises_key_error_when_not_found(self, mocker):
        from wurzel.executors.middlewares.secret_resolver.providers.vault import SupabaseVaultClient, VaultSecretProvider

        mock_supabase = mocker.MagicMock()
        mock_supabase.rpc.return_value.execute.return_value.data = None

        client = SupabaseVaultClient.__new__(SupabaseVaultClient)
        client._client = mock_supabase

        provider = VaultSecretProvider(client=client)
        with pytest.raises(KeyError, match="missing-key"):
            provider.resolve("missing-key")

    def test_supabase_vault_client_init(self, mocker):
        pytest.importorskip("supabase")
        mocker.patch("supabase.create_client", return_value=mocker.MagicMock())
        from wurzel.executors.middlewares.secret_resolver.providers.vault import SupabaseVaultClient

        client = SupabaseVaultClient(url="http://localhost:54321", service_role_key="fake-jwt")
        assert client._client is not None
