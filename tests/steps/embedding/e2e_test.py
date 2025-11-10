# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

# Standard library imports
import logging
import shutil
from pathlib import Path

import pytest

from wurzel.utils import HAS_LANGCHAIN_CORE, HAS_REQUESTS, HAS_SPACY, HAS_TIKTOKEN

if not HAS_LANGCHAIN_CORE or not HAS_REQUESTS or not HAS_SPACY or not HAS_TIKTOKEN:
    pytest.skip("Embedding dependencies (langchain-core, requests, spacy, tiktoken) are not available", allow_module_level=True)

from wurzel.exceptions import StepFailed
from wurzel.step_executor import BaseStepExecutor
from wurzel.steps import EmbeddingStep
from wurzel.steps.embedding.huggingface import HuggingFaceInferenceAPIEmbeddings
from wurzel.steps.embedding.step_multivector import EmbeddingMultiVectorStep


def test_embedding_step(mock_embedding, default_embedding_data, env, splitter_tokenizer_model, sentence_splitter_model):
    """Tests the execution of the `EmbeddingStep` with a mock input file.

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
    env.set("EMBEDDINGSTEP__API", "https://example-embedding.com/embed")
    env.set("EMBEDDINGSTEP__TOKEN_COUNT_MIN", "64")
    env.set("EMBEDDINGSTEP__TOKEN_COUNT_MAX", "256")
    env.set("EMBEDDINGSTEP__TOKEN_COUNT_BUFFER", "32")
    env.set("EMBEDDINGSTEP__TOKENIZER_MODEL", splitter_tokenizer_model)
    env.set("EMBEDDINGSTEP__SENTENCE_SPLITTER_MODEL", sentence_splitter_model)

    EmbeddingStep._select_embedding = mock_embedding
    input_folder, output_folder = default_embedding_data
    step_res = BaseStepExecutor(dont_encapsulate=False).execute_step(EmbeddingStep, [input_folder], output_folder)
    assert output_folder.is_dir()
    assert len(list(output_folder.glob("*"))) > 0

    step_output, step_report = step_res[0]

    assert len(step_output) == 11, "Step outputs have wrong count."
    assert step_report.results == 11, "Step report has wrong count of outputs."


def test_mutlivector_embedding_step(mock_embedding, tmp_path, env):
    """Tests the execution of the `EmbeddingMultiVectorStep` with a mock input file.

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
    env.set("EMBEDDINGMULTIVECTORSTEP__API", "https://example-embedding.com/embed")
    EmbeddingStep._select_embedding = mock_embedding
    EmbeddingMultiVectorStep._select_embedding = mock_embedding
    EmbeddingStep._select_embedding = mock_embedding
    mock_file = Path("tests/data/markdown.json")
    input_folder = tmp_path / "input"
    input_folder.mkdir()
    shutil.copy(mock_file, input_folder)
    output_folder = tmp_path / "out"
    BaseStepExecutor(dont_encapsulate=False).execute_step(EmbeddingMultiVectorStep, [input_folder], output_folder)
    assert output_folder.is_dir()
    assert len(list(output_folder.glob("*"))) > 0


def test_inheritance(env, default_embedding_data):
    env.set("INHERITEDSTEP__API", "https://example-embedding.com/embed")
    EXPECTED_EXCEPTION = "1234-exepected-4321"

    class InheritedStep(EmbeddingStep):
        @staticmethod
        def _select_embedding(*args, **kwargs) -> HuggingFaceInferenceAPIEmbeddings:
            raise RuntimeError(EXPECTED_EXCEPTION)

    inp, out = default_embedding_data
    with pytest.raises(StepFailed) as sf:
        with BaseStepExecutor() as ex:
            ex(InheritedStep, [inp], out)
    assert sf.value.message.endswith(EXPECTED_EXCEPTION)


def test_embedding_step_log_statistics(
    mock_embedding, default_embedding_data, env, caplog, splitter_tokenizer_model, sentence_splitter_model
):
    """Tests the logging of descriptive statistics in the `EmbeddingStep` with a mock input file."""
    env.set("EMBEDDINGSTEP__API", "https://example-embedding.com/embed")
    env.set("EMBEDDINGSTEP__NUM_THREADS", "1")  # Ensure deterministic behavior with single thread
    env.set("EMBEDDINGSTEP__TOKEN_COUNT_MIN", "64")
    env.set("EMBEDDINGSTEP__TOKEN_COUNT_MAX", "256")
    env.set("EMBEDDINGSTEP__TOKEN_COUNT_BUFFER", "32")
    env.set("EMBEDDINGSTEP__TOKENIZER_MODEL", splitter_tokenizer_model)
    env.set("EMBEDDINGSTEP__SENTENCE_SPLITTER_MODEL", sentence_splitter_model)

    EmbeddingStep._select_embedding = mock_embedding
    input_folder, output_folder = default_embedding_data

    with caplog.at_level(logging.INFO):
        BaseStepExecutor(dont_encapsulate=False).execute_step(EmbeddingStep, [input_folder], output_folder)

    # check if output log exists
    assert "Distribution of char length" in caplog.text, "Missing log output for char length"
    assert "Distribution of token length" in caplog.text, "Missing log output for token length"
    assert "Distribution of chunks count" in caplog.text, "Missing log output for chunks count"

    # check extras
    char_length_record = None
    token_length_record = None
    chunks_count_record = None

    for record in caplog.records:
        if "Distribution of char length" in record.message:
            char_length_record = record

        if "Distribution of token length" in record.message:
            token_length_record = record

        if "Distribution of chunks count" in record.message:
            chunks_count_record = record

    expected_char_length_count = 11

    # Check values if a small tolerance
    expected_char_length_mean = pytest.approx(609.18, abs=0.1)
    expected_token_length_mean = pytest.approx(257.18, abs=0.1)
    expected_chunks_count_mean = pytest.approx(3.18, abs=0.2)

    assert char_length_record.count == expected_char_length_count, (
        f"Invalid char length count: expected {expected_char_length_count}, got {char_length_record.count}"
    )
    assert char_length_record.mean == expected_char_length_mean, (
        f"Invalid char length mean: expected {expected_char_length_mean}, got {char_length_record.mean}"
    )
    assert token_length_record.mean == expected_token_length_mean, (
        f"Invalid token length mean: expected {expected_token_length_mean}, got {token_length_record.mean}"
    )
    assert chunks_count_record.mean == expected_chunks_count_mean, (
        f"Invalid chunks count mean: expected {expected_chunks_count_mean}, got {chunks_count_record.mean}"
    )
