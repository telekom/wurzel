# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import pytest

from wurzel.utils import HAS_SPACY, HAS_TIKTOKEN

if not HAS_SPACY or not HAS_TIKTOKEN:
    pytest.skip("Simple splitter dependencies (spacy, tiktoken) are not available", allow_module_level=True)

from wurzel.datacontract import MarkdownDataContract
from wurzel.utils.splitters.semantic_splitter import SemanticSplitter


@pytest.fixture(scope="module")
def splitter():
    """Fixture for SemanticSplitter with default settings."""
    return SemanticSplitter(
        token_limit=256,
        token_limit_buffer=32,
        token_limit_min=64,
        tokenizer_model="gpt-3.5-turbo",
        sentence_splitter_model="de_core_news_sm",
    )


@pytest.fixture(scope="module")
def small_splitter():
    """Fixture for SemanticSplitter with smaller token limits for testing."""
    return SemanticSplitter(
        token_limit=128,
        token_limit_buffer=16,
        token_limit_min=32,
        tokenizer_model="gpt-3.5-turbo",
        sentence_splitter_model="de_core_news_sm",
    )


@pytest.fixture
def short_text_en():
    """Short English text that should not be split."""
    return "This is a short text. It should remain as one chunk."


@pytest.fixture
def short_text_de():
    """Short German text that should not be split."""
    return "Dies ist ein kurzer Text. Er sollte als ein Chunk bleiben."


@pytest.fixture
def long_text_en():
    """Long English text that should be split into multiple chunks."""
    return """# Introduction

This is a comprehensive guide to understanding how text splitting works
in natural language processing systems.

## Background

Text splitting is essential for processing large documents. When documents
exceed the token limits of language models, they must be divided into
smaller, manageable chunks. The process should preserve semantic meaning
and context.

## Methods

There are several approaches to text splitting:

### Naive Splitting

Simply splitting on character or word count without regard to structure
or meaning. This is the simplest but least effective method.

### Semantic Splitting

This method considers the structure of the document, including headings,
paragraphs, and sentences. It aims to keep related content together
while respecting token limits.

### Recursive Splitting

A hierarchical approach that recursively splits documents based on
markdown structure, then sentences, and finally arbitrary positions
if necessary.

## Best Practices

When implementing text splitting, consider the following:

- Preserve headings for context
- Avoid splitting sentences when possible
- Maintain links and references intact
- Keep code blocks together
- Consider the downstream use case

## Conclusion

Effective text splitting requires balancing technical constraints with
semantic preservation. The choice of method depends on your specific
requirements."""


@pytest.fixture
def long_text_de():
    """Long German text that should be split into multiple chunks."""
    return """# Einführung

Dies ist ein umfassender Leitfaden zum Verständnis der Textaufteilung
in natürlichen Sprachverarbeitungssystemen.

## Hintergrund

Die Textaufteilung ist für die Verarbeitung großer Dokumente
unerlässlich. Wenn Dokumente die Token-Grenzen von Sprachmodellen
überschreiten, müssen sie in kleinere, handhabbare Stücke aufgeteilt
werden.

## Methoden

Es gibt verschiedene Ansätze zur Textaufteilung:

### Naive Aufteilung

Einfaches Aufteilen nach Zeichen- oder Wortanzahl ohne Berücksichtigung
von Struktur oder Bedeutung. Dies ist die einfachste, aber am wenigsten
effektive Methode.

### Semantische Aufteilung

Diese Methode berücksichtigt die Struktur des Dokuments, einschließlich
Überschriften, Absätzen und Sätzen. Sie zielt darauf ab, verwandte
Inhalte zusammenzuhalten und gleichzeitig Token-Grenzen zu respektieren.

## Fazit

Effektive Textaufteilung erfordert das Ausbalancieren technischer
Einschränkungen mit semantischer Erhaltung."""


@pytest.fixture
def text_with_links():
    """Text containing links that should not be broken."""
    return """# Documentation Links

Here are some important resources:

- [GitHub Repository](https://github.com/telekom/wurzel) for source code
- [API Documentation](https://docs.example.com/api/v1/reference) for developers
- [User Guide](https://example.com/guides/getting-started) for beginners

Visit [our website](https://www.telekom.com) for more information.
You can also check [the FAQ](https://example.com/faq#common-questions)
for common questions.

## External Links

For more details, see [Wikipedia](https://en.wikipedia.org/wiki/Natural_language_processing)
and [Stack Overflow](https://stackoverflow.com/questions/tagged/nlp).

Links should remain intact:
[https://example.com/very/long/path/to/resource](https://example.com/very/long/path/to/resource)."""


@pytest.fixture
def text_multilang_short():
    """Dictionary of short texts in multiple languages."""
    return {
        "en": "Hello world. This is a test.",
        "de": "Hallo Welt. Dies ist ein Test.",
        "fr": "Bonjour le monde. Ceci est un test.",
        "es": "Hola mundo. Esta es una prueba.",
        "zh": "你好世界。这是一个测试。",
    }


@pytest.fixture
def text_multilang_long():
    """Dictionary of longer texts in multiple languages."""
    return {
        "en": """# Technology Overview

Modern technology has transformed how we communicate and work.
From smartphones to cloud computing, innovations continue to reshape
our daily lives. Machine learning and artificial intelligence are
driving the next wave of technological advancement.

## Future Trends

The future promises even more exciting developments in quantum computing,
renewable energy, and biotechnology.""",
        "de": """# Technologieübersicht

Moderne Technologie hat verändert, wie wir kommunizieren und arbeiten.
Von Smartphones bis Cloud-Computing verändern Innovationen weiterhin
unser tägliches Leben. Maschinelles Lernen und künstliche Intelligenz
treiben die nächste Welle des technologischen Fortschritts voran.

## Zukunftstrends

Die Zukunft verspricht noch aufregendere Entwicklungen in
Quantencomputing, erneuerbaren Energien und Biotechnologie.""",
        "fr": """# Aperçu technologique

La technologie moderne a transformé notre façon de communiquer et
de travailler. Des smartphones au cloud computing, les innovations
continuent de remodeler notre vie quotidienne. L'apprentissage
automatique et l'intelligence artificielle stimulent la prochaine
vague de progrès technologique.

## Tendances futures

L'avenir promet des développements encore plus passionnants dans
l'informatique quantique, les énergies renouvelables et la
biotechnologie.""",
        "es": """# Visión general de tecnología

La tecnología moderna ha transformado cómo nos comunicamos y trabajamos.
Desde los teléfonos inteligentes hasta la computación en la nube,
las innovaciones continúan remodelando nuestra vida diaria.
El aprendizaje automático y la inteligencia artificial están impulsando
la próxima ola de avance tecnológico.

## Tendencias futuras

El futuro promete desarrollos aún más emocionantes en computación cuántica,
energía renovable y biotecnología.""",
    }


@pytest.fixture
def empty_document():
    """Empty markdown document."""
    return ""


@pytest.fixture
def only_headers():
    """Document with only headers."""
    return """# Main Title
## Subtitle
### Section Header
#### Subsection"""


@pytest.fixture
def markdown_contract_factory():
    """Factory fixture for creating MarkdownDataContract instances."""

    def _create(md: str, url: str = "https://test.example.com", keywords: str = "test"):
        return MarkdownDataContract(md=md, url=url, keywords=keywords)

    return _create
