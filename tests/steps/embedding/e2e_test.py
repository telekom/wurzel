# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

# Standard library imports
from pathlib import Path
import shutil

# Related third-party imports
from typing import List
import numpy as np
import pytest

# Local application/library specific imports
from wurzel.steps import EmbeddingStep
from wurzel.step_executor import BaseStepExecutor
from wurzel.steps.embedding.step_mutlivector import EmbeddingMultiVectorStep


@pytest.fixture(scope="module")
def mock_embedding():
    """
    A pytest fixture that provides a mock embedding class for testing.

    Overrides the `_select_embedding` method of the `EmbeddingStep` class
    to return an instance of the mock embedding class, which generates
    a fixed-size random vector upon calling `embed_query`.

    Returns
    -------
    MockEmbedding
        An instance of the mock embedding class.
    """

    class MockEmbedding:
        def embed_query(self, _: str) -> List[float]:
            """
            Simulates embedding of a query string into a fixed-size random vector.

            Parameters
            ----------
            _ : str
                The input query string (ignored in this mock implementation).

            Returns
            -------
            np.ndarray
                A random vector of size 768.
            """
            return list(np.random.random(768))

    def mock_func(*args, **kwargs):
        return MockEmbedding()

    return mock_func


def test_embedding_step(mock_embedding, tmp_path, env):
    """
    Tests the execution of the `EmbeddingStep` with a mock input file.

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
    EmbeddingStep._select_embedding = mock_embedding
    mock_file = Path("tests/data/markdown.json")
    input_folder = tmp_path / "input"
    input_folder.mkdir()
    shutil.copy(mock_file, input_folder)
    output_folder = tmp_path / "out"
    BaseStepExecutor(dont_encapsulate=False).execute_step(
        EmbeddingStep, [input_folder], output_folder
    )
    assert output_folder.is_dir()
    assert len(list(output_folder.glob("*"))) > 0


def test_mutlivector_embedding_step(mock_embedding, tmp_path, env):
    """
    Tests the execution of the `EmbeddingMultiVectorStep` with a mock input file.

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
    BaseStepExecutor(dont_encapsulate=False).execute_step(
        EmbeddingMultiVectorStep, [input_folder], output_folder
    )
    assert output_folder.is_dir()
    assert len(list(output_folder.glob("*"))) > 0
