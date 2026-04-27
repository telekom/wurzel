# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import pytest

from wurzel.manifest.secrets.placeholder import (
    SecretRef,
    find_placeholder_vars,
    parse_placeholder,
)


class TestParsePlaceholder:
    def test_vault_secret(self):
        ref = parse_placeholder("${secret:vault:my-api-key}")
        assert ref == SecretRef(provider="vault", ref="my-api-key")

    def test_k8s_secret_with_key(self):
        ref = parse_placeholder("${secret:k8s:my-db-secret/password}")
        assert ref == SecretRef(provider="k8s", ref="my-db-secret/password")

    def test_plain_string_returns_none(self):
        assert parse_placeholder("plain-value") is None

    def test_malformed_missing_provider_returns_none(self):
        assert parse_placeholder("${secret:only-one-part}") is None

    def test_not_a_placeholder_returns_none(self):
        assert parse_placeholder("https://example.com") is None

    def test_empty_string_returns_none(self):
        assert parse_placeholder("") is None

    def test_partial_syntax_returns_none(self):
        assert parse_placeholder("${secret:}") is None

    @pytest.mark.parametrize(
        "value,expected_provider,expected_ref",
        [
            ("${secret:vault:path/to/secret}", "vault", "path/to/secret"),
            ("${secret:k8s:ns-secret/key}", "k8s", "ns-secret/key"),
            ("${secret:vault:simple}", "vault", "simple"),
        ],
    )
    def test_parametrized_valid_placeholders(self, value, expected_provider, expected_ref):
        ref = parse_placeholder(value)
        assert ref is not None
        assert ref.provider == expected_provider
        assert ref.ref == expected_ref


class TestFindPlaceholderVars:
    def test_finds_placeholder_among_plain_values(self):
        env = {
            "PLAIN": "value",
            "SECRET": "${secret:vault:my-key}",
        }
        result = find_placeholder_vars(env)
        assert "SECRET" in result
        assert "PLAIN" not in result

    def test_empty_env_returns_empty(self):
        assert find_placeholder_vars({}) == {}

    def test_all_plain_returns_empty(self):
        assert find_placeholder_vars({"A": "1", "B": "2"}) == {}

    def test_multiple_placeholders_found(self):
        env = {
            "K1": "${secret:vault:s1}",
            "K2": "${secret:k8s:sec/key}",
            "K3": "plain",
        }
        result = find_placeholder_vars(env)
        assert set(result.keys()) == {"K1", "K2"}
        assert result["K1"].provider == "vault"
        assert result["K2"].provider == "k8s"
