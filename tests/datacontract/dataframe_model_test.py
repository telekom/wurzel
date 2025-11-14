# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

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
