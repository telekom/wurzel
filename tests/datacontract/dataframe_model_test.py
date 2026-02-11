# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import pandas as pd
import pytest

from wurzel.steps.data import EmbeddingResult


def test_load_from_csv_converts_dict_columns(tmp_path):
    csv = tmp_path / "embedded.csv"
    csv.write_text(
        'text,vector,url,keywords,embedding_input_text,metadata\n"foo","[0.1, 0.2]","","https://example.com","kw","{\'foo\': \'bar\'}"\n',
        encoding="utf-8",
    )

    df = EmbeddingResult.load_from_path(csv)

    metadata = df["metadata"].iloc[0]
    assert isinstance(metadata, dict)
    assert metadata["foo"] == "bar"


def test_save_and_load_roundtrip(tmp_path):
    """Save a DataFrame via save_to_path, load it back, verify contents."""
    df = pd.DataFrame(
        {
            "text": ["hello", "world"],
            "vector": [[0.1, 0.2], [0.3, 0.4]],
            "url": ["a.md", "b.md"],
            "keywords": ["kw1", "kw2"],
            "embedding_input_text": ["hello", "world"],
            "metadata": [{"k": "v"}, {}],
        }
    )
    EmbeddingResult.save_to_path(tmp_path / "out", df)
    assert (tmp_path / "out.csv").exists()

    loaded = EmbeddingResult.load_from_path(tmp_path / "out.csv")
    assert len(loaded) == 2
    assert loaded["text"].tolist() == ["hello", "world"]


def test_save_to_path_rejects_non_dataframe(tmp_path):
    """save_to_path raises NotImplementedError for non-DataFrame objects."""
    with pytest.raises(NotImplementedError, match="Cannot store"):
        EmbeddingResult.save_to_path(tmp_path / "bad", [{"text": "hello"}])
