# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import pytest

from wurzel.utils import HAS_QDRANT

if not HAS_QDRANT:
    pytest.skip("Qdrant is not available", allow_module_level=True)

from pydantic import SecretStr, ValidationError

from wurzel.executors.base_executor import step_env_encapsulation
from wurzel.steps.qdrant.settings import QdrantSettings
from wurzel.steps.qdrant.step import QdrantConnectorStep


class TestQdrantSettings:
    """Test suite for QdrantSettings class."""

    def test_default_apikey_empty(self):
        """Test that APIKEY defaults to empty SecretStr when no environment variable is set."""
        settings = QdrantSettings(COLLECTION="test-collection")
        assert isinstance(settings.APIKEY, SecretStr)
        assert settings.APIKEY.get_secret_value() == ""

    def test_apikey_from_env_string(self, env):
        """Test that APIKEY is correctly loaded from environment variable as string."""
        test_api_key = "test-secret-key-12345"  # pragma: allowlist secret
        env.set("QDRANTCONNECTORSTEP__COLLECTION", "test-collection")
        env.set("QDRANTCONNECTORSTEP__URI", ":memory:")  # Use in-memory to avoid connection
        env.set("QDRANTCONNECTORSTEP__APIKEY", test_api_key)

        with step_env_encapsulation(QdrantConnectorStep):
            step = QdrantConnectorStep()
            settings = step.settings

            assert isinstance(settings.APIKEY, SecretStr)
            assert settings.APIKEY.get_secret_value() == test_api_key

    def test_apikey_from_env_empty_string(self, env):
        """Test that APIKEY handles empty string from environment variable."""
        env.set("QDRANTCONNECTORSTEP__COLLECTION", "test-collection")
        env.set("QDRANTCONNECTORSTEP__URI", ":memory:")  # Use in-memory to avoid connection
        env.set("QDRANTCONNECTORSTEP__APIKEY", "")

        with step_env_encapsulation(QdrantConnectorStep):
            step = QdrantConnectorStep()
            settings = step.settings

            assert isinstance(settings.APIKEY, SecretStr)
            assert settings.APIKEY.get_secret_value() == ""

    def test_apikey_from_env_special_characters(self, env):
        """Test that APIKEY handles special characters in the secret."""
        test_api_key = "api-key-with-special-chars!@#$%^&*()_+-="  # pragma: allowlist secret
        env.set("QDRANTCONNECTORSTEP__COLLECTION", "test-collection")
        env.set("QDRANTCONNECTORSTEP__URI", ":memory:")  # Use in-memory to avoid connection
        env.set("QDRANTCONNECTORSTEP__APIKEY", test_api_key)

        with step_env_encapsulation(QdrantConnectorStep):
            step = QdrantConnectorStep()
            settings = step.settings

            assert isinstance(settings.APIKEY, SecretStr)
            assert settings.APIKEY.get_secret_value() == test_api_key

    def test_apikey_json_config(self, env):
        """Test that APIKEY can be loaded from JSON configuration."""
        test_api_key = "json-api-key"  # pragma: allowlist secret
        json_config = f'{{"COLLECTION": "test-collection", "URI": ":memory:", "APIKEY": "{test_api_key}"}}'
        env.set("QDRANTCONNECTORSTEP", json_config)

        with step_env_encapsulation(QdrantConnectorStep):
            step = QdrantConnectorStep()
            settings = step.settings

            assert isinstance(settings.APIKEY, SecretStr)
            assert settings.APIKEY.get_secret_value() == test_api_key

    def test_secretstr_representation(self):
        """Test that SecretStr APIKEY is properly masked in string representation."""
        settings = QdrantSettings(COLLECTION="test-collection", APIKEY=SecretStr("secret-key"))
        settings_str = str(settings)
        settings_repr = repr(settings)

        # SecretStr should mask the value
        assert "secret-key" not in settings_str
        assert "secret-key" not in settings_repr
        assert "**********" in settings_str or "SecretStr" in settings_str

    def test_required_collection_field(self):
        """Test that COLLECTION field is required and validation fails without it."""
        with pytest.raises(ValidationError) as exc_info:
            QdrantSettings()

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("COLLECTION",) and error["type"] == "missing" for error in errors)

    def test_all_settings_with_env(self, env):
        """Test loading all settings from environment variables including APIKEY."""
        env.set("QDRANTCONNECTORSTEP__COLLECTION", "test-collection")
        env.set("QDRANTCONNECTORSTEP__URI", ":memory:")  # Use in-memory to avoid connection
        env.set("QDRANTCONNECTORSTEP__APIKEY", "full-test-key")
        env.set("QDRANTCONNECTORSTEP__BATCH_SIZE", "512")
        env.set("QDRANTCONNECTORSTEP__REPLICATION_FACTOR", "2")

        with step_env_encapsulation(QdrantConnectorStep):
            step = QdrantConnectorStep()
            settings = step.settings

            assert settings.COLLECTION == "test-collection"
            assert settings.URI == ":memory:"
            assert isinstance(settings.APIKEY, SecretStr)
            assert settings.APIKEY.get_secret_value() == "full-test-key"
            assert settings.BATCH_SIZE == 512
            assert settings.REPLICATION_FACTOR == 2

    def test_direct_settings_instantiation_with_secretstr(self):
        """Test creating QdrantSettings directly with SecretStr for APIKEY."""
        test_api_key = "direct-secret-key"  # pragma: allowlist secret
        settings = QdrantSettings(COLLECTION="test-collection", APIKEY=SecretStr(test_api_key))

        assert isinstance(settings.APIKEY, SecretStr)
        assert settings.APIKEY.get_secret_value() == test_api_key

    def test_direct_settings_instantiation_with_string_for_apikey(self):
        """Test creating QdrantSettings directly with string for APIKEY (should convert to SecretStr)."""
        test_api_key = "string-to-secret"  # pragma: allowlist secret
        settings = QdrantSettings(COLLECTION="test-collection", APIKEY=test_api_key)

        assert isinstance(settings.APIKEY, SecretStr)
        assert settings.APIKEY.get_secret_value() == test_api_key
