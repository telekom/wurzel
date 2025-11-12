# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0
import pytest

from wurzel.utils import HAS_LANGCHAIN_CORE, HAS_REQUESTS, HAS_SPACY, HAS_TIKTOKEN

if not HAS_LANGCHAIN_CORE or not HAS_REQUESTS or not HAS_SPACY or not HAS_TIKTOKEN:
    pytest.skip("Embedding dependencies (langchain-core, requests, spacy, tiktoken) are not available", allow_module_level=True)

from wurzel.step_executor import BaseStepExecutor
from wurzel.steps.embedding.step import TruncatedEmbeddingStep


@pytest.mark.parametrize(
    "token_count_max,mean_text_length",
    [
        (99999, 959.4),
        (9999, 959.4),
        (256, 491.1),
        (128, 309.8),
        (32, 103.4),
    ],
)
def test_truncated_embedding_step(
    token_count_max, mean_text_length, mock_embedding, default_embedding_data, env, splitter_tokenizer_model, sentence_splitter_model
):
    """Tests the execution of the `TruncatedEmbeddingStep` with a mock input file and check total output count and mean length of texts.

    Parameters
    ----------
    mock_embedding : MockEmbedding
        The mock embedding fixture.
    tmp_path : pathlib.Path
        A pytest fixture that provides a temporary directory unique to the test invocation.

    Asserts
    -------
    Asserts that the `embedding.csv` file is created in the output folder.

    """
    env.set("TRUNCATEDEMBEDDINGSTEP__API", "https://example-embedding.com/embed")
    env.set("TRUNCATEDEMBEDDINGSTEP__TOKEN_COUNT_MIN", "64")
    env.set("TRUNCATEDEMBEDDINGSTEP__TOKEN_COUNT_MAX", str(token_count_max))
    env.set("TRUNCATEDEMBEDDINGSTEP__TOKEN_COUNT_BUFFER", "32")
    env.set("TRUNCATEDEMBEDDINGSTEP__TOKENIZER_MODEL", splitter_tokenizer_model)
    env.set("TRUNCATEDEMBEDDINGSTEP__SENTENCE_SPLITTER_MODEL", sentence_splitter_model)

    TruncatedEmbeddingStep._select_embedding = mock_embedding
    input_folder, output_folder = default_embedding_data
    step_res = BaseStepExecutor(dont_encapsulate=False).execute_step(TruncatedEmbeddingStep, [input_folder], output_folder)
    assert output_folder.is_dir()
    assert len(list(output_folder.glob("*"))) > 0

    step_output, step_report = step_res[0]

    assert len(step_output) == 7, "Step outputs have wrong count."
    assert step_report.results == 7, "Step report has wrong count of outputs."

    assert step_output.embedding_input_text.str.len().mean() == pytest.approx(mean_text_length, abs=0.1), (
        "Invalid mean length of embedding_input_text"
    )
