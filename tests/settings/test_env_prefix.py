# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for env_prefix support in SettingsLeaf."""

from pydantic_settings import SettingsConfigDict

from wurzel.step.settings import Settings, SettingsLeaf, get_env_prefix_from_settings


class CustomPrefixSettings(Settings):
    """Test settings class with custom env_prefix."""

    model_config = SettingsConfigDict(
        env_prefix="my_custom_prefix_",
        # Preserve all the base SettingsBase configuration
        env_nested_delimiter="__",
        extra="forbid",
        case_sensitive=True,
        frozen=False,
        revalidate_instances="always",
    )

    TEST_FIELD: str = "default_value"
    ANOTHER_FIELD: int = 42


class NestedCustomPrefixSettings(SettingsLeaf):
    """Test nested settings class with custom env_prefix."""

    model_config = SettingsConfigDict(
        env_prefix="nested_prefix_",
        # Preserve all the base SettingsBase configuration
        env_nested_delimiter="__",
        extra="forbid",
        case_sensitive=True,
        frozen=False,
        revalidate_instances="always",
    )

    NESTED_FIELD: bool = True
    NESTED_LIST: list[str] = ["default"]


def test_windows_case_sensitivity_limitation():
    """Test that documents the Windows case sensitivity limitation.

    This test documents the known limitation that on Windows, the case_sensitive=True
    setting in pydantic-settings has no effect because Python's os module treats
    environment variables as case-insensitive on Windows.

    See: https://docs.pydantic.dev/latest/concepts/pydantic_settings/#case-sensitivity
    """
    # Use direct environment variable setting to avoid monkeypatch issues
    import os

    original_value = os.environ.get("my_custom_prefix_TEST_FIELD")

    try:
        # Set environment variable directly - match the exact field name case
        os.environ["my_custom_prefix_TEST_FIELD"] = "UPPERCASE"

        settings = CustomPrefixSettings()
        actual_value = settings.TEST_FIELD

        # On Unix-like systems: should read from exact case match
        # On Windows: case_sensitive is ignored, but should still read from env var
        assert actual_value == "UPPERCASE", (
            f"Expected UPPERCASE, got '{actual_value}'. Default value 'default_value' suggests environment variables are not being read."
        )
    finally:
        # Clean up
        if original_value is None:
            os.environ.pop("my_custom_prefix_TEST_FIELD", None)
        else:
            os.environ["my_custom_prefix_TEST_FIELD"] = original_value


def test_case_sensitive_behavior():
    """Test that environment variable handling works correctly across platforms."""
    # Use direct environment variable setting to avoid monkeypatch issues
    import os

    original_value = os.environ.get("my_custom_prefix_TEST_FIELD")

    try:
        # Set environment variable directly - match the exact field name case
        os.environ["my_custom_prefix_TEST_FIELD"] = "UPPERCASE_VALUE"

        settings = CustomPrefixSettings()
        actual_value = settings.TEST_FIELD

        # Should read from the environment variable
        assert actual_value == "UPPERCASE_VALUE", (
            f"Expected UPPERCASE_VALUE, got '{actual_value}'. This suggests the environment variables are not being read correctly."
        )
    finally:
        # Clean up
        if original_value is None:
            os.environ.pop("my_custom_prefix_TEST_FIELD", None)
        else:
            os.environ["my_custom_prefix_TEST_FIELD"] = original_value


def test_custom_env_prefix_direct_usage():
    """Test that custom env_prefix in model_config is respected when using settings directly."""
    # Use direct environment variable setting to avoid monkeypatch issues
    import os

    original_test_field = os.environ.get("my_custom_prefix_TEST_FIELD")
    original_another_field = os.environ.get("my_custom_prefix_ANOTHER_FIELD")

    try:
        # Set environment variables directly - match the exact field name case
        os.environ["my_custom_prefix_TEST_FIELD"] = "CUSTOM_VALUE"
        os.environ["my_custom_prefix_ANOTHER_FIELD"] = "100"  # pragma: allowlist secret

        settings = CustomPrefixSettings()

        # Test that the custom prefix works and reads from env vars
        assert settings.TEST_FIELD == "CUSTOM_VALUE", (
            f"Expected CUSTOM_VALUE, got '{settings.TEST_FIELD}'. This suggests the custom env_prefix is not working correctly."
        )
        assert settings.ANOTHER_FIELD == 100, (
            f"Expected 100, got {settings.ANOTHER_FIELD}. This suggests the custom env_prefix is not working correctly."
        )
    finally:
        # Clean up
        if original_test_field is None:
            os.environ.pop("my_custom_prefix_TEST_FIELD", None)
        else:
            os.environ["my_custom_prefix_TEST_FIELD"] = original_test_field

        if original_another_field is None:
            os.environ.pop("my_custom_prefix_ANOTHER_FIELD", None)  # pragma: allowlist secret
        else:
            os.environ["my_custom_prefix_ANOTHER_FIELD"] = original_another_field  # pragma: allowlist secret


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


def test_settings_config_dict_overwrite_behavior():
    """Test what SettingsConfigDict values get overwritten in different scenarios."""

    # Test 1: Settings class with no custom model_config (should inherit all defaults)
    class DefaultSettings(Settings):
        TEST_FIELD: str = "default"

    # Check that it inherits all base configuration
    assert hasattr(DefaultSettings, "model_config")
    assert DefaultSettings.model_config.get("env_nested_delimiter") == "__"
    assert DefaultSettings.model_config.get("extra") == "forbid"
    assert DefaultSettings.model_config.get("case_sensitive") is True
    assert DefaultSettings.model_config.get("frozen") is False
    assert DefaultSettings.model_config.get("revalidate_instances") == "always"
    # Should not have env_prefix (or should be empty)
    env_prefix = DefaultSettings.model_config.get("env_prefix", "")
    assert env_prefix == ""

    # Test 2: Settings class with custom env_prefix only (should preserve other defaults)
    class CustomPrefixOnlySettings(Settings):
        model_config = SettingsConfigDict(env_prefix="custom_")
        TEST_FIELD: str = "default"

    # Should have custom env_prefix but preserve other defaults
    assert CustomPrefixOnlySettings.model_config.get("env_prefix") == "custom_"
    assert CustomPrefixOnlySettings.model_config.get("env_nested_delimiter") == "__"
    assert CustomPrefixOnlySettings.model_config.get("extra") == "forbid"
    assert CustomPrefixOnlySettings.model_config.get("case_sensitive") is True
    assert CustomPrefixOnlySettings.model_config.get("frozen") is False
    assert CustomPrefixOnlySettings.model_config.get("revalidate_instances") == "always"

    # Test 3: Settings class with partial custom config (should override specified, preserve others)
    class PartialCustomSettings(Settings):
        model_config = SettingsConfigDict(
            env_prefix="partial_",
            extra="allow",  # Override this specific setting
            frozen=True,  # Override this specific setting
        )
        TEST_FIELD: str = "default"

    # Should have custom values for specified settings, preserve defaults for others
    assert PartialCustomSettings.model_config.get("env_prefix") == "partial_"
    assert PartialCustomSettings.model_config.get("env_nested_delimiter") == "__"  # Preserved
    assert PartialCustomSettings.model_config.get("extra") == "allow"  # Overridden
    assert PartialCustomSettings.model_config.get("case_sensitive") is True  # Preserved
    assert PartialCustomSettings.model_config.get("frozen") is True  # Overridden
    assert PartialCustomSettings.model_config.get("revalidate_instances") == "always"  # Preserved

    # Test 4: with_prefix method should preserve all existing config and only change env_prefix
    prefixed = PartialCustomSettings.with_prefix("with_prefix_")

    # Should have new env_prefix but preserve all other configuration
    assert prefixed.model_config.get("env_prefix") == "with_prefix_"  # Changed
    assert prefixed.model_config.get("env_nested_delimiter") == "__"  # Preserved
    assert prefixed.model_config.get("extra") == "allow"  # Preserved from original
    assert prefixed.model_config.get("case_sensitive") is True  # Preserved
    assert prefixed.model_config.get("frozen") is True  # Preserved from original
    assert prefixed.model_config.get("revalidate_instances") == "always"  # Preserved


def test_real_world_step_settings_behavior():
    """Test the behavior with real step settings like SFTPManualMarkdownStep."""
    # Import a real step settings class
    from wurzel.steps.sftp.sftp_manual_markdown import SFTPManualMarkdownSettings

    # Check that it inherits defaults properly
    assert hasattr(SFTPManualMarkdownSettings, "model_config")
    assert SFTPManualMarkdownSettings.model_config.get("env_nested_delimiter") == "__"
    assert SFTPManualMarkdownSettings.model_config.get("extra") == "forbid"
    assert SFTPManualMarkdownSettings.model_config.get("case_sensitive") is True
    assert SFTPManualMarkdownSettings.model_config.get("frozen") is False
    assert SFTPManualMarkdownSettings.model_config.get("revalidate_instances") == "always"

    # Should not have custom env_prefix (should fall back to step name)
    env_prefix = SFTPManualMarkdownSettings.model_config.get("env_prefix", "")
    assert env_prefix == ""

    # Test that our utility function works correctly
    step_env_prefix = get_env_prefix_from_settings(SFTPManualMarkdownSettings, "SFTPManualMarkdownStep")
    assert step_env_prefix == "SFTPMANUALMARKDOWNSTEP"


def test_get_env_prefix_from_settings_utility():
    """Test the centralized get_env_prefix_from_settings utility function."""
    # Test with custom env_prefix
    assert get_env_prefix_from_settings(CustomPrefixSettings, "MyStep") == "my_custom_prefix_"

    # Test with no custom env_prefix (should fall back to step name)
    class DefaultSettings(Settings):
        TEST_FIELD: str = "default"

    assert get_env_prefix_from_settings(DefaultSettings, "MyStep") == "MYSTEP"

    # Test with empty env_prefix (should fall back to step name)
    class EmptyPrefixSettings(Settings):
        model_config = SettingsConfigDict(env_prefix="")
        TEST_FIELD: str = "test"

    assert get_env_prefix_from_settings(EmptyPrefixSettings, "TESTSTEP") == "TESTSTEP"


def test_empty_env_prefix_fallback():
    """Test that settings with empty env_prefix fall back to step name prefix."""

    class EmptyPrefixSettings(Settings):
        model_config = SettingsConfigDict(env_prefix="")
        TEST_FIELD: str = "test"

    # Test the utility function directly
    env_prefix = get_env_prefix_from_settings(EmptyPrefixSettings, "TESTSTEP")
    assert env_prefix == "TESTSTEP"
