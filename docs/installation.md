# Installation Guide

This guide covers installing Wurzel and its dependencies, including handling the special case of direct dependencies that cannot be installed through PyPI.

## Basic Installation

To get started with Wurzel, install the library using pip:

```bash
pip install wurzel
```

## Direct Dependencies (spaCy Model)

Due to PyPI restrictions on direct dependencies, some components require manual installation. This primarily affects the German spaCy model used for semantic text splitting.

### Manual Installation

If you plan to use the semantic text splitting functionality (e.g., `SemanticSplitter`), you'll need to manually install the German spaCy model:

```bash
pip install https://github.com/explosion/spacy-models/releases/download/de_core_news_sm-3.7.0/de_core_news_sm-3.7.0-py3-none-any.whl
```

### Using DIRECT_REQUIREMENTS.txt

If you're working with the source code, you can install from the provided requirements file:

```bash
pip install -r DIRECT_REQUIREMENTS.txt
```


## Optional Dependencies

Wurzel supports various optional features through extras:

### Vector Database Support

```bash
# For Qdrant vector database
pip install wurzel[qdrant]

# For Milvus vector database
pip install wurzel[milvus]
```

### Document Processing

```bash
# For PDF document processing with Docling
pip install wurzel[docling]
```

### Development Tools

```bash
# For linting and code quality tools
pip install wurzel[lint]

# For testing framework and tools
pip install wurzel[test]

# For documentation generation
pip install wurzel[docs]
```

### Install Everything

```bash
# Install all optional dependencies
pip install wurzel[all]

# Don't forget the direct dependencies!
pip install -r DIRECT_REQUIREMENTS.txt
```

## Development Installation

For development work, use the provided Makefile:

```bash
# Install all dependencies including development tools
make install

# Run tests
make test

# Run linting
make lint

# Generate documentation
make documentation
```

## Docker Installation

The Docker image includes all dependencies automatically:

```bash
# Pull the latest image
docker pull ghcr.io/telekom/wurzel:latest

# Or build locally
docker build -t wurzel .
```

## Troubleshooting

### spaCy Model Issues

If you encounter issues with the spaCy model:

1. Verify the model is installed:
   ```bash
   python -c "import spacy; nlp = spacy.load('de_core_news_sm'); print('Model loaded successfully')"
   ```

2. Reinstall the model if needed:
   ```bash
   pip uninstall de-core-news-sm
   pip install https://github.com/explosion/spacy-models/releases/download/de_core_news_sm-3.7.0/de_core_news_sm-3.7.0-py3-none-any.whl
   ```

### Environment Issues

- Ensure you're using Python 3.11 or 3.12
- Consider using a virtual environment:
  ```bash
  python -m venv .venv
  source .venv/bin/activate  # On Windows: .venv\Scripts\activate
  pip install wurzel
  ```

## Why Direct Dependencies?

PyPI has restrictions on packages that include direct dependencies to external URLs for security reasons. The spaCy German model is hosted on GitHub releases rather than PyPI, requiring manual installation.

This approach ensures:
- Security compliance with PyPI guidelines
- Ability to publish to PyPI without restrictions
- Clear separation of concerns between core functionality and external models
- Flexibility in model versioning and updates

For more information about this limitation, see the [PyPI documentation on direct dependencies](https://packaging.python.org/specifications/core-metadata/).
