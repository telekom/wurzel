# Simple Splitter Tests

This directory contains comprehensive tests for the `SimpleSplitterStep` and `SemanticSplitter`.

## Test Structure

### Configuration (`conftest.py`)
Contains reusable fixtures for all tests:
- **Splitter fixtures**: `splitter`, `small_splitter` with different token limits
- **Text fixtures**: Multiple languages (EN, DE, FR, ES, ZH, EL, CS)
- **Document fixtures**: Short, long, with links, edge cases
- **Factory fixture**: `markdown_contract_factory` for creating test contracts

### Test Files

1. **`test_splitter_comprehensive.py`**
   - Multi-language support tests (EN, DE, FR, ES, ZH, EL, CS)
   - Short and long document handling
   - Link preservation tests with validation
   - Metadata consistency tests with deterministic checks
   - Different token limit configurations
   - Code blocks and lists
   - URL and keywords preservation

2. **`test_concrete_outputs.py`**
   - Deterministic output validation using SHA256 hashes
   - Concrete link preservation tests (inline and reference-style)
   - Link syntax validation to ensure links are not split
   - Long URL preservation tests
   - Tables and code blocks with links
   - Reproducibility tests for same inputs

3. **`test_edge_cases.py`**
   - Link preservation (inline and reference-style) with syntax checks
   - Very short documents
   - Tables, blockquotes, horizontal rules
   - Special characters and unicode
   - Edge case formats
   - Mixed content documents

4. **`e2e_simple_splitter_test.py`**
   - End-to-end integration test
   - Uses file-based input
   - Tests complete step execution

## Requirements

**Network Access Required**: These tests require internet access to download
tokenizer data from OpenAI's servers during the first run. The data is cached
locally after the initial download.

Dependencies:
- `spacy` with `de_core_news_sm` model
- `tiktoken` for tokenization

## Running Tests

Run all splitter tests:
```bash
make test
# or
.venv/bin/pytest tests/steps/simple_splitter/ -v
```

Run specific test file:
```bash
.venv/bin/pytest tests/steps/simple_splitter/test_splitter_comprehensive.py -v
```

Run specific test:
```bash
.venv/bin/pytest tests/steps/simple_splitter/test_splitter_comprehensive.py::test_short_documents_not_split -v
```

## Test Coverage

The tests cover:
- ✅ Multiple languages (English, German, French, Spanish, Chinese, Greek, Czech)
- ✅ Short documents (below minimum token length)
- ✅ Long documents (requiring multiple chunks)
- ✅ Link preservation (inline and reference-style) with concrete validation
- ✅ Link syntax validation (ensures links are NOT split)
- ✅ Deterministic output validation using SHA256 hashes
- ✅ Edge cases (empty, headers-only, special characters)
- ✅ Different markdown elements (code blocks, lists, tables, blockquotes)
- ✅ Metadata consistency across chunks
- ✅ Different token limit configurations
- ✅ URL and keyword preservation
- ✅ Long URL handling without breakage
- ✅ Tables and code blocks containing links

## Design Principles

Following the problem statement requirements:
- **Slim tests**: Parameterized to avoid duplication
- **Reusable fixtures**: Defined in `conftest.py`
- **Multiple languages**: Tests include EN, DE, FR, ES, ZH, EL, CS
- **Link handling**: Tests ensure links are not broken during splitting
- **No code changes**: Tests work with existing splitter implementation
