# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import pytest

from wurzel.steps.qdrant.step import QdrantConnectorStep


@pytest.mark.parametrize(
    "text,expected_hash",
    [
        ("example_text_1", "5840445c9d0a1457627eaa4718d48bbc5071782ac6df6d85dfef7f82a4dc01a6"),
        ("example_text_2", "69cee72aa104c9a62e6ceb4e7cebdffef3ce0f385cbb807c4a587149bd9fc028"),
        ("example_text_3", "7fde1636e509f9a34474f6dcdaddb66db7b09871ed6f934a384b3fb3b491a24e"),
    ],
)
def test_tlsh_hash_same_output(text: str, expected_hash: str):
    """Test that QdrantConnectorStep.get_available_hashes produces the expected SHA-256 hash for given text inputs.

    Args:
        text (str): The input text to hash.
        expected_hash (str): The expected SHA-256 hash value for the input text.

    Asserts:
        The 'text_sha256_hash' key in the result matches the expected_hash.

    """
    result = QdrantConnectorStep.get_available_hashes(text)
    assert result["text_sha256_hash"] == expected_hash
