# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import pytest

from wurzel.utils.meta_steps import find_typed_steps_in_package


def test_find_ts():
    pkgs = find_typed_steps_in_package(__package__)
    expected = {"StepA", "StepB", "StepC"}
    assert expected.issubset(pkgs.keys())
    # Each expected class must be defined inside tests.utils, not leaked from an import
    for name in expected:
        assert pkgs[name].__module__.startswith("tests.utils"), f"{name} should be from tests.utils"


def test_utils_lazy_find_typed_steps_in_package():
    """Test that find_typed_steps_in_package is accessible via wurzel.utils lazy import."""
    import wurzel.utils  # pylint: disable=import-outside-toplevel

    fn = wurzel.utils.find_typed_steps_in_package  # triggers __getattr__
    assert callable(fn)


def test_utils_lazy_create_model():
    """Test that create_model is accessible via wurzel.utils lazy import."""
    import wurzel.utils  # pylint: disable=import-outside-toplevel

    fn = wurzel.utils.create_model
    assert callable(fn)


def test_utils_lazy_wz():
    """Test that WZ is accessible via wurzel.utils lazy import."""
    import wurzel.utils  # pylint: disable=import-outside-toplevel

    cls = wurzel.utils.WZ
    assert cls is not None


def test_utils_lazy_semantic_splitter():
    """Test that semantic_splitter module is accessible via wurzel.utils lazy import."""
    import wurzel.utils  # pylint: disable=import-outside-toplevel

    mod = wurzel.utils.semantic_splitter
    assert mod is not None


def test_utils_lazy_to_markdown():
    """Test that to_markdown module is accessible via wurzel.utils lazy import."""
    import wurzel.utils  # pylint: disable=import-outside-toplevel

    mod = wurzel.utils.to_markdown
    assert mod is not None


def test_utils_lazy_markdown_converter_settings():
    """Test that MarkdownConverterSettings is accessible via wurzel.utils lazy import."""
    import wurzel.utils  # pylint: disable=import-outside-toplevel

    cls = wurzel.utils.MarkdownConverterSettings
    assert cls is not None


def test_utils_lazy_attribute_error():
    """Test that accessing non-existent attribute raises AttributeError."""
    import wurzel.utils  # pylint: disable=import-outside-toplevel

    with pytest.raises(AttributeError, match="has no attribute"):
        _ = wurzel.utils.nonexistent_attribute
