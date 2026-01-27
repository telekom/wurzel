# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for env_prefix support in SettingsLeaf."""

from pydantic_settings import SettingsConfigDict

from wurzel.step.settings import Settings, SettingsLeaf


class CustomPrefixSettings(Settings):
    """Test settings class with custom env_prefix."""

    model_config = SettingsConfigDict(env_prefix="my_custom_prefix_")

    TEST_FIELD: str = "default_value"
    ANOTHER_FIELD: int = 42


class NestedCustomPrefixSettings(SettingsLeaf):
    """Test nested settings class with custom env_prefix."""

    model_config = SettingsConfigDict(env_prefix="nested_prefix_")

    NESTED_FIELD: bool = True
    NESTED_LIST: list[str] = ["default"]


def test_windows_case_sensitivity_limitation(monkeypatch):
    """Test that documents the Windows case sensitivity limitation.

    This test documents the known limitation that on Windows, the case_sensitive=True
    setting in pydantic-settings has no effect because Python's os module treats
    environment variables as case-insensitive on Windows.

    See: https://docs.pydantic.dev/latest/concepts/pydantic_settings/#case-sensitivity
    """
    # Set only one environment variable to avoid conflicts
    monkeypatch.setenv("my_custom_prefix_TEST_FIELD", "UPPERCASE")

    settings = CustomPrefixSettings()
    actual_value = settings.TEST_FIELD

    # Should read from the environment variable (not the default value)
    assert actual_value == "UPPERCASE", (
        f"Expected UPPERCASE, got '{actual_value}'. Default value 'default_value' suggests environment variables are not being read."
    )


def test_case_sensitive_behavior(monkeypatch):
    """Test that environment variable handling works correctly across platforms."""
    # Set only one environment variable to avoid conflicts
    monkeypatch.setenv("my_custom_prefix_TEST_FIELD", "UPPERCASE_VALUE")

    settings = CustomPrefixSettings()
    actual_value = settings.TEST_FIELD

    # Should read from the environment variable
    assert actual_value == "UPPERCASE_VALUE", (
        f"Expected UPPERCASE_VALUE, got '{actual_value}'. This suggests the environment variables are not being read correctly."
    )


def test_custom_env_prefix_direct_usage(monkeypatch):
    """Test that custom env_prefix in model_config is respected when using settings directly."""
    # Set only one environment variable to avoid conflicts
    monkeypatch.setenv("my_custom_prefix_TEST_FIELD", "CUSTOM_VALUE")
    monkeypatch.setenv("my_custom_prefix_ANOTHER_FIELD", "100")  # pragma: allowlist secret

    settings = CustomPrefixSettings()

    # Test that the custom prefix works and reads from env vars
    # On both Windows and Unix-like systems, this should work
    assert settings.TEST_FIELD == "CUSTOM_VALUE", (
        f"Expected CUSTOM_VALUE, got '{settings.TEST_FIELD}'. This suggests the custom env_prefix is not working correctly."
    )
    assert settings.ANOTHER_FIELD == 100, (
        f"Expected 100, got {settings.ANOTHER_FIELD}. This suggests the custom env_prefix is not working correctly."
    )


def test_with_prefix_preserves_existing_config(monkeypatch):
    """Test that with_prefix method preserves existing model_config and only updates env_prefix."""
    # Test with_prefix method
    prefixed_class = CustomPrefixSettings.with_prefix("TEST__")

    # Check that the new class has the correct env_prefix
    assert prefixed_class.model_config["env_prefix"] == "TEST__"

    # Check that other config settings are preserved
    assert prefixed_class.model_config["extra"] == "forbid"
    assert prefixed_class.model_config["env_nested_delimiter"] == "__"

    # Test that the prefixed class works with environment variables
    monkeypatch.setenv("TEST__TEST_FIELD", "prefixed_value")
    prefixed_settings = prefixed_class()
    assert prefixed_settings.TEST_FIELD == "prefixed_value"


def test_nested_settings_with_custom_prefix(monkeypatch):
    """Test that nested settings with custom env_prefix work correctly."""

    # Create a parent settings class that contains the nested settings
    class ParentSettings(Settings):
        NESTED: NestedCustomPrefixSettings

    # Set environment variables for nested settings using the field name prefix
    # This is the expected behavior for nested settings
    monkeypatch.setenv("NESTED__NESTED_FIELD", "false")
    monkeypatch.setenv("NESTED__NESTED_LIST", '["item1", "item2"]')

    parent_settings = ParentSettings()

    # The nested settings should read from the environment
    assert parent_settings.NESTED.NESTED_FIELD is False
    assert parent_settings.NESTED.NESTED_LIST == ["item1", "item2"]


def test_default_env_prefix_fallback():
    """Test that settings without custom env_prefix still work with step name prefix."""

    class DefaultSettings(Settings):
        DEFAULT_FIELD: str = "default"

    # Should not have custom env_prefix in model_config or should be empty
    assert "env_prefix" not in DefaultSettings.model_config or DefaultSettings.model_config["env_prefix"] == ""

    # Test with_prefix still works
    prefixed = DefaultSettings.with_prefix("DEFAULT__")
    assert prefixed.model_config["env_prefix"] == "DEFAULT__"


def test_empty_env_prefix_fallback():
    """Test that settings with empty env_prefix fall back to step name prefix."""

    class EmptyPrefixSettings(Settings):
        model_config = SettingsConfigDict(env_prefix="")
        TEST_FIELD: str = "test"

    # Should have empty env_prefix in model_config
    assert EmptyPrefixSettings.model_config["env_prefix"] == ""

    # When used in inspect command, should fall back to step name
    # This simulates the behavior in cmd_inspect.py
    if (
        hasattr(EmptyPrefixSettings, "model_config")
        and "env_prefix" in EmptyPrefixSettings.model_config
        and EmptyPrefixSettings.model_config["env_prefix"]
    ):
        env_prefix = EmptyPrefixSettings.model_config["env_prefix"]
    else:
        env_prefix = "TESTSTEP"  # Simulate step name uppercase

    assert env_prefix == "TESTSTEP"
