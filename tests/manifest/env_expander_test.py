# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import pytest

from wurzel.manifest.env_expander import EnvExpander


class TestExpandStepSettings:
    def test_single_key_prefixed(self):
        result = EnvExpander.expand_step_settings("ManualMarkdownStep", {"FOLDER_PATH": "./data"})
        assert result == {"MANUALMARKDOWNSTEP__FOLDER_PATH": "./data"}

    def test_multiple_keys_prefixed(self):
        result = EnvExpander.expand_step_settings("SimpleSplitterStep", {"BATCH_SIZE": "100", "MAX": "50"})
        assert result == {
            "SIMPLESPLITTERSTEP__BATCH_SIZE": "100",
            "SIMPLESPLITTERSTEP__MAX": "50",
        }

    def test_empty_settings_returns_empty(self):
        assert EnvExpander.expand_step_settings("MyStep", {}) == {}

    def test_class_name_uppercased(self):
        result = EnvExpander.expand_step_settings("myStep", {"KEY": "val"})
        assert "MYSTEP__KEY" in result

    @pytest.mark.parametrize(
        "class_name,key,expected",
        [
            ("StepA", "X", "STEPA__X"),
            ("step_b", "Y", "STEP_B__Y"),
            ("STEPC", "Z", "STEPC__Z"),
        ],
    )
    def test_prefix_format(self, class_name, key, expected):
        result = EnvExpander.expand_step_settings(class_name, {key: "v"})
        assert expected in result


class TestExpandMiddlewareSettings:
    def test_single_key_prefixed(self):
        result = EnvExpander.expand_middleware_settings("prometheus", {"GATEWAY": "host:9091"})
        assert result == {"PROMETHEUS__GATEWAY": "host:9091"}

    def test_multiple_keys(self):
        result = EnvExpander.expand_middleware_settings("prometheus", {"GATEWAY": "g", "JOB": "j"})
        assert result == {"PROMETHEUS__GATEWAY": "g", "PROMETHEUS__JOB": "j"}

    def test_empty_settings_returns_empty(self):
        assert EnvExpander.expand_middleware_settings("prometheus", {}) == {}

    def test_name_uppercased(self):
        result = EnvExpander.expand_middleware_settings("MyMiddleware", {"K": "v"})
        assert "MYMIDDLEWARE__K" in result


class TestExpandMiddlewaresList:
    def test_single_name(self):
        assert EnvExpander.expand_middlewares_list(["prometheus"]) == {"MIDDLEWARES": "prometheus"}

    def test_multiple_names_preserves_order(self):
        result = EnvExpander.expand_middlewares_list(["secret_resolver", "prometheus"])
        assert result == {"MIDDLEWARES": "secret_resolver,prometheus"}

    def test_empty_list(self):
        assert EnvExpander.expand_middlewares_list([]) == {"MIDDLEWARES": ""}
