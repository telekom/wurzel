# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0
import importlib.util

import pytest

from wurzel.steps.splitter import SimpleSplitterStep
from wurzel.utils.splitters.sentence_splitter import RegexSentenceSplitter, SentenceSplitter, SpacySentenceSplitter

from .sentence_splitter_test_cases import BASIC_TEST_CASES, DE_TEST_CASES, EL_TEST_CASES, HR_TEST_CASES, PL_TEST_CASES, REGEX_TEST_CASES

# Helpers for skip conditions
spacy_missing = importlib.util.find_spec("spacy") is None
spacy_default_model_name = "de_core_news_sm"
spacy_multilingual_model_name = "xx_ent_wiki_sm"
wtpsplit_missing = importlib.util.find_spec("wtpsplit") is None


@pytest.fixture(scope="function")
def spacy_splitter():
    yield SentenceSplitter.from_name(spacy_default_model_name)


@pytest.fixture(scope="function")
def regex_splitter():
    yield SentenceSplitter.from_name("regex")


@pytest.fixture(scope="function")
def sat_splitter():
    # A "small" SaT model (larger models should not be run as unit tests)
    # https://huggingface.co/segment-any-text/sat-3l-sm
    yield SentenceSplitter.from_name("sat-3l-sm")


def assert_splitter_test_cases(splitter: SentenceSplitter, test_cases: list[dict]):
    """Test splitter with test cases.

    Args:
        splitter (SentenceSplitter): Splitter to be tested.
        test_cases (list[dict]): Test cases.
    """
    # Iterate over test cases
    for idx, case in enumerate(test_cases):
        assert isinstance(case, dict), f"Case #{idx} is not a dict"
        assert "input_text" in case, f"Case #{idx} missing 'input_text'"
        assert "output_sentences" in case, f"Case #{idx} missing 'output_sentences'"

        input_text = case["input_text"]
        expected: list[str] = case["output_sentences"]

        assert isinstance(input_text, str), f"'input_text' in case #{idx} must be a string"
        assert isinstance(expected, list) and all(isinstance(s, str) for s in expected), (
            f"'output_sentences' in case #{idx} must be a list[str]"
        )

        got = splitter.get_sentences(input_text)

        preview = " ".join(input_text.splitlines()).strip()
        if len(preview) > 80:
            preview = preview[:77] + "..."

        assert got == expected, (
            "Sentence splitting mismatch\n"
            f"Case #{idx} — preview: {preview!r}\n"
            f"Expected ({len(expected)}): {expected}\n"
            f"Got      ({len(got)}): {got}"
        )


def test_from_name_routes_to_regex():
    splitter = SentenceSplitter.from_name("regex")
    assert isinstance(splitter, RegexSentenceSplitter)


@pytest.mark.skipif(spacy_missing, reason="spacy or model not installed")
def test_from_name_routes_to_spacy():
    splitter = SentenceSplitter.from_name(spacy_default_model_name)
    assert isinstance(splitter, SpacySentenceSplitter)


@pytest.mark.skipif(spacy_missing, reason="spacy or model not installed")
def test_spacy_sentence_splitter_simple():
    # Simple test
    splitter = SentenceSplitter.from_name(spacy_default_model_name)

    text = "Hello world. Wie gehts?\nWas ist dein Name. #.-"
    sents = splitter.get_sentences(text)

    assert sents == ["Hello world.", "Wie gehts?\n", "Was ist dein Name.", "#.-"]


@pytest.mark.skipif(spacy_missing, reason="spacy not installed")
def test_expection_on_unsupported_splitter_name():
    with pytest.raises(OSError):  # model not found error
        SentenceSplitter.from_name("this-splitter-does-not-exist")


def test_simple_splitter_step_settings(env):
    env.set("SENTENCE_SPLITTER_MODEL", "regex")

    step = SimpleSplitterStep()
    assert step.settings.SENTENCE_SPLITTER_MODEL == "regex"


@pytest.mark.skipif(spacy_missing, reason="spacy or model not installed")
@pytest.mark.parametrize(
    "test_cases",
    [
        pytest.param(BASIC_TEST_CASES, id="Basic test cases (mostly English)"),
        pytest.param(DE_TEST_CASES, id="German test cases"),
        pytest.param(HR_TEST_CASES, id="Croatian test cases"),
        pytest.param(PL_TEST_CASES, id="Polish test cases"),
        pytest.param(EL_TEST_CASES, id="Greek test cases"),
    ],
)
def test_spacy_sentence_splitter_basic(spacy_splitter, test_cases: list[dict]):
    assert_splitter_test_cases(splitter=spacy_splitter, test_cases=test_cases)


@pytest.mark.parametrize(
    "test_cases",
    [
        pytest.param(REGEX_TEST_CASES, id="Regex test cases (less challenging than Spacy test cases)"),
    ],
)
def test_regex_sentence_splitter(regex_splitter, test_cases: list[dict]):
    assert_splitter_test_cases(splitter=regex_splitter, test_cases=test_cases)


@pytest.mark.skipif(wtpsplit_missing, reason="wtpsplit not installed")
@pytest.mark.parametrize(
    "test_cases",
    [
        pytest.param(REGEX_TEST_CASES, id="Regex test cases (less challenging than Spacy test cases)"),
        pytest.param(DE_TEST_CASES, id="German test cases"),
        pytest.param(HR_TEST_CASES, id="Croatian test cases"),
        # TODO the test cases below fail with `sat-3l-sm`
        # pytest.param(BASIC_TEST_CASES, id="Basic test cases (mostly English)"),
        # pytest.param(PL_TEST_CASES, id="Polish test cases"),
        # pytest.param(EL_TEST_CASES, id="Greek test cases"),
    ],
)
def test_sat_sentence_splitter(sat_splitter, test_cases: list[dict]):
    assert_splitter_test_cases(splitter=sat_splitter, test_cases=test_cases)
