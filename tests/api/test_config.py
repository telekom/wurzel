# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for wurzel.api.config — WurzelConfig and legacy settings classes."""

import pytest

REQUIRED_ENV = {
    "API_KEY": "test-api-key",  # pragma: allowlist secret
    "AUTH_JWKS_URL": "http://localhost/jwks",
    "SUPABASE_URL": "http://localhost:54321",
    "SUPABASE_SERVICE_KEY": "test-service-key",  # pragma: allowlist secret
}


@pytest.fixture
def api_env(env):
    for k, v in REQUIRED_ENV.items():
        env.set(k, v)
    return env


class TestWurzelConfig:
    def test_instantiate_with_required_vars(self, api_env):
        from wurzel.api.config import WurzelConfig

        config = WurzelConfig()
        assert config.API_KEY.get_secret_value() == "test-api-key"
        assert config.AUTH_JWKS_URL == "http://localhost/jwks"
        assert config.SUPABASE_URL == "http://localhost:54321"

    def test_defaults_applied(self, api_env):
        from wurzel.api.config import WurzelConfig

        config = WurzelConfig()
        assert config.API_HOST == "0.0.0.0"
        assert config.API_PORT == 8000
        assert config.API_WORKERS == 1
        assert config.API_DEBUG is False
        assert config.AUTH_JWT_AUDIENCE == "authenticated"
        assert config.AUTH_ALGORITHM == "HS256"
        assert config.AUTH_ENABLED is True
        assert config.SUPABASE_KNOWLEDGE_TABLE == "knowledge"
        assert config.SUPABASE_INGEST_JOBS_TABLE == "ingest_jobs"
        assert config.SUPABASE_MANIFESTS_TABLE == "manifests"

    def test_override_optional_fields(self, api_env):
        from wurzel.api.config import WurzelConfig

        api_env.set("API_PORT", "9000")
        api_env.set("API_DEBUG", "true")
        api_env.set("AUTH_ENABLED", "false")
        config = WurzelConfig()
        assert config.API_PORT == 9000
        assert config.API_DEBUG is True
        assert config.AUTH_ENABLED is False

    def test_get_api_settings(self, api_env):
        from wurzel.api.config import APISettings, WurzelConfig

        config = WurzelConfig()
        api_settings = config.get_api_settings()
        assert isinstance(api_settings, APISettings)
        assert api_settings.api_key.get_secret_value() == "test-api-key"
        assert api_settings.port == 8000

    def test_get_auth_settings(self, api_env):
        from wurzel.api.config import AuthSettings, WurzelConfig

        config = WurzelConfig()
        auth = config.get_auth_settings()
        assert isinstance(auth, AuthSettings)
        assert auth.jwks_url == "http://localhost/jwks"
        assert auth.algorithm == "HS256"

    def test_get_supabase_settings(self, api_env):
        from wurzel.api.config import SupabaseSettings, WurzelConfig

        config = WurzelConfig()
        supa = config.get_supabase_settings()
        assert isinstance(supa, SupabaseSettings)
        assert supa.url == "http://localhost:54321"
        assert supa.service_key.get_secret_value() == "test-service-key"

    def test_missing_required_raises(self, env):
        from wurzel.api.config import WurzelConfig

        # Missing all required fields
        with pytest.raises(Exception):
            WurzelConfig()


class TestAPISettings:
    def test_instantiate_directly(self, env):
        from wurzel.api.config import APISettings

        env.set("API__api_key", "my-key")
        s = APISettings(api_key="my-key")
        assert s.api_key.get_secret_value() == "my-key"
        assert s.host == "0.0.0.0"
        assert s.port == 8000

    def test_cors_origins_default(self, env):
        from wurzel.api.config import APISettings

        s = APISettings(api_key="key")
        assert s.cors_origins == ["*"]


class TestAuthSettings:
    def test_instantiate_directly(self):
        from wurzel.api.config import AuthSettings

        s = AuthSettings(jwks_url="http://example.com/jwks")
        assert s.jwks_url == "http://example.com/jwks"
        assert s.enabled is True
        assert s.algorithm == "HS256"


class TestSupabaseSettings:
    def test_instantiate_directly(self):
        from wurzel.api.config import SupabaseSettings

        s = SupabaseSettings(url="http://example.com", service_key="svc-key")
        assert s.url == "http://example.com"
        assert s.service_key.get_secret_value() == "svc-key"
        assert s.knowledge_table == "knowledge"
