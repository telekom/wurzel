# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import pytest
from pydantic import SecretStr, ValidationError

from wurzel.exceptions import EnvSettingsError
from wurzel.executors import (
    BaseStepExecutor,
    PrometheusStepExecutor,
)
from wurzel.executors.base_executor import step_env_encapsulation
from wurzel.step import (
    PydanticModel,
    Settings,
    TypedStep,
)


class MySettings(Settings):
    KEY: str


class MyStep(TypedStep[MySettings, PydanticModel, PydanticModel]):
    def run(self, inpt: PydanticModel) -> PydanticModel:
        return PydanticModel()


class MyWithoutSettingsStep(TypedStep[None, PydanticModel, PydanticModel]):
    def run(self, inpt: PydanticModel) -> PydanticModel:
        return PydanticModel()


class MySecretSettings(Settings):
    """Settings class with SecretStr field for testing."""

    API_KEY: SecretStr = SecretStr("")
    PUBLIC_KEY: str = "default-public"


class MySecretStep(TypedStep[MySecretSettings, PydanticModel, PydanticModel]):
    """Step class with SecretStr settings for testing."""

    def run(self, inpt: PydanticModel) -> PydanticModel:
        return PydanticModel()


def test_missing():
    with pytest.raises(ValidationError):
        MyStep()


def test_missing_in_env():
    with pytest.raises(EnvSettingsError):
        with step_env_encapsulation(MyStep):
            MyStep()


def test_no_settings():
    with step_env_encapsulation(MyWithoutSettingsStep):
        MyWithoutSettingsStep()


@pytest.mark.parametrize("env_set", [("MYSTEP__KEY", "value"), ("MYSTEP", '{"KEY": "value"}')])
def test_env_set(env, env_set):
    env.set(*env_set)
    with pytest.raises(ValidationError):
        MyStep()
    with step_env_encapsulation(MyStep):
        MyStep()


@pytest.mark.parametrize(
    "executor,expect_warning",
    [
        (BaseStepExecutor, False),
        pytest.param(PrometheusStepExecutor, True, marks=pytest.mark.filterwarnings("ignore::DeprecationWarning")),
    ],
)
@pytest.mark.parametrize(
    "kwargs",
    [
        pytest.param({}, id="{}"),
        pytest.param({"dont_encapsulate": True}, id="True"),
        pytest.param({"dont_encapsulate": False}, id="False"),
    ],
)
def test_constructor(executor, expect_warning, kwargs):
    """Test executor constructors with various configurations.

    Note: PrometheusStepExecutor is deprecated, test is kept for backward compatibility.
    """
    if expect_warning:
        with pytest.warns(DeprecationWarning):
            with executor(**kwargs) as ex:
                assert ex
    else:
        with executor(**kwargs) as ex:
            assert ex


class TestSecretStrEncapsulation:
    """Test suite for SecretStr handling in step environment encapsulation."""

    def test_secret_str_preserved_in_env_encapsulation(self, env):
        """Test that SecretStr values are preserved correctly during environment encapsulation."""
        test_secret = "super-secret-api-key-123"  # pragma: allowlist secret
        test_public = "public-key-value"

        env.set("MYSECRETSTEP__API_KEY", test_secret)
        env.set("MYSECRETSTEP__PUBLIC_KEY", test_public)

        with step_env_encapsulation(MySecretStep):
            step = MySecretStep()
            settings = step.settings

            # Verify SecretStr field contains the actual secret value
            assert isinstance(settings.API_KEY, SecretStr)
            assert settings.API_KEY.get_secret_value() == test_secret

            # Verify regular string field works as expected
            assert settings.PUBLIC_KEY == test_public

    def test_secret_str_empty_value_in_env_encapsulation(self, env):
        """Test that empty SecretStr values are handled correctly during environment encapsulation."""
        env.set("MYSECRETSTEP__API_KEY", "")
        env.set("MYSECRETSTEP__PUBLIC_KEY", "public-value")

        with step_env_encapsulation(MySecretStep):
            step = MySecretStep()
            settings = step.settings

            # Verify empty SecretStr field
            assert isinstance(settings.API_KEY, SecretStr)
            assert settings.API_KEY.get_secret_value() == ""

            # Verify regular string field works as expected
            assert settings.PUBLIC_KEY == "public-value"

    def test_secret_str_special_characters_in_env_encapsulation(self, env):
        """Test that SecretStr with special characters are preserved during environment encapsulation."""
        test_secret = "api-key-with!@#$%^&*()_+-=special-chars"  # pragma: allowlist secret

        env.set("MYSECRETSTEP__API_KEY", test_secret)
        env.set("MYSECRETSTEP__PUBLIC_KEY", "public")

        with step_env_encapsulation(MySecretStep):
            step = MySecretStep()
            settings = step.settings

            # Verify SecretStr field with special characters
            assert isinstance(settings.API_KEY, SecretStr)
            assert settings.API_KEY.get_secret_value() == test_secret

    def test_secret_str_json_config_in_env_encapsulation(self, env):
        """Test that SecretStr can be loaded from JSON configuration in environment encapsulation."""
        test_secret = "json-secret-key"  # pragma: allowlist secret
        json_config = f'{{"API_KEY": "{test_secret}", "PUBLIC_KEY": "json-public"}}'

        env.set("MYSECRETSTEP", json_config)

        with step_env_encapsulation(MySecretStep):
            step = MySecretStep()
            settings = step.settings

            # Verify SecretStr field from JSON config
            assert isinstance(settings.API_KEY, SecretStr)
            assert settings.API_KEY.get_secret_value() == test_secret
            assert settings.PUBLIC_KEY == "json-public"

    def test_secret_str_default_value_in_env_encapsulation(self, env):
        """Test that SecretStr default values work correctly when no environment variable is set."""
        # Only set the public key, let API_KEY use its default
        env.set("MYSECRETSTEP__PUBLIC_KEY", "only-public")

        with step_env_encapsulation(MySecretStep):
            step = MySecretStep()
            settings = step.settings

            # Verify SecretStr field uses default (empty string)
            assert isinstance(settings.API_KEY, SecretStr)
            assert settings.API_KEY.get_secret_value() == ""
            assert settings.PUBLIC_KEY == "only-public"

    def test_secret_str_masking_in_logs(self, env):
        """Test that SecretStr values are properly masked when logged."""
        test_secret = "secret-should-be-masked"  # pragma: allowlist secret

        env.set("MYSECRETSTEP__API_KEY", test_secret)
        env.set("MYSECRETSTEP__PUBLIC_KEY", "visible-public")

        with step_env_encapsulation(MySecretStep):
            step = MySecretStep()
            settings = step.settings

            # Check that string representation masks the secret
            settings_str = str(settings)
            settings_repr = repr(settings)

            # Secret should not appear in string representations
            assert test_secret not in settings_str
            assert test_secret not in settings_repr

            # But public key should be visible
            assert "visible-public" in settings_str

            # SecretStr should show masked value or SecretStr indication
            assert "**********" in settings_str or "SecretStr" in settings_str
